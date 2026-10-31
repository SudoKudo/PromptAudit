"""Protect settings and diagnostics at persistence boundaries."""

import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.runner import ExperimentRunner
from models.api_model import APIModel
from utils.privacy import safe_settings, safe_text


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
