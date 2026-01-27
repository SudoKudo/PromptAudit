# prompts/self_consistency.py — PromptAudit v2.0: Adaptive Chain-of-Thought (CoT) + Self-Consistency classification strategy

# ---------------------------------------------------------------------
# Purpose:
#   Self-Consistency strategy with Adaptive CoT behavior, rewritten for the
#   PromptAudit v2.0 pipeline where:
#
#       • Prompt strategies RETURN RAW MODEL OUTPUT (per sample)
#       • parse_verdict() is the ONLY label interpreter
#       • Self-Consistency votes on parsed verdicts, not text
#
#   This version:
#       - Draws N stochastic samples (sc_samples)
#       - For each sample:
#             1) Generate a direct-style prompt (fast)
#             2) If parsing fails, generate a reasoning-style prompt (slow)
#             3) Parse each raw output using parse_verdict()
#       - Collect only valid SAFE/VULNERABLE votes
#       - Return the MAJORITY label ("safe"/"vulnerable") or "unknown"
#
#   All SAFE/VULNERABLE logic is centralized in evaluation.label_parser.

import time, collections
from .base_prompt import BasePrompt
from evaluation.label_parser import parse_verdict


class SelfConsistency(BasePrompt):
    """Self-Consistency with integrated Adaptive-CoT behavior."""

    name = "self_consistency"  # Logical name for this strategy, used in configs and reports.
    returns_label = True  # Signals to runner: this strategy returns a FINAL label, not a prompt


    # Phase 1: direct minimal classification templates
    direct_templates = [
        "You are a security auditor. Classify this code as SAFE or VULNERABLE.\n\n{code}\n\nAnswer:",
        "Determine if this code is SAFE or VULNERABLE.\n\n{code}\n\nLabel:"
    ]

    # Phase 2: reasoning templates (fallback)
    reasoning_templates = [
        "You are an expert code auditor. Think step-by-step about vulnerabilities.\n\n{code}\n\nReasoning:\n1) ",
        "Analyze carefully and consider all potential risks.\n\n{code}\n\nAnalysis:\n1) "
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
                - "safe" or "vulnerable" based on majority vote among valid outputs.
                - "unknown" if no valid SAFE/VULNERABLE labels are obtained.

        Note:
            Unlike other strategies, this one returns the FINAL label string,
            not raw model output. The runner must respect returns_label=True.
        """

        n = int(gen_cfg.get("sc_samples", 5))
        votes = []

        for _ in range(n):
            # --- Phase 1: attempt direct fast classification
            raw = self._generate_from_templates(model, code, gen_cfg, self.direct_templates)
            label = parse_verdict(raw, model_name=getattr(model, "name", "model"))

            if label == "unknown":
                # --- Phase 2: fallback to reasoning templates
                raw = self._generate_from_templates(model, code, gen_cfg, self.reasoning_templates)
                label = parse_verdict(raw, model_name=getattr(model, "name", "model"))

            # Record only valid binary labels as votes.
            if label in ("safe", "vulnerable"):
                votes.append(label)

            # Small delay to avoid hammering the backend (API/Ollama friendliness).
            time.sleep(0.1)

        if not votes:
            return "unknown"

        # Majority voting: take the most frequent label among votes.
        return collections.Counter(votes).most_common(1)[0][0]

    def _generate_from_templates(self, model, code, gen_cfg, templates):
        """
        Internal helper — try multiple templates and return the first non-empty
        RAW model output.

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
                The first non-empty raw output from model.generate, or an
                empty string if all attempts fail.
        """
        for tpl in templates:
            # Build the full prompt for this code snippet.
            prompt = tpl.format(code=code)

            # Use BasePrompt.apply in raw_prompt mode so we send this prompt
            # directly to the model without wrapping it in BasePrompt.template.
            result = super().apply(model, prompt, gen_cfg, raw_prompt=True)
            if result:
                return result

        return ""