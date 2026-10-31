"""Check request isolation, response reuse, and durable study outcomes."""

import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from core.inference import (
    GENERATION_DIAGNOSTIC_FIELDS, InferenceEngine, InferenceStateError, ManagedModel, ResponseCache,
    generation_diagnostics, performance_options,
)
from core.revision_study import run_study, StudyRunner
from core.runner import ExperimentRunner
from models.base import BaseModel
from prompts.self_consistency import SelfConsistency


class FixtureModel(BaseModel):
    def __init__(self, item, settings, state):
        super().__init__(item["name"], settings)
        self.state = state

    def get_model_info(self):
        return {"backend": "dummy", "cache_identity": self.state.get("identity", "v1")}

    def generate(self, prompt):
        seed = self.gen_cfg.get("seed", 42)
        with self.state["lock"]:
            self.state["active"] += 1
            self.state["peak"] = max(self.state["peak"], self.state["active"])
            self.state["calls"].append((prompt, seed))
        try:
            time.sleep(self.state.get("delay", 0))
            if self.state.get("barrier"):
                self.state["barrier"].wait(2)
            if self.gen_cfg.get("seed", 42) != seed:
                raise AssertionError("Request seeds leaked across worker clients")
            if self.state.get("fail"):
                raise ValueError("fixture failure")
            self._set_generation_info({"status": "ok", "eval_count": 1, "prompt_eval_count": 10,
                                       "done_reason": "stop"})
            return "SAFE" if seed % 2 == 0 else "VULNERABLE"
        finally:
            with self.state["lock"]:
                self.state["active"] -= 1
            if self.state.get("after_call"):
                self.state["after_call"]()


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = {"calls": [], "lock": threading.Lock(), "active": 0, "peak": 0}
        self.item = {"name": "fixture", "backend": "dummy"}

    def tearDown(self):
        self.temp.cleanup()

    def loader(self, item, settings):
        return FixtureModel(item, settings, self.state)

    def engine(self, *, workers=1, run_cache=None):
        return InferenceEngine(self.loader(self.item, {"seed": 42}), self.item, self.loader,
                               performance={"inference_workers": workers, "cache_root": str(self.root / "shared")},
                               run_cache=run_cache)

    def test_parallel_requests_keep_their_seeds_and_input_order(self):
        self.state["delay"] = 0.02
        requests = [(f"code {index}", {"seed": index}) for index in range(8)]
        original = copy.deepcopy(requests)
        engine = self.engine(workers=2)
        try:
            results = engine.generate_many(requests)
            self.assertEqual(requests, original)
            self.assertEqual([row["raw_output"] for row in results], ["SAFE", "VULNERABLE"] * 4)
            self.assertEqual(self.state["peak"], 2)
            self.assertEqual(engine.stats["generated_calls"], 8)
            self.assertEqual(engine.model.gen_cfg, {"seed": 42})
        finally:
            engine.close()

    def test_shared_cache_reuses_only_matching_requests_and_identity(self):
        first = self.engine()
        first.generate_many([("code", {"seed": 42, "temperature": 0.2, "experiment_name": "first"})])
        first.close()
        second = self.engine()
        try:
            result = second.generate_many([("code", {"seed": 42, "temperature": 0.2, "experiment_name": "second"})])[0]
            self.assertEqual(result["cache_status"], "shared")
            self.assertEqual(second.stats["generated_calls"], 0)
            second.generate_many([("other code", {"seed": 42, "temperature": 0.2}),
                                  ("code", {"seed": 43, "temperature": 0.2}),
                                  ("code", {"seed": 42, "temperature": 0.3})])
            self.assertEqual(second.stats["generated_calls"], 3)
        finally:
            second.close()
        self.state["identity"] = "v2"
        third = self.engine()
        try:
            third.generate_many([("code", {"seed": 42, "temperature": 0.2})])
            self.assertEqual(third.stats["generated_calls"], 1)
        finally:
            third.close()

    def test_stopping_drains_and_records_requests_already_running(self):
        self.state["barrier"] = threading.Barrier(2)
        engine = self.engine(workers=2)
        stopped = threading.Event()
        saved = []

        def control():
            if stopped.is_set():
                raise InterruptedError("stop requested")

        def record(index, result):
            saved.append(index)
            stopped.set()

        engine.control = control
        try:
            with self.assertRaises(InterruptedError):
                engine.generate_many([(f"code {i}", {"seed": i}) for i in range(4)], on_result=record)
            self.assertEqual(set(saved), {0, 1})
            self.assertEqual(len(self.state["calls"]), 2)
            self.assertEqual(engine.stats["generated_calls"], 2)
        finally:
            engine.close()

    def test_optional_shared_cache_failure_preserves_completed_results(self):
        engine = self.engine()
        recorded = []
        try:
            with patch.object(engine.shared_cache, "put", side_effect=OSError("cache unavailable")):
                results = engine.generate_many([("code", {"seed": 42})],
                                               on_result=lambda index, result: recorded.append(result))
            self.assertEqual(results[0]["raw_output"], "SAFE")
            self.assertEqual(len(recorded), 1)
            self.assertFalse(engine.stats["persistent_cache_enabled"])
            self.assertEqual(engine.stats["shared_cache_warning"], "OSError")
        finally:
            engine.close()

    def test_optional_shared_cache_close_failure_does_not_fail_the_run(self):
        engine = self.engine()
        cache = engine.shared_cache
        try:
            with patch.object(cache, "close", side_effect=OSError("cache unavailable")):
                engine.close()
            self.assertFalse(engine.stats["persistent_cache_enabled"])
        finally:
            cache.close()

    def test_ollama_shared_cache_requires_explicit_context_and_profile(self):
        model = self.loader(self.item, {"seed": 42})
        model.get_model_info = lambda: {"digest": "fixture-v1", "runtime_version": "fixture-runtime"}
        item = {"name": "fixture", "backend": "ollama"}
        options = {"cache_root": str(self.root / "shared"), "cache_profile": "v1"}
        engine = InferenceEngine(model, item, self.loader, performance=options)
        self.assertIsNone(engine.shared_cache)
        engine.close()
        model.gen_cfg["context_window"] = 4096
        engine = InferenceEngine(model, item, self.loader, performance={**options, "cache_profile": ""})
        self.assertIsNone(engine.shared_cache)
        engine.close()
        engine = InferenceEngine(model, item, self.loader, performance=options)
        try:
            self.assertIsNotNone(engine.shared_cache)
            requests = [("code", {"seed": 42})]
            engine.generate_many(requests)
            engine.generate_many(requests)
            self.assertEqual(engine.stats["shared_cache_hits"], 0)
            self.assertEqual(engine.stats["generated_calls"], 2)
        finally:
            engine.close()

    def test_cross_study_cache_keeps_all_voting_draws_and_call_budgets(self):
        samples = [{"id": 1, "code": "code", "label": "SAFE"}]
        cfg = {"section": "B", "datasets": ["fixture"], "models": [self.item],
               "families": ["adaptive_cot", "self_consistency"], "variants": ["reference"],
               "protocols": ["verdict_first"], "parser_modes": ["strict"], "seeds": [42],
               "generation": {"temperature": 0.2}, "votes": 5,
               "performance": {"inference_workers": 2, "cache_root": str(self.root / "shared")}}
        run_study(cfg, self.root / "b", pilot=True, dataset_loader=lambda _: samples,
                  model_loader=self.loader, progress=lambda _: None)
        self.assertEqual(len(self.state["calls"]), 5)
        cfg.update(section="C", components=[], voting_bases=["adaptive_cot"])
        run_study(cfg, self.root / "c", pilot=True, dataset_loader=lambda _: samples,
                  model_loader=self.loader, progress=lambda _: None)
        self.assertEqual(len(self.state["calls"]), 5)
        manifest = json.loads((self.root / "c/manifest.json").read_text())
        self.assertEqual(manifest["new_calls_this_session"], 5)
        self.assertEqual(manifest["inference_performance"][0]["generated_calls"], 0)
        self.assertEqual(manifest["inference_performance"][0]["shared_cache_hits"], 5)
        predictions = [json.loads(line) for line in (self.root / "c/predictions.jsonl").read_text().splitlines()]
        self.assertEqual(sorted(row["decision_calls"] for row in predictions), [1, 5, 5])
        self.assertTrue(all(row["generation_ids"] == predictions[0]["generation_ids"] for row in predictions))

    def test_serial_and_parallel_components_keep_the_same_decisions_and_pools(self):
        samples = [{"id": 1, "code": "first code", "label": "SAFE"},
                   {"id": 2, "code": "second code", "label": "VULNERABLE"}]
        cfg = {"section": "C", "datasets": ["fixture"], "models": [self.item],
               "protocols": ["verdict_first", "verdict_last"],
               "parser_modes": ["strict", "structured"], "seeds": [42, 43],
               "generation": {"temperature": 0.2}, "votes": 5,
               "performance": {"response_cache": False}}
        outcomes, requests = [], []
        for workers in (1, 2):
            cfg["performance"]["inference_workers"] = workers
            output = self.root / f"workers-{workers}"
            self.state["calls"].clear()
            run_study(cfg, output, pilot=True, dataset_loader=lambda _: samples,
                      model_loader=self.loader, progress=lambda _: None)
            rows = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
            outcomes.append([{key: value for key, value in row.items()
                              if key not in {"seconds", "decision_seconds", "generation_info"}} for row in rows])
            requests.append(sorted(self.state["calls"]))
        self.assertEqual(requests[0], requests[1])
        self.assertEqual(outcomes[0], outcomes[1])

    def test_failed_calls_replay_within_run_but_not_across_runs(self):
        self.state["fail"] = True
        store = ResponseCache(self.root / "run.sqlite3")
        engine = self.engine(run_cache=store)
        try:
            request = [("code", {"seed": 42})]
            self.assertTrue(engine.generate_many(request)[0]["error"])
            self.assertEqual(engine.generate_many(request)[0]["cache_status"], "run")
            self.assertEqual(len(self.state["calls"]), 1)
        finally:
            engine.close()
            store.close()
        self.state["fail"] = False
        engine = self.engine()
        try:
            self.assertEqual(engine.generate_many(request)[0]["raw_output"], "SAFE")
            self.assertEqual(engine.stats["generated_calls"], 1)
        finally:
            engine.close()

    def test_prefetch_consumes_raw_responses_without_generating_twice(self):
        store = ResponseCache(self.root / "run.sqlite3")
        engine = self.engine(workers=2, run_cache=store)
        model = ManagedModel(engine)
        try:
            model.prefetch([("code", {"seed": 42})])
            self.assertEqual(model.generate("code"), "SAFE")
            self.assertEqual(len(self.state["calls"]), 1)
            self.assertEqual(engine.stats["run_reuses"], 0)
            self.assertEqual(model.generate("code"), "SAFE")
            self.assertEqual(engine.stats["run_reuses"], 1)
        finally:
            engine.close()
            store.close()

    def test_standard_lookahead_starts_next_sample_before_slow_response_finishes(self):
        third_started = threading.Event()
        first_saw_third = []
        calls = []

        class UnevenModel(BaseModel):
            def get_model_info(self):
                return {"cache_identity": "uneven-fixture"}

            def generate(self, prompt):
                marker = next(index for index in range(4) if f"marker_{index}" in prompt)
                calls.append((marker, self.gen_cfg["seed"]))
                if marker == 0:
                    first_saw_third.append(third_started.wait(2))
                elif marker == 2:
                    third_started.set()
                self._set_generation_info({"status": "ok", "eval_count": 1, "prompt_eval_count": 10,
                                           "done_reason": "stop"})
                return "SAFE"

        samples = [{"id": index + 1, "code": f"int marker_{index}(void) {{ return 0; }}", "label": "SAFE"}
                   for index in range(4)]
        cfg = {"generation": {"seed": 42},
               "performance": {"inference_workers": 2, "response_cache": False, "prevent_system_sleep": False},
               "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None, dataset_loader=lambda _: samples,
                                  model_loader=lambda item, settings: UnevenModel(item["name"], settings))
        self.assertEqual(runner.run_all(["fixture"], [self.item], ["zero_shot"],
                                        ["verdict_first"], ["strict"]), "completed")
        self.assertEqual(first_saw_third, [True])
        self.assertEqual(sorted(calls), [(index, 42) for index in range(4)])
        self.assertTrue(all(row["pred"] == "safe" for row in runner.records[0]["predictions"]))
        self.assertEqual(runner.records[0]["inference_performance"]["standard_prefetch_samples"], 8)

    def test_stopping_standard_lookahead_saves_active_calls_and_resume_reuses_them(self):
        samples = [{"id": index + 1, "code": f"int marker_{index}(void) {{ return 0; }}", "label": "SAFE"}
                   for index in range(12)]
        cfg = {"generation": {"seed": 42},
               "performance": {"inference_workers": 2, "response_cache": False, "prevent_system_sleep": False},
               "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None, dataset_loader=lambda _: samples,
                                  model_loader=self.loader)
        self.state["barrier"] = threading.Barrier(2)
        self.state["after_call"] = runner.request_stop
        self.assertEqual(runner.run_all(["fixture"], [self.item], ["zero_shot"],
                                        ["verdict_first"], ["strict"]), "stopped")
        self.assertEqual(len(self.state["calls"]), 2)
        checkpoint = json.loads(Path(runner.checkpoint_path).read_text())
        self.assertEqual(checkpoint["current_combo"]["next_sample_index"], 0)
        self.assertEqual(checkpoint["current_combo"]["preds"], [])
        self.state.pop("barrier")
        self.state.pop("after_call")
        resumed = ExperimentRunner(cfg, progress=lambda _: None, dataset_loader=lambda _: samples,
                                   model_loader=self.loader)
        self.assertEqual(resumed.run_all([], [], [], resume_checkpoint=runner.checkpoint_path), "completed")
        self.assertEqual(len(self.state["calls"]), len(samples))
        self.assertEqual(len(set(self.state["calls"])), len(samples))
        self.assertEqual(len(resumed.records[0]["predictions"]), len(samples))

    def test_pausing_standard_lookahead_drains_active_calls_then_refills_on_resume(self):
        samples = [{"id": index + 1, "code": f"int marker_{index}(void) {{ return 0; }}", "label": "SAFE"}
                   for index in range(12)]
        cfg = {"generation": {"seed": 42},
               "performance": {"inference_workers": 2, "response_cache": False, "prevent_system_sleep": False},
               "output": {"run_root": str(self.root / "runs")}}
        paused_call_counts = []

        def progress(message):
            if message.startswith("Run paused. Checkpoint saved"):
                paused_call_counts.append(len(self.state["calls"]))
                self.state.pop("barrier")
                self.state.pop("after_call")
                runner.request_resume()

        runner = ExperimentRunner(cfg, progress=progress, dataset_loader=lambda _: samples, model_loader=self.loader)
        self.state["barrier"] = threading.Barrier(2)
        self.state["after_call"] = runner.request_pause
        self.assertEqual(runner.run_all(["fixture"], [self.item], ["zero_shot"],
                                        ["verdict_first"], ["strict"]), "completed")
        self.assertEqual(paused_call_counts, [2])
        self.assertEqual(len(self.state["calls"]), len(samples))
        self.assertEqual(len(set(self.state["calls"])), len(samples))
        self.assertEqual(len(runner.records[0]["predictions"]), len(samples))

    def test_unsupported_parallel_backends_and_bad_settings_fail_preflight(self):
        for backend in ("hf", "huggingface", "api"):
            with self.assertRaisesRegex(ValueError, "one worker"):
                performance_options({"inference_workers": 2}, backend)
        for value in (0, 9, True, 2.5):
            with self.assertRaises(ValueError):
                performance_options({"inference_workers": value})

    def test_corrupt_cache_entry_is_rejected(self):
        store = ResponseCache(self.root / "run.sqlite3")
        try:
            store.put("key", {"raw_output": "SAFE"})
            store.db.execute("UPDATE responses SET payload = ? WHERE key = ?", ('{}', "key"))
            with self.assertRaisesRegex(ValueError, "integrity"):
                store.get("key")
        finally:
            store.close()

    def test_standard_parsers_and_sc_share_raw_generations(self):
        samples = [{"id": 1, "code": "int f(void) { return 0; }", "label": "SAFE"},
                   {"id": 2, "code": "int g(void) { return 1; }", "label": "SAFE"}]
        cfg = {"generation": {"seed": 42, "temperature": 0.2, "sc_samples": 5},
               "performance": {"inference_workers": 2, "cache_root": str(self.root / "shared"),
                               "prevent_system_sleep": False}, "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None)
        with patch("core.runner.load_dataset", return_value=samples), patch("core.runner.load_model", side_effect=self.loader):
            status = runner.run_all(["fixture"], [self.item], ["adaptive_cot", "self_consistency"],
                                    ["verdict_first"], ["strict", "structured", "full"])
        self.assertEqual(status, "completed")
        self.assertEqual(len(self.state["calls"]), 10)
        self.assertEqual(len(runner.records), 6)
        for record in runner.records:
            self.assertTrue(all(row["pred"] == "safe" for row in record["predictions"]))
            calls = 5 if record["prompt"] == "self_consistency" else 1
            for row in record["predictions"]:
                self.assertEqual(row["decision_calls"], calls)
                self.assertEqual(row["decision_prompt_tokens"], 10 * calls)
                self.assertEqual(row["decision_output_tokens"], calls)
                self.assertEqual(row["decision_output_limit_hits"], 0)
                self.assertEqual(row["decision_generation_errors"], 0)
                self.assertGreaterEqual(row["decision_seconds"], 0)
                self.assertNotIn("raw_output", row)
                self.assertNotIn("generation_info", row)
        for prompt in ("adaptive_cot", "self_consistency"):
            matching = [record["predictions"] for record in runner.records if record["prompt"] == prompt]
            diagnostics = [[{field: row[field] for field in GENERATION_DIAGNOSTIC_FIELDS}
                            for row in predictions] for predictions in matching]
            self.assertEqual(diagnostics[0], diagnostics[1])
            self.assertEqual(diagnostics[0], diagnostics[2])

    def test_sc_diagnostics_include_failed_unresolved_and_capped_draws(self):
        class MixedVotes(BaseModel):
            def generate(self, prompt):
                index = self.gen_cfg["seed"] - 42
                self._set_generation_info({"prompt_eval_count": 100 + index, "eval_count": 10 + index,
                                           "generation_seconds": (index + 1) / 10,
                                           "done_reason": "length" if index == 2 else "stop",
                                           "status": "error" if index == 1 else "ok"})
                if index == 1:
                    raise RuntimeError("one failed draw")
                return "VULNERABLE" if index == 3 else "SAFE"

        settings = {"seed": 42, "temperature": 0.2}
        model = MixedVotes("fixture", settings)
        result = SelfConsistency().apply_with_context(model, "code", {"sc_samples": 5})
        self.assertEqual(result["label"], "safe")
        self.assertEqual(result["valid_votes"], 4)
        self.assertEqual(result["unknown_votes"], 1)
        diagnostics = result["generation_diagnostics"]
        self.assertEqual(diagnostics["decision_calls"], 5)
        self.assertEqual(diagnostics["decision_prompt_tokens"], 510)
        self.assertEqual(diagnostics["decision_output_tokens"], 60)
        self.assertAlmostEqual(diagnostics["decision_seconds"], 1.5)
        self.assertEqual(diagnostics["decision_generation_errors"], 1)
        self.assertEqual(diagnostics["decision_output_limit_hits"], 1)
        self.assertEqual(diagnostics["distinct_responses"], 3)
        self.assertIs(model.gen_cfg, settings)

    def test_missing_diagnostics_remain_unavailable(self):
        measured = generation_diagnostics([{"raw_output": "SAFE", "generation_info": {}}])
        self.assertEqual(measured["decision_calls"], 1)
        self.assertEqual(measured["decision_generation_errors"], 0)
        self.assertEqual(measured["distinct_responses"], 1)
        for field in ("decision_seconds", "decision_prompt_tokens", "decision_output_tokens",
                      "decision_output_limit_hits"):
            self.assertIsNone(measured[field])

    def test_prompt_construction_error_does_not_invent_a_generation_call(self):
        class BrokenPrompt:
            def apply(self, *args):
                raise ValueError("invalid prompt construction")

        cfg = {"performance": {"response_cache": False, "prevent_system_sleep": False},
               "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None)
        samples = [{"code": "code", "label": "SAFE"}]
        with patch("core.runner.load_dataset", return_value=samples), \
                patch("core.runner.load_model", side_effect=self.loader), \
                patch("core.runner.load_prompt", return_value=BrokenPrompt()):
            self.assertEqual(runner.run_all(["fixture"], [self.item], ["zero_shot"],
                                           ["verdict_first"], ["strict"]), "completed")
        self.assertEqual(self.state["calls"], [])
        prediction = runner.records[0]["predictions"][0]
        self.assertEqual(prediction["pred"], "unknown")
        self.assertEqual(prediction["decision_calls"], 0)
        self.assertEqual(prediction["decision_generation_errors"], 0)

    def test_standard_keeps_each_model_loaded_across_datasets(self):
        cohorts = {name: [{"id": index, "code": f"int {name}_{index}(void) {{ return 0; }}", "label": "SAFE"}
                          for index in range(2)] for name in ("alpha", "beta")}
        models = [self.item, {"name": "second", "backend": "dummy"}]
        cfg = {"generation": {"seed": 42}, "performance": {"response_cache": False,
               "prevent_system_sleep": False}, "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None)
        with patch("core.runner.load_dataset", side_effect=lambda name, **kwargs: cohorts[name]) as datasets, \
                patch("core.runner.load_model", side_effect=self.loader) as loaded:
            self.assertEqual(runner.run_all(list(cohorts), models, ["zero_shot", "cot"],
                                           ["verdict_first"], ["strict", "structured"]), "completed")
        self.assertEqual([call.args[0]["name"] for call in loaded.call_args_list], ["fixture", "second"])
        # Validate every cohort before loading the first model, then retain model-first execution.
        self.assertEqual([call.args[0] for call in datasets.call_args_list], ["alpha", "beta"] * 3)
        expected = [(model["name"], name) for model in models for name in cohorts for _ in range(4)]
        self.assertEqual([(row["model"], row["dataset"]) for row in runner.records], expected)
        self.assertEqual(len(self.state["calls"]), 16)
        for row in runner.records:
            self.assertEqual([sample["pred"] for sample in row["predictions"]], ["safe", "safe"])

    def test_standard_report_records_effective_model_settings_and_requested_votes(self):
        cfg = {"generation": {"seed": 42, "temperature": 0.2, "context_window": 4096, "sc_samples": 3},
               "performance": {"response_cache": False, "prevent_system_sleep": False},
               "output": {"run_root": str(self.root / "runs")}}
        model = {"name": "dummy", "backend": "dummy", "temperature": 0.9,
                 "context_window": 2048, "sc_samples": 9}
        runner = ExperimentRunner(cfg, progress=lambda _: None)
        with patch("core.runner.load_dataset", return_value=[{"code": "int f(void) { return 0; }", "label": "SAFE"}]):
            self.assertEqual(runner.run_all(["fixture"], [model], ["self_consistency"],
                                           ["verdict_first"], ["full"]), "completed")
        params = runner.records[0]["params"]
        self.assertEqual((params["temperature"], params["context_window"], params["sc_samples"]), (0.9, 2048, 3))
        self.assertEqual(runner.records[0]["predictions"][0]["decision_calls"], 3)

    def test_standard_model_first_order_resumes_every_combination_once(self):
        cohorts = {name: [{"id": index, "code": f"int {name}_{index}(void) {{ return 0; }}", "label": "SAFE"}
                          for index in range(2)] for name in ("alpha", "beta")}
        models = [self.item, {"name": "second", "backend": "dummy"}]
        cfg = {"generation": {"seed": 42}, "performance": {"response_cache": False,
               "prevent_system_sleep": False}, "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None)
        executions = []

        def tracked_loader(item, settings):
            model = self.loader(item, settings)
            generate = model.generate

            def tracked_generate(prompt):
                executions.append((item["name"], prompt, model.gen_cfg["seed"]))
                return generate(prompt)

            model.generate = tracked_generate
            return model

        self.state["after_call"] = lambda: runner.request_stop() if len(executions) == 5 else None
        with patch("core.runner.load_dataset", side_effect=lambda name, **kwargs: cohorts[name]), \
                patch("core.runner.load_model", side_effect=tracked_loader) as loaded:
            self.assertEqual(runner.run_all(list(cohorts), models, ["zero_shot", "cot"],
                                           ["verdict_first"], ["strict", "structured"]), "stopped")
            self.assertEqual(len(executions), 5)
            self.state["after_call"] = None
            resumed = ExperimentRunner(cfg, progress=lambda _: None)
            self.assertEqual(resumed.run_all([], [], [], resume_checkpoint=runner.checkpoint_path), "completed")
        self.assertEqual([call.args[0]["name"] for call in loaded.call_args_list], ["fixture", "fixture", "second"])
        keys = [(row["model"], row["dataset"], row["prompt"], row["parser_mode"]) for row in resumed.records]
        self.assertEqual(len(keys), 16)
        self.assertEqual(len(set(keys)), 16)
        self.assertEqual(len(executions), 16)
        self.assertEqual(len(set(executions)), 16)
        self.assertTrue(all(len(row["predictions"]) == 2 for row in resumed.records))

    def test_deferred_study_resumes_analysis_without_loading_a_model(self):
        cfg = {"section": "B", "datasets": ["fixture"], "models": [self.item],
               "families": ["zero_shot"], "variants": ["reference"], "protocols": ["verdict_first"],
               "parser_modes": ["strict"], "votes": 1, "generation": {"temperature": 0.2},
               "performance": {"defer_analysis": True, "response_cache": False}}
        outer = {"output": {"run_root": str(self.root / "runs")},
                 "performance": {"prevent_system_sleep": False}}
        samples = [{"id": 1, "code": "code", "label": "SAFE"}]
        runner = StudyRunner(outer, progress=lambda _: None, dataset_loader=lambda _: samples, model_loader=self.loader)
        self.assertEqual(runner.run_study(cfg, pilot=True, bootstrap=0), "generated")
        saved = StudyRunner.find_latest_resumable_checkpoint(outer)
        self.assertFalse(Path(runner.report_html_path).exists())
        resumed = StudyRunner(outer, progress=lambda _: None,
                              model_loader=lambda *_: self.fail("Analysis resume must not load a model"))
        self.assertEqual(resumed.run_study({}, resume_manifest=saved), "completed")
        self.assertEqual(len(self.state["calls"]), 1)

    def test_standard_resume_retains_failed_draws_for_other_parsers(self):
        samples = [{"id": 1, "code": "first code", "label": "SAFE"},
                   {"id": 2, "code": "second code", "label": "SAFE"}]
        cfg = {"generation": {"seed": 42, "temperature": 0.2},
               "performance": {"cache_root": str(self.root / "shared"), "prevent_system_sleep": False},
               "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None)
        self.state.update(fail=True, after_call=runner.request_stop)
        with patch("core.runner.load_dataset", return_value=samples), patch("core.runner.load_model", side_effect=self.loader):
            status = runner.run_all(["fixture"], [self.item], ["zero_shot"],
                                    ["verdict_first"], ["strict", "structured"])
            self.assertEqual(status, "stopped")
            self.state.update(fail=False, after_call=None)
            resumed = ExperimentRunner(cfg, progress=lambda _: None)
            self.assertEqual(resumed.run_all([], [], [], resume_checkpoint=runner.checkpoint_path), "completed")
        self.assertEqual(len(self.state["calls"]), 2)
        self.assertTrue(all([row["pred"] for row in record["predictions"]] == ["unknown", "safe"]
                            for record in resumed.records))

    def test_standard_resume_rejects_changed_model_identity(self):
        samples = [{"id": 1, "code": "first code", "label": "SAFE"},
                   {"id": 2, "code": "second code", "label": "SAFE"}]
        cfg = {"generation": {"seed": 42}, "performance": {"prevent_system_sleep": False,
               "response_cache": False}, "output": {"run_root": str(self.root / "runs")}}
        runner = ExperimentRunner(cfg, progress=lambda _: None)
        self.state["after_call"] = runner.request_stop
        with patch("core.runner.load_dataset", return_value=samples), patch("core.runner.load_model", side_effect=self.loader):
            self.assertEqual(runner.run_all(["fixture"], [self.item], ["zero_shot"],
                                           ["verdict_first"], ["strict"]), "stopped")
            self.state.update(after_call=None, identity="new-weights")
            resumed = ExperimentRunner(cfg, progress=lambda _: None)
            with self.assertRaises(InferenceStateError):
                resumed.run_all([], [], [], resume_checkpoint=runner.checkpoint_path)
        self.assertEqual(len(self.state["calls"]), 1)

    def test_study_resume_rejects_changed_execution_environment(self):
        cfg = {"section": "B", "datasets": ["fixture"], "models": [self.item],
               "families": ["zero_shot"], "variants": ["reference"],
               "protocols": ["verdict_first"], "parser_modes": ["strict"],
               "generation": {"temperature": 0.2}, "performance": {"response_cache": False}}
        samples = [{"id": 1, "code": "code", "label": "SAFE"}]
        output = self.root / "study"
        with patch.dict("os.environ", {"OLLAMA_FLASH_ATTENTION": "0"}):
            run_study(cfg, output, pilot=True, dataset_loader=lambda _: samples,
                      model_loader=self.loader, progress=lambda _: None)
        with patch.dict("os.environ", {"OLLAMA_FLASH_ATTENTION": "1"}):
            with self.assertRaisesRegex(InferenceStateError, "execution environment"):
                run_study(cfg, output, resume=True, pilot=True, dataset_loader=lambda _: samples,
                          model_loader=self.loader, progress=lambda _: None)
        self.assertEqual(len(self.state["calls"]), 1)


if __name__ == "__main__":
    unittest.main()
