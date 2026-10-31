"""Ollama backend for local PromptAudit inference runs."""

import requests

from .base import BaseModel, merge_generation_settings


class OllamaModel(BaseModel):
    """Local-inference backend using Ollama's HTTP API."""

    def __init__(self, name: str, gen_cfg: dict):
        super().__init__(name, merge_generation_settings(gen_cfg))
        self.session = requests.Session()

    def get_model_info(self):
        """Record the server's wrapper and model identity, including mutable tags."""
        info = {"backend": "ollama", "name": self.name, "input_format": "model_template"}
        try:
            response = self.session.post("http://127.0.0.1:11434/api/show",
                                         json={"model": self.name}, timeout=10)
            response.raise_for_status()
            data = response.json()
            for field in ("template", "system", "parameters", "details", "model_info", "capabilities",
                          "renderer", "parser", "template_source", "thinking"):
                if field in data:
                    info[field] = data[field]
            response = self.session.get("http://127.0.0.1:11434/api/tags", timeout=10)
            response.raise_for_status()
            def canonical(name):
                return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"

            info["digest"] = next((m.get("digest") for m in response.json().get("models", [])
                                   if any(canonical(value) == canonical(self.name)
                                          for value in (m.get("name"), m.get("model")) if value)), None)
            response = self.session.get("http://127.0.0.1:11434/api/version", timeout=10)
            response.raise_for_status()
            info["runtime_version"] = response.json().get("version")
        except Exception as exc:
            info["metadata_error"] = f"{type(exc).__name__}: {exc}"
        return info

    def generate(self, prompt: str) -> str:
        """Generate through the local server and retain its timing and status.

        Failures return an empty response with error details in generation info.
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
        context_window = self.gen_cfg.get("context_window", self.gen_cfg.get("num_ctx"))
        if context_window is not None:
            options["num_ctx"] = int(context_window)
        payload = {
            "model": self.name,
            "prompt": prompt,
            "options": options,
            "stream": False,
        }
        if "think" in self.gen_cfg:
            payload["think"] = self.gen_cfg["think"]

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
                    "thinking_output": data.get("thinking", ""),
                    "think": self.gen_cfg.get("think"),
                    "context_window": options.get("num_ctx"),
                    "http_status": response.status_code,
                    "done": data.get("done"),
                    "done_reason": data.get("done_reason"),
                    "output_limit_reached": (data.get("done_reason") == "length"
                                             if data.get("done_reason") is not None else None),
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
