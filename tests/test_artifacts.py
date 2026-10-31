"""Check saved-run normalization and disk-backed prediction access."""

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from evaluation.artifacts import ArtifactReader


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
        from tests.test_analysis_cli import standard_fixture

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
        from tests.test_analysis_cli import standard_fixture

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
