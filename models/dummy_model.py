"""Deterministic offline backend used for smoke tests and UI checks."""

class DummyModel:
    def __init__(self, name, gen_cfg):
        """Keep the same constructor arguments as the inference backends."""
        self.name = name
        self.gen_cfg = gen_cfg

    def generate(self, prompt: str) -> str:
        """Return a test label based on keyword matches in the prompt."""

        p = prompt.lower()

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

        return "VULNERABLE" if risky else "SAFE"
