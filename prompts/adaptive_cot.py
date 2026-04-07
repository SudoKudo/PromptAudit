"""Adaptive chain-of-thought prompt strategy for vulnerability classification."""

from .base_prompt import BasePrompt
from evaluation.output_protocol import normalize_output_protocol


class AdaptiveCoT(BasePrompt):
    """Adaptive Chain-of-Thought prompt strategy."""

    # Logical name for this strategy (used in configs and reporting).
    name = "adaptive_cot"

    def apply(self, model, code, gen_cfg):
        """Build and return the adaptive CoT prompt string."""
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
        """Build an adaptive CoT prompt that respects the selected verdict-placement protocol."""
        del model, gen_cfg, parser_mode

        protocol = normalize_output_protocol(output_protocol)
        placement_hint = (
            "Put the required verdict first. If you explain your answer, do it after that first line."
            if protocol == "verdict_first"
            else "Do any adaptive reasoning before the final verdict line."
        )

        prompt = (
            "You are a secure code auditor. Determine whether the following code is "
            "SAFE or VULNERABLE.\n\n"
            "Adjust the depth of your reasoning to the code:\n"
            "1) If the code is straightforward and obviously SAFE or VULNERABLE, keep any explanation brief.\n"
            "2) If the code uses pointer arithmetic, raw memory operations, manual resource "
            "management, or complex input handling, reason through the risks step by step.\n"
            f"3) {placement_hint}\n\n"
            f"Code:\n{code}\n"
        )
        return prompt
