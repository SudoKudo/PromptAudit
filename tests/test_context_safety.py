"""Test how Ollama handles prompts near its context limit."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from requests import ConnectionError

from core.inference import InferenceEngine, InferenceStateError
from core.revision_study import run_study
from evaluation.label_parser import parse_verdict_details
from models.base import BaseModel, ContextSafetyError, ContextWindowExceeded
from models.ollama_model import OllamaModel


def response(data, status=200):
    result = Mock(status_code=status)
    result.json.return_value = data
    return result


class ContextGuardTests(unittest.TestCase):
    def model(self, window=2048, budget=1024):
        model = OllamaModel("fixture", {"context_window": window, "max_new_tokens": budget})
        model.get_model_info = Mock(return_value={"model_info": {"fixture.context_length": 32768}})
        model.session = Mock()
        model.session.get.return_value = response({"models": [{"name": "fixture:latest", "context_length": window}]})
        return model

    def probes(self):
        return [response({"done": True, "prompt_eval_count": 12, "eval_count": 1}),
                response({"error": "request (2056 tokens) exceeds the available context size (256 tokens)"}, 400)]

    def test_ignored_truncation_flag_stops_before_scoring(self):
        model = self.model()
        model.session.post.return_value = response({"done": True, "prompt_eval_count": 128, "eval_count": 1})
        engine = InferenceEngine(model, {"name": "fixture", "backend": "ollama"}, lambda item, cfg: model,
                                 performance={"response_cache": False})
        on_result = Mock()
        try:
            with self.assertRaisesRegex(InferenceStateError, "truncated an oversized"):
                engine.generate_many([("code", model.gen_cfg)], on_result=on_result)
            self.assertEqual(model.session.post.call_count, 2)
            on_result.assert_not_called()
        finally:
            engine.close()

    def test_study_can_resume_after_ollama_was_offline(self):
        model = self.model()
        metadata = model.get_model_info.return_value
        model.get_model_info.return_value = {"metadata_error": "connection refused"}
        cfg = {"section": "B", "models": [{"name": "fixture", "backend": "ollama"}],
               "datasets": ["fixture"], "families": ["zero_shot"], "variants": ["reference"],
               "protocols": ["verdict_first"], "parser_modes": ["strict"],
               "performance": {"response_cache": False}, "generation": model.gen_cfg}
        with TemporaryDirectory() as temp:
            output = Path(temp) / "study"
            options = dict(model_loader=lambda item, settings: model, progress=lambda message: None,
                           dataset_loader=lambda name: [{"id": 1, "code": "int a;", "label": "SAFE"}])
            with self.assertRaisesRegex(InferenceStateError, "Make sure Ollama is running"):
                run_study(cfg, output, **options)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["resolved_models"], {})
            self.assertEqual(manifest["total_saved_calls"], 0)

            model.get_model_info.return_value = metadata
            model.session.post.side_effect = self.probes() + [
                response({"response": "SAFE", "done": True, "prompt_eval_count": 500})]
            run_study(cfg, output, resume=True, **options)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["total_saved_calls"], 1)

    def test_missing_or_extended_window_is_rejected_before_requests(self):
        model = self.model()
        del model.gen_cfg["context_window"]
        with self.assertRaisesRegex(ContextSafetyError, "explicit context window"):
            model.generate("code")
        model.gen_cfg["context_window"] = 65536
        with self.assertRaisesRegex(ContextSafetyError, "declared window"):
            model.generate("code")
        model.session.post.assert_not_called()

    def test_generation_disables_truncation_and_shifting(self):
        model = self.model()
        raw = " \nSAFE\n "
        model.session.post.side_effect = self.probes() + [response({
            "response": raw, "done": True, "done_reason": "stop", "prompt_eval_count": 500})]
        saved = model.generate("complete prompt")
        self.assertEqual(saved, raw)
        self.assertEqual(parse_verdict_details(saved, mode="strict")["label"], "safe")
        payload = model.session.post.call_args.kwargs["json"]
        self.assertFalse(payload["truncate"])
        self.assertFalse(payload["shift"])
        self.assertEqual(payload["options"]["num_ctx"], 2048)
        self.assertEqual(payload["options"]["num_predict"], 1024)
        self.assertTrue(model.get_generation_info()["input_headroom_verified"])

    def test_short_response_survives_reduced_headroom(self):
        model = self.model()
        model.session.post.side_effect = self.probes() + [response({
            "response": "SAFE", "done": True, "prompt_eval_count": 1206})]
        self.assertEqual(model.generate("complete prompt"), "SAFE")
        self.assertEqual(model.get_generation_info()["num_predict"], 842)

    def test_smaller_loaded_window_is_used_for_headroom(self):
        model = self.model(window=4096)
        model.session.get.return_value = response({"models": [{"name": "fixture", "context_length": 2048}]})
        model.session.post.side_effect = self.probes() + [response({
            "response": "SAFE", "done": True, "prompt_eval_count": 1206})]
        self.assertEqual(model.generate("complete prompt"), "SAFE")
        self.assertEqual(model.get_generation_info()["num_predict"], 842)

    def test_missing_loaded_window_stops_instead_of_assuming_a_default(self):
        model = self.model()
        model.session.get.return_value = response({"models": []})
        model.session.post.side_effect = self.probes() + [response({
            "response": "SAFE", "done": True, "prompt_eval_count": 500})]
        with self.assertRaisesRegex(ContextSafetyError, "loaded model's context window"):
            model.generate("complete prompt")

    def test_disconnected_server_or_missing_model_stops_the_run(self):
        for failure in (ConnectionError(), response({"error": "model not found"}, 404)):
            with self.subTest(failure=failure):
                model = self.model()
                model.session.post.side_effect = self.probes() + [failure]
                with self.assertRaises(ContextSafetyError):
                    model.generate("complete prompt")

    def test_parallel_workers_share_capability_probe_before_generation(self):
        from models.context_guard import _VERIFIED_MODELS
        _VERIFIED_MODELS.clear()
        models = [self.model(), self.model()]
        calls = []
        def post(url, *, json, timeout):
            calls.append(json)
            if json["options"]["num_ctx"] == 256:
                if len(json["prompt"]) > 100:
                    return response({"error": "request (2056 tokens) exceeds the available context size (256 tokens)"}, 400)
                return response({"done": True, "prompt_eval_count": 12})
            return response({"response": "SAFE", "done": True, "prompt_eval_count": 500})
        for model in models:
            model.get_model_info.return_value.update(digest="parallel-fixture", runtime_version="fixture-version")
            model.session.post.side_effect = post
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda m: m.generate("code"), models)), ["SAFE", "SAFE"])
        self.assertEqual(sum(c["options"]["num_ctx"] == 256 for c in calls), 2)
        _VERIFIED_MODELS.clear()

    def test_generic_context_error_retries_without_changing_window(self):
        model = self.model()
        model.session.post.side_effect = self.probes() + [
            response({"error": "context window exhausted"}, 500),
            response({"response": "SAFE", "done": True, "prompt_eval_count": 1258, "eval_count": 3}),
        ]
        self.assertEqual(model.generate("complete prompt"), "SAFE")
        self.assertEqual(model.session.post.call_count, 4)
        retry = model.session.post.call_args.kwargs["json"]["options"]
        self.assertEqual(retry["num_predict"], 512)
        self.assertEqual(retry["num_ctx"], 2048)
        self.assertEqual(model.get_generation_info()["retry_count"], 1)

    def test_oversized_input_returns_recorded_failure(self):
        model = self.model()
        model.session.post.side_effect = self.probes() + [
            response({"error": "request (31012 tokens) exceeds the available context size (2048 tokens)"}, 400),
        ]
        self.assertEqual(model.generate("long code"), "")
        self.assertEqual(model.session.post.call_count, 3)
        info = model.get_generation_info()
        self.assertEqual(info["error_type"], "ContextWindowExceeded")
        self.assertEqual(info["input_tokens_required"], 31012)
        self.assertNotIn("prompt_eval_count", info)
        self.assertEqual(info["reported_context_window"], 2048)

    def test_incomplete_or_failed_reply_cannot_supply_a_verdict(self):
        from evaluation.report import _without_response_text

        for failed_fields in ({}, {"done": False}, {"done": True, "error": "server error"}):
            with self.subTest(failed_fields=failed_fields):
                model = self.model()
                model.session.post.side_effect = self.probes() + [response({
                    "response": "SAFE", "thinking": "unfinished reasoning", "prompt_eval_count": 500,
                    **failed_fields,
                })]
                returned = model.generate("complete prompt")
                self.assertEqual(parse_verdict_details(returned)["label"], "unknown")
                info = model.get_generation_info()
                self.assertEqual(info["status"], "error")
                self.assertEqual(info["raw_response"], "SAFE")
                self.assertNotIn("raw_response", _without_response_text(info))
                self.assertNotIn("thinking_output", _without_response_text(info))

    def test_safety_errors_escape_inference_error_conversion(self):
        class Unsafe(BaseModel):
            def generate(self, prompt):
                raise ContextSafetyError("unsafe input")
        model = Unsafe("fixture", {})
        engine = InferenceEngine(model, {"name": "fixture", "backend": "dummy"}, lambda item, cfg: model,
                                 performance={"response_cache": False})
        try:
            with self.assertRaises(InferenceStateError):
                engine.generate_many([("code", {})])
        finally:
            engine.close()


class ExecutionCounterTests(unittest.TestCase):
    def test_execution_counter_names_are_only_inferred_when_unambiguous(self):
        from evaluation.template_analysis import _execution_rows
        saved = {"inference_performance": [{"workers": 2}]}
        self.assertEqual(_execution_rows(saved, [{"model_id": "a", "model": "model-a"}])[0]["model"], "model-a")
        self.assertEqual(_execution_rows(saved, [{"model_id": "a", "model": "model-a"},
                                                 {"model_id": "b", "model": "model-b"}])[0]["model"], "Unavailable")
