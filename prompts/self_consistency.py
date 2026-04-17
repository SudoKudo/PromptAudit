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
        vote_anomalies = []

        for vote_index in range(num_votes):
            details = self._generate_vote(
                model,
                code,
                gen_cfg,
                output_protocol,
                parser_mode,
                vote_index=vote_index,
            )
            label = details["label"]
            if label in {"safe", "vulnerable"}:
                votes.append((label, details.get("tier") or "unknown"))
            else:
                unknown_votes += 1
            anomaly = details.get("generation_anomaly")
            if anomaly:
                vote_anomalies.append(anomaly)

            if vote_delay:
                time.sleep(vote_delay)

        if not votes:
            return {
                "label": "unknown",
                "parse_tier": "sc_all_unknown",
                "vote_counts": {},
                "valid_votes": 0,
                "unknown_votes": unknown_votes or num_votes,
                "generation_anomalies": vote_anomalies,
                "generation_info": {
                    "status": "sc_all_unknown",
                    "valid_votes": 0,
                    "unknown_votes": unknown_votes or num_votes,
                    "anomaly_count": len(vote_anomalies),
                },
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
                "generation_anomalies": vote_anomalies,
                "generation_info": {
                    "status": "sc_no_majority",
                    "valid_votes": len(votes),
                    "unknown_votes": unknown_votes,
                    "anomaly_count": len(vote_anomalies),
                },
            }

        winning_tiers = [tier for label, tier in votes if label == winning_label]
        winning_tier = Counter(winning_tiers).most_common(1)[0][0] if winning_tiers else "unknown"

        return {
            "label": winning_label,
            "parse_tier": f"sc_vote_{winning_tier}",
            "vote_counts": dict(label_counts),
            "valid_votes": len(votes),
            "unknown_votes": unknown_votes,
            "generation_anomalies": vote_anomalies,
            "generation_info": {
                "status": "sc_vote_complete",
                "valid_votes": len(votes),
                "unknown_votes": unknown_votes,
                "anomaly_count": len(vote_anomalies),
            },
        }

    @staticmethod
    def _consume_model_generation_info(model):
        """Return backend generation metadata for the most recent vote, if any."""
        if hasattr(model, "consume_generation_info"):
            try:
                info = model.consume_generation_info()
                return info if isinstance(info, dict) else {}
            except Exception:
                return {}
        return {}

    def _generate_vote(self, model, code, gen_cfg, output_protocol, parser_mode, *, vote_index):
        """Generate one adaptive CoT vote using the active output protocol and parser mode."""
        prompt = self._adaptive_prompt.apply_with_context(
            model,
            code,
            gen_cfg,
            output_protocol=output_protocol,
            parser_mode=parser_mode,
        ).rstrip() + build_output_instruction(output_protocol)
        raw = super().apply(model, prompt, gen_cfg, raw_prompt=True)
        generation_info = self._consume_model_generation_info(model)
        if not raw:
            reason = "empty_response"
            if generation_info.get("status") == "error":
                reason = "generation_error"
            return {
                "label": "unknown",
                "tier": "unknown",
                "parser_mode": parser_mode,
                "output_protocol": output_protocol,
                "generation_info": generation_info,
                "generation_anomaly": {
                    "vote_index": vote_index + 1,
                    "reason": reason,
                    "prompt_text": prompt,
                    "generation_info": generation_info,
                },
            }

        parsed = parse_verdict_details(
            raw,
            model_name=getattr(model, "name", "model"),
            mode=parser_mode,
            output_protocol=output_protocol,
        )
        parsed["generation_info"] = generation_info
        return parsed
