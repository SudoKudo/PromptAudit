"""Instantiate the configured model backend for a PromptAudit run."""

from .ollama_model import OllamaModel
from .dummy_model import DummyModel
from .base import merge_generation_settings


def load_model(cfg_or_name, gen_cfg):
    """Load a backend by name or configuration, applying model-specific settings.

    A plain name selects Ollama. A mapping must name the model and may choose
    another backend. Settings in that mapping override the shared defaults.
    """
    if isinstance(cfg_or_name, dict):
        backend = str(cfg_or_name.get("backend", "ollama")).strip().lower()
        name = cfg_or_name.get("name") or "unnamed"
        overrides = {key: value for key, value in cfg_or_name.items() if key not in {"backend", "name"}}
        effective_gen_cfg = merge_generation_settings(gen_cfg, overrides)

    else:
        backend = "ollama"
        name = str(cfg_or_name)
        effective_gen_cfg = merge_generation_settings(gen_cfg)

    if backend == "ollama":
        return OllamaModel(name, effective_gen_cfg)

    elif backend == "dummy":
        return DummyModel(name or "dummy", effective_gen_cfg)

    elif backend in {"hf", "huggingface"}:
        from .hf_model import HFModel
        return HFModel(name, effective_gen_cfg)

    elif backend in {"api", "openai"}:
        from .api_model import APIModel
        return APIModel(name, effective_gen_cfg)

    else:
        raise ValueError(f"Unknown backend: {backend}")
