"""Export saved Python analysis values as traceable manuscript tables."""

import csv
import hashlib
from html import escape
import json
from pathlib import Path

from .metrics import DEFAULT_METRICS, METRIC_HELP
from utils.privacy import safe_settings


SCHEMA_VERSION = "1.0"
GROUP_FIELDS = ("dataset", "model_id", "model", "run_seed", "protocol", "parser_mode", "condition")
PREVIEW_ROWS = 50
_PRIVATE_FIELDS = {"raw_output", "raw_response", "prompt_text", "thinking_output", "response_preview",
                   "response_text_preview", "error_message", "response", "thinking", "code", "error", "review_notes",
                   "rationale_conclusion", "rationale_verdict_consistent"}


def _flatten(value, prefix=""):
    """Keep nested field names explicit; interval bounds use lower/upper suffixes."""
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            if key not in _PRIVATE_FIELDS:
                result.update(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, (list, tuple)):
        interval = len(value) == 2 and ("ci95" in prefix or "quantile95" in prefix)
        for index, child in enumerate(value):
            suffix = ("lower", "upper")[index] if interval else str(index)
            result.update(_flatten(child, f"{prefix}.{suffix}"))
    else:
        result[prefix] = value
    return result


def _csv_value(value):
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _display(value):
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def _write_csv(path, rows, *, control=None):
    # Find columns first, then stream rows without retaining the full draw table.
    fields, seen = [], set()
    for index, row in enumerate(rows()):
        if control and index % 100 == 0:
            control()
        for key in _flatten(safe_settings(row)):
            if key not in seen:
                seen.add(key)
                fields.append(key)
    fields = [key for key in GROUP_FIELDS if key in seen] + [key for key in fields if key not in GROUP_FIELDS]
    preview, count = [], 0
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for count, row in enumerate(rows(), 1):
            if control and count % 100 == 0:
                control()
            flat = _flatten(safe_settings(row))
            writer.writerow({key: _csv_value(value) for key, value in flat.items()})
            if len(preview) < PREVIEW_ROWS:
                preview.append(flat)
    return {"rows": count, "columns": fields, "preview": preview}


def _jsonl_rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _rank_rows(rows):
    for row in rows:
        context = {key: value for key, value in row.items() if key not in {"ranks", "changed_from_reference"}}
        for variant, ranks in row.get("ranks", {}).items():
            for family, rank in ranks.items():
                yield {**context, "variant": variant, "family": family, "rank": rank,
                       "ranking_changed_from_reference": row.get("changed_from_reference", {}).get(variant)}


def _score_rows(metrics, intervals):
    lookup = {tuple(row.get(key) for key in GROUP_FIELDS): row for row in intervals}
    for row in metrics:
        interval = lookup.get(tuple(row.get(key) for key in GROUP_FIELDS), {})
        yield {**row, "ci95": interval.get("ci95"), "interval_clusters": interval.get("clusters"),
               "interval_group_by": interval.get("group_by"),
               "interval_unavailable_reason": interval.get("unavailable_reason")}


def _tex(value):
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
                    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(char, char) for char in _display(value))


def _write_tex(path, metrics):
    columns = (*GROUP_FIELDS, "samples", *DEFAULT_METRICS)
    with path.open("w", encoding="utf-8") as stream:
        stream.write("% Saved configuration scores. Fractions are rounded only for display.\n")
        stream.write("% Wide table: select the needed rows and columns for the manuscript.\n")
        stream.write(r"\begin{tabular}{" + "l" * len(columns) + "}\n" + r"\hline" + "\n")
        stream.write(" & ".join(_tex(key) for key in columns) + r" \\" + "\n" + r"\hline" + "\n")
        for row in metrics:
            safe = safe_settings(row)
            stream.write(" & ".join(_tex(safe.get(key)) for key in columns) + r" \\" + "\n")
        stream.write(r"\hline" + "\n" + r"\end{tabular}" + "\n")


def _definitions():
    return {
        "metrics": {**METRIC_HELP,
            "SelectiveAccuracy": "(TP + TN) / answered_samples; unavailable when no sample is answered.",
            "SelectiveRisk": "1 - SelectiveAccuracy; unavailable when no sample is answered.",
            "FalsePositivesPer1000": "1000 * FP / samples; denominator includes answered and abstained samples."},
        "counts": {
            "TP": "VULNERABLE prediction with VULNERABLE gold label.",
            "TN": "SAFE prediction with SAFE gold label.",
            "FP": "VULNERABLE prediction with SAFE gold label.",
            "FN": "SAFE prediction with VULNERABLE gold label.",
            "UnFN": "UNKNOWN prediction with VULNERABLE gold label.",
            "Incorrect": "UNKNOWN prediction with SAFE gold label.",
            "Unknown": "UnFN + Incorrect.",
            "samples": "TP + TN + FP + FN + UnFN + Incorrect.",
            "answered_samples": "TP + TN + FP + FN."},
        "units": "Classification metrics, risks, coverage, rates, and prevalence are fractions in [0,1]; differences are signed fractions. FalsePositivesPer1000 is a count per 1,000 evaluated snippets.",
        "zero_denominators": "The seven classification metrics follow evaluation/metrics.py and return zero when their denominator is zero. Selective accuracy/risk and empty-cohort false positives per 1,000 remain unavailable.",
    }


def _write_index(path, manifest, tables):
    sections = []
    for name, table in tables.items():
        fields = table["columns"]
        heading = "".join(f"<th>{escape(key)}</th>" for key in fields)
        body = "".join("<tr>" + "".join(f"<td>{escape(_display(row.get(key)))}</td>" for key in fields)
                       + "</tr>" for row in table["preview"])
        sections.append(f'<details><summary>{escape(table["title"])} ({table["rows"]} rows)</summary>'
            f'<p>{escape(table["description"])} <a href="{escape(name)}.csv">Download full CSV</a></p>'
            f'<p>Preview: first {len(table["preview"])} rows. Display rounds decimals to four places.</p>'
            f'<div class="scroll"><table><thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div></details>')
    definitions = "".join(f"<dt>{escape(key)}</dt><dd>{escape(text)}</dd>"
                          for key, text in manifest["definitions"]["metrics"].items())
    status = "Pilot output. Use this to check the workflow; it is not a full experiment." if manifest["pilot"] else "Saved experiment analysis."
    document = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PromptAudit paper tables</title><style>
body{font:16px system-ui,sans-serif;margin:2rem;line-height:1.5;color:#202a38}a{color:#145eac}details{border:1px solid #ccd4df;padding:1rem;margin:1rem 0}summary{cursor:pointer;font-weight:600}.scroll{overflow:auto;max-height:32rem}table{border-collapse:collapse;font-size:.85rem;white-space:nowrap}th,td{padding:.4rem .7rem;border:1px solid #d7dce3;text-align:left}th{background:#edf2f8;position:sticky;top:0}input{padding:.6rem;width:min(36rem,90%)}dt{font-weight:600}dd{margin-bottom:.6rem}.status{background:#edf2f8;padding:1rem}
</style></head><body><h1>Paper tables</h1><p class="status">STATUS</p>
<p>These tables copy the saved Python analysis. CSV files retain full precision. No model calls, cross-model averages, or pooled scores are added by the exporter.</p>
<p><a href="manifest.json">Definitions, settings, and file hashes</a> | <a href="condition_scores.tex">Configuration table for LaTeX</a> | <a href="../analysis.json">Complete analysis JSON</a> | <a href="review_cases.csv">Review candidates</a></p>
<p>Keep dataset, model identity, run seed, condition, verdict order, and parser separate when selecting values for the paper. Seed summaries, wording spreads, and prevalence draw summaries describe different sources of variation. A mean F1 is not an F1 computed from pooled counts.</p>
<label for="search">Find a table or preview row</label><br><input id="search" type="search" placeholder="Search dataset, model, metric, or condition">
SECTIONS
<details><summary>Metric definitions</summary><dl>DEFINITIONS</dl></details>
<script>document.getElementById('search').addEventListener('input',function(){const q=this.value.toLowerCase();document.querySelectorAll('details').forEach(d=>{const rows=d.querySelectorAll('tbody tr');let matches=0;rows.forEach(r=>{const ok=!q||r.textContent.toLowerCase().includes(q);r.hidden=!ok;if(ok)matches++});const title=d.querySelector('summary').textContent.toLowerCase().includes(q);d.hidden=!!q&&!title&&!matches;if(q&&!d.hidden)d.open=true;if(title)rows.forEach(r=>r.hidden=false)})});</script></body></html>"""
    path.write_text(document.replace("STATUS", escape(status)).replace("SECTIONS", "\n".join(sections))
                    .replace("DEFINITIONS", definitions), encoding="utf-8")


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_paper_exports(stage, metrics, analysis, *, control=None):
    """Write manuscript exports from computed values; return their staged paths."""
    stage = Path(stage)
    target = stage / "paper"
    target.mkdir()
    research = analysis.get("research", {})
    tables = {}

    def add(name, title, description, rows):
        if control:
            control()
        tables[name] = {"title": title, "description": description,
                       **_write_csv(target / f"{name}.csv", rows, control=control)}

    add("condition_scores", "Configuration scores and counts",
        "One row per dataset/model/run-seed/protocol/parser/condition, with its matched cluster intervals. No aggregation across configurations.",
        lambda: _score_rows(metrics, analysis.get("condition_intervals", [])))
    specs = (
        ("condition_intervals", "Configuration intervals", "Cluster percentile intervals conditional on one run seed and observed cohort."),
        ("seed_summaries", "Across-seed variation", "Mean, sample SD, and range across matched run seeds. These are descriptive summaries, not pooled scores or confidence intervals."),
        ("component_and_voting_contrasts", "Component and voting comparisons", "Candidate minus reference on paired samples. The comparison field identifies direction; budget equality is recorded separately."),
        ("protocol_contrasts", "Verdict-order comparisons", "Verdict-last minus verdict-first on paired samples."),
        ("inference_performance", "Execution counters", "Session execution counters are separate from decision costs and shared response reuse."),
    )
    for key, title, description in specs:
        add(key, title, description, lambda key=key: iter(analysis.get(key, [])))
    add("wording_spread", "Task-wording spread", "Population SD and range across the selected task wordings within each family.",
        lambda: (row for row in analysis.get("template_summaries", []) if "metric" in row))
    add("wording_comparisons", "Task-wording comparisons", "Each candidate wording minus its family's reference wording on paired samples.",
        lambda: (row for row in analysis.get("template_summaries", []) if "metric" not in row))
    add("rankings", "Ranks across task wordings", "Ties share a rank. Changed ranking compares the complete family ranking with the reference wording.",
        lambda: _rank_rows(analysis.get("rankings", [])))
    for key, title, description in (
        ("selective_predictions", "Answered-only accuracy and risk", "One observed risk-coverage point per configuration. No confidence threshold curve is inferred."),
        ("prevalence_summaries", "Prevalence subset summaries", "Means and variation across repeated matched subsets; draw quantiles are not confidence intervals."),
        ("parser_comparisons", "Parser comparisons", "Only samples with verified shared response pools support parser comparisons."),
        ("output_summaries", "Response length and parser summaries", "Saved call coverage includes error records. The visible-response mean uses replies with text. Each row counts calls under its own parser and decision rule."),
        ("dataset_summaries", "Dataset composition", "Source samples are deduplicated across prediction configurations; missing metadata remains unavailable."),
        ("dataset_overlap", "Cross-dataset overlap", "Exact code hashes and supplied identifiers only. No near-duplicate detection or row removal."),
        ("cwe_breakdowns", "CWE scores", "Per-configuration scores using available CWE metadata. A sample can belong to multiple CWEs."),
        ("language_breakdowns", "Scores by code language", "Offline per-configuration scores and counts for each recorded language. No averaging across languages."),
        ("unavailable", "Unavailable dataset analyses", "Missing identifiers prevent these analyses; missing values are not zero overlap."),
        ("review_cases", "Author-review case identifiers", "Bounded flagged-case sample. Raw responses and completed human-review fields are excluded."),
    ):
        add(key, title, description, lambda key=key: iter(research.get(key, [])))
    detail = stage / "prevalence_draws.jsonl"
    add("prevalence_draws", "Individual prevalence draws", "Exact draw counts, scores, subset hashes, and conditional cluster intervals. Streamed without loading the complete draw table.",
        (lambda: _jsonl_rows(detail)) if detail.exists() else lambda: iter(research.get("prevalence_draws", [])))
    manifest = safe_settings({
        "schema_version": SCHEMA_VERSION, "created_at": analysis.get("analysis_provenance", {}).get("created_at"),
        "pilot": bool(analysis.get("pilot")), "run_status": analysis.get("run_status"),
        "artifact_kind": analysis.get("artifact_kind"), "input_artifacts": analysis.get("input_artifacts", []),
        "analysis_settings": analysis.get("analysis_settings", {}),
        "provenance": analysis.get("analysis_provenance", {}), "definitions": _definitions(),
        "response_hash_scope": "Standard cache hashes cover queried response IDs and verified payload hashes, including missing responses. Unused cache entries are excluded. Study generations.jsonl is hashed as a file.",
        "grouping_keys": list(GROUP_FIELDS),
        "aggregation_rules": {
            "configuration_scores": "Copied from Python calculations; counts apply only to that row's configuration.",
            "cross_configuration": "No pooling or averaging across models, datasets, conditions, protocols, parsers, or seeds is performed by this exporter.",
            "seed_summaries": "Existing matched-seed arithmetic means and sample SDs are copied; mean F1 differs from pooled-count F1.",
            "wording_spread": "Range and population SD across selected wordings are copied; no universal prompt ranking is implied.",
            "prevalence": "Existing repeated-subset summaries are copied; draw variation and conditional cluster intervals remain separate.",
            "paired_differences": "Candidate minus reference as named by each comparison. No multiple-comparison correction is inferred.",
        },
        "serialization": {"numeric_precision": "CSV and JSON retain Python's round-trip float representation; HTML and LaTeX display four decimal places.",
            "missing_values": "Empty CSV cells represent unavailable or absent values, never an assumed zero; reason fields explain unavailable analyses when recorded.",
            "nested_columns": "Dictionary keys and zero-based list indices use dotted names. Two-element ci95/quantile95 arrays use lower/upper suffixes.",
            "spreadsheet_strings": "Text beginning with =, +, -, or @ after whitespace is prefixed with an apostrophe in CSV only. Numeric negative values remain numeric.",
            "preview": f"HTML includes at most {PREVIEW_ROWS} rows from each CSV. Search applies to that preview; full tables are in CSV."},
        "design_notes": {**analysis.get("design_notes", {}), **research.get("design_notes", {})},
        "tables": {name: {key: value for key, value in table.items() if key != "preview"} for name, table in tables.items()},
    })
    manifest["provenance"]["exporter_sha256"] = _hash_file(Path(__file__))
    _write_tex(target / "condition_scores.tex", metrics)
    _write_index(target / "index.html", manifest, tables)
    manifest["file_sha256"] = {path.name: _hash_file(path) for path in sorted(target.iterdir())}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"schema_version": SCHEMA_VERSION, "index": "paper/index.html", "manifest": "paper/manifest.json",
            "files": [f"paper/{path.name}" for path in sorted(target.iterdir())]}
