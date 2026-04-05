<<<<<<< Updated upstream
# prompts/self_consistency.py — PromptAudit v2.0: Adaptive Chain-of-Thought (CoT) + Self-Consistency classification strategy
# Author: Steffen Camarato — University of Central Florida
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
=======
"""Self-consistency prompt strategy that votes across protocol-aware samples."""

import time
from collections import Counter
>>>>>>> Stashed changes

from .base_prompt import BasePrompt
from evaluation.label_parser import parse_verdict_details
from evaluation.output_protocol import build_output_instruction


class SelfConsistency(BasePrompt):
    """Self-consistency that parses each vote with the active protocol and parser."""

    name = "self_consistency"
    returns_label = True

    direct_templates = [
        "You are a security auditor. Classify this code as SAFE or VULNERABLE.\n\n{code}\n\nAnswer:",
        "Determine if this code is SAFE or VULNERABLE.\n\n{code}\n\nLabel:",
    ]

    reasoning_templates = [
        "You are an expert code auditor. Think step-by-step about vulnerabilities.\n\n{code}\n\nReasoning:\n1) ",
        "Analyze carefully and consider all potential risks.\n\n{code}\n\nAnalysis:\n1) ",
    ]

    def apply(self, model, code, gen_cfg):
        """Fallback entry point used when no ablation context is supplied."""
        result = self.apply_with_context(model, code, gen_cfg)
        return result["label"]

    def apply_with_context(
        self,
        model,
        code,
        gen_cfg,
        *,
        output_protocol="verdict_first",
        parser_mode="full",
    ):
        """Run multiple votes and return a structured final label."""
        num_votes = int(gen_cfg.get("sc_samples", 5))
        vote_delay = max(0.0, float(gen_cfg.get("sc_vote_delay_seconds", 0.0)))
        votes = []
        unknown_votes = 0

        for _ in range(num_votes):
            details = self._generate_vote(
                model,
                code,
                gen_cfg,
                self.direct_templates,
                output_protocol,
                parser_mode,
            )
            if details["label"] == "unknown":
                details = self._generate_vote(
                    model,
                    code,
                    gen_cfg,
                    self.reasoning_templates,
                    output_protocol,
                    parser_mode,
                )

            label = details["label"]
            if label in {"safe", "vulnerable"}:
                votes.append((label, details.get("tier") or "unknown"))
            else:
                unknown_votes += 1

            if vote_delay:
                time.sleep(vote_delay)

        if not votes:
            return {
                "label": "unknown",
                "parse_tier": "sc_all_unknown",
                "vote_counts": {},
                "valid_votes": 0,
                "unknown_votes": unknown_votes or num_votes,
            }

        label_counts = Counter(label for label, _tier in votes)
        winning_label, _ = label_counts.most_common(1)[0]
        winning_tiers = [tier for label, tier in votes if label == winning_label]
        winning_tier = Counter(winning_tiers).most_common(1)[0][0] if winning_tiers else "unknown"

        return {
            "label": winning_label,
            "parse_tier": f"sc_vote_{winning_tier}",
            "vote_counts": dict(label_counts),
            "valid_votes": len(votes),
            "unknown_votes": unknown_votes,
        }

    def _generate_vote(self, model, code, gen_cfg, templates, output_protocol, parser_mode):
        """Generate one vote using the active output protocol and parser mode."""
        instruction = build_output_instruction(output_protocol)
        for tpl in templates:
            prompt = tpl.format(code=code).rstrip() + instruction
            raw = super().apply(model, prompt, gen_cfg, raw_prompt=True)
            if not raw:
                continue
            details = parse_verdict_details(
                raw,
                model_name=getattr(model, "name", "model"),
                mode=parser_mode,
                output_protocol=output_protocol,
            )
            if details["label"] != "unknown":
                return details

        return {
            "label": "unknown",
            "tier": "unknown",
            "parser_mode": parser_mode,
            "output_protocol": output_protocol,
        }
