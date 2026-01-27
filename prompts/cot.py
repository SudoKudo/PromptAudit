# prompts/cot.py — PromptAudit v2.0: Chain-of-Thought (CoT) classification strategy

# ---------------------------------------------------------------------
# Purpose:
#   This prompt strategy encourages the model to reason step by step
#   about the code and its security properties before committing to
#   a classification.
#
# PromptAudit v2.0 design (Option A):
#   - This strategy does NOT call model.generate() itself.
#   - It only builds and returns a prompt string.
#   - The ExperimentRunner:
#       * Calls apply(model, code, gen_cfg) to get the CoT prompt.
#       * Appends the strict SAFE/VULNERABLE "TASK" block.
#       * Calls model.generate(full_prompt).
#       * Sends the raw model output to parse_verdict().
#
#   This keeps Chain-of-Thought reasoning separate from label parsing
#   and centralizes all classification logic.

from .base_prompt import BasePrompt


class CoT(BasePrompt):
    """Chain-of-Thought (CoT) prompt strategy."""

    # Logical identifier for this strategy (used in configs and reporting).
    name = "cot"

    # Single CoT-style template:
    #   - Ask for step by step reasoning about potential vulnerabilities.
    #   - The final SAFE/VULNERABLE formatting is not specified here;
    #     the runner adds that instruction block.
    template = (
        "You are a secure code auditor. Analyze the following code step by step, "
        "carefully reasoning about any potential security vulnerabilities, such as "
        "buffer overflows, injections, improper validation, race conditions, and "
        "other common issues.\n\n"
        "Explain your reasoning clearly before you decide on the final classification.\n\n"
        "Code:\n{code}\n\n"
        "Reasoning:\n1) "
    )

    def apply(self, model, code, gen_cfg):
        """
        Build and return the Chain-of-Thought prompt string.

        Args:
            model:
                Backend model instance (not used directly here, but included
                for interface consistency with other strategies).
            code (str):
                The code snippet to analyze.
            gen_cfg (dict):
                Generation configuration (temperature, etc.). Not used here,
                since this strategy does not call model.generate() itself.

        Returns:
            str:
                A fully formatted CoT prompt string. The ExperimentRunner will:
                    - Append the strict SAFE/VULNERABLE task instructions,
                    - Call model.generate(full_prompt),
                    - Feed the raw output to parse_verdict().
        """
        return self.template.format(code=code)
