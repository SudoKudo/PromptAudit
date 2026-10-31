"""Check combined experiment plans, response reuse, and saved batch resume."""

import copy
import json
from pathlib import Path
from datetime import datetime
import tempfile
import unittest
from unittest.mock import patch

from core.batch_runner import BatchRunner
from core.inference import InferenceStateError
from models.base import BaseModel


SAMPLES = [
    {"id": 1, "code": "int first(void) { return 0; }", "label": "SAFE", "cve_id": "CVE-A", "language": "C"},
    {"id": 2, "code": "int second(void) { return 1; }", "label": "SAFE", "cve_id": "CVE-B", "language": "C"},
]


class BatchRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.calls = []
        self.events = []
        self.after_call = None
        self.fail_draws = False
        self.item = {"name": "fixture", "backend": "dummy"}
        self.generation = {"seed": 42, "temperature": 0.2, "max_new_tokens": 128, "sc_samples": 5}
        self.cfg = {"generation": self.generation,
                    "performance": {"response_cache": False, "prevent_system_sleep": False},
                    "output": {"run_root": str(self.root)}}

    def tearDown(self):
        self.temp.cleanup()

    def loader(self, item, settings):
        owner = self

        class Fixture(BaseModel):
            def get_model_info(self):
                return {"cache_identity": "fixture-weights"}

            def generate(self, prompt):
                owner.calls.append((prompt, self.gen_cfg["seed"]))
                try:
                    if owner.fail_draws:
                        raise ValueError("fixture failure")
                    self._set_generation_info({"status": "ok", "prompt_eval_count": 10,
                                               "eval_count": 1, "done_reason": "stop"})
                    return "SAFE"
                finally:
                    if owner.after_call:
                        owner.after_call()

        return Fixture(item["name"], settings)

    def runner(self, **kwargs):
        return BatchRunner(self.cfg, progress=lambda _: None, overall_progress=self.events.append,
                           dataset_loader=kwargs.pop("dataset_loader", lambda _: copy.deepcopy(SAMPLES)),
                           model_loader=kwargs.pop("model_loader", self.loader), **kwargs)

    def study(self, section):
        return {"type": section, "pilot": True, "limit": 1, "bootstrap": 0, "config": {
            "section": section, "models": [self.item], "datasets": ["fixture"],
            "protocols": ["verdict_first", "verdict_last"], "parser_modes": ["strict", "full"],
            "seeds": [42], "generation": self.generation, "votes": 5,
            "performance": {"response_cache": False}}}

    def standard(self):
        return {"type": "standard", "models": [self.item], "datasets": ["fixture"],
                "prompts": ["zero_shot", "few_shot", "cot", "adaptive_cot", "self_consistency", "self_verification"],
                "protocols": ["verdict_first", "verdict_last"], "parsers": ["strict", "full"],
                "pilot": True, "limit": 1}

    def test_all_types_reuse_matching_pools_and_keep_all_reports(self):
        runner = self.runner()
        self.assertEqual(runner.run_batch([self.standard(), self.study("B"), self.study("C")]), "completed")
        self.assertEqual(len(self.calls), 98)
        manifest = json.loads((Path(runner.output_dir) / "batch_manifest.json").read_text())
        self.assertEqual([entry["status"] for entry in manifest["jobs"]], ["completed"] * 3)
        self.assertNotIn("last_failure", manifest)
        self.assertTrue(all("last_failure" not in entry for entry in manifest["jobs"]))
        self.assertEqual(manifest["work_estimate"]["generation_requests_before_cross_job_reuse"],
                         sum(entry["generation_units"] for entry in manifest["jobs"]))
        standard_checkpoint = json.loads(Path(manifest["jobs"][0]["checkpoint"]).read_text())
        self.assertTrue(standard_checkpoint["pilot"])
        standard_records = Path(standard_checkpoint["records_jsonl_path"]).read_text().splitlines()
        self.assertTrue(all(json.loads(line)["pilot"] for line in standard_records))
        for entry in manifest["jobs"]:
            self.assertTrue(Path(entry["report"]).exists())
        component = json.loads(Path(manifest["jobs"][2]["checkpoint"]).read_text())
        self.assertEqual(component["inference_performance"][0]["generated_calls"], 16)
        self.assertEqual(component["inference_performance"][0]["batch_cache_hits"], 12)
        percentages = [event["percent"] for event in self.events]
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(percentages[-1], 100)
        self.assertTrue(all(value < 100 for value in percentages[:-1]))
        self.assertTrue(Path(runner.report_html_path).exists())
        self.assertIsNone(BatchRunner.find_latest_resumable_checkpoint(self.cfg))

    def test_stop_resume_retains_failed_draws_and_does_not_repeat_work(self):
        first, second = self.study("B"), self.study("C")
        for job in (first, second):
            job["config"].update(protocols=["verdict_first"], parser_modes=["strict"])
        first["config"].update(families=["adaptive_cot", "self_consistency"], variants=["reference"])
        second["config"].update(components=[], voting_bases=["adaptive_cot"])
        runner = self.runner()
        self.fail_draws = True
        self.after_call = lambda: runner.request_stop() if len(self.calls) == 2 else None
        self.assertEqual(runner.run_batch([first, second]), "stopped")
        self.assertEqual(len(self.calls), 2)
        saved = BatchRunner.find_latest_resumable_checkpoint(self.cfg)
        self.assertNotIn("last_failure", json.loads(Path(saved).read_text()))
        before = self.events[-1]["percent"]
        self.events.clear()
        self.fail_draws = False
        self.after_call = None
        resumed = self.runner()
        self.assertEqual(resumed.run_batch([], resume_manifest=saved), "completed")
        self.assertEqual(len(self.calls), 5)
        manifest = json.loads(Path(saved).read_text())
        study_manifest = json.loads(Path(manifest["jobs"][1]["checkpoint"]).read_text())
        self.assertEqual(study_manifest["inference_performance"][0]["batch_cache_hits"], 5)
        predictions = [json.loads(line) for line in (Path(manifest["jobs"][1]["report"]).parent / "predictions.jsonl").read_text().splitlines()]
        self.assertEqual([row["pred"] for row in predictions], ["unknown", "safe", "safe"])
        self.assertGreaterEqual(self.events[0]["percent"], before)
        self.assertEqual(self.events[-1]["percent"], 100)

    def test_deferred_analysis_resumes_without_loading_models(self):
        job = self.study("B")
        job["config"].update(families=["zero_shot"], variants=["reference"])
        job["config"]["performance"]["defer_analysis"] = True
        runner = self.runner()
        self.assertEqual(runner.run_batch([job]), "generated")
        self.assertLess(self.events[-1]["percent"], 100)
        saved = BatchRunner.find_latest_resumable_checkpoint(self.cfg)
        calls = len(self.calls)
        # Analysis needs the saved predictions, not the original dataset or response cache.
        (Path(saved).parent / "responses.sqlite3").unlink()
        resumed = self.runner(model_loader=lambda *_: self.fail("Analysis must not load models"),
                              dataset_loader=lambda *_: self.fail("Analysis must not reload datasets"))
        self.assertEqual(resumed.run_batch([], resume_manifest=saved), "completed")
        self.assertEqual(len(self.calls), calls)

    def test_planning_counts_actual_rows_and_applies_pilot_limit_to_standard(self):
        job = self.standard()
        plan = self.runner()._plan([job])[0]
        self.assertEqual(plan["cohorts"][0]["samples"], 1)
        self.assertEqual(plan["generation_units"], 18)
        self.assertAlmostEqual(plan["prediction_units"], 1.2)
        job.pop("limit")
        plan = self.runner()._plan([job])[0]
        self.assertEqual(plan["generation_units"], 36)
        self.assertAlmostEqual(plan["prediction_units"], 2.4)

    def test_stop_during_analysis_keeps_generation_complete_for_resume(self):
        job = self.study("B")
        job["config"].update(families=["zero_shot"], variants=["reference"])
        runner = None
        def progress(message):
            if message == "Analyzing saved predictions...":
                runner.request_stop()
        runner = BatchRunner(self.cfg, progress=progress, overall_progress=self.events.append,
                             dataset_loader=lambda _: copy.deepcopy(SAMPLES), model_loader=self.loader)
        self.assertEqual(runner.run_batch([job]), "stopped")
        saved = Path(BatchRunner.find_latest_resumable_checkpoint(self.cfg))
        self.assertEqual(json.loads(saved.read_text())["jobs"][0]["status"], "generated")
        calls = len(self.calls)
        (saved.parent / "responses.sqlite3").unlink()
        resumed = self.runner(dataset_loader=lambda *_: self.fail("Analysis must not read datasets"),
                              model_loader=lambda *_: self.fail("Analysis must not load models"))
        self.assertEqual(resumed.run_batch([], resume_manifest=saved), "completed")
        self.assertEqual(len(self.calls), calls)

    def test_planning_reads_each_dataset_and_limit_once_without_retaining_samples(self):
        reads = []
        def loader(name):
            reads.append(name)
            return copy.deepcopy(SAMPLES)
        plans = self.runner(dataset_loader=loader)._plan([self.standard(), self.study("B"), self.study("C")])
        self.assertEqual(reads, ["fixture"])
        self.assertTrue(all(entry["cohorts"][0]["samples"] == 1 for entry in plans))
        self.assertTrue(all("code" not in str(entry["cohorts"]) for entry in plans))

    def test_dataset_failure_is_explicit_before_output_or_generation(self):
        def broken(_):
            raise OSError("fixture unavailable")
        runner = self.runner(dataset_loader=broken)
        with self.assertRaises(OSError):
            runner.run_batch([self.standard()])
        self.assertIsNone(runner.output_dir)
        self.assertFalse(self.calls)
        self.assertFalse(any(event["percent"] == 100 for event in self.events))

    def test_changed_dataset_cannot_be_reported_as_completed(self):
        reads = 0
        def changed(_):
            nonlocal reads
            reads += 1
            return copy.deepcopy(SAMPLES if reads == 1 else [{**SAMPLES[0], "code": "changed code"}])
        runner = self.runner(dataset_loader=changed)
        with self.assertRaisesRegex(InferenceStateError, "changed"):
            runner.run_batch([self.standard()])
        self.assertEqual(runner.final_status, "failed")
        self.assertFalse(self.calls)
        self.assertLess(self.events[-1]["percent"], 100)

    def test_missing_batch_cache_refuses_resume_without_overwriting_saved_manifest(self):
        job = self.study("B")
        job["config"].update(families=["zero_shot"], variants=["reference"])
        runner = self.runner()
        self.after_call = runner.request_stop
        self.assertEqual(runner.run_batch([job]), "stopped")
        saved = Path(BatchRunner.find_latest_resumable_checkpoint(self.cfg))
        before = saved.read_bytes()
        (saved.parent / "responses.sqlite3").unlink()
        self.after_call = None
        with self.assertRaisesRegex(InferenceStateError, "response cache is missing"):
            self.runner().run_batch([], resume_manifest=saved)
        self.assertEqual(saved.read_bytes(), before)

    def test_failure_metadata_is_private_and_preserves_analysis_resume(self):
        job = self.study("B")
        job["config"].update(families=["zero_shot"], variants=["reference"],
                             protocols=["verdict_first"], parser_modes=["strict"])
        private = r"Private Person C:\Private\University\secret.txt token=private-fixture"

        def fail_analysis(*_args, **_kwargs):
            raise RuntimeError(private)

        runner = self.runner()
        with patch("evaluation.template_analysis.analyze_study", side_effect=fail_analysis):
            with self.assertRaisesRegex(RuntimeError, "Private Person"):
                runner.run_batch([job])
        saved = Path(runner.output_dir) / "batch_manifest.json"
        text = saved.read_text(encoding="utf-8")
        manifest = json.loads(text)
        failure = manifest["last_failure"]
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["jobs"][0]["status"], "generated")
        self.assertEqual(manifest["jobs"][0]["last_failure"], failure)
        self.assertEqual(failure["exception_type"], "RuntimeError")
        self.assertEqual((failure["job_index"], failure["job_type"], failure["job_status"]), (0, "B", "generated"))
        self.assertEqual(failure["source"]["file"], "tests/test_batch_runner.py")
        self.assertEqual(failure["source"]["function"], "fail_analysis")
        self.assertGreater(failure["source"]["line"], 0)
        self.assertIsNotNone(datetime.fromisoformat(failure["timestamp"]).tzinfo)
        self.assertNotIn("Private Person", text)
        self.assertNotIn("private-fixture", text)
        self.assertNotIn(r"C:\Private", text)
        self.assertFalse(Path(failure["source"]["file"]).is_absolute())

        calls = len(self.calls)
        resumed = self.runner(model_loader=lambda *_: self.fail("Analysis must not load models"),
                              dataset_loader=lambda *_: self.fail("Analysis must not reload datasets"))
        self.assertEqual(resumed.run_batch([], resume_manifest=saved), "completed")
        self.assertEqual(len(self.calls), calls)


if __name__ == "__main__":
    unittest.main()
