# models/loader.py — Glacier Code v2.0 (Unified Model Loader for GUI + CLI)

# ---------------------------------------------------------------------
# This file provides the central entry point for loading model backends.
#
# I designed load_model() so the entire system (GUI, CLI, ExperimentRunner)
# can request a model using:
#       - A simple model name (string), or
#       - A detailed configuration dictionary
#
# Supported backends in Code v2.0:
#   - OllamaModel (local models run through Ollama)
#   - DummyModel  (offline instant-response model)
#
# The design is intentionally extensible — new backends (APIModel, HFModel)
# can be registered here without touching the runner or GUI.


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
                    "backend": one of {"ollama", "dummy"}
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
            An instantiated model backend object (OllamaModel or DummyModel).

    Behavior:
        - If backend is unknown → warns and falls back to DummyModel.
        - Ensures GUI and CLI both use identical loading logic.
    """

    # ------------------------------------------------------------------
    # Normalize input — whether dict or string
    # ------------------------------------------------------------------
    if isinstance(cfg_or_name, dict):
        # When a full config dict is provided (from GUI or config files)
        backend = cfg_or_name.get("backend", "ollama")
        name = cfg_or_name.get("name") or "unnamed"

    else:
        # When the user just passes a string (simplest case)
        backend = "ollama"        # Default assumption
        name = str(cfg_or_name)   # Preserve the name as string

    # ------------------------------------------------------------------
    # Model backend selection logic
    # ------------------------------------------------------------------
    if backend == "ollama":
        # Local model served through Ollama daemon
        return OllamaModel(name, gen_cfg)

    elif backend == "dummy":
        # Pure offline model for rapid testing
        return DummyModel(name or "dummy", gen_cfg)

    else:
        # ------------------------------------------------------------------
        # Graceful fallback for unsupported backends
        # ------------------------------------------------------------------
        print(f"[WARN] Unknown backend '{backend}', defaulting to DummyModel.")
        return DummyModel(name or "unknown", gen_cfg)
