"""Adaptive chain-of-thought prompt strategy for vulnerability classification."""

from .base_prompt import ROLE_INSTRUCTION, TASK_INSTRUCTION, BasePrompt, code_block
from evaluation.output_protocol import normalize_output_protocol


ADAPTIVE_REASONING_INSTRUCTION = (
    "Choose how much reasoning to use:\n"
    "1) If the code is straightforward and you can quickly and clearly determine whether it is "
    "SAFE or VULNERABLE, answer directly without a step-by-step explanation.\n"
    "2) Otherwise, reason through the security risks step by step. If you are unsure whether "
    "a direct answer is sufficient, use step-by-step reasoning.\n"
)
COMPLEXITY_GUIDANCE = (
    "Complex cases can include pointer arithmetic, raw memory operations, manual resource "
    "management, or complex input handling.\n"
)


class AdaptiveCoT(BasePrompt):
    """Request stepwise reasoning unless the classification is straightforward."""

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
            f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n"
            f"{ADAPTIVE_REASONING_INSTRUCTION}{COMPLEXITY_GUIDANCE}\n"
            f"{placement_hint}\n\n"
            f"Code:\n{code_block(code)}\n"
        )
        return prompt
