# prompts/prompt_loader.py — PromptAudit v2.0
# Author: Steffen Camarato — University of Central Florida
#
# Purpose:
#   Provide a single, well defined entry point for loading prompt strategies
#   by name. The rest of the system (GUI, runner, configs) can refer to
#   strategies with simple string identifiers, and this module maps those
#   identifiers to the appropriate Python classes.
#
#   This keeps all strategy wiring in one place and avoids scattering imports
#   across the codebase.

from .zero_shot import ZeroShot
from .few_shot import FewShot
from .cot import CoT
from .adaptive_cot import AdaptiveCoT
from .self_consistency import SelfConsistency


# Internal registry mapping human readable names to strategy classes.
#
# Keys:
#   String identifiers used in config.yaml, GUI selections and the runner.
#
# Values:
#   Concrete classes that implement the prompt strategy interface
#   (each subclassing BasePrompt and exposing an .apply(...) method).
_PROMPT_REGISTRY = {
    "zero_shot": ZeroShot,
    "few_shot": FewShot,
    "cot": CoT,
    "adaptive_cot": AdaptiveCoT,
    "self_consistency": SelfConsistency,
}


def load_prompt_strategy(name: str):
    """
    Load a prompt strategy instance by its logical name.

    This function is the single entry point for resolving user facing
    strategy names into concrete strategy objects. It is used by:

        - The GUI, when the user picks a prompt strategy from a dropdown.
        - The runner, when iterating over selected prompt strategies.
        - Any future CLI or automation code that needs to run experiments
          with a specific prompting method.

    Args:
        name (str):
            Logical name for the strategy. This is case insensitive and
            expected to match one of the keys in _PROMPT_REGISTRY, such as:
                - "zero_shot"
                - "few_shot"
                - "cot"
                - "adaptive_cot"
                - "self_consistency"

    Returns:
        An instance of the requested prompt strategy class.

    Raises:
        ValueError:
            If the provided name does not match any known strategy. The error
            message includes the unknown name and the list of valid options
            to make misconfigurations easy to diagnose.
    """
    # Normalize input to lowercase so "CoT", "COT" and "cot" are treated
    # identically throughout the pipeline.
    key = name.lower()

    cls = _PROMPT_REGISTRY.get(key)
    if cls is None:
        # Construct a helpful error message that lists valid options.
        valid = ", ".join(sorted(_PROMPT_REGISTRY.keys()))
        raise ValueError(f"Unknown prompt strategy: {name!r}. Valid options are: {valid}")

    # Instantiate and return the strategy object. Strategies do not require
    # constructor arguments right now, but this approach keeps the door open
    # for future configuration if needed.
    return cls()
