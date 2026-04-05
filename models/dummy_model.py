"""Deterministic offline backend used for smoke tests and UI checks."""

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
