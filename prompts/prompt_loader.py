"""Resolve prompt strategy names to their Python implementations."""

from .zero_shot import ZeroShot
from .few_shot import FewShot
from .cot import CoT
from .adaptive_cot import AdaptiveCoT
from .self_consistency import SelfConsistency
from .self_verification import SelfVerification


# Names used in configuration files and the dashboard.
_PROMPT_REGISTRY = {
    "zero_shot": ZeroShot,
    "few_shot": FewShot,
    "cot": CoT,
    "adaptive_cot": AdaptiveCoT,
    "self_consistency": SelfConsistency,
    "self_verification": SelfVerification,
}


def load_prompt_strategy(name: str):
    """Look up a prompting approach by name and return a new instance."""
    key = name.lower()

    cls = _PROMPT_REGISTRY.get(key)
    if cls is None:
        valid = ", ".join(sorted(_PROMPT_REGISTRY.keys()))
        raise ValueError(f"Unknown prompt strategy: {name!r}. Valid options are: {valid}")

    return cls()
