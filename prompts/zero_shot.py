# prompts/zero_shot.py — PromptAudit v2.0: Zero-Shot classification strategy
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   ZeroShot is the simplest prompt strategy. It builds a single,
#   clean instruction prompt for classifying a code snippet from a
#   security perspective.
#
# PromptAudit v2.0 design (Option A):
#   - This strategy DOES NOT call model.generate() itself.
#   - It only builds and returns a prompt string.
#   - The ExperimentRunner:
#       * Calls apply(model, code, gen_cfg) → gets the prompt string.
#       * Appends the strict SAFE/VULNERABLE "TASK" block.
#       * Calls model.generate(full_prompt).
#       * Sends the raw model output to parse_verdict().
#
#   This keeps ZeroShot simple and makes the runner the single place
#   that talks to the model backend for this strategy.

from .base_prompt import BasePrompt


class ZeroShot(BasePrompt):
    """Zero-shot classification prompt strategy."""

    # Logical name used in configs and reports.
    name = "zero_shot"

    # Single zero-shot template:
    #   - Assigns the model a security auditing role.
    #   - Asks it to examine the code and consider security implications.
    #   - DOES NOT specify the exact SAFE/VULNERABLE output format; the runner
    #     will add the strict first-line instructions.
    template = (
        "You are a secure code auditor. Examine the following code and determine "
        "whether it is secure or vulnerable to potential exploits.\n"
        "Briefly consider issues such as buffer overflows, injections, improper "
        "validation, and other common weaknesses.\n\n"
        "{code}\n\n"
    )

    def apply(self, model, code, gen_cfg):
        """
        Build and return the zero-shot prompt string.

        Args:
            model:
                Backend model instance (not used directly here, but kept in the
                signature for interface consistency with other strategies).
            code (str):
                The code snippet to be analyzed.
            gen_cfg (dict):
                Generation configuration (temperature, etc.). Not used here,
                since this strategy does not call model.generate() itself.

        Returns:
            str:
                A fully formatted prompt string. The ExperimentRunner will:
                    - Append the strict SAFE/VULNERABLE task instructions.
                    - Call model.generate(full_prompt).
                    - Feed the raw output to parse_verdict().
        """
        return self.template.format(code=code)
