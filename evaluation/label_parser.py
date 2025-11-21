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

import re


def parse_verdict(text: str, *, model_name: str | None = None) -> str:
    """
    Parse the raw LLM output into one of:
        - "safe"
        - "vulnerable"
        - "unknown"

    Args:
        text (str):
            Raw model output (or a pre-normalized label string such as
            "safe", "vulnerable", or "unknown").

        model_name (str | None):
            Optional model identifier (kept for future per-model heuristics).
            Currently unused in the logic but part of the public interface.

    Returns:
        str:
            Normalized verdict label: "safe", "vulnerable", or "unknown".
    """

    # Normalize and split into meaningful lines
    text = str(text).strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    if not lines:
        return "unknown"

    # ================================================================
    # TIER 1: STRICT FIRST-LINE RULE
    # ================================================================
    # The first non-empty line must contain ONLY "SAFE" or "VULNERABLE".
    # Example:
    #   "SAFE"
    #   "VULNERABLE"
    #
    # This is the primary path when the model follows the "FIRST LINE ONLY"
    # instruction added by the runner.
    first_line = lines[0]
    parts = first_line.split()

    if parts:
        # Strip non-letter characters (e.g., "SAFE:", "SAFE." → "SAFE").
        token = "".join(ch for ch in parts[0] if ch.isalpha()).lower()
        # Entire line must be a single word label.
        if len(parts) == 1 and token in ("safe", "vulnerable"):
            return token

    # ================================================================
    # TIER 2: EXPLICIT VERDICT MARKERS
    # ================================================================
    # Look for clear structured lines:
    #   Final answer: SAFE
    #   Answer: VULNERABLE
    #   Classification: SAFE
    #   Verdict: VULNERABLE.
    #
    # The pattern must match FULL lines with no extra words, preventing
    # mistakes like interpreting "Final answer: this code is not safe".
    verdict_pattern = re.compile(
        r"^(final answer|answer|classification|verdict|label)\s*:\s*"
        r"(safe|vulnerable)\s*[.!]?\s*$",
        re.IGNORECASE,
    )

    explicit_label: str | None = None
    # Scan bottom-up so we prefer the "final" answer line when present.
    for ln in reversed(lines):
        m = verdict_pattern.search(ln)
        if m:
            explicit_label = m.group(2).lower()
            break

    if explicit_label is not None:
        return explicit_label

    # ================================================================
    # TIER 3: NEGATION-AWARE LEXICAL SCAN
    # ================================================================
    # Fallback heuristic when there is no strict first-line label and no
    # explicit verdict line.
    #
    # Handles patterns such as:
    #   "The code is not safe"                → vulnerable
    #   "This code is unsafe"                 → vulnerable
    #   "There is a critical vulnerability"   → vulnerable
    #   "The code is vulnerable to X"         → vulnerable
    #   "The code is not vulnerable"          → safe
    #   "No vulnerabilities were found"       → safe
    #   "The code appears secure"             → safe
    #
    # Mixed signals (both safe and vulnerable cues) are treated as unknown
    # to avoid over-committing:
    #   "The code seems safe but is vulnerable to X" → unknown
    lowered = text.lower()

    # ---- Vulnerability cues (including negation of safety) ----
    has_not_safe = bool(re.search(r"\bnot\s+safe\b", lowered))
    has_unsafe = bool(re.search(r"\bunsafe\b", lowered))

    # Direct mentions of vulnerability / risk / exploitability.
    has_vulnerable = bool(re.search(r"\bvulnerable\b", lowered))
    has_vulnerability = bool(re.search(r"\bvulnerabilit(?:y|ies)\b", lowered))
    has_exploitable = bool(re.search(r"\bexploitable\b", lowered))
    has_at_risk = bool(re.search(r"\bat\s+risk\b", lowered))

    # ---- Safe cues ----
    has_safe_word = bool(re.search(r"\bsafe\b", lowered))
    has_secure_word = bool(re.search(r"\bsecure\b", lowered))

    # ---- Negated vulnerability cues (indicating safety) ----
    # Examples:
    #   "not vulnerable"
    #   "not vulnerable to buffer overflow"
    #   "no vulnerabilities"
    #   "no known vulnerabilities"
    has_not_vulnerable = bool(re.search(r"\bnot\s+vulnerable\b", lowered))
    has_no_vuln = bool(re.search(r"\bno\s+(known\s+)?vulnerabilit(?:y|ies)\b", lowered))

    # Combine vulnerability indicators (raw) before negation handling.
    vulnerable_signal_raw = (
        has_not_safe
        or has_unsafe
        or has_vulnerable
        or has_vulnerability
        or has_exploitable
        or has_at_risk
    )

    # Signals that explicitly negate vulnerability (and thus push toward "safe").
    safe_negating_vuln = has_not_vulnerable or has_no_vuln

    # Final vulnerable signal:
    #   - We only treat it as "vulnerable" if:
    #       * there are vulnerability cues, AND
    #       * they are NOT immediately contradicted by negation like "not vulnerable"
    vulnerable_signal = vulnerable_signal_raw and not safe_negating_vuln

    # Final safe signal:
    #   - Positive safe words ("safe", "secure") that are not negated by "not safe"/"unsafe"
    #   - OR explicit negations of vulnerability (no vulnerabilities, not vulnerable)
    positive_safe = (
        (has_safe_word or has_secure_word or safe_negating_vuln)
        and not has_not_safe
        and not has_unsafe
    )

    # ------------------------------------------------------------
    # Decision logic:
    #   - If we see strong vulnerable cues and no safe signal → vulnerable
    #   - If we see strong safe cues and no vulnerable signal → safe
    #   - If both or neither activate → unknown (ambiguous or neutral)
    # ------------------------------------------------------------
    if vulnerable_signal and not positive_safe:
        return "vulnerable"

    if positive_safe and not vulnerable_signal:
        return "safe"

    # Anything else = ambiguous mix, neutral discussion, or refusal.
    return "unknown"
