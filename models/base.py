"""Common interface implemented by all PromptAudit model backends."""

import math


def merge_generation_settings(base, overrides=None):
    """Validate settings and merge model overrides using one context-window name."""
    def normalize(settings):
        if settings is None:
            return {}
        if not isinstance(settings, dict):
            raise ValueError("Generation settings must be a dictionary")
        result = dict(settings)
        for key in ("max_new_tokens", "context_window", "num_ctx", "num_beams"):
            if key in result and (type(result[key]) is not int or result[key] < 1):
                raise ValueError(f"{key} must be a positive integer")
        if "context_window" in result and "num_ctx" in result:
            if result["context_window"] != result["num_ctx"]:
                raise ValueError("context_window and num_ctx must agree when both are set")
        if "num_ctx" in result:
            result["context_window"] = result.pop("num_ctx")

        for key in ("temperature", "top_p", "repetition_penalty"):
            if key not in result:
                continue
            value = result[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key} must be a finite number")
            if key == "temperature" and value < 0:
                raise ValueError("temperature must be nonnegative")
            if key == "top_p" and not 0 < value <= 1:
                raise ValueError("top_p must be greater than zero and at most one")
            if key == "repetition_penalty" and value <= 0:
                raise ValueError("repetition_penalty must be positive")
        if "top_k" in result and (type(result["top_k"]) is not int or result["top_k"] < 0):
            raise ValueError("top_k must be a nonnegative integer")
        if "seed" in result and type(result["seed"]) is not int:
            raise ValueError("seed must be an integer")
        if "stop_sequences" in result:
            stops = result["stop_sequences"]
            if not isinstance(stops, list) or any(not isinstance(s, str) or not s for s in stops):
                raise ValueError("stop_sequences must be a list of nonempty strings")
        if "chat_template_kwargs" in result:
            kwargs = result["chat_template_kwargs"]
            if not isinstance(kwargs, dict) or any(not isinstance(k, str) for k in kwargs):
                raise ValueError("chat_template_kwargs must be a dictionary with string keys")
            reserved = {"tokenize", "add_generation_prompt", "continue_final_message", "return_tensors", "return_dict"}
            conflicts = reserved.intersection(kwargs)
            if conflicts:
                raise ValueError("chat_template_kwargs cannot override " + ", ".join(sorted(conflicts)))
        return result

    return {**normalize(base), **normalize(overrides)}


class BaseModel:
    def __init__(self, name, gen_cfg):
        """Store the model name and generation settings."""
        self.name = name
        self.gen_cfg = gen_cfg
        self._last_generation_info = {}

    def _set_generation_info(self, info):
        """Record backend-specific metadata for the most recent generation call."""
        self._last_generation_info = dict(info or {})

    def get_generation_info(self):
        """Return a copy of the most recent generation metadata without clearing it."""
        return dict(self._last_generation_info or {})

    def consume_generation_info(self):
        """Return and clear the most recent generation metadata."""
        info = self.get_generation_info()
        self._last_generation_info = {}
        return info

    def get_model_info(self):
        """Return available model and input-format details for experiment records."""
        return {}

    def generate(self, prompt):
        """Return generated text for a prompt. Subclasses implement this method."""
        raise NotImplementedError("Subclasses must implement `generate()`")
