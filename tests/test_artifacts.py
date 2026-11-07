"""Saved run artifacts and offline analysis commands."""

import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from evaluation.artifacts import ArtifactReader
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
    def test_standard_analysis_rejects_missing_conditions_and_samples(self):
        from core.runner import _model_identity

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "standard"
            standard_fixture(output, 42)
            records = output / "records.jsonl"
            checkpoint = output / "checkpoint.json"
            model = {"name": "fixture", "backend": "dummy"}
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            saved.update(selected_datasets=["fixture"], selected_models=[model],
                         selected_prompts=["zero_shot"], selected_output_protocols=["verdict_last"],
                         selected_parser_modes=["strict", "full"],
                         dataset_inventory={"fixture": {"selected_samples": 2}})
            checkpoint.write_text(json.dumps(saved), encoding="utf-8")
            record = json.loads(records.read_text(encoding="utf-8"))
            record.update(artifact_schema_version=2, model_id=_model_identity(model))
            other = {**record, "parser_mode": "full"}
            records.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing one or more selected conditions"):
                ArtifactReader(output)
            records.write_text("\n".join(map(json.dumps, (record, {**other, "predictions": other["predictions"][:1]}))),
                               encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "prediction count"):
                ArtifactReader(output)
            records.write_text("\n".join(map(json.dumps, (record, other))), encoding="utf-8")
            with ArtifactReader(output):
                pass

    def test_reanalysis_preserves_private_review_notes(self):
        from evaluation.template_analysis import analyze_artifacts

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "standard"
            standard_fixture(output, 42)
            records = output / "records.jsonl"
            record = json.loads(records.read_text(encoding="utf-8"))
            record["predictions"][0]["pred"] = "unknown"
            records.write_text(json.dumps(record) + "\n", encoding="utf-8")
            analyze_artifacts(output, 0, options={"output_audit": True})
            worksheet = output / "review_cases.csv"
            with worksheet.open(encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                fields, rows = reader.fieldnames, list(reader)
            rows[0]["review_notes"] = "private author note"
            with worksheet.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            for enabled, status in ((True, "current"), (False, "previous")):
                analyze_artifacts(output, 0, options={"output_audit": enabled})
                with worksheet.open(encoding="utf-8", newline="") as stream:
                    retained = next(csv.DictReader(stream))
                self.assertEqual(retained["review_notes"], "private author note")
                self.assertEqual(retained["candidate_status"], status)
                for name in ("analysis.json", "analysis_report.html", "paper/review_cases.csv"):
                    self.assertNotIn("private author note", (output / name).read_text(encoding="utf-8"))

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


def write_study(path, *, samples=2, seed=42, pilot=True):
    path.mkdir(exist_ok=True)
    manifest = {"status": "completed", "pilot": pilot, "config": {"models": [{"name": "fixture"}],
        "generation": {"temperature": 0.2}, "analysis": {"prevalence": False}},
        "resolved_models": {"fixture-id": {"digest": "fixture-weights"}},
        "inference_namespaces": {"fixture-id": "fixture-runtime"}}
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with (path / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for sample in range(samples):
            row = {"dataset": "fixture", "model_id": "fixture-id", "model": "fixture", "run_seed": seed,
                "protocol": "verdict_last", "parser_mode": "strict", "condition": "cot/reference/verdict_last",
                "comparison": "templates", "family": "cot", "variant": "reference",
                "sample_uid": f"sample-{sample}", "sample_id": str(sample), "code_sha256": f"code-{sample}",
                "cve_id": f"CVE-{sample}", "gold": "safe", "pred": "safe",
                "aggregation": {"policy": "first"}, "generation_ids": [f"call-{sample}"],
                "decision_calls": 1, "decision_seconds": 0.1}
            stream.write(json.dumps(row) + "\n")


class ArtifactReaderTests(unittest.TestCase):
    def test_prediction_sequences_decode_only_requested_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_study(output, samples=500)
            with ArtifactReader(output) as reader:
                key = next(iter(reader.groups))
                rows = reader.groups[key]["cot/reference/verdict_last"]
                self.assertNotIsInstance(rows, list)
                with patch("evaluation.artifacts.json.loads", wraps=json.loads) as decode:
                    self.assertEqual(len(rows), 500)
                    self.assertEqual(decode.call_count, 0)
                    self.assertEqual(rows[250]["sample_uid"], "sample-250")
                    self.assertEqual(decode.call_count, 1)
                    self.assertEqual(next(iter(rows))["sample_uid"], "sample-0")
                    self.assertEqual(decode.call_count, 2)
                index = Path(reader._temporary.name)
                self.assertTrue(index.exists())
            self.assertFalse(index.exists())

    def test_standard_records_use_saved_keys_without_exposing_raw_text(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            (output / "checkpoint.json").write_text(json.dumps({"status": "generated", "analysis": {}}))
            record = {"dataset": "fixture", "model": "fixture", "model_id": "fixture-id",
                "model_info": {"digest": "fixed"}, "inference_namespace": "fixture-namespace",
                "prompt": "cot", "run_id": "run",
                "params": {"seed": 43}, "predictions": [{"id": 1, "gold": "safe", "pred": "unknown",
                    "sample_uid": "stable", "code_sha256": "code", "generation_ids": ["response-key"]}]}
            (output / "records.jsonl").write_text(json.dumps(record) + "\n")
            payload = json.dumps({"raw_output": "private-response-fixture", "generation_info": {}})
            connection = sqlite3.connect(output / "generation_cache.sqlite3")
            connection.execute("CREATE TABLE responses (key TEXT, payload TEXT, checksum TEXT)")
            connection.execute("INSERT INTO responses VALUES (?,?,?)", ("response-key", payload,
                hashlib.sha256(payload.encode()).hexdigest()))
            connection.commit()
            connection.close()
            with ArtifactReader(output) as reader:
                rows = next(iter(reader.groups.values()))
                row = next(iter(rows.values()))[0]
                self.assertEqual(reader.kind, "standard")
                self.assertEqual(row["run_seed"], 43)
                self.assertTrue(row["traceability_available"])
                self.assertTrue(row["analysis_identity_available"])
                self.assertNotIn("raw_output", row)
                self.assertEqual(reader.get_generation("response-key")["raw_output"], "private-response-fixture")
                self.assertIsNone(reader.get_generation("missing"))

    def test_generation_lookup_uses_offsets_and_detects_conflicting_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "first", Path(folder) / "second"
            for seed, (path, text) in enumerate(((first, "SAFE"), (second, "VULNERABLE")), start=42):
                write_study(path, seed=seed)
                (path / "generations.jsonl").write_text(json.dumps({"generation_id": "call", "raw_output": text}) + "\n")
            with ArtifactReader([first, second]) as reader:
                with self.assertRaisesRegex(ValueError, "Different saved responses"):
                    reader.get_generation("call")

    def test_disjoint_cohorts_with_the_same_configuration_and_seed_are_not_pooled(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "first", Path(folder) / "second"
            write_study(first)
            write_study(second)
            rows = [json.loads(line) for line in (second / "predictions.jsonl").read_text().splitlines()]
            for row in rows:
                row["sample_uid"] = "other-" + row["sample_uid"]
            (second / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "same configuration and run seed"):
                ArtifactReader([first, second])

    def test_inputs_changed_during_analysis_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_study(output)
            with ArtifactReader(output) as reader:
                with (output / "predictions.jsonl").open("a") as stream:
                    stream.write("\n")
                with self.assertRaisesRegex(ValueError, "changed during analysis"):
                    reader.check_inputs()

    def test_mixed_pilot_and_full_runs_cannot_be_published_together(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "first", Path(folder) / "second"
            write_study(first, seed=42, pilot=False)
            write_study(second, seed=43, pilot=True)
            with self.assertRaisesRegex(ValueError, "Pilot and full runs"):
                ArtifactReader([first, second])
            with ArtifactReader(second) as reader:
                self.assertTrue(reader.artifact_summary()[0]["pilot"])

    def test_standard_response_provenance_tracks_only_queried_content(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run"
            standard_fixture(output, 42)
            cache = output / "generation_cache.sqlite3"
            connection = sqlite3.connect(cache)
            connection.execute("CREATE TABLE responses (key TEXT PRIMARY KEY, payload TEXT, checksum TEXT)")
            for key in ("first", "second", "unused"):
                payload = json.dumps({"raw_output": key, "generation_info": {}})
                connection.execute("INSERT INTO responses VALUES (?,?,?)",
                    (key, payload, hashlib.sha256(payload.encode()).hexdigest()))
            connection.commit()
            connection.close()
            name = "generation_cache.sqlite3/queried_responses"
            with ArtifactReader(output) as reader:
                reader.get_generation("first")
                reader.get_generation("second")
                original = reader.input_hashes[name]
                reader.check_inputs()
            with ArtifactReader(output) as reader:
                reader.get_generation("second")
                reader.get_generation("first")
                self.assertEqual(reader.input_hashes[name], original)
            connection = sqlite3.connect(cache)
            connection.execute("DELETE FROM responses WHERE key='unused'")
            connection.commit()
            connection.close()
            with ArtifactReader(output) as reader:
                reader.get_generation("first")
                reader.get_generation("second")
                self.assertEqual(reader.input_hashes[name], original)
                reader.get_generation("missing")
                self.assertNotEqual(reader.input_hashes[name], original)

    def test_standard_response_snapshot_rejects_concurrent_wal_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run"
            standard_fixture(output, 42)
            connection = sqlite3.connect(output / "generation_cache.sqlite3")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE responses (key TEXT PRIMARY KEY, payload TEXT, checksum TEXT)")
            def write_response(text):
                payload = json.dumps({"raw_output": text, "generation_info": {}})
                connection.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?)",
                    ("first", payload, hashlib.sha256(payload.encode()).hexdigest()))
                connection.commit()
            write_response("SAFE")
            try:
                with ArtifactReader(output) as reader:
                    self.assertEqual(reader.get_generation("first")["raw_output"], "SAFE")
                    write_response("VULNERABLE")
                    self.assertEqual(reader.get_generation("first")["raw_output"], "SAFE")
                    with self.assertRaisesRegex(ValueError, "response cache changed during analysis"):
                        reader.check_inputs()
            finally:
                connection.close()

    def test_incomplete_standard_generation_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            (output / "checkpoint.json").write_text(json.dumps({"status": "running"}))
            (output / "records.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "completed Standard generation"):
                ArtifactReader(output)


if __name__ == "__main__":
    unittest.main()
