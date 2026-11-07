"""Check complete Ollama prompts with the installed model's own tokenizer."""

import re
import threading

from .base import ContextSafetyError


POLICY_VERSION = 2
_OVERFLOW = re.compile(r"request \((\d+) tokens\) exceeds the available context size \((\d+) tokens\)")
_VERIFIED_MODELS = set()
_VERIFICATION_LOCK = threading.Lock()


def context_overflow(message):
    """Return the input count and window reported by Ollama."""
    match = _OVERFLOW.search(message)
    if match:
        return tuple(map(int, match.groups()))
    return None


class OllamaContextGuard:
    """Check that Ollama preserves the full input."""

    def __init__(self, model):
        self.model = model
        self.verified = False
        self.metadata = None

    def settings(self):
        cfg = self.model.gen_cfg
        window = cfg.get("context_window", cfg.get("num_ctx"))
        budget = cfg.get("max_new_tokens", 100)
        if type(window) is not int or type(budget) is not int or not 0 < budget < window:
            raise ContextSafetyError("Ollama requires an explicit context window larger than max output tokens. "
                                     "Set a supported window for each model before starting a new run.")
        if self.metadata is None:
            self.metadata = self.model.get_model_info()
        if self.metadata.get("metadata_error"):
            raise ContextSafetyError(f"Cannot read Ollama metadata for {self.model.name}. "
                                     "Make sure Ollama is running and the model is installed.")
        model_info = self.metadata.get("model_info")
        if not isinstance(model_info, dict):
            raise ContextSafetyError(f"Ollama did not report model details for {self.model.name}.")
        limits = [v for k, v in model_info.items()
                  if k.endswith(".context_length") and type(v) is int and v > 0]
        if not limits:
            raise ContextSafetyError(f"Ollama did not report a context limit for {self.model.name}.")
        if window > min(limits):
            raise ContextSafetyError(f"Requested context {window} exceeds the model's declared window {min(limits)}.")
        return window, budget

    def count_input(self, prompt):
        # A small window obtains an exact token count from overflow errors without
        # evaluating long inputs on the GPU. Very short probes generate at most one token.
        body = {"model": self.model.name, "prompt": prompt, "stream": False,
                "truncate": False, "shift": False,
                "options": {"num_ctx": 256, "num_predict": 1, "temperature": 0, "seed": 42},
                "keep_alive": self.model.gen_cfg.get("ollama_keep_alive", "5m")}
        if "think" in self.model.gen_cfg:
            body["think"] = self.model.gen_cfg["think"]
        try:
            response = self.model.session.post("http://127.0.0.1:11434/api/generate", json=body, timeout=300)
            if response.status_code == 400:
                overflow = context_overflow(str(response.json().get("error", "")))
                if overflow:
                    tokens, available = overflow
                    if available != 256 or tokens <= available:
                        raise ContextSafetyError("Ollama changed the tokenizer probe window; input safety is unverified.")
                    return tokens
            response.raise_for_status()
            data = response.json()
            tokens = data.get("prompt_eval_count")
            if type(tokens) is not int or not 0 < tokens <= 256 or not data.get("done"):
                raise ContextSafetyError("Ollama returned incomplete token-count diagnostics.")
            return tokens
        except ContextSafetyError:
            raise
        except Exception as exc:
            raise ContextSafetyError("Ollama could not check the prompt size. Check the server and installed model.") from exc

    def ensure_verified(self):
        self.settings()
        if self.verified:
            return
        identity = (self.metadata.get("digest"), self.metadata.get("runtime_version"), POLICY_VERSION)
        cacheable = all(identity[:2])
        # Workers must finish the small-window probe before any worker switches
        # the same model to its experiment window.
        with _VERIFICATION_LOCK:
            if not cacheable or identity not in _VERIFIED_MODELS:
                self.count_input("Context safety check.")
                if self.count_input(" x 7391" * 512) <= 256:
                    raise ContextSafetyError("Ollama truncated an oversized safety probe. Update the server before experiments.")
                if cacheable:
                    _VERIFIED_MODELS.add(identity)
            self.verified = True

    def loaded_window(self):
        try:
            response = self.model.session.get("http://127.0.0.1:11434/api/ps", timeout=10)
            response.raise_for_status()
            def canonical(name):
                return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"
            loaded = next((m for m in response.json().get("models", [])
                           if canonical(m.get("name", m.get("model", ""))) == canonical(self.model.name)), {})
            window = loaded.get("context_length")
            if type(window) is not int or window < 1:
                raise ContextSafetyError("Ollama did not report the loaded model's context window. Check the server.")
            return window
        except ContextSafetyError:
            raise
        except Exception as exc:
            raise ContextSafetyError("Cannot read the loaded context window from Ollama.") from exc

