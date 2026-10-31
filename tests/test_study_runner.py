"""Check dashboard study controls without loading a model or opening a window."""

import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

from core.revision_study import StudyRunner, build_conditions, run_study
from models.base import BaseModel


SAMPLES = [
    {"id": 1, "code": "int f(void) { return 0; }", "label": "SAFE", "cve_id": "CVE-A"},
    {"id": 2, "code": "void f(char *s) { gets(s); }", "label": "VULNERABLE", "cve_id": "CVE-B"},
]


def study_config(section="B"):
    return {
        "section": section, "models": [{"name": "fixture", "backend": "dummy"}],
        "datasets": ["fixture"], "families": ["adaptive_cot", "self_consistency"],
        "variants": ["reference"], "components": [], "voting_bases": ["cot"],
        "protocols": ["verdict_last"], "parser_modes": ["strict"], "seeds": [42],
        "votes": 5, "generation": {"temperature": 0.2, "max_new_tokens": 100},
    }


class StudyRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.calls = []
        self.after_call = None
        self.logs = []
        self.cfg = {"output": {"run_root": str(self.root)},
                    "performance": {"prevent_system_sleep": False}}

    def tearDown(self):
        self.temp.cleanup()

    def model_loader(self, item, settings):
        owner = self

        class FixtureModel(BaseModel):
            def generate(self, prompt):
                owner.calls.append((prompt, self.gen_cfg.copy()))
                self._set_generation_info({"prompt_eval_count": 10, "eval_count": 1,
                                           "done_reason": "stop"})
                if owner.after_call:
                    owner.after_call()
                return "SAFE"

        return FixtureModel(item["name"], settings)

    def runner(self, progress=None):
        return StudyRunner(self.cfg, progress=progress or self.logs.append,
                           dataset_loader=lambda _: copy.deepcopy(SAMPLES), model_loader=self.model_loader)

    def test_study_finishes_with_report_and_progress(self):
        runner = self.runner()
        self.assertEqual(runner.run_study(study_config(), pilot=True, bootstrap=0), "completed")
        self.assertEqual(len(self.calls), 10)
        self.assertTrue(Path(runner.report_html_path).exists())
        self.assertTrue(any("sample 2 / 2" in message for message in self.logs))
        manifest = json.loads((Path(runner.output_dir) / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "completed")
        self.assertIsNone(StudyRunner.find_latest_resumable_checkpoint(self.cfg))

    def test_stop_preserves_calls_and_saved_resume_reuses_them(self):
        runner = self.runner()
        self.after_call = runner.request_stop
        self.assertEqual(runner.run_study(study_config(), pilot=True, bootstrap=0), "stopped")
        self.assertEqual(len(self.calls), 1)
        saved = StudyRunner.find_latest_resumable_checkpoint(self.cfg)
        self.assertEqual(Path(saved).parent, Path(runner.output_dir))
        self.assertEqual(json.loads(Path(saved).read_text())["status"], "interrupted")
        self.after_call = None
        resumed = self.runner()
        self.assertEqual(resumed.run_study({}, resume_manifest=saved), "completed")
        self.assertEqual(len(self.calls), 10)
        manifest = json.loads(Path(saved).read_text())
        self.assertEqual(manifest["new_calls_this_session"], 9)
        self.assertEqual(manifest["config"]["bootstrap_resamples"], 0)

    def test_paused_study_waits_before_loading_then_resumes(self):
        paused = threading.Event()
        errors = []

        def progress(message):
            if "Run paused" in message:
                paused.set()

        runner = self.runner(progress)
        runner.request_pause()

        def work():
            try:
                runner.run_study(study_config(), pilot=True, bootstrap=0)
            except BaseException as exc:
                errors.append(exc)

        worker = threading.Thread(target=work)
        worker.start()
        try:
            self.assertTrue(paused.wait(3))
            self.assertEqual(self.calls, [])
            runner.request_resume()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(runner.final_status, "completed")
        finally:
            runner.request_stop()
            worker.join(5)

    def test_stop_during_analysis_resumes_without_model_calls(self):
        runner = self.runner()

        def progress(message):
            if message == "Analyzing saved predictions...":
                runner.request_stop()

        runner.progress = progress
        self.assertEqual(runner.run_study(study_config(), pilot=True, bootstrap=20), "stopped")
        self.assertEqual(len(self.calls), 10)
        self.assertFalse(Path(runner.report_html_path).exists())
        saved = StudyRunner.find_latest_resumable_checkpoint(self.cfg)
        self.assertEqual(json.loads(Path(saved).read_text())["status"], "completed")
        resumed = self.runner()
        self.assertEqual(resumed.run_study({}, resume_manifest=saved), "completed")
        self.assertEqual(len(self.calls), 10)
        self.assertTrue(Path(resumed.report_html_path).exists())

    def test_component_and_voting_selections_keep_pool_budgets_correct(self):
        cfg = study_config("C")
        cfg["voting_policies"] = ["first"]
        conditions = build_conditions(cfg)
        self.assertEqual(len(conditions), 1)
        self.assertEqual(conditions[0]["draws"], 1)
        cfg["generation"]["temperature"] = 0
        self.runner().run_study(cfg, pilot=True, bootstrap=0)
        self.assertEqual(len(self.calls), 2)

        self.calls.clear()
        cfg["generation"]["temperature"] = 0.2
        cfg["voting_policies"] = ["first", "majority_valid"]
        runner = self.runner()
        runner.run_study(cfg, pilot=True, bootstrap=0)
        self.assertEqual(len(self.calls), 10)
        rows = [json.loads(line) for line in (Path(runner.output_dir) / "predictions.jsonl").read_text().splitlines()]
        for sample in ("1", "2"):
            matched = [row for row in rows if row["sample_id"] == sample]
            self.assertEqual(matched[0]["generation_ids"], matched[1]["generation_ids"])
            self.assertEqual(sorted(row["decision_calls"] for row in matched), [1, 5])

    def test_invalid_study_options_fail_before_output_or_inference(self):
        cases = [
            {"analysis": {"rankings": "yes"}},
            {"analysis": {"unsupported": True}},
            {"progress_every_n_samples": 0},
            {"section": "C", "components": [], "voting_bases": []},
        ]
        for index, overrides in enumerate(cases):
            with self.subTest(overrides=overrides):
                cfg = study_config()
                cfg.update(overrides)
                output = self.root / str(index)
                with self.assertRaises(ValueError):
                    run_study(cfg, output, pilot=True, dataset_loader=lambda _: SAMPLES,
                              model_loader=self.model_loader, progress=lambda _: None)
                self.assertFalse(output.exists())
        self.assertFalse(self.calls)

    def test_legacy_metric_and_diagnostic_visibility_options_do_not_hide_results(self):
        cfg = study_config()
        cfg["metrics"] = {"include": ["unsupported"]}
        cfg["analysis"] = {"diagnostics": False}
        runner = self.runner()
        self.assertEqual(runner.run_study(cfg, pilot=True, bootstrap=0), "completed")
        manifest = json.loads((Path(runner.output_dir) / "manifest.json").read_text())
        self.assertNotIn("metrics", manifest["config"])
        self.assertNotIn("diagnostics", manifest["config"].get("analysis", {}))
        self.assertIn("EffectiveF1", Path(runner.report_html_path).read_text())


if __name__ == "__main__":
    unittest.main()
