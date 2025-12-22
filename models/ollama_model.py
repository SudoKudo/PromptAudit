# models/ollama_model.py — Ollama backend for Glacier Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# This class provides local model inference through the Ollama runtime.
#
# Why Ollama?
#   - Fast local inference
#   - Easy model management (pull, update, run)
#   - No GPU required (supports CPU-only)
#   - Drop-in backend replacement for API/HF models
#
# I designed this class to match the BaseModel interface so the GUI and
# experiment runner can treat it exactly like other model backends.


import requests, json, time
from .base import BaseModel


class OllamaModel(BaseModel):
    """Local-inference backend using Ollama's HTTP API."""

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

        # Optional stop sequences (["SAFE", "VULNERABLE"], etc.)
        if stop_list := self.gen_cfg.get("stop_sequences"):
            payload["options"]["stop"] = stop_list

        try:
            # Send request to Ollama and record how long generation takes
            start = time.time()
            response = requests.post(url, json=payload, timeout=300)

            # Raise an exception for any HTTP error (4xx or 5xx)
            response.raise_for_status()

            # Ollama responds with JSON containing "response" text
            data = response.json()
            return data.get("response", "").strip()

        except Exception as e:
            # Graceful failure: print error but return empty string
            print(f"[OllamaModel] ❌ Generation failed: {e}")
            return ""
