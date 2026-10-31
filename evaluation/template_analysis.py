"""Summarize template variation separately from CVE sampling uncertainty."""

import csv
import hashlib
import json
import platform
import random
import statistics
import sys
import tempfile
from array import array
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from html import escape
from itertools import product
from pathlib import Path

from core import __version__
from .metrics import DEFAULT_METRICS, DIAGNOSTIC_HELP, METRIC_HELP, Metrics
from .artifacts import ArtifactReader
from prompts.template_variants import VARIANTS, text_hash
from utils.privacy import safe_settings, safe_text


GROUP_FIELDS = ("dataset", "model_id", "model", "run_seed", "protocol", "parser_mode")


def _counts(rows):
    tracker = Metrics()
    for row in rows:
        tracker.add(row["gold"], row["pred"])
    tracker.compute()
    return tracker


INTERVAL_METRICS = ("Recall", "F1", "Coverage", "AbstentionRate", "EffectiveF1")
CONDITION_METRICS = (*DEFAULT_METRICS, "FalsePositivesPer1000")
COUNT_FIELDS = ("TP", "TN", "FP", "FN", "Incorrect", "UnFN")
BOOTSTRAP_SEED = 42


def _scores(counts):
    tracker = Metrics(**dict(zip(COUNT_FIELDS, counts)))
    tracker.compute()
    total = sum(counts)
    return {**{field: getattr(tracker, field) for field in DEFAULT_METRICS},
            "FalsePositivesPer1000": 1000 * tracker.FP / total if total else 0.0}


class _BootstrapCache:
    """Reuse condition scores within one analysis, with a bounded memory budget."""

    def __init__(self, max_bytes=32 * 1024 * 1024):
        self.max_bytes = max_bytes
        self._entries = OrderedDict()
        self._bytes = 0

    def get(self, key):
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._entries.move_to_end(key)
        return entry[0]

    def put(self, key, scores):
        counts = key[2]
        size = (256 + sys.getsizeof(key) + sys.getsizeof(counts) + sys.getsizeof(scores)
                + sum(sys.getsizeof(vector) for vector in scores.values())
                + sum(sys.getsizeof(row) + sum(sys.getsizeof(value) for value in row) for row in counts))
        if size > self.max_bytes:
            return
        previous = self._entries.pop(key, None)
        if previous:
            self._bytes -= previous[1]
        while self._entries and self._bytes + size > self.max_bytes:
            _old_key, (_old_scores, old_size) = self._entries.popitem(last=False)
            self._bytes -= old_size
        self._entries[key] = (scores, size)
        self._bytes += size


def _resample_scores(counts, bootstrap, seed, control):
    rng = random.Random(seed)
    scores = {field: array("d") for field in CONDITION_METRICS}
    for resample in range(bootstrap):
        if control and resample % 100 == 0:
            control()
        sampled = rng.choices(counts, k=len(counts))
        current = _scores(tuple(map(sum, zip(*sampled))))
        for field in CONDITION_METRICS:
            scores[field].append(current[field])
    return scores


def _condition_bootstrap(counts, bootstrap, seed, control, cache):
    key = (bootstrap, seed, counts)
    scores = cache.get(key)
    if scores is not None:
        if control:
            control()
        return scores
    scores = _resample_scores(counts, bootstrap, seed, control)
    cache.put(key, scores)
    return scores


def cluster_intervals(rows, bootstrap=1000, seed=BOOTSTRAP_SEED, *, group_by="cve_id", control=None,
                      _bootstrap_cache=None):
    """Percentile intervals resample whole observed clusters, never individual rows."""
    if type(bootstrap) is not int or bootstrap < 0:
        raise ValueError("bootstrap must be a nonnegative integer")
    if group_by not in {"cve_id", "repository"}:
        raise ValueError("group_by must be cve_id or repository")
    clusters = {}
    samples, missing = 0, False
    for index, row in enumerate(rows):
        if control and index % 1000 == 0:
            control()
        samples += 1
        identifier = row.get(group_by)
        if not identifier:
            missing = True
            continue
        tracker = clusters.setdefault(str(identifier), Metrics())
        tracker.add(row["gold"], row["pred"])
    result = {"ci95": None, "clusters": len(clusters), "group_by": group_by, "samples": samples,
              "unavailable_reason": None,
              "uncertainty": "Cluster sampling only, conditional on this run seed and observed cohort"}
    if missing:
        result["unavailable_reason"] = f"Complete {group_by} identifiers are required"
    elif len(clusters) < 2:
        result["unavailable_reason"] = "At least two clusters are required"
    elif not bootstrap:
        result["unavailable_reason"] = "Bootstrap resamples were set to zero"
    else:
        counts = tuple(tuple(getattr(tracker, field) for field in COUNT_FIELDS) for tracker in clusters.values())
        cache = _bootstrap_cache if _bootstrap_cache is not None else _BootstrapCache()
        scores = _condition_bootstrap(counts, bootstrap, seed, control, cache)
        result["ci95"] = {field: [ordered[int((bootstrap - 1) * percentile)] for percentile in (0.025, 0.975)]
                          for field, values in scores.items() if (ordered := sorted(values))}
        coverage = result["ci95"]["Coverage"]
        result["ci95"]["AbstentionRate"] = [1 - coverage[1], 1 - coverage[0]]
    return result


def resolve_analysis_settings(supplied=None):
    """Validate shared GUI, CLI, and saved-run analysis settings."""
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, dict):
        raise ValueError("analysis must be a mapping")
    defaults = {"enabled": True, "rankings": True, "paired_comparisons": True,
                "prevalence": True, "output_audit": True, "dataset_audit": True,
                "group_by": "cve_id", "bootstrap_resamples": 1000,
                "prevalence_repeats": 20, "prevalence_size": 1000, "review_case_limit": 50}
    unknown = set(supplied) - set(defaults) - {"diagnostics"}
    if unknown:
        raise ValueError("Unsupported analysis settings: " + ", ".join(sorted(unknown)))
    resolved = {key: supplied.get(key, value) for key, value in defaults.items()}
    for key in ("enabled", "rankings", "paired_comparisons", "prevalence", "output_audit", "dataset_audit"):
        if type(resolved[key]) is not bool:
            raise ValueError(f"{key} must be true or false")
    for key, minimum in (("bootstrap_resamples", 0), ("prevalence_repeats", 1),
                         ("prevalence_size", 20), ("review_case_limit", 0)):
        if type(resolved[key]) is not int or resolved[key] < minimum:
            raise ValueError(f"{key} must be an integer of at least {minimum}")
    if resolved["group_by"] not in {"cve_id", "repository"}:
        raise ValueError("group_by must be cve_id or repository")
    return resolved


def paired_comparison(reference, candidate, bootstrap=1000, seed=BOOTSTRAP_SEED, *, control=None,
                      _bootstrap_cache=None, group_by="cve_id"):
    """Resample the same clusters on both sides of a matched comparison."""
    if group_by not in {"cve_id", "repository"}:
        raise ValueError("group_by must be cve_id or repository")
    if control:
        control()
    left = {r["sample_uid"]: r for r in reference}
    right = {r["sample_uid"]: r for r in candidate}
    if len(left) != len(reference) or len(right) != len(candidate):
        raise ValueError("Paired comparisons require one prediction per sample in each condition")
    if any(r["gold"] not in {"safe", "vulnerable"} or r["pred"] not in {"safe", "vulnerable", "unknown"}
           for rows in (reference, candidate) for r in rows):
        raise ValueError("Comparisons require valid gold and prediction labels")
    if left.keys() != right.keys():
        raise ValueError("Template comparison requires exactly the same samples")
    if any(left[k]["gold"] != right[k]["gold"] for k in left):
        raise ValueError("Gold labels differ across matched conditions")
    n = len(left)
    reference_scores, candidate_scores = _counts(reference), _counts(candidate)
    result = {"samples": n, "label_disagreement": sum(left[k]["pred"] != right[k]["pred"]
                                                       for k in left) / n if n else 0.0,
              "f1_difference": candidate_scores.F1 - reference_scores.F1,
              "metric_differences": {field: getattr(candidate_scores, field) - getattr(reference_scores, field)
                                     for field in INTERVAL_METRICS},
              "cve_bootstrap_ci95": None, "cve_bootstrap_ci95_by_metric": None, "clusters": 0,
              "cluster_bootstrap_ci95_by_metric": None, "group_by": group_by,
              "uncertainty": "Cluster sampling only, conditional on this run seed and these templates"}
    result["same_decision_budget"] = (_same_budget(reference, candidate)
        if all("decision_calls" in row for rows in (reference, candidate) for row in rows) else None)
    if not n or not all(left[k].get(group_by) for k in left):
        result["ci_unavailable_reason"] = f"Complete {group_by} identifiers are required"
        return result
    clusters = defaultdict(lambda: [[], []])
    for key in left:
        if left[key].get(group_by) != right[key].get(group_by):
            raise ValueError("Cluster identifiers differ across matched conditions")
        clusters[left[key][group_by]][0].append(left[key])
        clusters[left[key][group_by]][1].append(right[key])
    result["clusters"] = len(clusters)
    if len(clusters) < 2 or bootstrap < 1:
        result["ci_unavailable_reason"] = "At least two clusters and a positive bootstrap count are required"
        return result
    totals = []
    for pair in clusters.values():
        trackers = [_counts(rows) for rows in pair]
        totals.append([tuple(getattr(tracker, field) for field in COUNT_FIELDS) for tracker in trackers])
    # Re-seeding each condition draws the same CVE positions used by the paired
    # sampler, so a condition's score vector can serve several comparisons.
    cache = _bootstrap_cache if _bootstrap_cache is not None else _BootstrapCache()
    a = _condition_bootstrap(tuple(pair[0] for pair in totals), bootstrap, seed, control, cache)
    b = _condition_bootstrap(tuple(pair[1] for pair in totals), bootstrap, seed, control, cache)
    intervals = {}
    for field in INTERVAL_METRICS:
        if control:
            control()
        values = sorted(right - left for left, right in zip(a[field], b[field]))
        intervals[field] = [values[int((len(values) - 1) * p)] for p in (0.025, 0.975)]
    intervals["AbstentionRate"] = [-intervals["Coverage"][1], -intervals["Coverage"][0]]
    result["cluster_bootstrap_ci95_by_metric"] = intervals
    if group_by == "cve_id":
        result["cve_bootstrap_ci95_by_metric"] = intervals
        result["cve_bootstrap_ci95"] = intervals["F1"]
    return result


def _validate_study(manifest, groups):
    """Check the saved study matrix before publishing scores from its rows."""
    if manifest.get("status") != "completed":
        raise ValueError("Analysis requires a completed study; resume an interrupted run first")
    if not groups:
        raise ValueError("The study has no predictions to analyze")
    modern = manifest.get("schema_version", 0) >= 3
    if modern:
        cfg = manifest["config"]
        conditions = {c["id"]: c for c in manifest["conditions"]}
        cohorts = {c["name"]: {s["sample_uid"]: s for s in c["samples"]} for c in manifest["cohorts"]}
        selections = manifest.get("model_selections")
        model_names = ({m["model_id"]: m["name"] for m in selections} if selections else
                       {key: value.get("name") for key, value in manifest["resolved_models"].items()})
        if not model_names or len(model_names) != len(cfg["models"]):
            raise ValueError("The manifest does not identify every selected model")
        allowed_names = {m["name"] for m in cfg["models"]}
        expected_groups = set(product(cohorts, model_names, cfg.get("seeds", [42]),
                                      cfg.get("protocols", ["verdict_first"]),
                                      cfg.get("parser_modes", ["strict", "structured", "full"])))
        actual_groups = {(key[0], key[1], key[3], key[4], key[5]) for key in groups}
        if actual_groups != expected_groups:
            raise ValueError("Prediction groups do not match the manifest's model/dataset/seed/protocol/parser matrix")
    names_seen = {}
    for key, saved_conditions in groups.items():
        dataset, model_id, model_name, _seed, protocol, _parser = key
        if modern:
            expected = {name for name, condition in conditions.items() if condition["protocol"] == protocol}
            if set(saved_conditions) != expected:
                raise ValueError("Prediction conditions do not match the manifest")
            expected_name = model_names[model_id]
            if model_name not in allowed_names or (expected_name is not None and model_name != expected_name):
                raise ValueError("Prediction model name does not match the manifest")
            if model_id in names_seen and names_seen[model_id] != model_name:
                raise ValueError("One model identity has inconsistent names in the predictions")
            names_seen[model_id] = model_name
        for condition_id, rows in saved_conditions.items():
            sample_ids = {r["sample_uid"] for r in rows}
            if len(sample_ids) != len(rows):
                raise ValueError(f"Duplicate predictions for {condition_id}")
            if modern and sample_ids != cohorts[dataset].keys():
                raise ValueError("Prediction samples do not match the manifest cohort")
            for row in rows:
                if row["gold"] not in {"safe", "vulnerable"} or row["pred"] not in {"safe", "vulnerable", "unknown"}:
                    raise ValueError("Predictions contain an invalid gold or prediction label")
                if modern:
                    sample = cohorts[dataset][row["sample_uid"]]
                    if any(row.get(field) != value for field, value in sample.items()):
                        raise ValueError("Prediction sample metadata does not match the manifest")
                    condition = conditions[condition_id]
                    if any(row.get(field) != condition[field] for field in ("comparison", "family", "variant", "protocol")):
                        raise ValueError("Prediction condition metadata does not match the manifest")
                    draws = condition["draws"]
                    used = 1 if condition["policy"] == "first" else draws
                    ids = row.get("generation_ids", [])
                    if (row["aggregation"]["policy"] != condition["policy"] or row.get("pool_calls") != draws
                            or row["decision_calls"] != used or len(ids) != draws or len(set(ids)) != draws
                            or row["aggregation"].get("label") != row["pred"]):
                        raise ValueError("Prediction label, policy, generation pool, or decision budget does not match the manifest")


def _same_budget(reference, candidate):
    return ({r["sample_uid"]: r["decision_calls"] for r in reference}
            == {r["sample_uid"]: r["decision_calls"] for r in candidate})


def _prediction_hash(reader):
    hashes = {name: value for name, value in reader.input_hashes.items()
              if name.endswith(("predictions.jsonl", "records.jsonl"))}
    if len(hashes) == 1:
        return next(iter(hashes.values()))
    return text_hash(json.dumps(hashes, sort_keys=True))


def _seed_signature(rows):
    samples, settings, available = [], set(), True
    for row in rows:
        samples.append((row["sample_uid"], row["gold"], row.get("code_sha256")))
        settings.add(row.get("analysis_settings_hash"))
        available = available and bool(row.get("analysis_identity_available") and row.get("traceability_available"))
    return {"cohort": text_hash(json.dumps(sorted(samples), sort_keys=True)),
            "settings": tuple(sorted(value or "" for value in settings)), "identity_available": available}


def _seed_summaries(groups):
    summaries = []
    fields = tuple(field for field in GROUP_FIELDS if field != "run_seed") + ("condition",)
    for key, runs in groups.items():
        seeds = sorted(run["run_seed"] for run in runs)
        reason = None
        if len(seeds) < 2:
            reason = "At least two run seeds are required to measure across-seed variation"
        elif not all(run["identity_available"] for run in runs):
            reason = "Complete sample and model identities are required for across-run comparison"
        elif len({run["cohort"] for run in runs}) != 1:
            reason = "Run seeds do not use the same code and gold-labeled cohort"
        elif len({run["settings"] for run in runs}) != 1:
            reason = "Run seeds use different model identities or generation settings"
        for metric in DEFAULT_METRICS:
            values = [run["metric"][metric] for run in runs]
            summaries.append({**dict(zip(fields, key)), "metric": metric, "run_seeds": seeds,
                "runs": len(runs), "mean": statistics.mean(values) if not reason else None,
                "sample_sd": statistics.stdev(values) if not reason else None,
                "minimum": min(values) if not reason else None, "maximum": max(values) if not reason else None,
                "unavailable_reason": reason,
                "uncertainty": "Descriptive variation across run seeds, separate from cluster sampling intervals"})
    return summaries


def _report_value(value):
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return safe_text(json.dumps(safe_settings(value), ensure_ascii=False, sort_keys=True))
    return safe_text(value)


def _report_table(title, rows, columns, descriptions=None, *, filterable=True, open_by_default=True):
    if not rows:
        return ""
    descriptions = descriptions or {}
    header = "".join(f'<th scope="col" title="{escape(descriptions.get(key, key), quote=True)}">'
                     f'{escape(label)}</th>' for key, label in columns)
    def cell(value):
        kind = "number" if type(value) in (int, float) else "text"
        return f'<td class="{kind}">{escape(_report_value(value))}</td>'

    body = "".join("<tr>" + "".join(cell(row.get(key)) for key, _label in columns)
                   + "</tr>" for row in rows)
    search = f' data-filterable data-title="{escape(title, quote=True)}"' if filterable else ""
    expanded = " open" if open_by_default else ""
    return (f'<details{expanded}{search}><summary>{escape(title)} ({len(rows)})</summary><div class="table-wrap">'
            f"<table><caption>{escape(title)}</caption><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"
            '<p class="empty-filter" hidden>No matching rows.</p></details>')


def _execution_rows(manifest, metrics):
    """Keep session execution counters separate from reused decision costs."""
    names = {row["model_id"]: row["model"] for row in metrics}
    summaries = manifest.get("inference_performance", [])
    if not isinstance(summaries, list):
        return []
    fields = ("workers", "generated_calls", "shared_cache_hits", "run_reuses", "batch_cache_hits", "wall_seconds",
              "generation_seconds", "persistent_cache_enabled", "shared_cache_warning")
    return [{"model": safe_text(names.get(summary.get("model_id"), summary.get("model_id", "Unavailable"))),
             **{field: summary.get(field) for field in fields},
             "shared_cache_warning": summary.get("shared_cache_warning") or "None recorded"}
            for summary in summaries if isinstance(summary, dict)]


def _write_study_report(path, manifest, metrics, analysis):
    """Render escaped summaries without embedding raw model outputs or source code."""
    context = [(key, label) for key, label in (("dataset", "Dataset"), ("model", "Model"),
               ("run_seed", "Run seed"), ("protocol", "Verdict order"), ("parser_mode", "Parser"))]
    metric_names = list(DEFAULT_METRICS)
    options = analysis["analysis_options"]
    descriptions = {**METRIC_HELP, **DIAGNOSTIC_HELP,
                    "SelectiveAccuracy": "Correct predictions among answered samples: (TP + TN) / (TP + TN + FP + FN). Unavailable when no samples are answered; separate from overall Accuracy.",
                    "SelectiveRisk": "One minus selective accuracy, among answered samples only. Unavailable when no samples are answered.",
                    "FalsePositivesPer1000": "1,000 times FP divided by all evaluated snippets, including UNKNOWN outputs. This is not FP divided by the SAFE class size.",
                    "condition": "Saved template or component/voting condition. Each row uses its recorded matched cohort.",
                    "same_decision_budget": "Whether both methods used the same recorded number of decision calls for every sample.",
                    "label_disagreement": "Fraction of matched samples whose parsed labels differ, including UNKNOWN.",
                    "range": "Maximum minus minimum score over the selected task wordings. This is template variation, not a confidence interval.",
                    "template_population_sd": "Population standard deviation over the selected task wordings; it does not measure CVE sampling uncertainty.",
                    "clusters": "Number of observed resampling clusters. Related snippets stay together; the configured grouping is CVE or repository.",
                    "samples": "Number of samples in each condition, including UNKNOWN outcomes.",
                    "Unknown": "Samples whose prediction is UNKNOWN, including unresolved or failed responses.",
                    "pool_calls_per_sample": "Mean number of recorded draws in the shared response pool. A first-draw decision may read one draw from a larger saved pool.",
                    "workers": "Maximum concurrent inference requests configured for this model in the recorded session.",
                    "generated_calls": "Actual backend executions in the generation session saved in the manifest, including failed calls.",
                    "shared_cache_hits": "Responses copied from the cross-run cache during this session; these are not fresh model executions.",
                    "run_reuses": "Cache reuses recorded by the inference engine. Replay from the study's saved call journal is separate and is not counted here.",
                    "batch_cache_hits": "Matching responses reused across experiment types in the same batch; these are not fresh model executions.",
                    "wall_seconds": "Elapsed lifetime of this model's inference engine during the current session, including waits and prediction processing. Excludes analysis and some startup work.",
                    "generation_seconds": "Sum of backend request durations for fresh executions. Concurrent durations overlap, so this is not elapsed wall time.",
                    "persistent_cache_enabled": "Whether the optional cross-run cache was enabled for this model's recorded session.",
                    "shared_cache_warning": "Recorded cache failure category, if present. A missing value does not establish a cache failure.",
                    "draws": "Requested draws in the condition's shared pool; first uses only the first draw.",
                    "policy": "First reads the first requested draw, including UNKNOWN. Majority requested requires more than half of requested draws; majority valid requires more than half of valid draws plus the configured minimum."}
    sections = [_report_table("Classification metrics", metrics,
                             context + [("condition", "Condition"), ("samples", "Samples"), ("Unknown", "UNKNOWN")]
                             + [(name, name) for name in metric_names], descriptions)]
    diagnostic_fields = [key for key in DIAGNOSTIC_HELP if key.endswith("per_sample")
                         or key in {"distinct_responses_per_pool", "output_limit_hit_rate",
                                    "output_limit_measurement_coverage"}]
    sections.append(_report_table("Decision cost and generation diagnostics", metrics,
                    context + [("condition", "Condition")]
                    + [("pool_calls_per_sample", "Pool draws / sample")]
                    + [(name, name.replace("_", " ").capitalize()) for name in diagnostic_fields], descriptions))
    spreads = [row for row in analysis["template_summaries"] if "templates" in row]
    sections.append(_report_table("Task-wording score variation", spreads,
                    context + [("family", "Approach"), ("metric", "Metric"), ("templates", "Wordings"),
                               ("minimum", "Minimum"), ("maximum", "Maximum"), ("range", "Range"),
                               ("template_population_sd", "Population SD")], descriptions))
    rank_rows = []
    for row in analysis["rankings"]:
        for family in sorted(next(iter(row["ranks"].values()))):
            rank_rows.append({**row, "family": family,
                              **{variant: ranks[family] for variant, ranks in row["ranks"].items()}})
    rank_variants = [variant for variant in VARIANTS if any(variant in row for row in rank_rows)]
    sections.append(_report_table("Approach ranks across task wordings", rank_rows,
                    context + [("metric", "Metric"), ("family", "Approach")]
                    + [(variant, variant) for variant in rank_variants], descriptions))
    comparisons = [row for row in analysis["template_summaries"] if "metric_differences" in row]
    comparisons += analysis["component_and_voting_contrasts"] + analysis["protocol_contrasts"]
    comparison_rows = []
    for row in comparisons:
        displayed = {**row, "contrast": row.get("comparison", f"{row.get('variant', '')}_minus_reference"),
                     "subject": row.get("family", row.get("condition")),
                     "interval_note": row.get("ci_unavailable_reason", f"{row.get('group_by', 'cve_id')} clustered 95% intervals")}
        if row.get("comparison") == "verdict_last_minus_first":
            displayed["protocol"] = "Both (last minus first)"
        for metric, value in row["metric_differences"].items():
            interval = (row.get("cluster_bootstrap_ci95_by_metric") or row.get("cve_bootstrap_ci95_by_metric") or {}).get(metric)
            displayed[metric] = (f"{value:+.4f} [{interval[0]:+.4f}, {interval[1]:+.4f}]"
                                 if interval else f"{value:+.4f} [unavailable]")
        comparison_rows.append(displayed)
    difference_help = {**descriptions, **{metric: f"Candidate minus reference {metric}. Brackets contain a paired cluster-resampled 95% interval when available. "
                                         + METRIC_HELP[metric] for metric in INTERVAL_METRICS}}
    sections.append(_report_table("Paired prediction comparisons", comparison_rows,
                    context + [("subject", "Approach / condition"), ("contrast", "Candidate minus reference"),
                               ("samples", "Samples"), ("label_disagreement", "Label disagreement"),
                               ("same_decision_budget", "Equal decision budget")]
                    + [(metric, f"Difference: {metric} [95% interval]") for metric in INTERVAL_METRICS]
                    + [("clusters", "Clusters"), ("interval_note", "Interval status")], difference_help))
    interval_rows = [{**row, **{metric: (row.get("ci95") or {}).get(metric) for metric in CONDITION_METRICS}}
                     for row in analysis.get("condition_intervals", [])]
    sections.append(_report_table("Per-configuration cluster intervals", interval_rows,
        context + [("condition", "Condition"), ("group_by", "Grouping"), ("clusters", "Clusters")]
        + [(metric, metric + " [95% interval]") for metric in CONDITION_METRICS]
        + [("unavailable_reason", "Interval status")], descriptions))
    sections.append(_report_table("Variation across run seeds", analysis.get("seed_summaries", []),
        [(key, label) for key, label in context if key != "run_seed"]
        + [("condition", "Condition"), ("metric", "Metric"), ("runs", "Run seeds"), ("run_seeds", "Seeds"),
           ("mean", "Mean"), ("sample_sd", "Sample SD"), ("minimum", "Minimum"), ("maximum", "Maximum"),
           ("unavailable_reason", "Comparison status")], descriptions))
    research = analysis.get("research", {})
    research_specs = (
        ("Answered-sample accuracy and screening results", "selective_predictions",
         [("samples", "Samples"), ("answered_samples", "Answered"), ("Accuracy", "Overall Accuracy"),
          ("SelectiveAccuracy", "Selective accuracy"), ("SelectiveRisk", "Selective risk"),
          ("Coverage", "Coverage"), ("FalsePositivesPer1000", "False positives / 1,000")]),
        ("Class-imbalance means and subset-draw SD", "prevalence_summaries",
         [("prevalence", "Vulnerable fraction"), ("samples", "Subset samples"), ("draws", "Subset draws"),
          *[(name, name + " mean (SD)") for name in CONDITION_METRICS], ("unavailable_reason", "Status")]),
        ("Parser disagreement and recovery", "parser_comparisons",
         [("reference_parser", "Reference"), ("candidate_parser", "Candidate"), ("samples", "Samples"),
          ("changed_labels", "Changed labels"), ("recovered_verdicts", "Recovered verdicts"),
          ("new_abstentions", "New abstentions"), ("pool_verification_coverage", "Shared-pool coverage"),
          ("changed_draw_labels", "Changed draw labels"), ("recovered_draw_verdicts", "Recovered draws"),
          ("candidate_lexical_fallback_draws", "Candidate lexical fallback draws"),
          ("draw_details_coverage", "Parser detail coverage")]),
        ("Response length and decision summaries", "output_summaries",
         [("gold", "Gold label"), ("pred", "Prediction"), ("correctness", "Outcome"),
          ("samples", "Samples"), ("mean_visible_chars_per_call", "Mean visible characters / call"),
          ("mean_output_tokens_per_measured_call", "Mean reported output tokens / measured call"),
          ("response_measurement_coverage", "Response coverage"), ("token_measurement_coverage", "Token coverage"),
          ("draw_label_counts", "Draw labels"), ("parser_tier_counts", "Parser tiers")]),
        ("CWE breakdowns", "cwe_breakdowns", [("cwe_id", "CWE"), ("samples", "Samples")]
         + [(name, name) for name in DEFAULT_METRICS]),
        ("Scores by code language", "language_breakdowns", [("language", "Language"), ("samples", "Samples")]
         + [(name, name) for name in DEFAULT_METRICS]),
    )
    for title, key, fields in research_specs:
        rows = research.get(key, [])
        if key == "prevalence_summaries":
            displayed = []
            for row in rows:
                values = {}
                for name in CONDITION_METRICS:
                    spread = row.get("draw_variation", {}).get(name, {})
                    mean, sd = spread.get("mean"), spread.get("sample_sd")
                    values[name] = (f"{mean:.4f} ({sd:.4f})" if sd is not None else f"{mean:.4f} (SD unavailable)") if mean is not None else None
                displayed.append({**row, **values})
            rows = displayed
        sections.append(_report_table(title, rows,
            context + [("condition", "Condition")] + fields, descriptions))
    sections.append(_report_table("Evaluated dataset inventory", research.get("dataset_summaries", []),
        [("dataset", "Dataset"), ("samples", "Samples"), ("code_hash_coverage", "Code hash coverage"),
         ("cve_metadata_coverage", "CVE metadata coverage"), ("cwe_metadata_coverage", "CWE metadata coverage"),
         ("duplicate_code_groups", "Exact duplicate groups"), ("conflicting_label_code_groups", "Conflicting label groups")], descriptions))
    sections.append(_report_table("Cross-dataset overlap", research.get("dataset_overlap", []),
        [("dataset_a", "Dataset A"), ("dataset_b", "Dataset B"), ("shared_exact_code_hashes", "Shared exact code hashes"),
         ("conflicting_label_code_hashes", "Conflicting code labels"), ("shared_cves", "Shared CVEs"),
         ("shared_projects", "Shared projects"), ("shared_repositories", "Shared repositories")], descriptions))
    sections.append(_report_table("Unavailable analyses and metadata", research.get("unavailable", []),
        [("analysis", "Analysis"), ("dataset", "Dataset"), ("reason", "Reason")], descriptions))
    sections.append(_report_table("Cases prepared for manual review", research.get("review_cases", []),
        context + [("condition", "Condition"), ("sample_uid", "Sample ID"), ("generation_ids", "Response IDs"),
                   ("reasons", "Reasons"), ("rationale_verdict_consistent", "Human consistency review"),
                   ("review_notes", "Human notes")], descriptions, open_by_default=False))
    disabled = [name.replace("_", " ") for name, enabled in options.items() if not enabled]
    optional_note = "Disabled optional sections: " + ", ".join(disabled) + "." if disabled else "All optional analysis sections are enabled."
    pilot_note = "Offline/pilot results: use these to check the workflow, not to support performance claims." if manifest["pilot"] else "Completed experimental study."
    provenance = analysis["analysis_provenance"]
    execution_rows = _execution_rows(manifest, metrics)
    execution = _report_table("Recorded generation execution", execution_rows,
        [("model", "Model"), ("workers", "Workers"), ("generated_calls", "Fresh executions"),
         ("shared_cache_hits", "Cross-run cache hits"), ("run_reuses", "Engine cache reuses"),
         ("batch_cache_hits", "Batch reuse"),
         ("wall_seconds", "Model session time (s)"), ("generation_seconds", "Summed request time (s)"),
         ("persistent_cache_enabled", "Cross-run cache enabled"), ("shared_cache_warning", "Cache warning")],
        descriptions, filterable=False)
    if not execution:
        execution = '<p class="note">Inference execution counters are unavailable for this run.</p>'
    cfg = manifest.get("config", {})
    setup = [{"setting": label, "value": value} for label, value in (
        ("Experiment type", "Standard prompts" if analysis.get("artifact_kind") == "standard" else "Task wordings" if str(cfg.get("section")).upper() == "B" else "Components and voting" if str(cfg.get("section")).upper() == "C" else "Combined saved runs"),
        ("Run seeds", cfg.get("seeds")), ("Requested voting draws", cfg.get("votes")),
        ("Minimum valid votes (majority_valid only)", cfg.get("min_valid_votes")),
        ("Saved call records across sessions", manifest.get("total_saved_calls")),
        ("Newly saved call records this session", manifest.get("new_calls_this_session")),
        ("Runtime package versions", manifest.get("package_versions")))]
    setup_table = _report_table("Run setup", setup, [("setting", "Setting"), ("value", "Recorded value")], filterable=False)
    condition_rows = [{key: condition.get(key) for key in ("id", "comparison", "family", "variant", "protocol", "draws", "policy")}
                      for condition in manifest.get("conditions", [])]
    setup_table += _report_table("Selected experiment conditions", condition_rows,
        [("id", "Condition"), ("comparison", "Comparison"), ("family", "Approach / component"),
         ("variant", "Task wording / state"), ("protocol", "Verdict order"), ("draws", "Pool draws"), ("policy", "Decision policy")], descriptions,
        open_by_default=False)
    document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PromptAudit {version} study report</title><style>
*{box-sizing:border-box}body{font:15px system-ui,sans-serif;max-width:1600px;margin:2rem auto;padding:0 1.2rem;color:#172a3a;background:#f7fafc}
h1{margin-bottom:.5rem}p{line-height:1.5}.note{background:#e9f2fa;padding:.8rem 1rem;border-left:4px solid #226c9c}
details{background:white;border:1px solid #cbd6df;border-radius:6px;margin:1rem 0;padding:.8rem}
summary{font-weight:600;cursor:pointer}.table-wrap{overflow:auto;max-height:70vh;margin-top:.8rem}
table{border-collapse:collapse;width:100%;font-size:.85rem}th,td{border:1px solid #d7e0e7;padding:.5rem;text-align:left;vertical-align:top}
th{position:sticky;top:0;background:#e9f2fa;min-width:5.5rem;max-width:13rem;cursor:help}tbody tr:nth-child(even){background:#f7fafc}
td.text{min-width:6rem;max-width:22rem;overflow-wrap:anywhere}td.number{font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}
caption{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.report-filter{display:block;margin:1rem 0;font-weight:600}.report-filter input{display:block;width:min(100%,34rem);margin-top:.4rem;padding:.65rem;font:inherit;border:1px solid #8fa7b9;border-radius:4px}
footer{font-size:.85rem;color:#4d6070;margin-top:1.5rem}code{overflow-wrap:anywhere}[hidden]{display:none!important}
@media(max-width:600px){body{margin:1rem auto;padding:0 .65rem}h1{font-size:1.6rem}details{padding:.65rem}.table-wrap{max-height:65vh}}
</style></head><body><h1>PromptAudit {version} study report</h1>""".replace("{version}", escape(__version__))
    document += f'<p class="note">{escape(pilot_note)}</p>'
    if analysis.get("paper_exports"):
        document += ('<p><a href="paper/index.html">Open paper tables and full-precision exports</a>. '
                     'Use these saved Python calculations when updating the manuscript.</p>')
    document += ("<p>Hover over column headers for definitions. Scores and differences are proportions. "
                 "All classification metrics are included here and in <code>metrics.csv</code>. "
                 "Raw prompts, responses, and predictions remain in the run directory.</p>")
    document += f"<p>{escape(optional_note)}</p>"
    document += setup_table
    document += execution
    document += ("<p>Execution counters describe the generation session saved in the manifest. A generation resume "
                 "records that session's counters; an analysis-only resume keeps the saved counters and makes no new model calls. "
                 "Newly saved call records can include cross-run cache hits. Existing saved-journal calls may be replayed "
                 "without a backend execution or engine-cache hit. Decision-cost tables retain the original cost of "
                 "the calls used by each decision; shared-pool costs must not be summed as independent executions.</p>")
    document += ("<p>Paired intervals resample CVEs and keep related samples together. They describe CVE sampling uncertainty "
                 "conditional on the run seed and templates, and do not correct for multiple comparisons. Repository grouping, "
                 "when selected, requires complete recorded repository identifiers instead. "
                 "A first-draw decision uses one response; majority policies use their requested pool. "
                 "Shared pools are generated once. Output length does not establish reasoning quality. "
                 "Paired metric differences and intervals cover Recall, F1, Coverage, AbstentionRate, and EffectiveF1. "
                 "Abstention intervals are the reversed complements of coverage intervals. Across-seed sample SD is a separate "
                 "descriptive measure, not a cluster confidence interval.</p>")
    document += ('<label class="report-filter" for="report-search">Find experiment rows'
                 '<input id="report-search" type="search" placeholder="Dataset, model, condition, seed, or parser" autocomplete="off"></label>'
                 '<p id="filter-status" role="status" aria-live="polite">All experiment rows are shown.</p>')
    document += "".join(sections)
    document += ('<p>Detailed prevalence draws and their conditional cluster intervals are saved in '
                 '<a href="prevalence_draws.jsonl">prevalence_draws.jsonl</a>; descriptive subset-draw variation is not a confidence interval. '
                 '<a href="review_cases.csv">review_cases.csv</a> contains compact response IDs and blank author-review fields. '
                 'No review is considered complete until the authors fill those fields. Selective accuracy is reported at observed '
                 'coverage; no confidence-threshold curve is inferred and no selective-accuracy interval is claimed.</p>')
    for note in research.get("design_notes", {}).values():
        document += f'<p>{escape(str(note))}</p>'
    document += (f"<footer>Analysis created {escape(provenance['created_at'])}. "
                 f"Bootstrap resamples: {analysis['bootstrap_resamples']}; seed: {provenance['bootstrap_seed']}. "
                 f"Prediction SHA-256: <code>{escape(provenance['predictions_sha256'])}</code>. "
                 "See analysis.json for full comparisons and provenance.</footer>")
    document += """<script>
const search = document.getElementById('report-search');
search.addEventListener('input', () => {
  const words = search.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);
  let matches = 0;
  document.querySelectorAll('details[data-filterable]').forEach(section => {
    const rows = [...section.querySelectorAll('tbody tr')];
    let visible = 0;
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.hidden = !words.every(word => text.includes(word));
      if (!row.hidden) visible++;
    });
    matches += visible;
    section.querySelector('summary').textContent = section.dataset.title + ' (' + visible + '/' + rows.length + ')';
    section.querySelector('.table-wrap').hidden = visible === 0;
    section.querySelector('.empty-filter').hidden = visible !== 0;
  });
  document.getElementById('filter-status').textContent = words.length ? matches + ' matching table rows.' : 'All experiment rows are shown.';
});
</script></body></html>"""
    document = document.replace("<code>metrics.csv</code>", f"<code>{escape(analysis.get('metrics_file', 'metrics.csv'))}</code>")
    if analysis.get("artifact_kind") == "standard":
        document = document.replace("study report", "saved-result analysis")
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(document, encoding="utf-8")
    temporary.replace(path)


def _analyze_reader(reader, bootstrap, settings, control, detail_sink=None):
    from .research_analysis import decision_scores
    output, manifest = reader.output, reader.manifest
    analysis_options = {key: settings[key] for key in ("rankings", "paired_comparisons", "prevalence", "output_audit", "dataset_audit")}
    paired_enabled = analysis_options["paired_comparisons"]
    groups, protocol_groups = reader.groups, reader.protocol_groups
    for index, source in enumerate(reader.source_manifests):
        checked = dict(source)
        if reader.source_kinds[index] == "standard" and checked.get("status") == "generated":
            checked["status"] = "completed"
        _validate_study(checked, reader.source_groups(index))
    # Individual manifests validate their own matrix; the combined check rejects
    # duplicate decisions when several saved runs contain the same run seed.
    if len(reader.sources) > 1:
        _validate_study({"status": "completed"}, groups)
    bootstrap_cache = _BootstrapCache()
    metrics, summaries, rankings, contrasts, protocol_contrasts = [], [], [], [], []
    condition_intervals, seed_inputs = [], defaultdict(list)
    for key, conditions in groups.items():
        if control:
            control()
        context = dict(zip(GROUP_FIELDS, key))
        template_rows = defaultdict(dict)
        for condition, rows in conditions.items():
            if control:
                control()
            first = rows[0]
            def measured_mean(field):
                values = [r.get(field) for r in rows]
                return statistics.mean(values) if all(v is not None for v in values) else None

            decision_calls = sum(r.get("decision_calls") or 0 for r in rows)
            limit_hits = [r.get("decision_output_limit_hits") for r in rows]
            metric = {**context, "pilot": manifest["pilot"], "condition": condition, "comparison": first["comparison"],
                      "family": first["family"], "variant": first["variant"],
                      "policy": first["aggregation"]["policy"], "samples": len(rows),
                      **decision_scores(rows),
                      "calls_per_sample": measured_mean("decision_calls"),
                      "pool_calls_per_sample": measured_mean("pool_calls"),
                      "seconds_per_sample": measured_mean("decision_seconds"),
                      "prompt_tokens_per_sample": measured_mean("decision_prompt_tokens"),
                      "output_tokens_per_sample": measured_mean("decision_output_tokens"),
                      "distinct_responses_per_pool": measured_mean("distinct_responses"),
                      "output_limit_hit_rate": (sum(limit_hits) / decision_calls
                                                if decision_calls and all(v is not None for v in limit_hits) else None),
                      "output_limit_measurement_coverage": sum(v is not None for v in limit_hits) / len(rows),
                      "generation_errors_per_sample": measured_mean("decision_generation_errors")}
            metrics.append(metric)
            condition_intervals.append({**context, "condition": condition,
                **cluster_intervals(rows, bootstrap, group_by=settings["group_by"], control=control,
                                    _bootstrap_cache=bootstrap_cache)})
            seed_key = tuple(context[field] for field in GROUP_FIELDS if field != "run_seed") + (condition,)
            seed_inputs[seed_key].append({"run_seed": context["run_seed"], "metric": metric,
                                         **_seed_signature(rows)})
            if first["comparison"] == "templates":
                template_rows[first["family"]][first["variant"]] = (metric, rows)
        if template_rows:
            variants = set.intersection(*(set(v) for v in template_rows.values()))
            if any(set(v) != variants for v in template_rows.values()):
                raise ValueError("Rank comparisons require the same variants for every family")
            if not variants.issubset(VARIANTS):
                raise ValueError("Unsupported template variants in saved predictions")
            expected_samples = None
            for family, variants_for_family in template_rows.items():
                reference = variants_for_family.get("reference")
                if reference is None:
                    raise ValueError("Task-wording analysis requires the reference variant")
                for variant, (metric, rows) in variants_for_family.items():
                    sample_ids = {r["sample_uid"] for r in rows}
                    if expected_samples is None:
                        expected_samples = sample_ids
                    if sample_ids != expected_samples:
                        raise ValueError("Rank comparisons require the same sample cohort")
                    if variant != "reference" and paired_enabled:
                        summaries.append({**context, "family": family, "variant": variant,
                                          **paired_comparison(reference[1], rows, bootstrap, control=control,
                                                              _bootstrap_cache=bootstrap_cache, group_by=settings["group_by"])})
                for field in INTERVAL_METRICS:
                    scores = [metric[field] for metric, _rows in variants_for_family.values()]
                    summaries.append({**context, "family": family, "metric": field,
                                      "templates": len(scores), "minimum": min(scores),
                                      "maximum": max(scores), "range": max(scores) - min(scores),
                                      "template_population_sd": statistics.pstdev(scores)})
            for field in (("F1", "Recall", "EffectiveF1") if analysis_options["rankings"] else ()):
                per_variant = {}
                for variant in sorted(variants):
                    scores = {f: v[variant][0][field] for f, v in template_rows.items()}
                    per_variant[variant] = {f: 1 + sum(s > score for s in scores.values())
                                            for f, score in scores.items()}
                baseline = per_variant["reference"]
                rankings.append({**context, "metric": field, "ranks": per_variant,
                                 "changed_from_reference": {v: ranks != baseline
                                                            for v, ranks in per_variant.items()}})
        for family in sorted({rows[0]["family"] for rows in conditions.values()
                              if rows[0]["comparison"] == "components" and paired_enabled}):
            off = conditions[f"{family}/off/{context['protocol']}"]
            on = conditions[f"{family}/on/{context['protocol']}"]
            contrasts.append({**context, "family": family, "comparison": "component_on_minus_off",
                              **paired_comparison(off, on, bootstrap, control=control,
                                                  _bootstrap_cache=bootstrap_cache, group_by=settings["group_by"])})
        reasoning_key = f"reasoning/on/{context['protocol']}"
        adaptive_key = f"adaptive/on/{context['protocol']}"
        if paired_enabled and reasoning_key in conditions and adaptive_key in conditions:
            contrasts.append({**context, "family": "adaptive", "comparison": "adaptive_minus_unconditional_reasoning",
                              **paired_comparison(conditions[reasoning_key], conditions[adaptive_key], bootstrap,
                                                  control=control, _bootstrap_cache=bootstrap_cache, group_by=settings["group_by"])})
        for family in sorted({rows[0]["family"] for rows in conditions.values()
                              if rows[0]["comparison"] == "voting"}):
            policies = {policy: conditions[key] for policy in ("first", "majority_requested", "majority_valid")
                        if (key := f"{family}/{policy}/{context['protocol']}") in conditions}
            pools = [{r["sample_uid"]: r["generation_ids"] for r in rows} for rows in policies.values()]
            if any(pool != pools[0] for pool in pools[1:]):
                raise ValueError("Voting policies must use the same generation pool")
            if paired_enabled and "majority_requested" in policies and "majority_valid" in policies:
                requested, valid = policies["majority_requested"], policies["majority_valid"]
                contrasts.append({**context, "family": family, "comparison": "majority_valid_minus_requested",
                                  "same_decision_budget": _same_budget(requested, valid),
                                  **paired_comparison(requested, valid, bootstrap, control=control,
                                                      _bootstrap_cache=bootstrap_cache, group_by=settings["group_by"])})
            if paired_enabled and "first" in policies:
                for policy, candidate in policies.items():
                    if policy == "first":
                        continue
                    contrasts.append({**context, "family": family, "comparison": f"{policy}_minus_first",
                                      "same_decision_budget": _same_budget(policies["first"], candidate),
                                      **paired_comparison(policies["first"], candidate, bootstrap, control=control,
                                                          _bootstrap_cache=bootstrap_cache, group_by=settings["group_by"])})
    for key, protocols in protocol_groups.items():
        if paired_enabled and "verdict_first" in protocols and "verdict_last" in protocols:
            context = dict(zip([field for field in GROUP_FIELDS if field != "protocol"], key[:-1]))
            protocol_contrasts.append({**context, "condition": key[-1],
                                       "comparison": "verdict_last_minus_first",
                                       **paired_comparison(protocols["verdict_first"],
                                                           protocols["verdict_last"], bootstrap, control=control,
                                                           _bootstrap_cache=bootstrap_cache, group_by=settings["group_by"])})
    if control:
        control()
    result = {"pilot": manifest["pilot"], "run_status": manifest["status"],
              "metric_names": list(DEFAULT_METRICS), "analysis_options": analysis_options, "analysis_settings": settings,
              "artifact_kind": reader.kind, "input_artifacts": reader.artifact_summary(),
              "inference_performance": _execution_rows(manifest, metrics),
              "analysis_provenance": {
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "python": platform.python_version(),
                  "bootstrap_seed": BOOTSTRAP_SEED,
                  "source_hashes": {name: text_hash((Path(__file__).resolve().parents[1] / name).read_text(encoding="utf-8"))
                                    for name in ("evaluation/metrics.py", "evaluation/template_analysis.py",
                                                 "evaluation/artifacts.py", "evaluation/research_analysis.py",
                                                 "evaluation/paper_exports.py",
                                                 "prompts/template_variants.py", "utils/privacy.py")},
                  "input_hashes": reader.input_hashes,
                  "predictions_sha256": _prediction_hash(reader),
                  "manifest_sha256": reader.input_hashes.get("manifest.json", reader.input_hashes.get("checkpoint.json")),
              },
              "bootstrap_resamples": bootstrap, "template_summaries": summaries,
              "rankings": rankings, "component_and_voting_contrasts": contrasts,
              "protocol_contrasts": protocol_contrasts,
              "condition_intervals": condition_intervals, "seed_summaries": _seed_summaries(seed_inputs),
              "design_notes": {
                  "templates": "Spreads and rankings describe the selected task wordings.",
                  "protocols": "Verdict-last permits a generated explanation before the decision; verdict-first does not.",
                  "voting": "Policies reuse each base prompt's pool; budget equality is checked from actual decision calls.",
                  "diagnostics": "Token counts and output-limit rates use decision calls; missing measurements stay null.",
              },
              "metric_note": "Metric definitions are implemented in evaluation/metrics.py."}
    from .research_analysis import run_research_analyses
    result["research"] = run_research_analyses(reader, settings, bootstrap, control=control,
        interval_fn=lambda rows, **kwargs: cluster_intervals(rows, **kwargs, _bootstrap_cache=bootstrap_cache),
        detail_sink=detail_sink)
    result["analysis_provenance"]["input_hashes"] = dict(reader.input_hashes)
    return metrics, result


def _write_analysis_files(stage, metrics, result, manifest, *, standard, control=None):
    metrics_name = "analysis_metrics.csv" if standard else "metrics.csv"
    report_name = "analysis_report.html" if standard else "report.html"
    if metrics:
        with (stage / metrics_name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
            writer.writeheader()
            writer.writerows(metrics)
    else:
        (stage / metrics_name).write_text("", encoding="utf-8")
    result["metrics_file"] = metrics_name
    result["report_file"] = report_name
    research = result.get("research", {})
    research["detail_files"] = {"prevalence_draws": "prevalence_draws.jsonl", "review_cases": "review_cases.csv"}
    cases = research.get("review_cases", [])
    fields = ["case_id", *GROUP_FIELDS, "condition", "sample_uid", "sample_id", "gold", "pred",
              "generation_ids", "reasons", "rationale_conclusion", "rationale_verdict_consistent", "review_notes"]
    with (stage / "review_cases.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for case in cases:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                             for key, value in case.items()})
    from .paper_exports import write_paper_exports
    result["paper_exports"] = write_paper_exports(stage, metrics, result, control=control)
    (stage / "analysis.json").write_text(json.dumps(safe_settings(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    _write_study_report(stage / report_name, manifest, metrics, result)
    return (metrics_name, "analysis.json", report_name, "prevalence_draws.jsonl", "review_cases.csv",
            *result["paper_exports"]["files"])


def analyze_artifacts(output, bootstrap=1000, *, control=None, options=None):
    """Analyze completed saved runs without loading models or changing predictions."""
    if type(bootstrap) is not int or bootstrap < 0:
        raise ValueError("bootstrap must be a nonnegative integer")
    if control:
        control()
    with ArtifactReader(output, control=control) as reader:
        supplied = {**reader.manifest.get("config", {}).get("analysis", {}), **(options or {})}
        settings = resolve_analysis_settings(supplied)
        settings["bootstrap_resamples"] = bootstrap
        with tempfile.TemporaryDirectory(prefix=".analysis-", dir=reader.output) as directory:
            stage = Path(directory)
            digest = hashlib.sha256()
            with (stage / "prevalence_draws.jsonl").open("w", encoding="utf-8", newline="") as stream:
                def detail_sink(kind, row):
                    if kind != "prevalence_draws":
                        raise ValueError("Unsupported analysis detail kind")
                    line = json.dumps(safe_settings(row), ensure_ascii=False, allow_nan=False) + "\n"
                    digest.update(line.encode("utf-8"))
                    stream.write(line)
                metrics, result = _analyze_reader(reader, bootstrap, settings, control, detail_sink)
            result["analysis_provenance"]["detail_hashes"] = {"prevalence_draws.jsonl": digest.hexdigest()}
            files = _write_analysis_files(stage, metrics, result, reader.manifest,
                                          standard=reader.source_kinds[0] == "standard", control=control)
            if control:
                control()
            reader.check_inputs()
            # There are no cancellation boundaries inside this short commit step.
            # Every file is fully staged before any previous result is replaced.
            for filename in files:
                destination = reader.output / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                (stage / filename).replace(destination)
            return result


def analyze_study(output, bootstrap=1000, *, control=None, options=None):
    """Compatibility entry point for analysis of saved study predictions."""
    return analyze_artifacts(output, bootstrap, control=control, options=options)
