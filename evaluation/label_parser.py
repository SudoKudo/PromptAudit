<<<<<<< Updated upstream
# evaluation/label_parser.py for PromptAudit v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Centralized parser for converting raw model output → SAFE / VULNERABLE / UNKNOWN.
#
# Three-tiered parsing:
#   Tier 1: STRICT first-line rule
#           - First non-empty line must be a single word: SAFE or VULNERABLE.
#   Tier 2: EXPLICIT verdict markers
#           - Lines like "Final answer: SAFE", "Verdict: VULNERABLE."
#           - Must match the entire line to avoid "Final answer: this code is not safe".
#   Tier 3: NEGATION-AWARE lexical scan
#           - Looks at the full text for cues of safety or vulnerability, including
#             negated forms such as "not safe" and "not vulnerable".
#
# This keeps runner.py clean and makes parsing testable and consistent
# across prompt strategies.
# ---------------------------------------------------------------------
=======
"""Parse model output into SAFE, VULNERABLE, or UNKNOWN labels."""
>>>>>>> Stashed changes

import re


AVAILABLE_PARSER_MODES = ("strict", "structured", "full")

_EXPLICIT_VERDICT_PATTERNS = [
    re.compile(
        r"^(final answer|answer|classification|verdict|label|conclusion)\s*[:\-]?\s*(?:is\s+)?"
        r"(safe|vulnerable)\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:the\s+)?(?:final\s+answer|answer|classification|verdict)\s+is\s+"
        r"(safe|vulnerable)\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(therefore|thus|overall|ultimately|in conclusion),?\s+(?:the\s+code\s+is\s+)?"
        r"(safe|vulnerable)\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:the\s+code|this\s+code)\s+is\s+(safe|vulnerable)\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
]

_RE_NOT_SAFE = re.compile(r"\bnot\s+safe\b")
_RE_UNSAFE = re.compile(r"\bunsafe\b")
_RE_VULNERABLE = re.compile(r"\bvulnerable\b")
_RE_VULNERABILITY = re.compile(r"\bvulnerabilit(?:y|ies)\b")
_RE_EXPLOITABLE = re.compile(r"\bexploitable\b")
_RE_AT_RISK = re.compile(r"\bat\s+risk\b")
_RE_SAFE = re.compile(r"\bsafe\b")
_RE_SECURE = re.compile(r"\bsecure\b")
_RE_NOT_VULNERABLE = re.compile(r"\bnot\s+vulnerable\b")
_RE_NO_VULN = re.compile(r"\bno\s+(known\s+)?vulnerabilit(?:y|ies)\b")


def normalize_parser_mode(value: str | None) -> str:
    """Normalize parser-mode aliases to canonical internal names."""
    key = str(value or "full").strip().lower()
    aliases = {
        "strict": "strict",
        "structured": "structured",
        "full": "full",
        "heuristic": "full",
    }
    return aliases.get(key, key)


def _normalize_token_label(token: str) -> str | None:
    cleaned = "".join(ch for ch in str(token) if ch.isalpha()).lower()
    return cleaned if cleaned in {"safe", "vulnerable"} else None


def _strict_line_label(lines: list[str], output_protocol: str) -> tuple[str, str | None]:
    """Parse the exact verdict line dictated by the output protocol."""
    if not lines:
        return "unknown", None

    idx = 0 if output_protocol == "verdict_first" else -1
    target_line = lines[idx]
    parts = target_line.split()
    if len(parts) == 1:
        label = _normalize_token_label(parts[0])
        if label:
            tier = "strict_first_line" if output_protocol == "verdict_first" else "strict_last_line"
            return label, tier

    return "unknown", None


def _explicit_verdict_label(lines: list[str]) -> tuple[str, str | None]:
    """Parse explicit verdict lines with broader but still line-anchored patterns."""
    for ln in reversed(lines):
        for pattern in _EXPLICIT_VERDICT_PATTERNS:
            match = pattern.search(ln)
            if match:
                label = match.groups()[-1].lower()
                if label in {"safe", "vulnerable"}:
                    return label, "explicit_verdict"

    return "unknown", None


def _lexical_fallback_label(text: str) -> tuple[str, str | None]:
    """Fallback heuristic for freer model outputs."""
    lowered = text.lower()

    has_not_safe = bool(_RE_NOT_SAFE.search(lowered))
    has_unsafe = bool(_RE_UNSAFE.search(lowered))

    has_vulnerable = bool(_RE_VULNERABLE.search(lowered))
    has_vulnerability = bool(_RE_VULNERABILITY.search(lowered))
    has_exploitable = bool(_RE_EXPLOITABLE.search(lowered))
    has_at_risk = bool(_RE_AT_RISK.search(lowered))

    has_safe_word = bool(_RE_SAFE.search(lowered))
    has_secure_word = bool(_RE_SECURE.search(lowered))

    has_not_vulnerable = bool(_RE_NOT_VULNERABLE.search(lowered))
    has_no_vuln = bool(_RE_NO_VULN.search(lowered))

    vulnerable_signal_raw = (
        has_not_safe
        or has_unsafe
        or has_vulnerable
        or has_vulnerability
        or has_exploitable
        or has_at_risk
    )
    safe_negating_vuln = has_not_vulnerable or has_no_vuln
    vulnerable_signal = vulnerable_signal_raw and not safe_negating_vuln

    positive_safe = (
        (has_safe_word or has_secure_word or safe_negating_vuln)
        and not has_not_safe
        and not has_unsafe
    )

    if vulnerable_signal and not positive_safe:
        return "vulnerable", "lexical_fallback"
    if positive_safe and not vulnerable_signal:
        return "safe", "lexical_fallback"

    return "unknown", None


def parse_verdict_details(
    text: str,
    *,
    model_name: str | None = None,
    mode: str = "full",
    output_protocol: str = "verdict_first",
) -> dict:
    """
    Parse raw model output into a structured verdict result.

    Returns a dictionary containing:
        - label: "safe" | "vulnerable" | "unknown"
        - tier: which parser tier matched, or None
        - parser_mode: normalized parser mode used
        - output_protocol: normalized protocol used
    """
    del model_name  # Reserved for future model-specific parsing heuristics.

    parser_mode = normalize_parser_mode(mode)
    protocol = str(output_protocol or "verdict_first").strip().lower()

    text = str(text or "").strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    if not lines:
        return {
            "label": "unknown",
            "tier": None,
            "parser_mode": parser_mode,
            "output_protocol": protocol,
        }

    label, tier = _strict_line_label(lines, protocol)
    if label != "unknown":
        return {
            "label": label,
            "tier": tier,
            "parser_mode": parser_mode,
            "output_protocol": protocol,
        }

    if parser_mode in {"structured", "full"}:
        label, tier = _explicit_verdict_label(lines)
        if label != "unknown":
            return {
                "label": label,
                "tier": tier,
                "parser_mode": parser_mode,
                "output_protocol": protocol,
            }

    if parser_mode == "full":
        label, tier = _lexical_fallback_label(text)
        if label != "unknown":
            return {
                "label": label,
                "tier": tier,
                "parser_mode": parser_mode,
                "output_protocol": protocol,
            }

    return {
        "label": "unknown",
        "tier": None,
        "parser_mode": parser_mode,
        "output_protocol": protocol,
    }


def parse_verdict(
    text: str,
    *,
    model_name: str | None = None,
    mode: str = "full",
    output_protocol: str = "verdict_first",
) -> str:
    """Backward-compatible label-only parser wrapper."""
    return parse_verdict_details(
        text,
        model_name=model_name,
        mode=mode,
        output_protocol=output_protocol,
    )["label"]
