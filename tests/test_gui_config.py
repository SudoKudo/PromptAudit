"""Check dashboard selections and dispatch without creating a desktop window."""

import copy
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ui import dashboard


def preferences(mode="B"):
    return {
        "experiment_types": [mode] if isinstance(mode, str) else list(mode), "study_wordings": ["reference", "paraphrase"],
        "study_components": ["examples", "reasoning", "adaptive"],
        "study_voting_bases": ["cot", "adaptive_cot"],
        "study_voting_policies": ["first", "majority_requested", "majority_valid"],
        "study_seeds": "42, 43", "study_min_valid_votes": 3, "study_bootstrap": 1000,
        "study_pilot": True, "study_limit": "2",
        "study_analysis": {"paired_comparisons": True, "rankings": True},
        "debug_raw_outputs": False,
        "save_debug_log": False, "checkpoint_every_n_samples": 10, "checkpoint_every_seconds": 15,
        "progress_every_n_samples": 10, "sc_vote_delay_seconds": 0,
        "inference_workers": 1, "response_cache": True, "defer_analysis": False,
        "cache_profile": "", "context_window": "",
        "prevent_system_sleep": False, "keep_display_awake": False,
        "temperature": 0.2, "top_p": 0.9, "top_k": 40, "max_new_tokens": 1024,
        "repetition_penalty": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0,
        "num_beams": 1, "seed": 42, "stop_sequences": [], "sc_samples": 5,
        "experiment_name": "Fixture", "experiment_notes": "",
    }


def study(prefs):
    runtime = dashboard.build_runtime_config({"generation": {}, "performance": {}}, prefs)
    return dashboard.build_gui_study_config(
        runtime, prefs, [{"name": "fixture", "backend": "dummy"}],
        ["cot", "self_verification"], ["toy"], ["verdict_last"], ["strict"],
        mode=next(name for name in prefs["experiment_types"] if name in {"B", "C"}),
    )


class DashboardConfigTests(unittest.TestCase):
    def test_deferred_analysis_is_shown_as_generated_not_stopped(self):
        view = SimpleNamespace(
            msg_queue=queue.Queue(), stop_btn=Mock(), pause_btn=Mock(), resume_btn=Mock(), run_btn=Mock(),
            progress=Mock(), progress_label=Mock(), status_label=Mock(), open_report_btn=Mock(),
            work_label=Mock(), runner=SimpleNamespace(report_html_path=None),
            _refresh_resume_checkpoint_ui=Mock(), _log=Mock(), after=Mock(), _poll_msgs=Mock(),
        )
        view.msg_queue.put(("done", "generated"))
        dashboard.PromptAuditDashboard._poll_msgs(view)
        view.status_label.configure.assert_called_with(text="Analysis deferred")
        view.progress.configure.assert_not_called()
        view.open_report_btn.configure.assert_called_with(text="Open Run Summary", state="disabled")
        view.run_btn.configure.assert_called_with(state="normal")
        self.assertIn("without new inference", view._log.call_args.args[0])

    def test_open_report_uses_a_file_uri_with_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "study report.html"
            path.write_text("<html></html>")
            view = SimpleNamespace(runner=SimpleNamespace(report_html_path=str(path)), cfg={})
            with patch.object(dashboard.webbrowser, "open_new_tab") as browser:
                dashboard.PromptAuditDashboard._open_report(view)
            browser.assert_called_once_with(path.resolve().as_uri())

    def test_seed_list_is_explicit_and_unique(self):
        self.assertEqual(dashboard.parse_run_seeds("42, 43"), [42, 43])
        for value in ("", "42,", ",42", "42,,43", "42,42", "42,other", "42.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                dashboard.parse_run_seeds(value)

    def test_preset_names_cannot_escape_the_local_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(dashboard, "PRESETS_DIR", folder):
            self.assertEqual(Path(dashboard.preset_path("sample study")), Path(folder) / "sample study.yaml")
            for name in ("../escape", "a/b", "a\\b", ".", "..", "CON", "LPT1.txt", "name.", "name:"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    dashboard.preset_path(name)

    def test_runtime_snapshot_preserves_selections_without_mutating_defaults(self):
        base = {"generation": {"max_new_tokens": 8}, "metrics": {"include": ["Accuracy"]}}
        original = copy.deepcopy(base)
        prefs = preferences()
        cfg = dashboard.build_runtime_config(base, prefs)
        prefs["stop_sequences"].append("stop")
        self.assertEqual(base, original)
        self.assertEqual(cfg["generation"]["max_new_tokens"], 1024)
        self.assertEqual(cfg["generation"]["stop_sequences"], [])
        self.assertNotIn("metrics", cfg)

    def test_wording_study_keeps_selected_families_wordings_and_analysis(self):
        prefs = preferences()
        cfg, options = study(prefs)
        self.assertEqual(cfg["families"], ["cot"])
        self.assertEqual(cfg["variants"], ["reference", "paraphrase"])
        self.assertEqual(cfg["seeds"], [42, 43])
        self.assertTrue(cfg["analysis"]["paired_comparisons"])
        self.assertTrue(cfg["analysis"]["rankings"])
        self.assertEqual(cfg["analysis"]["bootstrap_resamples"], 1000)
        self.assertEqual(options, {"pilot": True, "limit": 2, "bootstrap": 1000})
        prefs["study_wordings"] = ["paraphrase"]
        with self.assertRaisesRegex(ValueError, "Reference"):
            study(prefs)

    def test_saved_result_analysis_settings_apply_to_standard_and_studies(self):
        prefs = preferences(["standard", "B", "C"])
        prefs["study_bootstrap"] = 25
        prefs["study_analysis"].update(group_by="repository", prevalence=False,
            prevalence_size=200, prevalence_repeats=3, review_case_limit=0)
        runtime = dashboard.build_runtime_config({}, prefs)
        jobs = dashboard.build_gui_jobs(runtime, prefs, [{"name": "fixture", "backend": "dummy"}],
                                        ["cot"], ["toy"], ["verdict_last"], ["strict"])
        self.assertTrue(runtime["analysis"]["enabled"])
        self.assertEqual(runtime["analysis"]["group_by"], "repository")
        self.assertEqual(runtime["analysis"]["bootstrap_resamples"], 25)
        self.assertFalse(runtime["analysis"]["prevalence"])
        self.assertEqual(runtime["analysis"]["review_case_limit"], 0)
        for job in jobs[1:]:
            for key in ("group_by", "bootstrap_resamples", "prevalence", "prevalence_size",
                        "prevalence_repeats", "review_case_limit"):
                self.assertEqual(job["config"]["analysis"][key], runtime["analysis"][key])
        self.assertFalse(jobs[2]["config"]["analysis"]["rankings"])
        prefs["study_analysis"]["group_by"] = "changed"
        self.assertEqual(runtime["analysis"]["group_by"], "repository")

    def test_invalid_analysis_options_fail_before_starting_a_run(self):
        invalid = (("group_by", "sample"), ("prevalence_size", 19),
                   ("prevalence_repeats", 0), ("prevalence_repeats", True),
                   ("review_case_limit", -1), ("output_audit", "yes"))
        for key, value in invalid:
            prefs = preferences()
            prefs["study_analysis"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                dashboard.build_runtime_config({}, prefs)

    def test_performance_options_are_portable_and_copied_to_studies(self):
        prefs = preferences()
        base = {"performance": {"cache_root": "results/local-cache"}}
        runtime = dashboard.build_runtime_config(base, prefs)
        self.assertEqual(runtime["performance"]["inference_workers"], 1)
        self.assertTrue(runtime["performance"]["response_cache"])
        self.assertFalse(runtime["performance"]["defer_analysis"])
        prefs.update(inference_workers=2, response_cache=False, defer_analysis=True)
        runtime = dashboard.build_runtime_config(base, prefs)
        cfg, _ = dashboard.build_gui_study_config(
            runtime, prefs, [{"name": "fixture", "backend": "dummy"}], ["cot"],
            ["toy"], ["verdict_last"], ["strict"],
            mode="B",
        )
        self.assertEqual(cfg["performance"]["inference_workers"], 2)
        self.assertFalse(cfg["performance"]["response_cache"])
        self.assertTrue(cfg["performance"]["defer_analysis"])
        runtime["performance"]["cache_root"] = "changed"
        self.assertEqual(cfg["performance"]["cache_root"], "results/local-cache")
        self.assertEqual(base, {"performance": {"cache_root": "results/local-cache"}})

    def test_invalid_performance_options_fail_before_dispatch(self):
        for key, value in (("inference_workers", 0), ("inference_workers", 9),
                           ("inference_workers", True), ("inference_workers", "2"),
                           ("response_cache", "yes"), ("defer_analysis", "no"), ("cache_profile", None)):
            prefs = preferences()
            prefs[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                dashboard.build_runtime_config({}, prefs)

    def test_optional_context_and_cache_profile_preserve_explicit_choices(self):
        prefs = preferences()
        base = {"generation": {"context_window": 2048, "num_ctx": 2048}}
        runtime = dashboard.build_runtime_config(base, prefs)
        self.assertNotIn("context_window", runtime["generation"])
        self.assertNotIn("num_ctx", runtime["generation"])
        prefs.update(context_window="8192", cache_profile=" local-v2 ")
        cfg, _ = study(prefs)
        self.assertEqual(cfg["generation"]["context_window"], 8192)
        self.assertEqual(cfg["performance"]["cache_profile"], "local-v2")
        self.assertEqual(base["generation"]["context_window"], 2048)
        for value in ("0", "-1", "8192.5", "not-a-number", True):
            prefs["context_window"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                dashboard.build_runtime_config(base, prefs)

    def test_component_study_keeps_policy_and_component_choices_separate(self):
        prefs = preferences("C")
        prefs["study_components"] = []
        prefs["study_voting_bases"] = ["adaptive_cot"]
        prefs["study_voting_policies"] = ["first"]
        cfg, _ = study(prefs)
        self.assertEqual(cfg["components"], [])
        self.assertEqual(cfg["voting_bases"], ["adaptive_cot"])
        self.assertEqual(cfg["voting_policies"], ["first"])
        self.assertFalse(cfg["analysis"]["rankings"])
        prefs["study_voting_bases"].append("cot")
        self.assertEqual(cfg["voting_bases"], ["adaptive_cot"])
        prefs["study_components"] = ["reasoning"]
        prefs["study_voting_bases"] = []
        self.assertEqual(study(prefs)[0]["components"], ["reasoning"])
        prefs["study_components"] = []
        with self.assertRaisesRegex(ValueError, "component comparison or a voting base"):
            study(prefs)

    def test_invalid_study_numbers_fail_before_dispatch(self):
        for key, value in (("study_seeds", "42,42"), ("study_bootstrap", -1),
                           ("study_limit", "bad"), ("study_limit", "0"),
                           ("sc_samples", 0), ("study_min_valid_votes", 6)):
            prefs = preferences("C")
            prefs[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                study(prefs)
        prefs = preferences()
        prefs.update(study_pilot=False, study_limit="2")
        self.assertIsNone(study(prefs)[1]["limit"])

    def test_multiple_experiment_types_build_independent_jobs(self):
        prefs = preferences(["standard", "B", "C"])
        runtime = dashboard.build_runtime_config({}, prefs)
        jobs = dashboard.build_gui_jobs(runtime, prefs, [{"name": "fixture", "backend": "dummy"}],
                                        ["cot", "self_verification"], ["toy"], ["verdict_last"], ["strict"])
        self.assertEqual([job["type"] for job in jobs], ["standard", "B", "C"])
        self.assertEqual(jobs[0]["prompts"], ["cot", "self_verification"])
        self.assertEqual(jobs[1]["config"]["families"], ["cot"])
        self.assertEqual(jobs[2]["config"]["components"], ["examples", "reasoning", "adaptive"])
        self.assertEqual(jobs[0]["limit"], 2)
        self.assertTrue(jobs[0]["pilot"])
        self.assertNotIn("metrics", jobs[1]["config"])
        prefs["study_wordings"].append("reworded")
        self.assertEqual(jobs[1]["config"]["variants"], ["reference", "paraphrase"])
        jobs[0]["models"][0]["name"] = "changed"
        self.assertEqual(jobs[1]["config"]["models"][0]["name"], "fixture")

    def test_saved_single_type_migrates_without_metric_options(self):
        self.assertEqual(dashboard.selected_experiment_types({"study_mode": "C", "metrics": ["F1"]}), ["C"])
        self.assertEqual(dashboard.selected_experiment_types({"study_mode": "invalid"}), ["standard"])
        self.assertEqual(dashboard.selected_experiment_types({"experiment_types": ["C", "standard", "B"]}), ["standard", "B", "C"])
        for selected in ("B", ["B", "B"], ["invalid"], [{}]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                dashboard.selected_experiment_types({"experiment_types": selected})
        prefs = preferences([])
        with self.assertRaisesRegex(ValueError, "at least one experiment type"):
            dashboard.build_gui_jobs({}, prefs, [], [], [], [], [])

    def test_overall_progress_is_not_reset_by_sample_counters(self):
        view = SimpleNamespace(msg_queue=queue.Queue(), progress=Mock(), progress_label=Mock(),
            work_label=Mock(), status_label=Mock(), sample_counter=Mock(), _log=Mock(), after=Mock(), _poll_msgs=Mock())
        view.msg_queue.put(("overall_progress", {"percent": 42.5, "done": 85, "total": 200,
                                                "stage": "Task wordings", "detail": "Reusing saved responses"}))
        view.msg_queue.put(("sample_progress", "Finished sample 1 / 4", 1, 4))
        dashboard.PromptAuditDashboard._poll_msgs(view)
        view.progress.configure.assert_called_once_with(value=42.5)
        view.progress_label.configure.assert_called_once_with(text="42.5% estimated")
        view.sample_counter.configure.assert_called_once_with(text="Samples: 1/4")
        self.assertIn("85/200 work units", view.work_label.configure.call_args.kwargs["text"])

    def test_worker_dispatch_uses_batch_snapshot_and_respects_pending_pause(self):
        class Runner:
            def __init__(self, cfg, progress=None, overall_progress=None):
                self.cfg, self.progress, self.overall_progress = cfg, progress, overall_progress
                self.paused = self.stopped = False

            def request_pause(self):
                self.paused = True

            def request_stop(self):
                self.stopped = True

            def run_batch(self, jobs, **options):
                self.jobs, self.options = jobs, options
                self.overall_progress({"percent": 12, "done": 12, "total": 100, "stage": "Standard"})
                return "completed"

            def run_study(self, cfg, **options):
                self.study, self.options = cfg, options
                return "completed"

            def run_all(self, *args, **options):
                self.options = options
                return "completed"

        jobs = [{"type": "standard", "models": [{"name": "fixture"}]}]
        window = SimpleNamespace(msg_queue=queue.Queue(), _pending_pause=True, _pending_stop=False)
        with patch.object(dashboard, "BatchRunner", Runner), patch.object(dashboard, "StudyRunner", Runner), \
                patch.object(dashboard, "ExperimentRunner", Runner):
            dashboard.PromptAuditDashboard._worker_run(window, jobs, lambda *_: None, None, {"fixture": True})
            self.assertEqual(window.msg_queue.get_nowait()[0], "overall_progress")
            self.assertEqual(window.msg_queue.get_nowait(), ("done", "completed"))
            self.assertTrue(window.runner.paused)
            self.assertEqual(window.runner.jobs, jobs)
            dashboard.PromptAuditDashboard._worker_run(window, [], lambda *_: None, "saved/manifest.json", {})
            self.assertEqual(window.msg_queue.get_nowait(), ("done", "completed"))
            self.assertEqual(window.runner.options["resume_manifest"], "saved/manifest.json")
            dashboard.PromptAuditDashboard._worker_run(window, [], lambda *_: None, "saved/checkpoint.json", {})
            self.assertEqual(window.msg_queue.get_nowait(), ("done", "completed"))
            self.assertEqual(window.runner.options["resume_checkpoint"], "saved/checkpoint.json")


if __name__ == "__main__":
    unittest.main()
