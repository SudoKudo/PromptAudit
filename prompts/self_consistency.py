# prompts/self_consistency.py — Glacier v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   This strategy combines Self-Consistency (multiple stochastic samples +
#   majority vote) with AdaptiveCoT-style efficiency:
#
#     1. For each of N samples (sc_samples):
#          a) Try a fast direct SAFE/VULNERABLE classification.
#          b) If unclear, fall back to CoT-style reasoning prompts.
#     2. Collect all valid SAFE/VULNERABLE responses as votes.
#     3. Return the majority label, or UNKNOWN if no valid votes.
#
#   With raw_prompt=True:
#     - The direct and reasoning templates are now sent directly to the model,
#       with no additional wrapping from BasePrompt.template.


import time, collections
from .base_prompt import BasePrompt


class SelfConsistency(BasePrompt):
    """Self-Consistency with integrated AdaptiveCoT behavior for efficiency."""

    # Logical name for this strategy, used in configs and reports.
    name = "self_consistency"

    # Phase 1: direct minimal classification templates (fast path)
    direct_templates = [
        "You are a security auditor. Classify this code as SAFE or VULNERABLE. "
        "Respond with one word only — SAFE or VULNERABLE.\n\nCode:\n{code}\n\nAnswer:",
        "Determine if this code is SAFE or VULNERABLE. Do not explain. "
        "Respond with one word only: SAFE or VULNERABLE.\n\n{code}\n\nLabel:"
    ]

    # Phase 2: fallback reasoning templates (slow path)
    reasoning_templates = [
        "You are an expert in secure software analysis. Think step-by-step, then on the final line output only SAFE or VULNERABLE.\n\nCode:\n{code}\n\nReasoning:\n1) ",
        "You are a senior secure code auditor. Analyze carefully, then finish with one word only: SAFE or VULNERABLE.\n\n{code}\n\nAnalysis:\n1) "
    ]

    def apply(self, model, code, gen_cfg):
        """
        Run multiple adaptive samples and return majority binary classification.

        Args:
            model:
                Model backend that implements `generate(prompt: str) -> str`.
            code (str):
                Code snippet to classify.
            gen_cfg (dict):
                Generation configuration dict. Relevant key:
                    - "sc_samples": number of self-consistency samples to draw.
                Other fields (temperature, etc.) are used by the model backend.

        Returns:
            str:
                - "SAFE" or "VULNERABLE" based on majority vote among valid outputs.
                - "UNKNOWN" if no valid SAFE/VULNERABLE labels are obtained.
        """

        # Number of self-consistency samples (default to 5 if missing).
        n = int(gen_cfg.get("sc_samples", 5))
        votes = []

        for i in range(n):
            # --- Phase 1: attempt direct fast classification
            label = self._try_templates(model, code, gen_cfg, self.direct_templates)

            if label == "UNKNOWN":
                # --- Phase 2: fallback to reasoning templates
                label = self._try_templates(model, code, gen_cfg, self.reasoning_templates)

            # Record only valid binary labels as votes.
            if label in ("SAFE", "VULNERABLE"):
                votes.append(label)

            # Small delay to avoid hammering the backend (API/Ollama friendliness).
            time.sleep(0.1)

        if not votes:
            return "UNKNOWN"

        # Majority voting: take the most frequent label among votes.
        return collections.Counter(votes).most_common(1)[0][0]

    def _try_templates(self, model, code, gen_cfg, templates):
        """
        Internal helper — test multiple templates and return the first valid binary result.

        Args:
            model:
                Model backend with `generate(prompt: str) -> str`.
            code (str):
                Code snippet to embed into each template.
            gen_cfg (dict):
                Generation configuration (kept for interface consistency).
            templates (list[str]):
                List of prompt templates to try, each containing {code}.

        Returns:
            str:
                - "SAFE" or "VULNERABLE" if any template yields a clean label.
                - "UNKNOWN" if all templates are ambiguous or empty.
        """
        for tpl in templates:
            # Build the full prompt for this code snippet.
            prompt = tpl.format(code=code)

            # Use BasePrompt.apply in raw_prompt mode so we send this prompt
            # directly to the model without wrapping it in BasePrompt.template.
            result = super().apply(model, prompt, gen_cfg, raw_prompt=True)
            if not result:
                continue

            # Normalize the model output and split into non-empty lines.
            text = result.strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

            # Take the last non-empty line; the label is expected here.
            last = lines[-1] if lines else ""

            # Extract the first token, strip punctuation, and normalize case.
            first = (last.split()[0] if last else "").strip(":，。.").upper()

            # If the token is a valid label, return it immediately.
            if first in ("SAFE", "VULNERABLE"):
                return first

        # If none of the templates produced a valid label, indicate failure.
        return "UNKNOWN"
