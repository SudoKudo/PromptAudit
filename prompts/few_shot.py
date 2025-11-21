# prompts/few_shot.py — PromptAudit v2.0: Few-Shot classification strategy
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   This prompt strategy gives the model a couple of labeled examples first,
#   then asks it to analyze a new code sample from a security perspective.
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
#   This keeps label semantics centralized and ensures consistent behavior
#   across ZeroShot, FewShot, CoT, AdaptiveCoT, and SelfConsistency.

from .base_prompt import BasePrompt


# Few-shot labeled examples shown to the model before the new sample.
# These illustrate:
#   - A vulnerable use of strcpy (no bounds checking).
#   - A safer use of strncpy with an explicit bound.
EXAMPLES = """Examples:
Code:
strcpy(dst, src);
Label: VULNERABLE

Code:
strncpy(dst, src, sizeof(dst));
Label: SAFE
"""


class FewShot(BasePrompt):
    """
    Few-shot prompt strategy.

    Behavior:
        - Provides two labeled examples (one VULNERABLE, one SAFE).
        - Then presents the new code snippet to be audited.
        - Lets the model reason about the code and produce an output.
        - Returns ONLY the prompt string; the runner handles generation and
          label parsing.

    The runner will:
        - Append a strict "FIRST LINE ONLY: SAFE or VULNERABLE" instruction.
        - Call model.generate(full_prompt).
        - Pass the raw model output into parse_verdict().
    """

    # Logical name for this strategy (used in configs and reporting).
    name = "few_shot"

    # Single canonical few-shot template:
    #   - Shows EXAMPLES with labels.
    #   - Then asks the model to analyze the new code.
    #   - Output formatting is NOT constrained here; the runner adds that.
    template = (
        "Use the examples below as prior knowledge for classifying code security.\n"
        "First, review the examples and their labels. Then analyze the new code snippet.\n\n"
        f"{EXAMPLES}\n"
        "Now analyze this code from a security perspective:\n\n"
        "{code}\n\n"
    )

    def apply(self, model, code, gen_cfg):
        """
        Build and return the few-shot prompt string.

        Args:
            model:
                Model object (not used directly here, but kept in the signature
                for consistency with other strategies).
            code (str):
                The code snippet to classify.
            gen_cfg (dict):
                Generation configuration (temperature, stop sequences, etc.).
                Not used here because this strategy does not call
                model.generate() itself.

        Returns:
            str:
                A fully formatted prompt string containing:
                    - The labeled examples, and
                    - The target code snippet to analyze.
                The ExperimentRunner will:
                    - Append SAFE/VULNERABLE task instructions,
                    - Call model.generate(full_prompt),
                    - Feed the raw output into parse_verdict().
        """
        return self.template.format(code=code)