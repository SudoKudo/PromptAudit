# prompts/zero_shot.py — Zero-Shot classification strategy for Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   This is the simplest strategy: a single, clean zero-shot prompt that asks
#   the model to classify code as SAFE or VULNERABLE with no examples.
#
# Design (aligned with the Code v2.0 ecosystem):
#   - Exactly ONE prompt is sent to the model per code snippet.
#   - Output is constrained to a single final label: SAFE or VULNERABLE.
#   - The label is parsed from the last non-empty line.
#   - We call model.generate(prompt) directly so this prompt is not wrapped
#     by BasePrompt.template (same pattern as CoT and FewShot).


from .base_prompt import BasePrompt


class ZeroShot(BasePrompt):
    """
    Zero-shot classification prompt strategy.

    Behavior:
        - Assigns the model a security auditing role.
        - Asks it to examine the code and classify it strictly as SAFE or VULNERABLE.
        - Requires the answer to be exactly one word on the final line.
        - Parses that final word and returns it as the classification.

    This implementation:
        - Uses one canonical zero-shot template (no extra variants).
        - Makes a single model call per code snippet.
    """

    # Logical name used in configs and reports.
    name = "zero_shot"

    # Single canonical zero-shot template:
    #   - Clear role: "secure code auditor".
    #   - Clear task: classify strictly as SAFE or VULNERABLE.
    #   - Clear output format: exactly one word on its own final line.
    template = (
        "You are a secure code auditor. Examine the code and classify it strictly as SAFE or VULNERABLE.\n\n"
        "{code}\n\n"
        "Respond with exactly one word on its own final line: SAFE or VULNERABLE."
    )

    def apply(self, model, code, gen_cfg):
        """
        Apply the zero-shot strategy to a given code snippet.

        Args:
            model:
                Model backend that must implement `generate(prompt: str) -> str`.
            code (str):
                The code snippet to classify.
            gen_cfg (dict):
                Generation configuration (temperature, stop sequences, etc.).
                Included for interface consistency with other strategies, but
                this method does not directly modify behavior based on it.
                The model backend typically uses its own stored gen_cfg.

        Returns:
            str:
                - "SAFE" or "VULNERABLE" if a valid label is parsed.
                - "UNKNOWN" if the response does not contain a clear label.

        Process:
            1) Format the zero-shot template with the code snippet.
            2) Call model.generate(prompt) once.
            3) Strip and split the response into non-empty lines.
            4) Take the last non-empty line and extract its first token.
            5) Normalize that token and check if it is SAFE or VULNERABLE.
            6) Return the label, or "UNKNOWN" if parsing fails.
        """

        # 1) Build the full zero-shot prompt.
        prompt = self.template.format(code=code)

        # 2) Send the prompt directly to the model (no BasePrompt wrapping).
        result = model.generate(prompt)
        if not result:
            # If the model returns nothing, we cannot determine a label.
            return "UNKNOWN"

        # 3) Normalize the model output: remove leading/trailing whitespace,
        #    and filter out blank lines.
        text = result.strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        # 4) Take the last non-empty line; the answer should be here.
        last = lines[-1] if lines else ""

        # 5) Extract the first token, strip punctuation, and normalize case.
        first = (last.split()[0] if last else "").strip(":，。.").upper()

        # 6) Return the label if it is valid; otherwise return UNKNOWN.
        if first in ("SAFE", "VULNERABLE"):
            return first

        # Fallback if the model response doesn't match the expected pattern.
        return "UNKNOWN"
