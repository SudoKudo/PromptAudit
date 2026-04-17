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

        url = "http://127.0.0.1:11434/api/generate"
        options = {
            "temperature": self.gen_cfg.get("temperature", 0.2),
            "top_p": self.gen_cfg.get("top_p", 0.9),
            "top_k": self.gen_cfg.get("top_k", 40),
            "num_predict": self.gen_cfg.get("max_new_tokens", 100),
            "repeat_penalty": self.gen_cfg.get("repetition_penalty", 1.0),
            "seed": self.gen_cfg.get("seed", 42),
        }
        payload = {
            "model": self.name,
            "prompt": prompt,
            "options": options,
            "stream": False,
        }

        keep_alive = self.gen_cfg.get("ollama_keep_alive")
        if keep_alive:
            payload["keep_alive"] = keep_alive

        if stop_list := self.gen_cfg.get("stop_sequences"):
            payload["options"]["stop"] = stop_list

        prompt_chars = len(str(prompt or ""))
        self._set_generation_info(
            {
                "backend": "ollama",
                "model": self.name,
                "endpoint": url,
                "prompt_chars": prompt_chars,
                "num_predict": options.get("num_predict"),
                "temperature": options.get("temperature"),
                "top_p": options.get("top_p"),
                "top_k": options.get("top_k"),
                "seed": options.get("seed"),
                "status": "pending",
            }
        )

        response = None
        try:
            response = self.session.post(url, json=payload, timeout=300)
            response.raise_for_status()

            data = response.json()
            raw_response = data.get("response", "")
            text = str(raw_response or "").strip()
            self._set_generation_info(
                {
                    "backend": "ollama",
                    "model": self.name,
                    "endpoint": url,
                    "prompt_chars": prompt_chars,
                    "response_chars": len(text),
                    "raw_response_chars": len(str(raw_response or "")),
                    "http_status": response.status_code,
                    "done": data.get("done"),
                    "done_reason": data.get("done_reason"),
                    "total_duration": data.get("total_duration"),
                    "load_duration": data.get("load_duration"),
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "prompt_eval_duration": data.get("prompt_eval_duration"),
                    "eval_count": data.get("eval_count"),
                    "eval_duration": data.get("eval_duration"),
                    "num_predict": options.get("num_predict"),
                    "temperature": options.get("temperature"),
                    "top_p": options.get("top_p"),
                    "top_k": options.get("top_k"),
                    "seed": options.get("seed"),
                    "response_preview": text[:240],
                    "status": "ok" if text else "empty_response",
                }
            )
            return text

        except Exception as e:
            error_info = {
                "backend": "ollama",
                "model": self.name,
                "endpoint": url,
                "prompt_chars": prompt_chars,
                "num_predict": options.get("num_predict"),
                "temperature": options.get("temperature"),
                "top_p": options.get("top_p"),
                "top_k": options.get("top_k"),
                "seed": options.get("seed"),
                "status": "error",
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
            if response is not None:
                error_info["http_status"] = getattr(response, "status_code", None)
                try:
                    error_info["response_text_preview"] = str(response.text or "")[:500]
                except Exception:
                    pass
            self._set_generation_info(error_info)
            print(f"[OllamaModel] Generation failed: {e}")
            return ""
