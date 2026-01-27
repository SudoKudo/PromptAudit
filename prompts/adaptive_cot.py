# prompts/adaptive_cot.py — PromptAudit v2.0: Adaptive Chain-of-Thought (CoT) classification strategy

# -------------------------------------------------------------------------
# Purpose:
#   Adaptive Chain-of-Thought (CoT) strategy that encourages the model to:
#     1) Try to make a quick decision if it is confident.
#     2) Otherwise, reason step by step before deciding.
#
# PromptAudit v2.0 design (Option A):
#   - This strategy does NOT call model.generate() itself.
#   - It only builds and returns a prompt string.
#   - The ExperimentRunner:
#       * Calls apply(model, code, gen_cfg) to get the adaptive CoT prompt.
#       * Appends the strict SAFE or VULNERABLE "TASK" block.
#       * Calls model.generate(full_prompt).
#       * Sends the raw model output to parse_verdict().
#
#   This keeps the adaptive reasoning behavior inside the prompt text but
#   centralizes all label parsing logic in evaluation.label_parser.

from .base_prompt import BasePrompt


class AdaptiveCoT(BasePrompt):
    """Adaptive Chain-of-Thought prompt strategy."""

    # Logical name for this strategy (used in configs and reporting).
    name = "adaptive_cot"

    # Single adaptive CoT template:
    #   - Tells the model to decide quickly if possible.
    #   - If not confident, it should think step by step about vulnerabilities.
    #   - The exact SAFE or VULNERABLE output format is not defined here;
    #     the runner will append the strict labeling instructions.
    template = (
        "You are a secure code auditor. Your goal is to determine whether the "
        "following code is SAFE or VULNERABLE.\n\n"
        "1) First, quickly consider whether the code appears safe or unsafe.\n"
        "2) If you are not confident, reason step by step about potential "
        "vulnerabilities such as buffer overflows, injections, improper "
        "validation, race conditions, and other common issues.\n"
        "3) After your reasoning, you will receive separate instructions on how "
        "to present the final classification.\n\n"
        "Code:\n{code}\n\n"
        "Begin your analysis:\n1) "
    )

    def apply(self, model, code, gen_cfg):
        """
        Build and return the adaptive CoT prompt string.

        Args:
            model:
                Backend model instance (not used directly here, but included
                for interface consistency with other strategies).
            code (str):
                The code snippet to analyze.
            gen_cfg (dict):
                Generation configuration (temperature, top_p, etc.). Not used
                here, since this strategy does not call model.generate() itself.

        Returns:
            str:
                A fully formatted adaptive CoT prompt string. The
                ExperimentRunner will:
                    - Append the strict SAFE or VULNERABLE task instructions,
                    - Call model.generate(full_prompt),
                    - Feed the raw output to parse_verdict().
        """
        return self.template.format(code=code)