# prompts/cot.py — Chain-of-Thought (CoT) strategy for Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   This prompt strategy asks the model to REASON step-by-step about the code
#   and then produce a final classification label (SAFE or VULNERABLE).
#
# Changes (per your request):
#   - Fixed the logic so the CoT prompt is sent **directly** to the model
#     instead of being wrapped inside BasePrompt.template.
#   - Ensured this strategy sends **exactly one prompt per sample** by using
#     a single CoT template (no multi-template loop).


from .base_prompt import BasePrompt


class CoT(BasePrompt):
    """
    Chain-of-Thought (CoT) prompt strategy.

    Behavior:
        - Uses a single reasoning-style prompt that asks the model to think
          step-by-step about potential vulnerabilities in the code.
        - After the reasoning, the model is explicitly instructed to end with a
          final label: SAFE or VULNERABLE, on its own line.
        - The code then parses the model's response and extracts that final label
          from the last non-empty line.

    This implementation:
        - Makes one model call per code snippet (no looping over multiple templates).
        - Sends the CoT prompt directly to model.generate(), not through BasePrompt.apply.
    """

    # Logical identifier for this strategy (used in configs / reporting).
    name = "cot"

    # Single CoT-style template:
    #   - Ask for step-by-step reasoning.
    #   - Require the model to end with SAFE or VULNERABLE on a new line.
    template = (
        "Analyze the following code step-by-step, reasoning about potential vulnerabilities. "
        "After your reasoning, on a new final line, output only one word: SAFE or VULNERABLE.\n\n"
        "Code:\n{code}\n\nReasoning:\n1) "
    )

    def apply(self, model, code, gen_cfg):
        """
        Apply the CoT strategy to a given code snippet.

        Args:
            model:
                Model object that must implement `generate(prompt: str) -> str`.
            code (str):
                The code snippet to analyze.
            gen_cfg (dict):
                Generation configuration dictionary (temperature, stop sequences, etc.).
                It is included for interface consistency (other strategies use it),
                but this method does not modify behavior based on gen_cfg directly.

        Returns:
            str:
                - "SAFE" or "VULNERABLE" if a valid label is parsed from the model output.
                - "UNKNOWN" if the model's response does not contain a clear final label.

        Process:
            1) Format the CoT template with {code} to build a single, full prompt.
            2) Call model.generate(prompt) once.
            3) Strip and split the response into non-empty lines.
            4) Look at the last non-empty line and extract the first token.
            5) Normalize and check if that token is SAFE or VULNERABLE.
            6) Return the label, or "UNKNOWN" if no valid label is found.
        """

        # ------------------------------------------------------------------
        # 1) Build the full CoT prompt with the provided code snippet.
        # ------------------------------------------------------------------
        prompt = self.template.format(code=code)

        # ------------------------------------------------------------------
        # 2) Call the model directly with the CoT prompt.
        #    (We intentionally do NOT call BasePrompt.apply here, because
        #     that would wrap this CoT prompt inside the base template.)
        # ------------------------------------------------------------------
        result = model.generate(prompt)
        if not result:
            # If the model returns an empty or falsy string, we cannot extract a label.
            return "UNKNOWN"

        # ------------------------------------------------------------------
        # 3) Normalize the model output and split into non-empty lines.
        # ------------------------------------------------------------------
        text = result.strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        # Take the last non-empty line; the label is expected to appear here.
        last = lines[-1] if lines else ""

        # ------------------------------------------------------------------
        # 4) Extract the first token from that last line, remove punctuation,
        #    and normalize to uppercase for comparison.
        # ------------------------------------------------------------------
        first = (last.split()[0] if last else "").strip(":，。.").upper()

        # ------------------------------------------------------------------
        # 5) Check if the token is a valid label.
        # ------------------------------------------------------------------
        if first in ("SAFE", "VULNERABLE"):
            return first

        # ------------------------------------------------------------------
        # 6) If the final line does not yield a clean label, return UNKNOWN.
        # ------------------------------------------------------------------
        return "UNKNOWN"
