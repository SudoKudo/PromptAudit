# prompts/adaptive_cot.py — Glacier v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   Adaptive Chain-of-Thought (CoT) strategy:
#     - Phase 1: Try fast, direct SAFE/VULNERABLE classification prompts.
#     - Phase 2: If the result is unclear, fall back to reasoning-style CoT.
#
#   This class:
#     - May call the model multiple times per sample (across templates + phases).
#     - Returns a single final label: SAFE, VULNERABLE, or UNKNOWN.
#
#   With the BasePrompt.raw_prompt fix:
#     - We now send the CoT prompts *directly* to the model (no base template
#       wrapping), via raw_prompt=True.


from .base_prompt import BasePrompt


class AdaptiveCoT(BasePrompt):
    """
    Adaptive Chain-of-Thought strategy.

    High-level behavior:
      - Fast path:
          * Use short, direct classification prompts.
          * If the last non-empty line cleanly yields SAFE or VULNERABLE, return it.
      - Slow path:
          * If fast path is uncertain, use CoT-style prompts that encourage reasoning.
          * Still require the final line to be SAFE or VULNERABLE.
      - If neither phase yields a clear label, return UNKNOWN.
    """

    # Logical name for this strategy (used in configs / reporting).
    name = "adaptive_cot"

    # Phase 1: Direct templates (fast, minimal)
    direct_templates = [
        # Template 1 — explicit role + one-word output constraint
        "You are a security auditor. Classify the following code as SAFE or VULNERABLE. "
        "Respond with only one word — SAFE or VULNERABLE.\n\nCode:\n{code}\n\nAnswer:",

        # Template 2 — variant wording, same constraints
        "Determine if the code is SAFE or VULNERABLE. Do not explain. Respond with one word only.\n\n{code}\n\nLabel:"
    ]

    # Phase 2: Reasoning templates (slower CoT)
    reasoning_templates = [
        # Template 1 — step-by-step reasoning, then final label
        "You are a senior secure code auditor. Analyze the code step-by-step. "
        "After reasoning, on the last line, write only SAFE or VULNERABLE.\n\nCode:\n{code}\n\nReasoning:\n1) ",

        # Template 2 — similar concept, slightly different wording
        "You are an expert in secure software analysis. Think carefully, reason concisely, "
        "then end your response with exactly one word: SAFE or VULNERABLE.\n\n{code}\n\nThoughts:\n1) "
    ]

    def apply(self, model, code, gen_cfg):
        """
        Apply the adaptive CoT strategy to a given code snippet.

        Args:
            model:
                Model backend that implements `generate(prompt: str) -> str`.
            code (str):
                Code snippet to analyze.
            gen_cfg (dict):
                Generation configuration dict (temperature, stop sequences, etc.).
                This method does not directly inspect gen_cfg, but keeps it for
                interface consistency with other strategies.

        Returns:
            str:
                - "SAFE" or "VULNERABLE" if a clear label is extracted from any phase.
                - "UNKNOWN" if all attempts fail.
        """

        # --- Phase 1: quick classification (no explicit reasoning in output)
        for tpl in self.direct_templates:
            prompt = tpl.format(code=code)

            # Send the fully-formed prompt directly, without wrapping in BasePrompt.template.
            result = super().apply(model, prompt, gen_cfg, raw_prompt=True)
            if not result:
                continue

            text = result.strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            last = lines[-1] if lines else ""
            first = (last.split()[0] if last else "").strip(":，。.").upper()

            if first in ("SAFE", "VULNERABLE"):
                return first

        # --- Phase 2: slower reasoning if first pass was uncertain
        for tpl in self.reasoning_templates:
            prompt = tpl.format(code=code)

            # Again, send the CoT prompt as-is via raw_prompt=True.
            result = super().apply(model, prompt, gen_cfg, raw_prompt=True)
            if not result:
                continue

            text = result.strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            last = lines[-1] if lines else ""
            first = (last.split()[0] if last else "").strip(":，。.").upper()

            if first in ("SAFE", "VULNERABLE"):
                return first

        # If neither fast nor slow path produced a valid label, return UNKNOWN.
        return "UNKNOWN"
