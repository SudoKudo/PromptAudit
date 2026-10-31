"""Compare aggregation policies on the same saved predictions."""

from collections import Counter


POLICIES = ("first", "majority_requested", "majority_valid")


def aggregate_votes(labels, policy="majority_requested", min_valid_votes=3):
    """Invalid votes stay in the requested-vote denominator, where applicable."""
    labels = list(labels)
    if not labels or any(x not in {"safe", "vulnerable", "unknown"} for x in labels):
        raise ValueError("Votes must be a nonempty list of parsed labels")
    if policy not in POLICIES:
        raise ValueError(f"Unknown aggregation policy: {policy}")
    if min_valid_votes < 1:
        raise ValueError("min_valid_votes must be positive")
    counts = Counter(x for x in labels if x != "unknown")
    valid = sum(counts.values())
    result = {"label": "unknown", "valid_votes": valid, "unknown_votes": len(labels) - valid,
              "vote_counts": dict(counts), "policy": policy, "reason": "no_valid_votes"}
    if policy == "first":
        result.update(label=labels[0], reason="first_draw")
        return result
    if policy == "majority_valid" and valid < min_valid_votes:
        result["reason"] = "too_few_valid_votes"
        return result
    denominator = len(labels) if policy == "majority_requested" else valid
    winners = [label for label, count in counts.items() if count > denominator / 2]
    if winners:
        result.update(label=winners[0], reason="majority")
    elif valid:
        result["reason"] = "tie_or_no_majority"
    return result
