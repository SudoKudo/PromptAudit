"""OpenAI-style HTTP backend used when PromptAudit runs against a remote API."""

import requests

from .base import BaseModel


class APIModel(BaseModel):
    """OpenAI-style REST API backend for text generation."""

    def __init__(self, name: str, gen_cfg: dict):
        super().__init__(name, gen_cfg)
        self.session = requests.Session()

    def generate(self, prompt: str) -> str:
        """
        Send the prompt to an OpenAI-compatible API endpoint and return the model's text output.

        Behavior:
            - Reads configuration from self.gen_cfg (temperature, top-p, etc.)
            - Supports a customizable API host (default: https://api.openai.com)
            - Supports optional stop sequences
            - Gracefully handles request errors by printing a detailed message

        Args:
            prompt (str): The text prompt to send to the API.

        Returns:
            str: Generated text (stripped), or "" if the request fails.
        """

        # Build the API endpoint URL.
        url = f"{self.gen_cfg.get('api_host', 'https://api.openai.com')}/v1/completions"

        # HTTP headers: bearer token + JSON content type.
        headers = {
            "Authorization": f"Bearer {self.gen_cfg.get('api_key', '')}",
            "Content-Type": "application/json",
        }

        # Request payload: follows OpenAI's /v1/completions format.
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

        try:
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("choices", [{}])[0].get("text", "").strip()
        except Exception as e:
            print(f"[APIModel] Generation failed: {e}")
            return ""
