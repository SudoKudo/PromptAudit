"""Check common cohort validation and durable prediction-to-response links."""

import copy
import csv
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from code_datasets._local_cve_dataset_loader import load_cvefixes_dataset
from code_datasets.validation import DatasetValidationError, sample_identity, validate_samples
from core.batch_runner import BatchRunner
from core.inference import InferenceEngine, ManagedModel, ResponseCache
from core.revision_study import run_study
from core.runner import ExperimentRunner
from evaluation.metrics import Metrics
from models.base import BaseModel


SAMPLES = [{"id": 71, "code": " int sample(void) { return 0; }\n", "label": "SAFE",
            "language": "C", "cve_id": "CVE-fixture", "file_number": 3, "filename": "sample.c"}]
ITEM = {"name": "fixture", "backend": "dummy"}


class ValidationTraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.calls = []
        self.output = "SAFE"
        self.fail_seed = None
        self.cfg = {"generation": {"seed": 42, "temperature": 0.2, "sc_samples": 5},
                    "performance": {"response_cache": False, "prevent_system_sleep": False},
                    "output": {"run_root": str(self.root)}}

    def tearDown(self):
        self.temp.cleanup()

    def loader(self, item, settings):
        owner = self

        class Fixture(BaseModel):
            def get_model_info(self):
                return {"backend": "dummy", "cache_identity": "validation-fixture"}

            def generate(self, prompt):
                owner.calls.append((prompt, self.gen_cfg["seed"]))
                if self.gen_cfg["seed"] == owner.fail_seed:
                    raise ValueError("fixture failure")
                self._set_generation_info({"status": "ok", "eval_count": 1, "prompt_eval_count": 10})
                return owner.output

        return Fixture(item["name"], settings)

    def runner(self, *, cfg=None, dataset_loader=None, model_loader=None):
        return ExperimentRunner(cfg or self.cfg, progress=lambda _: None,
            dataset_loader=dataset_loader or (lambda _: copy.deepcopy(SAMPLES)),
            model_loader=model_loader or self.loader)

    def test_standard_pilot_is_retained_in_results_and_paper_exports(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["pilot"] = True
        cfg["analysis"] = {"enabled": True, "bootstrap_resamples": 0,
                           "prevalence": False, "output_audit": False, "dataset_audit": False}
        runner = self.runner(cfg=cfg)
        self.assertEqual(runner.run_all(["fixture"], [ITEM], ["zero_shot"],
                                       ["verdict_first"], ["strict"]), "completed")
        output = Path(runner.output_dir)
        for filename in ("checkpoint.json", "analysis.json", "paper/manifest.json"):
            self.assertTrue(json.loads((output / filename).read_text())["pilot"], filename)
        self.assertTrue(runner.records[0]["pilot"])
        self.assertTrue(json.loads((output / "records.jsonl").read_text())["pilot"])
        with (output / "metrics.csv").open(newline="", encoding="utf-8") as stream:
            self.assertEqual(next(csv.DictReader(stream))["pilot"], "True")
        with (output / "paper/condition_scores.csv").open(newline="", encoding="utf-8") as stream:
            self.assertEqual(next(csv.DictReader(stream))["pilot"], "True")

    def test_analysis_resume_keeps_saved_pilot_and_legacy_default(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                cfg = copy.deepcopy(self.cfg)
                cfg["pilot"] = True
                cfg["analysis"] = {"enabled": True, "bootstrap_resamples": 0,
                                   "prevalence": False, "output_audit": False, "dataset_audit": False}
                cfg["performance"]["defer_analysis"] = True
                runner = self.runner(cfg=cfg)
                self.assertEqual(runner.run_all(["fixture"], [ITEM], ["zero_shot"],
                                               ["verdict_first"], ["strict"]), "generated")
                checkpoint = Path(runner.checkpoint_path)
                if legacy:
                    state = json.loads(checkpoint.read_text())
                    state.pop("pilot")
                    checkpoint.write_text(json.dumps(state), encoding="utf-8")
                    record_path = Path(runner.records_jsonl_path)
                    record = json.loads(record_path.read_text())
                    record.pop("pilot")
                    record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
                resumed_cfg = copy.deepcopy(cfg)
                resumed_cfg["pilot"] = legacy
                forbidden = Mock(side_effect=AssertionError("Analysis cannot reload inference inputs"))
                resumed = self.runner(cfg=resumed_cfg, dataset_loader=forbidden, model_loader=forbidden)
                self.assertEqual(resumed.run_all([], [], [], resume_checkpoint=checkpoint), "completed")
                forbidden.assert_not_called()
                expected = not legacy
                for filename in ("checkpoint.json", "analysis.json", "paper/manifest.json"):
                    self.assertEqual(json.loads((Path(runner.output_dir) / filename).read_text())["pilot"],
                                     expected, filename)

    def test_fresh_runs_in_the_same_second_keep_separate_artifacts(self):
        first = self.runner()
        second_cfg = copy.deepcopy(self.cfg)
        second_cfg["generation"]["seed"] = 43
        second = self.runner(cfg=second_cfg)
        with patch("core.runner.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 30, 12, 0, 0)
            first.run_all(["fixture"], [ITEM], ["zero_shot"], ["verdict_first"], ["strict"])
            original = Path(first.records_jsonl_path).read_bytes()
            second.run_all(["fixture"], [ITEM], ["zero_shot"], ["verdict_first"], ["strict"])
        self.assertNotEqual(first.output_dir, second.output_dir)
        self.assertEqual(Path(first.records_jsonl_path).read_bytes(), original)
        self.assertEqual(first.records[0]["run_seed"], 42)
        self.assertEqual(second.records[0]["run_seed"], 43)

    def test_validation_preserves_source_and_normalizes_legacy_pairs(self):
        original = copy.deepcopy(SAMPLES)
        original[0]["label"] = " safe "
        rows = validate_samples(original, "fixture")
        self.assertEqual(rows[0]["label"], "SAFE")
        self.assertEqual(original[0]["label"], " safe ")
        self.assertEqual(rows[0]["code"], SAMPLES[0]["code"])
        self.assertEqual(validate_samples([("code", "vulnerable")], "legacy"),
                         [{"id": 0, "code": "code", "label": "VULNERABLE", "language": "unknown"}])

    def test_invalid_samples_and_ambiguous_ids_are_rejected(self):
        bad = [{**SAMPLES[0], "label": value} for value in ("UNKNOWN", "", None, 1)]
        bad += [{**SAMPLES[0], "code": value} for value in ("", " \n", None, b"code")]
        bad += [{**SAMPLES[0], "id": value} for value in (None, " ", True, 1.5, [], {})]
        for sample in bad:
            with self.subTest(sample=sample), self.assertRaises(DatasetValidationError):
                validate_samples([sample], "fixture")
        for rows in ([], [SAMPLES[0], SAMPLES[0]],
                     [{**SAMPLES[0], "id": 1}, {**SAMPLES[0], "id": "1"}]):
            with self.subTest(rows=rows), self.assertRaises(DatasetValidationError):
                validate_samples(rows, "fixture")

    def test_sample_identity_matches_existing_study_hash(self):
        identity = sample_identity(SAMPLES[0], "fixture")
        expected = {"sample_id": "71", "gold": "safe", "cve_id": "CVE-fixture",
                    "file_number": 3, "filename": "sample.c", "language": "C",
                    "code_sha256": hashlib.sha256(SAMPLES[0]["code"].encode()).hexdigest()}
        digest = hashlib.sha256(json.dumps({"dataset": "fixture", **expected}, sort_keys=True,
                                         ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(identity, {**expected, "sample_uid": digest})

    def test_invalid_gold_never_changes_metric_counters(self):
        tracker = Metrics()
        tracker.add("safe", "safe")
        before = tracker.to_dict()
        for prediction in ("safe", "vulnerable", "unknown"):
            with self.assertRaises(ValueError):
                tracker.add("unknown", prediction)
            self.assertEqual(tracker.to_dict(), before)

    def test_standard_validates_every_selected_dataset_before_loading_a_model(self):
        invalid = [{**SAMPLES[0], "label": "UNKNOWN"}]
        factory = Mock(side_effect=AssertionError("No model should be loaded"))
        runner = self.runner(dataset_loader=lambda name: copy.deepcopy(SAMPLES if name == "good" else invalid),
                             model_loader=factory)
        with self.assertRaises(DatasetValidationError):
            runner.run_all(["good", "bad"], [ITEM], ["zero_shot"], ["verdict_first"], ["strict"])
        factory.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_invalid_analysis_settings_fail_before_loading_models(self):
        factory = Mock(side_effect=AssertionError("No model should be loaded"))
        for settings in ({"group_by": "sample"}, {"prevalence_repeats": 0}, {"bootstrap_resamples": True}):
            cfg = {**self.cfg, "analysis": settings}
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.runner(cfg=cfg, model_loader=factory)
            study = {"section": "B", "models": [ITEM], "datasets": ["fixture"],
                     "analysis": settings, "families": ["zero_shot"], "variants": ["reference"]}
            with self.subTest(study=settings), self.assertRaises(ValueError):
                run_study(study, self.root / "study", pilot=True,
                          dataset_loader=lambda _: copy.deepcopy(SAMPLES), model_loader=factory)
        factory.assert_not_called()

    def test_study_and_batch_reject_invalid_later_cohorts_before_inference(self):
        invalid = [{**SAMPLES[0], "code": ""}]
        cohorts = lambda name: copy.deepcopy(SAMPLES if name == "good" else invalid)
        factory = Mock(side_effect=AssertionError("No model should be loaded"))
        study = {"section": "B", "datasets": ["good", "bad"], "models": [ITEM],
                 "families": ["zero_shot"], "variants": ["reference"], "protocols": ["verdict_first"],
                 "parser_modes": ["strict"], "seeds": [42], "votes": 1,
                 "generation": {"temperature": 0.2}}
        with self.assertRaises(DatasetValidationError):
            run_study(study, self.root / "study", pilot=True, dataset_loader=cohorts,
                      model_loader=factory, progress=lambda _: None)
        job = {"type": "standard", "datasets": ["good", "bad"], "models": [ITEM],
               "prompts": ["zero_shot"], "protocols": ["verdict_first"], "parsers": ["strict"]}
        batch = BatchRunner(self.cfg, progress=lambda _: None, dataset_loader=cohorts, model_loader=factory)
        with self.assertRaises(DatasetValidationError):
            batch.run_batch([job])
        factory.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_standard_links_sc_draws_and_parser_replay_to_saved_responses(self):
        self.fail_seed = 43
        runner = self.runner()
        self.assertEqual(runner.run_all(["fixture"], [ITEM], ["adaptive_cot", "self_consistency"],
                                       ["verdict_first"], ["strict", "full"]), "completed")
        self.assertEqual(len(self.calls), 5)
        with closing(sqlite3.connect(Path(runner.output_dir) / "generation_cache.sqlite3")) as db:
            saved = {key: json.loads(payload) for key, payload in db.execute("SELECT key,payload FROM responses")}
        self.assertEqual(len(saved), 5)
        for record in runner.records:
            row = record["predictions"][0]
            self.assertEqual(row["sample_id"], "71")
            self.assertEqual(row["sample_uid"], sample_identity(SAMPLES[0], "fixture")["sample_uid"])
            self.assertEqual(row["code_sha256"], hashlib.sha256(SAMPLES[0]["code"].encode()).hexdigest())
            expected_draws = 5 if record["prompt"] == "self_consistency" else 1
            self.assertEqual(len(row["generation_ids"]), expected_draws)
            self.assertEqual(row["decision_generation_ids"], row["generation_ids"])
            self.assertTrue(set(row["generation_ids"]).issubset(saved))
            self.assertEqual([vote["generation_id"] for vote in row["parsed_votes"]], row["generation_ids"])
            if expected_draws == 5:
                self.assertEqual(row["pred"], "safe")
                self.assertEqual(sum(vote["label"] == "unknown" for vote in row["parsed_votes"]), 1)
            with Path(runner._prediction_csv_path(record)).open(newline="", encoding="utf-8") as stream:
                exported = next(csv.DictReader(stream))
            self.assertEqual(json.loads(exported["generation_ids"]), row["generation_ids"])
        pairs = [record["predictions"][0]["generation_ids"] for record in runner.records
                 if record["prompt"] == "self_consistency"]
        self.assertEqual(pairs[0], pairs[1])

    def test_prefetch_only_records_keys_when_a_sample_consumes_them(self):
        cache = ResponseCache(self.root / "cache.sqlite3")
        engine = InferenceEngine(self.loader(ITEM, {"seed": 42}), ITEM, self.loader,
            performance={"response_cache": False}, run_cache=cache)
        managed = ManagedModel(engine)
        try:
            managed.prefetch([("first", {"seed": 42}), ("second", {"seed": 43})])
            self.assertEqual(managed.consume_request_trace(), [])
            managed.begin_sample_trace()
            managed.generate("first")
            self.assertEqual(managed.consume_request_trace(), [engine.key("first", {"seed": 42})])
            self.assertEqual(len(self.calls), 2)
        finally:
            engine.close()
            cache.close()

    def test_study_keeps_per_draw_parser_details_and_decision_pool_links(self):
        self.output = "Assessment: the code is safe."
        cfg = {"section": "C", "datasets": ["fixture"], "models": [ITEM], "components": [],
               "voting_bases": ["cot"], "voting_policies": ["first", "majority_requested"],
               "protocols": ["verdict_first"], "parser_modes": ["strict", "full"], "seeds": [42],
               "votes": 5, "generation": {"temperature": 0.2}}
        output = self.root / "study"
        run_study(cfg, output, pilot=True, dataset_loader=lambda _: copy.deepcopy(SAMPLES),
                  model_loader=self.loader, progress=lambda _: None)
        predictions = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
        calls = {row["generation_id"] for row in
                 (json.loads(line) for line in (output / "generations.jsonl").read_text().splitlines())}
        self.assertEqual(len(calls), 5)
        for row in predictions:
            self.assertEqual(len(row["parsed_votes"]), 5)
            self.assertEqual(set(row["generation_ids"]), calls)
            expected = row["generation_ids"][:1] if row["aggregation"]["policy"] == "first" else row["generation_ids"]
            self.assertEqual(row["decision_generation_ids"], expected)
            self.assertEqual({vote["label"] for vote in row["parsed_votes"]},
                             {"unknown"} if row["parser_mode"] == "strict" else {"safe"})
            self.assertEqual({vote["tier"] for vote in row["parsed_votes"]},
                             {None} if row["parser_mode"] == "strict" else {"lexical_fallback"})

    def test_directory_inventory_explains_exclusions_without_adding_nested_rows(self):
        folder = self.root / "source" / "CVE-fixture"
        folder.mkdir(parents=True)
        (folder / "README.txt").write_text("  1. good.c\n  2. unknown.zz\n  3. empty.c\n  4. missing.c\n")
        for number in (1, 2, 3, 4):
            (folder / f"{number:02}_before_file.txt").write_text("" if number == 3 else "code")
            if number != 4:
                (folder / f"{number:02}_after_file.txt").write_text("" if number == 3 else "code")
        (folder / "05_after_orphan.txt").write_text("code")
        nested = folder / "CVE-nested"
        nested.mkdir()
        (nested / "01_before_nested.c.txt").write_text("ignored")
        rows, inventory = load_cvefixes_dataset(folder.parent, return_inventory=True)
        self.assertEqual([row["label"] for row in rows], ["VULNERABLE", "SAFE", "VULNERABLE"])
        self.assertEqual(inventory["nested_cve_folders_ignored"], 1)
        self.assertEqual(inventory["missing_after_files"], 1)
        self.assertEqual(inventory["orphan_after_files"], 1)
        self.assertEqual(inventory["excluded_code_files"],
                         {"unsupported_language": 2, "empty_code": 2, "unreadable_code": 0})

    def test_batch_wrapper_retains_source_inventory_in_both_runners(self):
        folder = self.root / "source" / "CVE-fixture"
        folder.mkdir(parents=True)
        (folder / "README.txt").write_text("  1. good.c\n  2. skipped.zz\n")
        for number in (1, 2):
            for role in ("before", "after"):
                (folder / f"{number:02}_{role}_file.txt").write_text("code")
        selection = {"name": "fixture", "source": "local", "path": str(folder.parent)}
        standard = {"type": "standard", "datasets": [selection], "models": [ITEM],
                    "prompts": ["zero_shot"], "protocols": ["verdict_first"], "parsers": ["strict"]}
        study = {"type": "B", "pilot": True, "bootstrap": 0, "config": {
            "section": "B", "datasets": [selection], "models": [ITEM], "families": ["zero_shot"],
            "variants": ["reference"], "protocols": ["verdict_first"], "parser_modes": ["strict"],
            "seeds": [42], "generation": {"temperature": 0.2}}}
        runner = BatchRunner(self.cfg, progress=lambda _: None, model_loader=self.loader)
        self.assertEqual(runner.run_batch([standard, study]), "completed")
        manifest = json.loads((Path(runner.output_dir) / "batch_manifest.json").read_text())
        checkpoints = [json.loads(Path(job["checkpoint"]).read_text()) for job in manifest["jobs"]]
        inventories = [checkpoints[0]["dataset_inventory"]["fixture"], checkpoints[1]["cohorts"][0]["inventory"]]
        for inventory in inventories:
            self.assertEqual(inventory["format"], "cve_folders")
            self.assertEqual(inventory["loaded_samples"], 2)
            self.assertEqual(inventory["selected_samples"], 2)
            self.assertEqual(inventory["source_exclusions"]["unsupported_language"], 2)

    def test_deferred_standard_analysis_resumes_without_data_models_or_cache(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["analysis"] = {"enabled": True, "bootstrap_resamples": 0}
        cfg["performance"]["defer_analysis"] = True
        runner = self.runner(cfg=cfg)
        self.assertEqual(runner.run_all(["fixture"], [ITEM], ["zero_shot"],
                                       ["verdict_first"], ["strict"]), "generated")
        checkpoint = Path(runner.checkpoint_path)
        self.assertEqual(ExperimentRunner.find_latest_resumable_checkpoint(cfg), str(checkpoint))
        original = Path(runner.records_jsonl_path).read_bytes()
        (Path(runner.output_dir) / "generation_cache.sqlite3").unlink()
        forbidden = Mock(side_effect=AssertionError("Analysis cannot reload inference inputs"))
        resumed = self.runner(cfg=cfg, dataset_loader=forbidden, model_loader=forbidden)

        def analyze(output, bootstrap, **kwargs):
            self.assertEqual(bootstrap, 0)
            kwargs["control"]()
            (Path(output) / "analysis_report.html").write_text("<html>analysis</html>")

        with patch("evaluation.template_analysis.analyze_artifacts", side_effect=analyze, create=True) as analyzed:
            self.assertEqual(resumed.run_all([], [], [], resume_checkpoint=checkpoint), "completed")
        analyzed.assert_called_once()
        forbidden.assert_not_called()
        self.assertEqual(Path(runner.records_jsonl_path).read_bytes(), original)
        self.assertFalse((Path(runner.output_dir) / "generation_cache.sqlite3").exists())
        self.assertEqual(json.loads(checkpoint.read_text())["status"], "completed")

    def test_stopping_standard_analysis_keeps_generation_complete(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["analysis"] = {"enabled": True, "bootstrap_resamples": 0}
        runner = self.runner(cfg=cfg)

        def interrupted(output, bootstrap, **kwargs):
            runner.request_stop()
            kwargs["control"]()

        with patch("evaluation.template_analysis.analyze_artifacts", side_effect=interrupted, create=True):
            self.assertEqual(runner.run_all(["fixture"], [ITEM], ["zero_shot"],
                                           ["verdict_first"], ["strict"]), "stopped")
        self.assertEqual(json.loads(Path(runner.checkpoint_path).read_text())["status"], "generated")
        calls = len(self.calls)
        resumed = self.runner(cfg=cfg, dataset_loader=Mock(side_effect=AssertionError("No data reload")),
                              model_loader=Mock(side_effect=AssertionError("No model reload")))
        with patch("evaluation.template_analysis.analyze_artifacts", return_value={}, create=True):
            self.assertEqual(resumed.run_all([], [], [], resume_checkpoint=runner.checkpoint_path), "completed")
        self.assertEqual(len(self.calls), calls)

    def test_batch_resumes_deferred_standard_analysis_without_response_caches(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["analysis"] = {"enabled": True, "bootstrap_resamples": 0}
        cfg["performance"]["defer_analysis"] = True
        job = {"type": "standard", "datasets": ["fixture"], "models": [ITEM], "prompts": ["zero_shot"],
               "protocols": ["verdict_first"], "parsers": ["strict"], "pilot": True, "limit": 1}
        runner = BatchRunner(cfg, progress=lambda _: None, dataset_loader=lambda _: copy.deepcopy(SAMPLES),
                             model_loader=self.loader)
        self.assertEqual(runner.run_batch([job]), "generated")
        checkpoint = Path(runner.output_dir) / "batch_manifest.json"
        manifest = json.loads(checkpoint.read_text())
        (Path(runner.output_dir) / "responses.sqlite3").unlink()
        (Path(manifest["jobs"][0]["checkpoint"]).parent / "generation_cache.sqlite3").unlink()
        calls = len(self.calls)
        forbidden = Mock(side_effect=AssertionError("Analysis cannot reload inference inputs"))
        resumed = BatchRunner(cfg, progress=lambda _: None, dataset_loader=forbidden, model_loader=forbidden)
        with patch("evaluation.template_analysis.analyze_artifacts", return_value={}, create=True) as analyzed:
            self.assertEqual(resumed.run_batch([], resume_manifest=checkpoint), "completed")
        analyzed.assert_called_once()
        forbidden.assert_not_called()
        self.assertEqual(len(self.calls), calls)


if __name__ == "__main__":
    unittest.main()
