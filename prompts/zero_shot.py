"""Zero-shot prompt strategy for direct vulnerability classification."""

from .base_prompt import ROLE_INSTRUCTION, TASK_INSTRUCTION, BasePrompt, code_block


class ZeroShot(BasePrompt):
    """Zero-shot classification prompt strategy."""

    name = "zero_shot"

    # The runner appends the selected verdict-placement instruction.
    template = (
        f"{ROLE_INSTRUCTION}\n{TASK_INSTRUCTION}\n\n"
        "Give a direct classification without a step-by-step explanation.\n"
        "Return only the verdict word in the required position, without an explanation.\n"
        "Briefly consider issues such as buffer overflows, injections, improper "
        "validation, and other common weaknesses.\n\n"
        "{code}\n\n"
    )

    def apply(self, model, code, gen_cfg):
        """Build the direct-classification prompt. The runner adds verdict instructions."""
        return self.template.format(code=code_block(code))
