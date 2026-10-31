"""Check manuscript exports against the values supplied by offline analysis."""

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.paper_exports import PREVIEW_ROWS, write_paper_exports


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


class PaperExportTests(unittest.TestCase):
    def test_values_context_intervals_and_provenance_are_preserved(self):
        context = {"dataset": "fixture", "model_id": "weights-1", "model": "fixture model",
                   "run_seed": 42, "protocol": "verdict_last", "parser_mode": "strict", "condition": "zero/reference"}
        value = 1 / 3
        metrics = [{**context, "samples": 3, "answered_samples": 2, "TP": 1, "TN": 1, "FP": 0,
                    "FN": 0, "UnFN": 0, "Incorrect": 1, "Accuracy": value, "F1": 0.12345678901234567}]
        analysis = {"pilot": False, "run_status": "completed", "artifact_kind": "standard",
            "condition_intervals": [{**context, "ci95": {"Accuracy": [value, 0.9]}}],
            "seed_summaries": [{**{key: val for key, val in context.items() if key != "run_seed"},
                                "metric": "F1", "run_seeds": [42, 43], "mean": None,
                                "unavailable_reason": "Model identities differ"}],
            "research": {"dataset_overlap": [{"dataset_a": "a", "dataset_b": "b", "shared_projects": None}]},
            "analysis_provenance": {"created_at": "fixture-time", "source_hashes": {"metrics.py": "source-hash"},
                                    "input_hashes": {"records.jsonl": "input-hash"}}}
        with tempfile.TemporaryDirectory() as directory:
            result = write_paper_exports(directory, metrics, analysis)
            target = Path(directory) / "paper"
            scores = read_csv(target / "condition_scores.csv")
            self.assertEqual(len(scores), 1)
            self.assertEqual(float(scores[0]["Accuracy"]), value)
            self.assertEqual(scores[0]["F1"], repr(metrics[0]["F1"]))
            for key, val in context.items():
                self.assertEqual(scores[0][key], str(val))
            bounds = read_csv(target / "condition_intervals.csv")[0]
            self.assertEqual(float(bounds["ci95.Accuracy.lower"]), value)
            self.assertEqual(float(bounds["ci95.Accuracy.upper"]), 0.9)
            seed = read_csv(target / "seed_summaries.csv")[0]
            self.assertEqual(seed["run_seeds.0"], "42")
            self.assertEqual(seed["mean"], "")
            self.assertEqual(seed["unavailable_reason"], "Model identities differ")
            self.assertEqual(read_csv(target / "dataset_overlap.csv")[0]["shared_projects"], "")
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["provenance"]["input_hashes"]["records.jsonl"], "input-hash")
            self.assertEqual(manifest["provenance"]["source_hashes"]["metrics.py"], "source-hash")
            self.assertEqual(manifest["tables"]["condition_scores"]["rows"], 1)
            self.assertIn("mean F1 differs", manifest["aggregation_rules"]["seed_summaries"])
            for name, digest in manifest["file_sha256"].items():
                self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(set(result["files"]), {str(path.relative_to(directory)).replace("\\", "/") for path in target.iterdir()})

    def test_untrusted_text_is_escaped_and_raw_responses_are_excluded(self):
        metrics = [{"dataset": "=HYPERLINK(\"bad\")", "model": "<script>alert(1)</script>_&%",
                    "condition": "a{b}\\c", "run_seed": 42, "F1": 0.5, "delta": -0.5,
                    "raw_output": "PRIVATE RESPONSE", "thinking": "PRIVATE THINKING", "api_key": "PRIVATE KEY"}]
        analysis = {"pilot": True, "research": {"review_cases": [{"case_id": "case1", "review_notes": "PRIVATE REVIEW", "reasons": ["output_limit"]}]}}
        with tempfile.TemporaryDirectory() as directory:
            write_paper_exports(directory, metrics, analysis)
            target = Path(directory) / "paper"
            row = read_csv(target / "condition_scores.csv")[0]
            self.assertEqual(row["dataset"], "'=HYPERLINK(\"bad\")")
            self.assertEqual(row["delta"], "-0.5")
            html = (target / "index.html").read_text(encoding="utf-8")
            tex = (target / "condition_scores.tex").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertIn(r"\_\&\%", tex)
            self.assertIn(r"a\{b\}\textbackslash{}c", tex)
            self.assertIn("Pilot output", html)
            for path in target.iterdir():
                content = path.read_text(encoding="utf-8")
                self.assertNotIn("PRIVATE RESPONSE", content)
                self.assertNotIn("PRIVATE THINKING", content)
                self.assertNotIn("PRIVATE KEY", content)
                self.assertNotIn("PRIVATE REVIEW", content)

    def test_prevalence_detail_is_streamed_and_preview_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "prevalence_draws.jsonl"
            with source.open("w", encoding="utf-8") as stream:
                for draw in range(PREVIEW_ROWS + 9):
                    stream.write(json.dumps({"dataset": "fixture", "condition": "x", "draw": draw,
                        "F1": draw / 100, "cluster_intervals": {"ci95": {"F1": [0.1, 0.9]}}}) + "\n")
            original = Path.read_text

            def forbid_full_read(path, *args, **kwargs):
                if path == source:
                    raise AssertionError("Detail JSONL must be streamed")
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", forbid_full_read):
                write_paper_exports(directory, [], {"research": {"prevalence_draws": [{"draw": "wrong-inline-source"}]}})
            rows = read_csv(Path(directory) / "paper" / "prevalence_draws.csv")
            self.assertEqual(len(rows), PREVIEW_ROWS + 9)
            self.assertEqual(rows[-1]["draw"], str(PREVIEW_ROWS + 8))
            self.assertEqual(rows[0]["cluster_intervals.ci95.F1.lower"], "0.1")
            manifest = json.loads((Path(directory) / "paper" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["tables"]["prevalence_draws"]["rows"], PREVIEW_ROWS + 9)
            html = (Path(directory) / "paper" / "index.html").read_text(encoding="utf-8")
            self.assertIn(f"Preview: first {PREVIEW_ROWS} rows", html)
            self.assertNotIn("wrong-inline-source", html)

    def test_rank_rows_keep_their_variant_family_and_run_axes(self):
        analysis = {"rankings": [{"dataset": "a", "run_seed": 42, "metric": "F1",
            "ranks": {"reference": {"cot": 1, "zero_shot": 1}, "variant2": {"cot": 2, "zero_shot": 1}},
            "changed_from_reference": {"reference": False, "variant2": True}}]}
        with tempfile.TemporaryDirectory() as directory:
            write_paper_exports(directory, [], analysis)
            rows = read_csv(Path(directory) / "paper" / "rankings.csv")
            self.assertEqual(len(rows), 4)
            candidate = next(row for row in rows if row["variant"] == "variant2" and row["family"] == "cot")
            self.assertEqual(candidate["rank"], "2")
            self.assertEqual(candidate["run_seed"], "42")
            self.assertEqual(candidate["ranking_changed_from_reference"], "True")


if __name__ == "__main__":
    unittest.main()
