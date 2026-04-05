"""Instantiate the configured model backend for a PromptAudit run."""

from .ollama_model import OllamaModel
from .dummy_model import DummyModel


def load_model(cfg_or_name, gen_cfg):
    """
    Load a model from either a simple string or a configuration dict.

    Args:
        cfg_or_name (str | dict):
            - If str:
                This is treated as the model name (e.g., "gemma:7b").
                The default backend is assumed to be "ollama".
            - If dict:
                Expected fields:
                    "backend": one of {"ollama", "dummy", "hf", "api"}
                    "name":    model name string

        gen_cfg (dict):
            Generation settings passed directly to the chosen model backend.
            Examples:
                - temperature
                - top_p
                - max_new_tokens
                - stop_sequences
                - seed

    Returns:
        BaseModel:
            An instantiated model backend object.

    Behavior:
        - Backend-specific model settings in cfg_or_name override gen_cfg.
        - Unknown backends raise ValueError instead of silently changing the run.
        - Ensures GUI and CLI both use identical loading logic.
    """

    # ------------------------------------------------------------------
    # Normalize input — whether dict or string
    # ------------------------------------------------------------------
    effective_gen_cfg = dict(gen_cfg or {})

    if isinstance(cfg_or_name, dict):
        # When a full config dict is provided (from GUI or config files)
        backend = str(cfg_or_name.get("backend", "ollama")).strip().lower()
        name = cfg_or_name.get("name") or "unnamed"
        for key, value in cfg_or_name.items():
            if key not in {"backend", "name"}:
                effective_gen_cfg[key] = value

    else:
        # When the user just passes a string (simplest case)
        backend = "ollama"        # Default assumption
        name = str(cfg_or_name)   # Preserve the name as string

    # ------------------------------------------------------------------
    # Model backend selection logic
    # ------------------------------------------------------------------
    if backend == "ollama":
        # Local model served through Ollama daemon
        return OllamaModel(name, effective_gen_cfg)

    elif backend == "dummy":
        # Pure offline model for rapid testing
        return DummyModel(name or "dummy", effective_gen_cfg)

    elif backend in {"hf", "huggingface"}:
        from .hf_model import HFModel
        return HFModel(name, effective_gen_cfg)

    elif backend in {"api", "openai"}:
        from .api_model import APIModel
        return APIModel(name, effective_gen_cfg)

    else:
        raise ValueError(f"Unknown backend: {backend}")
