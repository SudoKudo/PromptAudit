"""Chain-of-thought prompt strategy for vulnerability classification."""

from .base_prompt import BasePrompt
from evaluation.output_protocol import normalize_output_protocol


class CoT(BasePrompt):
    """Chain-of-Thought (CoT) prompt strategy."""

    # Logical identifier for this strategy (used in configs and reporting).
    name = "cot"

    def apply(self, model, code, gen_cfg):
        """Build and return the Chain-of-Thought prompt string."""
        return self.apply_with_context(model, code, gen_cfg)

    def apply_with_context(
        self,
        model,
        code,
        gen_cfg,
        *,
        output_protocol="verdict_first",
        parser_mode="full",
    ):
        """Build a CoT prompt that respects the selected verdict-placement protocol."""
        del model, gen_cfg, parser_mode

        protocol = normalize_output_protocol(output_protocol)
        placement_hint = (
            "Give the required verdict first, then explain your reasoning starting on the second line."
            if protocol == "verdict_first"
            else "Reason step by step first, then place the final verdict on the last line."
        )

        prompt = (
            "You are a secure code auditor. Analyze the following code step by step, "
            "carefully reasoning about potential security vulnerabilities such as buffer "
            "overflows, injections, improper validation, race conditions, and other "
            "common issues.\n\n"
            f"{placement_hint}\n\n"
            "Consider at least these factors in your reasoning:\n"
            "1) Inputs and trust boundaries\n"
            "2) Validation and sanitization\n"
            "3) Memory safety and resource management\n"
            "4) Injection, race, and logic risks\n\n"
            f"Code:\n{code}\n"
        )
        return prompt
