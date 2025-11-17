# prompts/few_shot.py — Few-Shot classification strategy for Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   This prompt strategy gives the model a couple of labeled examples first,
#   then asks it to classify a new code sample as SAFE or VULNERABLE.
#
#   Design choices (aligned with the whole Code v2.0 ecosystem):
#     - Exactly ONE prompt is sent per sample (no multi-template fallback here).
#     - Output is constrained to a single final label: SAFE or VULNERABLE.
#     - The final label is parsed from the last non-empty line.
#     - We call model.generate(prompt) directly to avoid wrapping this prompt
#       inside BasePrompt.template (same fix we applied to CoT).
#
#   The examples are deliberately simple and C-style to keep the few-shot signal
#   clear: one obviously unsafe pattern, one obviously safer alternative.


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
        - Then presents the new code snippet to classify.
        - Instructs the model to respond with exactly one word on the final line:
          SAFE or VULNERABLE.
        - Parses that final label and returns it as the result.

    This implementation:
        - Uses a single canonical few-shot template (no redundant variants).
        - Makes exactly one model call per sample.
        - Keeps the interface consistent with other strategies (CoT, adaptive, etc.).
    """

    # Logical name for this strategy (used in configs and reporting).
    name = "few_shot"

    # Single canonical few-shot template:
    #   - Shows EXAMPLES with labels.
    #   - Then asks the model to classify the new code.
    #   - Enforces a strict one-word label on the final line.
    template = (
        "Use the examples as prior knowledge. Classify the following code strictly as SAFE or VULNERABLE.\n\n"
        f"{EXAMPLES}\n"
        "Now analyze:\n{code}\n\n"
        "Respond with exactly one word on its own final line: SAFE or VULNERABLE."
    )

    def apply(self, model, code, gen_cfg):
        """
        Apply the few-shot strategy to a given code snippet.

        Args:
            model:
                Model object that must implement `generate(prompt: str) -> str`.
            code (str):
                The code snippet to classify.
            gen_cfg (dict):
                Generation configuration (temperature, stop sequences, etc.).
                It is accepted for consistency with other strategies, but this
                method does not directly modify behavior based on gen_cfg.
                The underlying model backend uses its own stored gen_cfg.

        Returns:
            str:
                - "SAFE" or "VULNERABLE" if a valid label is parsed from the model output.
                - "UNKNOWN" if the response does not contain a clear SAFE/VULNERABLE label.

        Process:
            1) Format the few-shot template with the new code snippet.
            2) Call model.generate(prompt) once.
            3) Strip and split the response into non-empty lines.
            4) Examine the last non-empty line and take its first token.
            5) Normalize that token and return it if it's SAFE or VULNERABLE.
            6) Otherwise, return "UNKNOWN".
        """

        # 1) Build the full few-shot prompt containing examples + the new code.
        prompt = self.template.format(code=code)

        # 2) Call the model directly with the constructed prompt.
        result = model.generate(prompt)
        if not result:
            return "UNKNOWN"

        # 3) Normalize the model output: trim and remove empty lines.
        text = result.strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        # 4) Look at the last non-empty line; the label is expected to be here.
        last = lines[-1] if lines else ""

        # 5) Extract the first token from that line, strip punctuation, and normalize.
        first = (last.split()[0] if last else "").strip(":，。.").upper()

        # 6) If the token is a valid label, return it; otherwise return UNKNOWN.
        if first in ("SAFE", "VULNERABLE"):
            return first

        return "UNKNOWN"
