"""Self-consistency prompt strategy that votes across protocol-aware samples."""

import time
from collections import Counter

from .base_prompt import BasePrompt
from .adaptive_cot import AdaptiveCoT
from evaluation.label_parser import parse_verdict_details
from evaluation.output_protocol import build_output_instruction


class SelfConsistency(BasePrompt):
    """Self-consistency that samples adaptive CoT responses under the active protocol."""

    name = "self_consistency"
    returns_label = True

    def __init__(self):
        super().__init__()
        self._adaptive_prompt = AdaptiveCoT()

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
        """Run multiple adaptive CoT votes and return a structured final label."""
        num_votes = int(gen_cfg.get("sc_samples", 5))
        vote_delay = max(0.0, float(gen_cfg.get("sc_vote_delay_seconds", 0.0)))
        votes = []
        unknown_votes = 0

        for _ in range(num_votes):
            details = self._generate_vote(
                model,
                code,
                gen_cfg,
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
        winning_label, winning_count = label_counts.most_common(1)[0]
        if winning_count <= num_votes / 2:
            return {
                "label": "unknown",
                "parse_tier": "sc_no_majority",
                "vote_counts": dict(label_counts),
                "valid_votes": len(votes),
                "unknown_votes": unknown_votes,
            }

        winning_tiers = [tier for label, tier in votes if label == winning_label]
        winning_tier = Counter(winning_tiers).most_common(1)[0][0] if winning_tiers else "unknown"

        return {
            "label": winning_label,
            "parse_tier": f"sc_vote_{winning_tier}",
            "vote_counts": dict(label_counts),
            "valid_votes": len(votes),
            "unknown_votes": unknown_votes,
        }

    def _generate_vote(self, model, code, gen_cfg, output_protocol, parser_mode):
        """Generate one adaptive CoT vote using the active output protocol and parser mode."""
        prompt = self._adaptive_prompt.apply_with_context(
            model,
            code,
            gen_cfg,
            output_protocol=output_protocol,
            parser_mode=parser_mode,
        ).rstrip() + build_output_instruction(output_protocol)
        raw = super().apply(model, prompt, gen_cfg, raw_prompt=True)
        if not raw:
            return {
                "label": "unknown",
                "tier": "unknown",
                "parser_mode": parser_mode,
                "output_protocol": output_protocol,
            }

        return parse_verdict_details(
            raw,
            model_name=getattr(model, "name", "model"),
            mode=parser_mode,
            output_protocol=output_protocol,
        )
