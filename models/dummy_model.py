# models/dummy_model.py — Offline “fake” model for Glacier Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# 🔹 Purpose:
# This is my offline testing model — a no-API, no-network, instant-response model.
#
# I use this DummyModel whenever I want:
#   - Quick local testing without calling Ollama / HuggingFace / APIs
#   - Fully deterministic, zero-latency responses
#   - A simple way to validate the experiment runner, GUI, and report pipeline
#
# Behavior:
#   - Scans the prompt for risky functions / patterns
#   - If anything dangerous appears → returns "VULNERABLE"
#   - Otherwise → returns "SAFE"
#
# This lets me test the entire Code v2.0 pipeline without requiring real model inference.


class DummyModel:
    def __init__(self, name, gen_cfg):
        """
        Initialize the dummy model.

        Args:
            name (str): Model name (for logging and display).
            gen_cfg (dict): Generation settings (ignored by the dummy model).

        Note:
            Although DummyModel doesn't actually use gen_cfg, I keep the argument
            for compatibility so it can be swapped into the system without
            altering runner/model loading code.
        """
        self.name = name
        self.gen_cfg = gen_cfg

    def generate(self, prompt: str) -> str:
        """
        Generate a classification based purely on keyword matching.

        Args:
            prompt (str):
                The input string containing code that may or may not be vulnerable.

        Returns:
            str: Either "VULNERABLE" or "SAFE".

        Behavior:
            - Converts the prompt to lowercase for case-insensitive checks.
            - Looks for common dangerous functions and patterns.
            - If any appear, classify the code as "VULNERABLE".
            - Otherwise return "SAFE".
        """

        # Lowercase entire prompt so substring checks are case-insensitive.
        p = prompt.lower()

        # List of dangerous patterns commonly associated with security vulnerabilities.
        risky = any(
            x in p
            for x in [
                "gets(",
                "strcpy(",
                "sprintf(",
                "eval(",
                "exec(",
                "runtime.getruntime",
                "processbuilder",
            ]
        )

        # If any risky pattern is found → mark as vulnerable.
        return "VULNERABLE" if risky else "SAFE"
