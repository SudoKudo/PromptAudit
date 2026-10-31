"""Exercise saved-run analysis and dataset auditing through the command line."""

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from run_revision_study import main


def standard_fixture(output, seed):
    output.mkdir()
    predictions = []
    for index, gold in enumerate(("safe", "vulnerable")):
        predictions.append({"id": index + 1, "sample_id": str(index), "sample_uid": f"sample-{index}",
            "code_sha256": hashlib.sha256(f"code-{index}".encode()).hexdigest(), "gold": gold,
            "pred": gold if seed == 42 else "safe", "cve_id": f"CVE-{index}", "language": "C",
            "decision_calls": 1, "decision_seconds": 0.1, "generation_ids": [],
            "decision_generation_ids": [], "pool_calls": 1})
    record = {"run_id": f"fixture-{seed}", "dataset": "fixture", "model": "fixture",
        "model_backend": "dummy", "model_id": "fixture-model", "model_info": {"digest": "fixture-weights"},
        "inference_namespace": "fixture-model-runtime-and-prompt-sources",
        "prompt": "zero_shot", "output_protocol": "verdict_last", "parser_mode": "strict",
        "run_seed": seed, "params": {"seed": seed, "temperature": 0.2}, "predictions": predictions}
    (output / "records.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    (output / "checkpoint.json").write_text(json.dumps({"status": "completed", "gen_cfg": {"seed": seed},
        "analysis": {"prevalence": False, "output_audit": False}}), encoding="utf-8")
    (output / "metrics.csv").write_text("original classification summary\n", encoding="utf-8")
    (output / "report.html").write_text("<html>original charts</html>", encoding="utf-8")


class AnalysisCliTests(unittest.TestCase):
    def test_standard_repeats_can_be_analyzed_without_inference_or_source_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "first", Path(folder) / "second"
            standard_fixture(first, 42)
            standard_fixture(second, 43)
            before = {(directory, name): (directory / name).read_bytes()
                      for directory in (first, second)
                      for name in ("records.jsonl", "checkpoint.json", "metrics.csv", "report.html")}
            with patch("core.runner.load_model", side_effect=AssertionError("Analysis must not load a model")):
                main(["analyze", str(first), str(second), "--bootstrap", "0", "--skip-prevalence",
                      "--skip-output-audit"])
            self.assertTrue((first / "analysis_report.html").exists())
            self.assertTrue((first / "analysis.json").exists())
            self.assertTrue((first / "paper" / "index.html").exists())
            self.assertIn('href="paper/index.html"', (first / "analysis_report.html").read_text(encoding="utf-8"))
            with (first / "analysis_metrics.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual({int(row["run_seed"]) for row in rows}, {42, 43})
            with (first / "paper" / "condition_scores.csv").open(newline="", encoding="utf-8") as stream:
                exported = list(csv.DictReader(stream))
            for original, paper in zip(rows, exported):
                for field, value in original.items():
                    self.assertEqual(value, paper[field])
            manifest = json.loads((first / "paper" / "manifest.json").read_text(encoding="utf-8"))
            for name, digest in manifest["file_sha256"].items():
                self.assertEqual(hashlib.sha256((first / "paper" / name).read_bytes()).hexdigest(), digest)
            with (first / "paper" / "language_breakdowns.csv").open(newline="", encoding="utf-8") as stream:
                language_rows = list(csv.DictReader(stream))
            self.assertEqual({int(row["run_seed"]) for row in language_rows}, {42, 43})
            self.assertTrue(all(row["language"] == "C" for row in language_rows))
            for (directory, name), contents in before.items():
                self.assertEqual((directory / name).read_bytes(), contents)

    def test_dataset_audit_reports_cross_dataset_label_conflicts_without_code_text(self):
        selections = {
            "left": [{"id": 1, "code": "int shared_code(void) { return 0; }", "label": "SAFE",
                      "cve_id": "CVE-shared", "project": "fixture-project"}],
            "right": [{"id": 9, "code": "int shared_code(void) { return 0; }", "label": "VULNERABLE",
                       "cve_id": "CVE-shared", "project": "fixture-project"}],
        }
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "audit.json"
            with patch("code_datasets.dataset_loader.load_dataset", side_effect=lambda name: selections[name]), \
                    patch("core.runner.load_model", side_effect=AssertionError("Audit must not load a model")):
                main(["audit-datasets", "left", "right", "--output", str(output)])
            text = output.read_text(encoding="utf-8")
            result = json.loads(text)
            overlap = result["dataset_overlap"][0]
            self.assertEqual(overlap["shared_exact_code_hashes"], 1)
            self.assertEqual(overlap["conflicting_label_code_hashes"], 1)
            self.assertEqual(overlap["shared_cves"], 1)
            self.assertNotIn("int shared_code", text)
            self.assertEqual(selections["left"][0]["label"], "SAFE")


if __name__ == "__main__":
    unittest.main()
