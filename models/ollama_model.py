"""Ollama backend for local PromptAudit inference runs."""

import requests
from .base import BaseModel


class OllamaModel(BaseModel):
    """Local-inference backend using Ollama's HTTP API."""

    def __init__(self, name: str, gen_cfg: dict):
        super().__init__(name, gen_cfg)
        self.session = requests.Session()

    def generate(self, prompt: str) -> str:
        """
        Generate text using an Ollama model via the local HTTP endpoint.

        Args:
            prompt (str): The input prompt to feed into the model.

        Returns:
            str: The generated text (stripped), or "" if an error occurs.

        API Details:
            POST http://localhost:11434/api/generate
            Payload:
                {
                    "model": "<model-name>",
                    "prompt": "<input-text>",
                    "options": {
                        "temperature": ...,
                        "top_p": ...,
                        "top_k": ...,
                        "num_predict": ...,
                        "repeat_penalty": ...,
                        "seed": ...,
                        "stop": [...]
                    },
                    "stream": false
                }
        """

        # ------------------------------------------------------------------
        # Ollama local HTTP endpoint
        # ------------------------------------------------------------------
        # url = "http://127.0.0.1:11434/api/generate"
        url = "http://127.0.0.1:11434/api/generate"

        # ------------------------------------------------------------------
        # Build generation options (fully compatible with Ollama spec)
        # ------------------------------------------------------------------
        options = {
            "temperature": self.gen_cfg.get("temperature", 0.2),
            "top_p": self.gen_cfg.get("top_p", 0.9),
            "top_k": self.gen_cfg.get("top_k", 40),
            "num_predict": self.gen_cfg.get("max_new_tokens", 100),
            "repeat_penalty": self.gen_cfg.get("repetition_penalty", 1.0),
            "seed": self.gen_cfg.get("seed", 42),
        }

        # ------------------------------------------------------------------
        # Full request payload
        # ------------------------------------------------------------------
        payload = {
            "model": self.name,      # Model name in Ollama (e.g., "gemma:7b")
            "prompt": prompt,
            "options": options,
            "stream": False,         # Disable streaming for simplified processing
        }

        keep_alive = self.gen_cfg.get("ollama_keep_alive")
        if keep_alive:
            payload["keep_alive"] = keep_alive

        # Optional stop sequences (["SAFE", "VULNERABLE"], etc.)
        if stop_list := self.gen_cfg.get("stop_sequences"):
            payload["options"]["stop"] = stop_list

        try:
            # Reuse one HTTP session so localhost connections stay warm across samples.
            response = self.session.post(url, json=payload, timeout=300)

            # Raise an exception for any HTTP error (4xx or 5xx)
            response.raise_for_status()

            # Ollama responds with JSON containing "response" text
            data = response.json()
            return data.get("response", "").strip()

        except Exception as e:
            # Graceful failure: print error but return empty string
            print(f"[OllamaModel] ❌ Generation failed: {e}")
            return ""
