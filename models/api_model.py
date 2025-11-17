# models/api_model.py — REST API backend model wrapper for Glacier Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# This class lets Code v2.0 talk to ANY OpenAI-style text-generation API
# (OpenAI, together.ai, compatible self-hosted servers, etc.).
#
# I built this as a drop-in model backend so the experiment runner and GUI
# do not need to know anything about REST calls. They just call model.generate()
# and receive text back, same as with Ollama or HuggingFace backends.
#
# The structure closely mirrors OpenAI's legacy /v1/completions format so it
# works with many third-party providers.

import requests, json
from .base import BaseModel


class APIModel(BaseModel):
    """OpenAI-style REST API backend for text generation."""

    def generate(self, prompt: str) -> str:
        """
        Send the prompt to an OpenAI-compatible API endpoint and return the model’s text output.

        Behavior:
            - Reads configuration from self.gen_cfg (temperature, top-p, etc.)
            - Supports customizable API host (default: https://api.openai.com)
            - Supports optional stop sequences
            - Gracefully handles request errors by printing a detailed message

        Args:
            prompt (str): The text prompt to send to the API.

        Returns:
            str: Generated text (stripped), or "" if the request fails.
        """

        # ------------------------------------------------------------------
        # Build the API endpoint URL
        # ------------------------------------------------------------------
        # The user can override "api_host" in config; default is OpenAI’s API.
        url = f"{self.gen_cfg.get('api_host', 'https://api.openai.com')}/v1/completions"

        # ------------------------------------------------------------------
        # HTTP headers: bearer token + JSON content type
        # ------------------------------------------------------------------
        headers = {
            "Authorization": f"Bearer {self.gen_cfg.get('api_key', '')}",
            "Content-Type": "application/json"
        }

        # ------------------------------------------------------------------
        # Request payload: follows OpenAI's /v1/completions format
        # ------------------------------------------------------------------
        payload = {
            "model": self.name,  # Name of the remote model (e.g., "gpt-3.5-turbo-instruct")
            "prompt": prompt,
            "temperature": self.gen_cfg.get("temperature", 0.2),
            "top_p": self.gen_cfg.get("top_p", 0.9),
            "max_tokens": self.gen_cfg.get("max_new_tokens", 100),
            "frequency_penalty": self.gen_cfg.get("frequency_penalty", 0.0),
            "presence_penalty": self.gen_cfg.get("presence_penalty", 0.0),
        }

        # Optional stop sequences (list of strings)
        # Example: ["SAFE", "VULNERABLE"]
        if stop_list := self.gen_cfg.get("stop_sequences"):
            payload["stop"] = stop_list

        try:
            # ------------------------------------------------------------------
            # Make the HTTP POST request
            # ------------------------------------------------------------------
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120  # Long timeout for slow servers
            )

            # Raise exception if the server returned any 4xx/5xx status code
            response.raise_for_status()

            # ------------------------------------------------------------------
            # Parse the JSON response
            # ------------------------------------------------------------------
            # Expected shape:
            # {
            #   "choices": [
            #       { "text": "..." }
            #   ]
            # }
            result = response.json()

            return result.get("choices", [{}])[0].get("text", "").strip()

        except Exception as e:
            # Error handling: print a clear error message and return empty text.
            print(f"[APIModel] ❌ Generation failed: {e}")
            return ""
