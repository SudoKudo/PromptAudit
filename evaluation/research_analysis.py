"""Analyze saved decisions without requesting new model responses."""

from collections import Counter, OrderedDict, defaultdict
from fractions import Fraction
import hashlib
import heapq
import json
from math import isfinite, lcm
import random
import re
import sqlite3
import statistics
import tempfile

from .label_parser import parse_verdict_details
from .metrics import DEFAULT_METRICS, Metrics


GROUP_FIELDS = ("dataset", "model_id", "model", "run_seed", "protocol", "parser_mode")
PREVALENCES = (0.20, 0.10, 0.05)
COUNT_FIELDS = ("TP", "TN", "FP", "FN", "UnFN", "Incorrect")


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _scores_from_counts(tracker):
    tracker.compute()
    total = sum(getattr(tracker, key) for key in COUNT_FIELDS)
    answered = tracker.TP + tracker.TN + tracker.FP + tracker.FN
    accuracy = (tracker.TP + tracker.TN) / answered if answered else None
    return {**tracker.to_dict(), "samples": total, "answered_samples": answered,
            "SelectiveAccuracy": accuracy,
            "SelectiveRisk": 1 - accuracy if accuracy is not None else None,
            "FalsePositivesPer1000": 1000 * tracker.FP / total if total else None}


def decision_scores(rows):
    """Keep answered-only accuracy separate from the paper's overall Accuracy."""
    tracker = Metrics()
    for row in rows:
        tracker.add(row["gold"], row["pred"])
    return _scores_from_counts(tracker)


def _cohort(rows):
    identities, sources = {}, {}
    for row in rows:
        uid = row.get("sample_uid")
        if not uid:
            raise ValueError("Research analysis requires sample identifiers")
        if uid in identities:
            raise ValueError("A condition contains duplicate sample identifiers")
        identities[uid] = row["gold"]
        sources[uid] = {field: row.get(field) for field in (
            "gold", "code_sha256", "cve_id", "repository", "project", "cwe_id",
            "filename", "file_number", "pair_id", "language")}
    return identities, _hash(sorted(sources.items()))


def prevalence_plan(rows, size=1000, repeats=20, *, dataset="", run_seed=42):
    """Use exact class ratios, one feasible size, and matched draws across methods."""
    if type(size) is not int or size < 1 or type(repeats) is not int or repeats < 1:
        raise ValueError("Prevalence size and repeats must be positive integers")
    identities, signature = _cohort(rows)
    if any(not row.get("code_sha256") or row.get("traceability_available") is False for row in rows):
        return {"samples": 0, "cohort_sha256": signature, "draws": (),
                "unavailable_reason": "Stable sample identities and code hashes are required for matched prevalence subsets"}
    classes = {gold: sorted(uid for uid, label in identities.items() if label == gold)
               for gold in ("safe", "vulnerable")}
    ratios = [Fraction(str(value)) for value in PREVALENCES]
    multiple = lcm(*(ratio.denominator for ratio in ratios))
    available = min([size] + [bound for ratio in ratios for bound in (
        len(classes["vulnerable"]) * ratio.denominator // ratio.numerator,
        len(classes["safe"]) * ratio.denominator // (ratio.denominator - ratio.numerator))])
    selected_size = available // multiple * multiple
    if not selected_size:
        return {"samples": 0, "cohort_sha256": signature, "draws": (),
                "unavailable_reason": f"At least {multiple} feasible samples are needed for the exact preset ratios"}

    def draws():
        for draw in range(repeats):
            seed = int(_hash(["prevalence-v1", dataset, run_seed, draw])[:16], 16)
            rng = random.Random(seed)
            safe = rng.sample(classes["safe"], len(classes["safe"]))
            vulnerable = rng.sample(classes["vulnerable"], len(classes["vulnerable"]))
            for rate, ratio in zip(PREVALENCES, ratios):
                vulnerable_count = selected_size * ratio.numerator // ratio.denominator
                ids = sorted(vulnerable[:vulnerable_count] + safe[:selected_size - vulnerable_count])
                yield {"prevalence": rate, "draw": draw, "subset_seed": seed,
                       "sample_ids": ids, "subset_sha256": _hash(ids)}
    return {"samples": selected_size, "cohort_sha256": signature, "draws": draws(),
            "unavailable_reason": None}


class _Intervals:
    """Reuse identical cluster/count calculations without retaining sample rows."""

    def __init__(self, function, bootstrap, group_by, control):
        self.function, self.bootstrap, self.group_by, self.control = function, bootstrap, group_by, control
        self.cache = OrderedDict()

    def get(self, rows):
        if self.function is None:
            return {"ci95": None, "clusters": 0, "group_by": self.group_by,
                    "unavailable_reason": "No interval calculation was supplied"}
        clusters = defaultdict(lambda: [0] * 6)
        categories = {("vulnerable", "vulnerable"): 0, ("safe", "safe"): 1,
                      ("safe", "vulnerable"): 2, ("vulnerable", "safe"): 3,
                      ("vulnerable", "unknown"): 4, ("safe", "unknown"): 5}
        for row in rows:
            clusters[str(row.get(self.group_by) or "")][categories[(row["gold"], row["pred"])]] += 1
        key = _hash([self.bootstrap, self.group_by, sorted(clusters.items())])
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        result = self.function(rows, bootstrap=self.bootstrap, seed=42, group_by=self.group_by,
                               control=self.control)
        self.cache[key] = result
        if len(self.cache) > 128:
            self.cache.popitem(last=False)
        return result


def _spread(values):
    values = [value for value in values if value is not None]
    if not values:
        return {"mean": None, "sample_sd": None, "minimum": None, "maximum": None,
                "draw_quantile95": None}
    ordered = sorted(values)
    return {"mean": statistics.mean(values), "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
            "minimum": min(values), "maximum": max(values),
            "draw_quantile95": [ordered[int((len(ordered) - 1) * p)] for p in (0.025, 0.975)]}


def _prevalence(rows, context, options, intervals, control):
    lookup = {row["sample_uid"]: row for row in rows}
    plan = prevalence_plan(rows, options.get("prevalence_size", 1000),
                           options.get("prevalence_repeats", 20),
                           dataset=context["dataset"], run_seed=context["run_seed"])
    if plan["unavailable_reason"]:
        return [], [{**context, "unavailable_reason": plan["unavailable_reason"],
                     "cohort_sha256": plan["cohort_sha256"], "samples": 0}]
    draws, by_rate = [], defaultdict(list)
    for draw in plan["draws"]:
        if control:
            control()
        selected = [lookup[uid] for uid in draw["sample_ids"]]
        scores = decision_scores(selected)
        result = {**context, **{key: value for key, value in draw.items() if key != "sample_ids"},
                  "cohort_sha256": plan["cohort_sha256"], **scores,
                  "cluster_intervals": intervals.get(selected)}
        draws.append(result)
        by_rate[draw["prevalence"]].append(result)
    fields = (*DEFAULT_METRICS, "FalsePositivesPer1000", "SelectiveAccuracy", "SelectiveRisk")
    summaries = [{**context, "prevalence": rate, "samples": plan["samples"], "draws": len(group),
                  "cohort_sha256": plan["cohort_sha256"],
                  "draw_variation": {field: _spread([row[field] for row in group]) for field in fields},
                  "uncertainty_note": "Draw quantiles describe subset variation, not confidence intervals; each draw has a separate conditional cluster interval"}
                 for rate, group in by_rate.items()]
    return draws, summaries


def compare_parsers(reference, candidate, *, generation_lookup=None, control=None):
    """Count parser effects only where the saved generation pools match."""
    left = {row["sample_uid"]: row for row in reference}
    right = {row["sample_uid"]: row for row in candidate}
    if len(left) != len(reference) or len(right) != len(candidate):
        raise ValueError("Parser comparisons require one prediction per sample")
    if left.keys() != right.keys():
        raise ValueError("Parser comparisons require the same samples")
    counts = Counter()
    for index, (uid, a) in enumerate(left.items()):
        if control and index % 100 == 0:
            control()
        b = right[uid]
        if a["gold"] != b["gold"]:
            raise ValueError("Gold labels differ across parsers")
        if not a.get("generation_ids") or not b.get("generation_ids"):
            counts["missing_pool_links"] += 1
            continue
        if a["generation_ids"] != b["generation_ids"]:
            counts["different_pools"] += 1
            continue
        counts["verified_samples"] += 1
        counts["changed_labels"] += a["pred"] != b["pred"]
        counts["recovered_verdicts"] += a["pred"] == "unknown" and b["pred"] != "unknown"
        counts["new_abstentions"] += a["pred"] != "unknown" and b["pred"] == "unknown"
        counts["changed_answered_labels"] += a["pred"] != b["pred"] and "unknown" not in {a["pred"], b["pred"]}
        a_details = {item.get("generation_id"): item for item in a.get("parsed_votes", [])}
        b_details = {item.get("generation_id"): item for item in b.get("parsed_votes", [])}
        for generation_id in a["generation_ids"]:
            counts["matched_pool_draws"] += 1
            details = [a_details.get(generation_id), b_details.get(generation_id)]
            if any(item is None for item in details) and generation_lookup:
                call = generation_lookup(generation_id)
                if call is not None:
                    details = [item or parse_verdict_details(call.get("raw_output", ""),
                        mode=row["parser_mode"], output_protocol=row["protocol"])
                        for item, row in zip(details, (a, b))]
            if any(item is None for item in details):
                counts["draws_without_parser_details"] += 1
                continue
            label_a, label_b = (item["label"] for item in details)
            counts["verified_draws"] += 1
            counts["changed_draw_labels"] += label_a != label_b
            counts["recovered_draw_verdicts"] += label_a == "unknown" and label_b != "unknown"
            counts["new_draw_abstentions"] += label_a != "unknown" and label_b == "unknown"
            counts["candidate_lexical_fallback_draws"] += details[1].get("tier") == "lexical_fallback"
    verified = counts["verified_samples"]
    return {"samples": len(left), **{key: counts[key] for key in ("verified_samples", "changed_labels",
            "recovered_verdicts", "new_abstentions", "changed_answered_labels", "missing_pool_links", "different_pools",
            "matched_pool_draws", "verified_draws", "changed_draw_labels", "recovered_draw_verdicts",
            "new_draw_abstentions", "candidate_lexical_fallback_draws", "draws_without_parser_details")},
            "pool_verification_coverage": verified / len(left) if left else None,
            "draw_details_coverage": counts["verified_draws"] / counts["matched_pool_draws"] if counts["matched_pool_draws"] else None,
            "label_disagreement": counts["changed_labels"] / verified if verified else None,
            "unavailable_reason": None if verified else "No samples have verified shared response pools"}


class _ReviewCases:
    def __init__(self, limit):
        self.limit = limit
        self.heap = []
        self.seen = set()
        self.candidates = 0

    def add(self, row, context, reasons):
        if not reasons:
            return
        identity = _hash([context, row["sample_uid"], sorted(reasons)])
        if identity in self.seen:
            return
        self.candidates += 1
        if not self.limit:
            return
        priority = int(identity, 16)
        if len(self.heap) >= self.limit and priority >= -self.heap[0][0]:
            return
        case = {**context, "case_id": identity, "sample_uid": row["sample_uid"],
                "sample_id": row.get("sample_id"), "gold": row["gold"], "pred": row["pred"],
                "generation_ids": row.get("generation_ids", []), "reasons": sorted(reasons),
                "rationale_conclusion": "", "rationale_verdict_consistent": "", "review_notes": ""}
        item = (-priority, identity, case)
        if len(self.heap) == self.limit:
            removed = heapq.heapreplace(self.heap, item)
            self.seen.discard(removed[1])
        else:
            heapq.heappush(self.heap, item)
        self.seen.add(identity)

    def rows(self):
        return [item[2] for item in sorted(self.heap, key=lambda item: item[1])]


class _GenerationCache:
    def __init__(self, reader):
        self.reader = reader
        self.cache = OrderedDict()
        self.bytes = 0

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key][0]
        call = self.reader.get_generation(key)
        size = len((call or {}).get("raw_output", "").encode("utf-8")) + 512
        if size <= 2 * 1024 * 1024:
            self.cache[key] = (call, size)
            self.bytes += size
            while self.bytes > 2 * 1024 * 1024 or len(self.cache) > 128:
                _key, (_old, removed) = self.cache.popitem(last=False)
                self.bytes -= removed
        return call


def _output_summary(rows, context, cache, cases, control):
    totals = defaultdict(lambda: Counter())
    for index, row in enumerate(rows):
        if control and index % 100 == 0:
            control()
        correctness = "abstained" if row["pred"] == "unknown" else "correct" if row["pred"] == row["gold"] else "incorrect"
        counts = totals[(row["gold"], row["pred"], correctness)]
        counts["samples"] += 1
        ids = row.get("decision_generation_ids")
        if ids is None:
            pool = row.get("generation_ids", [])
            ids = pool[:1] if row.get("aggregation", {}).get("policy") == "first" else pool
        requested = row.get("decision_calls")
        budget = requested if type(requested) is int and requested >= 0 else len(ids) if ids else None
        if budget is None:
            counts["samples_without_decision_budget"] += 1
        else:
            if budget < len(ids):
                raise ValueError("Saved decision calls are fewer than the linked decision responses")
            counts["samples_with_decision_budget"] += 1
            counts["known_decision_calls"] += budget
            counts["missing_responses"] += budget - len(ids)
        reasons = {"unresolved_verdict"} if row["pred"] == "unknown" else set()
        saved_details = {item.get("generation_id"): item for item in row.get("parsed_votes", [])}
        for generation_id in ids:
            call = cache.get(generation_id)
            if call is None:
                counts["missing_responses"] += 1
                continue
            raw = str(call.get("raw_output") or "")
            info = call.get("generation_info") or {}
            counts["available_responses"] += 1
            counts["response_chars"] += len(raw)
            tokens = info.get("eval_count", info.get("completion_tokens"))
            if type(tokens) in (int, float) and isfinite(tokens) and tokens >= 0:
                counts["measured_token_calls"] += 1
                counts["output_tokens"] += tokens
            details = saved_details.get(generation_id) or parse_verdict_details(raw,
                mode=context["parser_mode"], output_protocol=context["protocol"])
            counts["tier:" + str(details.get("tier") or "unknown")] += 1
            counts["draw_label:" + str(details.get("label") or "unknown")] += 1
            if details.get("tier") == "lexical_fallback":
                reasons.add("lexical_fallback")
            if info.get("output_limit_reached") is True or info.get("done_reason") == "length":
                counts["output_cap_calls"] += 1
                reasons.add("output_limit")
            if call.get("error") or info.get("status") == "error":
                counts["generation_error_calls"] += 1
                reasons.add("generation_error")
            if len(raw.splitlines()) > 1:
                reasons.add("rationale_verdict_review")
        if not ids:
            counts["samples_without_response_links"] += 1
        cases.add(row, context, reasons)
    result = []
    for (gold, label, correctness), counts in sorted(totals.items()):
        available = counts["available_responses"]
        measured = counts["measured_token_calls"]
        complete_budget = not counts["samples_without_decision_budget"]
        decision_calls = counts["known_decision_calls"] if complete_budget else None
        result.append({**context, "gold": gold, "pred": label, "correctness": correctness,
                       **{key: counts[key] for key in ("samples", "available_responses",
                           "samples_without_response_links", "output_cap_calls", "generation_error_calls",
                           "known_decision_calls", "samples_without_decision_budget")},
                       "decision_calls": decision_calls,
                       "missing_responses": counts["missing_responses"] if complete_budget else None,
                       "known_missing_responses": counts["missing_responses"],
                       "decision_budget_measurement_coverage": counts["samples_with_decision_budget"] / counts["samples"],
                       "mean_visible_chars_per_call": counts["response_chars"] / available if available else None,
                       "response_measurement_coverage": available / decision_calls if decision_calls else None,
                       "mean_output_tokens_per_measured_call": counts["output_tokens"] / measured if measured else None,
                       "token_measurement_coverage": measured / decision_calls if decision_calls else None,
                       "unavailable_reason": None if available else "No linked saved responses were available",
                       "draw_label_counts": {key[11:]: value for key, value in counts.items() if key.startswith("draw_label:")},
                       "parser_tier_counts": {key[5:]: value for key, value in counts.items() if key.startswith("tier:")}})
    return result


def _cwes(value):
    if isinstance(value, list):
        value = " ".join(map(str, value))
    text = str(value or "").strip()
    return sorted(set(re.findall(r"CWE-\d+", text.upper()))) or (["CWE-" + text] if text.isdigit() else [])


class _DatasetIndex:
    def __init__(self, directory):
        self.db = sqlite3.connect(str(directory) + "/samples.sqlite3")
        self.db.execute("CREATE TABLE samples (dataset TEXT, uid TEXT, gold TEXT, code_sha256 TEXT, cve_id TEXT, project TEXT, repository TEXT, cwe_id TEXT, PRIMARY KEY(dataset,uid))")

    def add(self, dataset, row):
        values = (dataset, row["sample_uid"], row["gold"], str(row.get("code_sha256") or ""),
                  str(row.get("cve_id") or ""), str(row.get("project") or ""),
                  str(row.get("repository") or ""), json.dumps(_cwes(row.get("cwe_id"))))
        previous = self.db.execute("SELECT * FROM samples WHERE dataset=? AND uid=?", values[:2]).fetchone()
        if previous and previous != values:
            raise ValueError("A sample has inconsistent labels, code hashes, or metadata across conditions")
        if previous is None:
            self.db.execute("INSERT INTO samples VALUES (?,?,?,?,?,?,?,?)", values)

    def summarize(self):
        self.db.commit()
        self.db.execute("CREATE INDEX IF NOT EXISTS code_hashes ON samples(code_sha256,dataset)")
        datasets = [row[0] for row in self.db.execute("SELECT DISTINCT dataset FROM samples ORDER BY dataset")]
        summaries, overlap = [], []
        for dataset in datasets:
            total, vulnerable, hashes, cves, cwes, projects, repositories = self.db.execute(
                "SELECT COUNT(*), SUM(gold='vulnerable'), SUM(code_sha256!=''), SUM(cve_id!=''), SUM(cwe_id!='[]'), SUM(project!=''), SUM(repository!='') FROM samples WHERE dataset=?", (dataset,)).fetchone()
            duplicate_groups = self.db.execute("SELECT COUNT(*) FROM (SELECT code_sha256 FROM samples WHERE dataset=? AND code_sha256!='' GROUP BY code_sha256 HAVING COUNT(*)>1)", (dataset,)).fetchone()[0]
            conflicting = self.db.execute("SELECT COUNT(*) FROM (SELECT code_sha256 FROM samples WHERE dataset=? AND code_sha256!='' GROUP BY code_sha256 HAVING COUNT(DISTINCT gold)>1)", (dataset,)).fetchone()[0]
            summaries.append({"dataset": dataset, "samples": total, "vulnerable_samples": vulnerable,
                              "safe_samples": total - vulnerable, "observed_vulnerable_fraction": vulnerable / total if total else None,
                              "code_hash_coverage": hashes / total if total else None,
                              "cve_metadata_coverage": cves / total if total else None,
                              "cwe_metadata_coverage": cwes / total if total else None,
                              "project_metadata_coverage": projects / total if total else None,
                              "repository_metadata_coverage": repositories / total if total else None,
                              "duplicate_code_groups": duplicate_groups if hashes else None,
                              "conflicting_label_code_groups": conflicting if hashes else None})
        for index, left in enumerate(datasets):
            for right in datasets[index + 1:]:
                shared = {}
                for column in ("code_sha256", "cve_id", "project", "repository"):
                    query = f"SELECT COUNT(*) FROM (SELECT {column} FROM samples WHERE dataset=? AND {column}!='' INTERSECT SELECT {column} FROM samples WHERE dataset=? AND {column}!='')"
                    available = all(self.db.execute(f"SELECT COUNT(*) FROM samples WHERE dataset=? AND {column}!=''", (dataset,)).fetchone()[0]
                                    for dataset in (left, right))
                    shared[column] = self.db.execute(query, (left, right)).fetchone()[0] if available else None
                conflicts = self.db.execute("SELECT COUNT(DISTINCT a.code_sha256) FROM samples a JOIN samples b ON a.code_sha256=b.code_sha256 WHERE a.dataset=? AND b.dataset=? AND a.code_sha256!='' AND a.gold!=b.gold", (left, right)).fetchone()[0]
                overlap.append({"dataset_a": left, "dataset_b": right, "shared_exact_code_hashes": shared["code_sha256"],
                                "shared_cves": shared["cve_id"], "shared_projects": shared["project"],
                                "shared_repositories": shared["repository"],
                                "conflicting_label_code_hashes": conflicts if shared["code_sha256"] is not None else None})
        return summaries, overlap

    def close(self):
        self.db.close()


def _dataset_unavailable(summaries):
    return [{"analysis": name, "dataset": row["dataset"],
             "reason": "Required identifiers were not recorded"}
            for row in summaries for name, field in (
                ("exact_code_overlap", "code_hash_coverage"), ("CVE_overlap", "cve_metadata_coverage"),
                ("CWE_breakdown", "cwe_metadata_coverage"), ("project_overlap", "project_metadata_coverage"),
                ("repository_overlap", "repository_metadata_coverage")) if row[field] == 0]


def audit_dataset_cohorts(cohorts, *, control=None):
    """Audit selected source cohorts before inference without changing their rows."""
    names = set()
    with tempfile.TemporaryDirectory(prefix="promptaudit-datasets-") as directory:
        index = _DatasetIndex(directory)
        try:
            for dataset, rows in cohorts:
                if not isinstance(dataset, str) or not dataset.strip() or dataset in names:
                    raise ValueError("Dataset audit requires distinct nonempty dataset names")
                names.add(dataset)
                seen, identities = set(), set()
                for position, original in enumerate(rows):
                    if control and position % 1000 == 0:
                        control()
                    row = dict(original)
                    gold = str(row.get("gold", row.get("label", ""))).strip().lower()
                    if gold not in {"safe", "vulnerable"}:
                        raise ValueError("Dataset audit requires SAFE or VULNERABLE gold labels")
                    code_hash = row.get("code_sha256")
                    if code_hash is None:
                        code = row.get("code")
                        if not isinstance(code, str) or not code.strip():
                            raise ValueError("Dataset audit requires nonempty code or a recorded code hash")
                        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
                    elif not re.fullmatch(r"[0-9a-f]{64}", str(code_hash)):
                        raise ValueError("Dataset audit requires a valid SHA-256 code hash")
                    source_id = str(row.get("sample_id", row.get("id", position)))
                    if not source_id.strip() or source_id in seen:
                        raise ValueError("Dataset audit requires unique nonempty source sample IDs")
                    seen.add(source_id)
                    uid = row.get("sample_uid") or _hash([dataset, source_id, gold, code_hash])
                    if uid in identities:
                        raise ValueError("Dataset audit requires unique sample identities")
                    identities.add(uid)
                    index.add(dataset, {**row, "sample_uid": uid, "gold": gold, "code_sha256": code_hash})
                if not seen:
                    raise ValueError(f"Dataset {dataset} has no samples to audit")
            if not names:
                raise ValueError("Select at least one dataset to audit")
            summaries, overlap = index.summarize()
            return {"dataset_summaries": summaries, "dataset_overlap": overlap,
                    "unavailable": _dataset_unavailable(summaries),
                    "design_note": "Exact code hashes and supplied identifiers only; selected source rows are not dropped or relabeled. Missing metadata is reported as incomplete coverage, and near-duplicate code is not detected."}
        finally:
            index.close()


def run_research_analyses(reader, options=None, bootstrap=1000, *, control=None, interval_fn=None,
                         detail_sink=None):
    """Return compact offline analyses; raw responses stay in their original store."""
    options = options or {}
    selective, prevalence_draws, prevalence_summaries, output_summaries, cwe_rows = [], [], [], [], []
    language_rows = []
    cases = _ReviewCases(options.get("review_case_limit", 50))
    intervals = _Intervals(interval_fn, bootstrap, options.get("group_by", "cve_id"), control)
    generations = _GenerationCache(reader)
    cohort_signatures = {}
    parser_groups = defaultdict(dict)
    prevalence_draw_count = 0
    with tempfile.TemporaryDirectory(prefix="promptaudit-research-") as directory:
        dataset_index = _DatasetIndex(directory)
        try:
            for group, conditions in reader.iter_groups():
                if control:
                    control()
                group_context = dict(zip(GROUP_FIELDS, group))
                parser_groups[group[:5]][group[5]] = conditions
                for condition, rows in conditions.items():
                    if control:
                        control()
                    first = rows[0]
                    context = {**group_context, "condition": condition, "family": first.get("family"),
                               "variant": first.get("variant"), "comparison": first.get("comparison")}
                    _identities, signature = _cohort(rows)
                    cohort_key = (group_context["dataset"], group_context["run_seed"])
                    previous = cohort_signatures.setdefault(cohort_key, signature)
                    if previous != signature:
                        raise ValueError("Research comparisons require the same gold-labeled cohort and source metadata across configurations")
                    scores = decision_scores(rows)
                    selective.append({**context, **scores})
                    language_counts = defaultdict(Metrics)
                    for row in rows:
                        language = str(row.get("language") or "").strip() or "Unspecified"
                        language_counts[language].add(row["gold"], row["pred"])
                    for language, tracker in sorted(language_counts.items()):
                        language_rows.append({**context, "language": language, **_scores_from_counts(tracker)})
                    if options.get("prevalence", True):
                        draws, summaries = _prevalence(rows, context, options, intervals, control)
                        prevalence_draw_count += len(draws)
                        if detail_sink:
                            for draw in draws:
                                detail_sink("prevalence_draws", draw)
                        else:
                            prevalence_draws.extend(draws)
                        prevalence_summaries.extend(summaries)
                    if options.get("output_audit", True):
                        output_summaries.extend(_output_summary(rows, context, generations, cases, control))
                    if options.get("dataset_audit", True):
                        cwe_counts = defaultdict(Metrics)
                        for row in rows:
                            dataset_index.add(group_context["dataset"], row)
                            for cwe in _cwes(row.get("cwe_id")):
                                cwe_counts[cwe].add(row["gold"], row["pred"])
                        for cwe, tracker in sorted(cwe_counts.items()):
                            tracker.compute()
                            cwe_rows.append({**context, "cwe_id": cwe,
                                "samples": sum(getattr(tracker, key) for key in COUNT_FIELDS), **tracker.to_dict()})
            datasets, overlap = dataset_index.summarize() if options.get("dataset_audit", True) else ([], [])
        finally:
            dataset_index.close()
    parser_comparisons = []
    order = ("strict", "structured", "full")
    for group, modes in sorted(parser_groups.items()):
        for index, reference in enumerate(order):
            for candidate in order[index + 1:]:
                if reference not in modes or candidate not in modes:
                    continue
                if set(modes[reference]) != set(modes[candidate]):
                    raise ValueError("Parser comparison conditions differ")
                for condition, rows in modes[reference].items():
                    if control:
                        control()
                    result = compare_parsers(rows, modes[candidate][condition],
                                             generation_lookup=generations.get, control=control)
                    parser_comparisons.append({**dict(zip(GROUP_FIELDS[:5], group)), "condition": condition,
                        "reference_parser": reference, "candidate_parser": candidate, **result})
    return {"selective_predictions": selective, "prevalence_summaries": prevalence_summaries,
            "prevalence_draws": prevalence_draws, "parser_comparisons": parser_comparisons,
            "prevalence_draw_count": prevalence_draw_count,
            "prevalence_detail_storage": "external JSONL" if detail_sink else "inline",
            "output_summaries": output_summaries, "dataset_summaries": datasets,
            "dataset_overlap": overlap, "cwe_breakdowns": cwe_rows, "language_breakdowns": language_rows,
            "review_cases": cases.rows(), "review_case_candidates": cases.candidates,
            "unavailable": _dataset_unavailable(datasets),
            "design_notes": {
                "languages": "Language scores use recorded language labels within each configuration. Missing labels form an Unspecified group; no languages are pooled or inferred from filenames.",
                "prevalence": "Exact 20%, 10%, and 5% vulnerable subsets share one feasible size and deterministic selections across configurations within each dataset/run seed. Shared class-specific permutations make the rate subsets overlap. Twenty draws and a 1,000-sample target are configurable project choices. Samples are drawn without replacement within a draw; draws overlap.",
                "prevalence_uncertainty": "Draw quantiles describe subset variation. Cluster confidence intervals are conditional on each realized subset; neither is a joint interval over both sources of variation.",
                "selective_prediction": "Selective accuracy scores answered samples only. No answered samples gives unavailable accuracy/risk. Abstentions identify potential review workload; no human-review outcome or cost is assumed. The paper's Recall still treats vulnerable abstentions as missed detections. Each configuration provides one observed risk-coverage point; no confidence threshold curve is inferred.",
                "output_audit": "Lengths describe visible response text and backend-reported output tokens separately. Backend token counts can include reasoning tokens; tokenizers differ. Neither length nor rationale-verdict agreement establishes correctness or causality.",
                "review_cases": "A bounded deterministic hash-ranked sample of flagged cases. Blank human-review fields require author review; the exported summaries contain no raw responses or thinking text.",
                "dataset_audit": "Exact code hashes and supplied identifiers only. Repeated predictions are deduplicated by dataset/sample ID. Missing hashes or metadata limit observed overlap; no samples are dropped or relabeled. CWE categories can overlap."}}

