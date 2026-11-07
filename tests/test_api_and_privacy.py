"""API requests, diagnostics, and credential handling."""

from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from core.inference import generation_diagnostics
from core.runner import ExperimentRunner
from models.api_model import APIModel
from utils.privacy import safe_settings, safe_text


def completion(text=" SAFE ", *, reason="stop", usage=None):
    response = Mock(status_code=200)
    response.json.return_value = {"choices": [{"text": text, "finish_reason": reason}],
        "usage": usage, "system_fingerprint": "fixture-runtime"}
    return response


class APIModelTests(unittest.TestCase):
    def test_request_keeps_the_prompt_and_passes_seed_and_stop_settings(self):
        settings = {"api_host": "https://example.test", "api_key": "private-fixture-key",
            "seed": 73, "max_new_tokens": 128, "stop_sequences": ["END"]}
        model = APIModel("fixture", settings)
        response = completion(usage={"prompt_tokens": 17, "completion_tokens": 3})
        with patch.object(model.session, "post", return_value=response) as post:
            self.assertEqual(model.generate("unchanged prompt"), "SAFE")
        self.assertEqual(post.call_args.args, ("https://example.test/v1/completions",))
        self.assertEqual(post.call_args.kwargs["json"]["prompt"], "unchanged prompt")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "fixture")
        self.assertEqual(post.call_args.kwargs["json"]["seed"], 73)
        self.assertEqual(post.call_args.kwargs["json"]["stop"], ["END"])
        info = model.consume_generation_info()
        self.assertEqual(info["status"], "ok")
        self.assertEqual(info["prompt_eval_count"], 17)
        self.assertEqual(info["eval_count"], 3)
        self.assertEqual(info["done_reason"], "stop")
        self.assertFalse(info["output_limit_reached"])
        self.assertEqual(info["system_fingerprint"], "fixture-runtime")
        self.assertNotIn("private-fixture-key", json.dumps(info))
        self.assertEqual(model.get_generation_info(), {})

    def test_output_cap_and_token_counts_reach_the_shared_diagnostics(self):
        model = APIModel("fixture", {"seed": 42})
        response = completion("VULNERABLE", reason="length", usage={"prompt_tokens": 20, "completion_tokens": 100})
        with patch.object(model.session, "post", return_value=response):
            text = model.generate("code")
        info = model.get_generation_info()
        diagnostics = generation_diagnostics([{"raw_output": text, "generation_info": info, "seconds": 0.5}])
        self.assertEqual(info["done_reason"], "length")
        self.assertEqual(diagnostics["decision_output_limit_hits"], 1)
        self.assertEqual(diagnostics["decision_prompt_tokens"], 20)
        self.assertEqual(diagnostics["decision_output_tokens"], 100)
        self.assertEqual(diagnostics["decision_generation_errors"], 0)

    def test_absent_or_invalid_optional_measurements_stay_unavailable(self):
        model = APIModel("fixture", {})
        response = completion(reason=None, usage={"prompt_tokens": -1, "completion_tokens": True})
        with patch.object(model.session, "post", return_value=response) as post:
            self.assertEqual(model.generate("code"), "SAFE")
        self.assertNotIn("seed", post.call_args.kwargs["json"])
        info = model.get_generation_info()
        self.assertIsNone(info["prompt_eval_count"])
        self.assertIsNone(info["eval_count"])
        self.assertIsNone(info["output_limit_reached"])

    def test_http_error_records_status_and_type_without_response_or_credentials(self):
        model = APIModel("fixture", {"api_key": "private-fixture-key"})
        response = Mock(status_code=429, text="private-fixture-response")
        response.raise_for_status.side_effect = requests.HTTPError("private-fixture-key private-fixture-response")
        output = io.StringIO()
        with patch.object(model.session, "post", return_value=response), redirect_stdout(output):
            self.assertEqual(model.generate("private-fixture-prompt"), "")
        info = model.get_generation_info()
        self.assertEqual(info["status"], "error")
        self.assertEqual(info["error_type"], "HTTPError")
        self.assertEqual(info["http_status"], 429)
        self.assertNotIn("private-fixture", json.dumps(info) + output.getvalue())
        diagnostics = generation_diagnostics([{"raw_output": "", "generation_info": info}])
        self.assertEqual(diagnostics["decision_generation_errors"], 1)

    def test_new_failure_and_empty_response_do_not_reuse_success_metadata(self):
        model = APIModel("fixture", {})
        with patch.object(model.session, "post", return_value=completion(usage={"prompt_tokens": 9, "completion_tokens": 2})):
            model.generate("code")
        with patch.object(model.session, "post", side_effect=requests.Timeout("private-fixture-timeout")), redirect_stdout(io.StringIO()):
            self.assertEqual(model.generate("code"), "")
        self.assertEqual(model.get_generation_info()["status"], "error")
        self.assertNotIn("eval_count", model.get_generation_info())
        with patch.object(model.session, "post", return_value=completion("", usage=None)):
            self.assertEqual(model.generate("code"), "")
        self.assertEqual(model.get_generation_info()["status"], "empty_response")
        self.assertNotIn("error_type", model.get_generation_info())


class PrivacyTests(unittest.TestCase):
    def test_settings_remove_nested_credentials_without_changing_inputs(self):
        settings = {
            "temperature": 0.2, "max_new_tokens": 1024, "model": "org/model",
            "API-Key": "private-test-value", "tokenizer": "org/tokenizer",
            "models": [{"headers": {"Authorization": "Bearer private-test-value"},
                        "client_secret": "private-test-value", "revision": "main"}],
        }
        before = copy.deepcopy(settings)
        sanitized = safe_settings(settings)
        self.assertEqual(settings, before)
        self.assertEqual(sanitized, {
            "temperature": 0.2, "max_new_tokens": 1024, "model": "org/model",
            "tokenizer": "org/tokenizer", "models": [{"headers": {}, "revision": "main"}],
        })

    def test_urls_keep_public_options_and_remove_credentials(self):
        url = "https://account:private-test-value@example.test/api?revision=main&api_key=private-test-value#access_token=private-test-value"
        self.assertEqual(safe_text(url), "https://example.test/api?revision=main")
        ordinary = "https://example.test/model?revision=main#documentation"
        self.assertEqual(safe_text(ordinary), ordinary)
        self.assertEqual(safe_text("Authorization: Bearer private-test-value"),
                         "Authorization: Bearer [REDACTED]")

    def test_checkpoint_and_records_omit_runtime_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            runner = ExperimentRunner({"api": {"api_key": "private-test-value"}}, progress=lambda _: None)
            runner.checkpoint_path = str(Path(folder) / "checkpoint.json")
            runner.selected_models = [{"name": "fixture", "backend": "api", "api_key": "private-test-value"}]
            runner.current_combo_state = {"model_item": runner.selected_models[0], "next_sample_index": 0}
            runner._save_checkpoint()
            state = json.loads(Path(runner.checkpoint_path).read_text())
            self.assertNotIn("private-test-value", json.dumps(state))
            self.assertEqual(state["selected_models"][0]["name"], "fixture")
            self.assertEqual(runner.gen_cfg["api_key"], "private-test-value")
            runner.records_jsonl_path = str(Path(folder) / "records.jsonl")
            record = {"params": runner.gen_cfg, "predictions": []}
            with patch.object(runner, "_write_single_prediction_csv"):
                runner._append_record(record)
            self.assertNotIn("private-test-value", Path(runner.records_jsonl_path).read_text())
            self.assertNotIn("api_key", runner.records[0]["params"])

    def test_api_reads_environment_key_without_storing_or_logging_it(self):
        response = Mock()
        response.json.return_value = {"choices": [{"text": "SAFE"}]}
        with patch.dict(os.environ, {"PROMPTAUDIT_API_KEY": "private-test-value"}, clear=True):
            model = APIModel("fixture", {})
            with patch.object(model.session, "post", return_value=response) as post:
                self.assertEqual(model.generate("code"), "SAFE")
                self.assertEqual(post.call_args.kwargs["headers"]["Authorization"],
                                 "Bearer private-test-value")
                self.assertNotIn("api_key", model.gen_cfg)
            output = io.StringIO()
            with patch.object(model.session, "post", side_effect=RuntimeError("private-test-value")):
                with redirect_stdout(output):
                    self.assertEqual(model.generate("code"), "")
            self.assertNotIn("private-test-value", output.getvalue())


if __name__ == "__main__":
    unittest.main()
