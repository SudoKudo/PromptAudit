"""Helpers for verdict-first and verdict-last output-protocol ablations."""

AVAILABLE_OUTPUT_PROTOCOLS = ("verdict_first", "verdict_last")


def normalize_output_protocol(value: str | None) -> str:
    """Normalize output-protocol aliases to the canonical internal names."""
    key = str(value or "verdict_first").strip().lower()
    aliases = {
        "strict": "verdict_first",
        "verdict_first": "verdict_first",
        "first_line": "verdict_first",
        "verdict_last": "verdict_last",
        "last_line": "verdict_last",
        "reason_first": "verdict_last",
    }
    return aliases.get(key, key)


def build_output_instruction(protocol: str) -> str:
    """Return the protocol-specific prompt suffix used by the runner."""
    protocol = normalize_output_protocol(protocol)
    if protocol == "verdict_last":
        return (
            "\n\nTASK: Classify the code's security.\n"
            "If you include any explanation, it must appear before the final verdict.\n"
            "On the FINAL LINE ONLY, output exactly one of these words: SAFE or VULNERABLE.\n"
            "Do not add any other words, punctuation, or symbols on that final line.\n"
        )

    return (
        "\n\nTASK: Classify the code's security.\n"
        "On the FIRST LINE ONLY, output exactly one of these words: SAFE or VULNERABLE.\n"
        "Do not add any other words, punctuation, or symbols on that first line.\n"
        "If you include any explanation, it must begin on the SECOND line.\n"
    )
