"""OpenAI-style HTTP backend used when PromptAudit runs against a remote API."""

import os

import requests

from .base import BaseModel


class APIModel(BaseModel):
    """OpenAI-style REST API backend for text generation."""

    def __init__(self, name: str, gen_cfg: dict):
        super().__init__(name, gen_cfg)
        self.session = requests.Session()

    def generate(self, prompt: str) -> str:
        """Send the prompt to the configured completion endpoint.

        Credentials come from settings or the environment. Failures return an empty
        response with an error status; credentials and response bodies are not logged.
        """

        url = f"{self.gen_cfg.get('api_host', 'https://api.openai.com')}/v1/completions"
        api_key = (self.gen_cfg.get("api_key") or os.environ.get("PROMPTAUDIT_API_KEY")
                   or os.environ.get("OPENAI_API_KEY", ""))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.name,
            "prompt": prompt,
            "temperature": self.gen_cfg.get("temperature", 0.2),
            "top_p": self.gen_cfg.get("top_p", 0.9),
            "max_tokens": self.gen_cfg.get("max_new_tokens", 100),
            "frequency_penalty": self.gen_cfg.get("frequency_penalty", 0.0),
            "presence_penalty": self.gen_cfg.get("presence_penalty", 0.0),
        }

        if stop_list := self.gen_cfg.get("stop_sequences"):
            payload["stop"] = stop_list
        if "seed" in self.gen_cfg:
            payload["seed"] = self.gen_cfg["seed"]

        info = {"backend": "api", "model": self.name, "prompt_chars": len(prompt),
                "num_predict": payload["max_tokens"], "seed": payload.get("seed"), "status": "pending"}
        self._set_generation_info(info)
        response = None
        try:
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            choice = (result.get("choices") or [{}])[0]
            text = (choice.get("text") or "").strip()
            reason = choice.get("finish_reason")
            usage = result.get("usage")
            usage = usage if isinstance(usage, dict) else {}

            def token_count(field):
                value = usage.get(field)
                return value if type(value) is int and value >= 0 else None

            info.update(status="ok" if text else "empty_response", response_chars=len(text),
                        http_status=response.status_code if type(response.status_code) is int else None,
                        prompt_eval_count=token_count("prompt_tokens"), eval_count=token_count("completion_tokens"),
                        done_reason=reason,
                        output_limit_reached=reason == "length" if reason in {"stop", "length", "content_filter"} else None)
            fingerprint = result.get("system_fingerprint")
            if isinstance(fingerprint, str):
                info["system_fingerprint"] = fingerprint
            self._set_generation_info(info)
            return text
        except Exception as exc:
            info.update(status="error", error_type=type(exc).__name__)
            if response is not None and type(response.status_code) is int:
                info["http_status"] = response.status_code
            self._set_generation_info(info)
            print(f"[APIModel] Generation failed ({type(exc).__name__}).")
            return ""
