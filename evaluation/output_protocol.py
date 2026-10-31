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
    if key not in aliases:
        raise ValueError(f"Unknown output protocol: {value}")
    return aliases[key]


def build_output_instruction(protocol: str) -> str:
    """Keep formatting requirements shared while changing verdict placement."""
    protocol = normalize_output_protocol(protocol)
    instructions = (
        "\n\nRESPONSE FORMAT:\n"
        "Use plain text without headings, Markdown, code fences, or a repeated copy of the code.\n"
        "Give exactly one standalone verdict line containing only SAFE or VULNERABLE, with no prefix, punctuation, quotes, or formatting.\n"
        "Follow the task instructions for whether to explain. For a direct answer, output only the verdict word.\n"
        "When reasoning or verification is requested, include it in the position specified below and keep it focused on the code.\n"
    )
    if protocol == "verdict_last":
        return instructions + (
            "If you provide an explanation, write it first. Do not give the verdict before the explanation.\n"
            "Finish with a separate FINAL LINE containing only SAFE or VULNERABLE. Do not write anything after that line.\n"
            "Required response layout (replace the placeholders; do not print the brackets):\n"
            "[explanation only if required by the task]\n"
            "[verdict]\n"
            "Replace [verdict] with exactly SAFE or VULNERABLE.\n"
        )

    return instructions + (
        "On the FIRST LINE ONLY, output SAFE or VULNERABLE. Do not write anything before that line.\n"
        "Put any requested explanation on following lines. Do not repeat the verdict later.\n"
        "Required response layout (replace the placeholders; do not print the brackets):\n"
        "[verdict]\n"
        "[explanation only if required by the task]\n"
        "Replace [verdict] with exactly SAFE or VULNERABLE.\n"
    )
