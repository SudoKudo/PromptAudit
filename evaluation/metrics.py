"""Track confusion counts and derive PromptAudit evaluation metrics."""

from dataclasses import dataclass


DEFAULT_METRICS = ("Accuracy", "Precision", "Recall", "F1", "Coverage", "AbstentionRate", "EffectiveF1")
METRIC_HELP = {
    "Accuracy": "Correct SAFE/VULNERABLE predictions divided by all evaluated samples: (TP + TN) / (TP + TN + FP + FN + UnFN + Incorrect). Unresolved SAFE and VULNERABLE responses both count as incorrect outcomes.",
    "Precision": "Among predictions labeled VULNERABLE, the fraction whose gold label is VULNERABLE: TP / (TP + FP).",
    "Recall": "Fraction of vulnerable samples detected: TP / (TP + FN + vulnerable abstentions). Unresolved vulnerable outputs count as missed detections.",
    "F1": "Harmonic mean of precision and recall. Uses the project's recall definition, which includes vulnerable abstentions.",
    "Coverage": "Fraction of all samples that receive a usable SAFE or VULNERABLE prediction. UNKNOWN predictions reduce coverage.",
    "AbstentionRate": "Fraction of all samples whose prediction is UNKNOWN, including unresolved or failed responses. Equal to 1 - Coverage.",
    "EffectiveF1": "F1 multiplied by Coverage. This project-specific score combines classification performance with the fraction of usable predictions.",
}
DIAGNOSTIC_HELP = {
    "calls_per_sample": "Mean model calls used by the decision rule. A first-draw decision uses one call; a majority uses the requested pool, including unresolved draws.",
    "seconds_per_sample": "Mean recorded generation time for calls used by the decision rule. Shared response pools are reused rather than generated for each policy.",
    "prompt_tokens_per_sample": "Mean total input tokens across the decision calls, when the backend reports every count. Tokenizers differ between models; unavailable measurements remain missing.",
    "output_tokens_per_sample": "Mean total generated tokens across the decision calls, when every count is available. This measures output cost, not reasoning quality or causality.",
    "distinct_responses_per_pool": "Mean number of different raw response strings in each sampled pool. Different seeds can still produce identical responses; string diversity does not establish reasoning diversity.",
    "output_limit_hit_rate": "Fraction of decision calls reported to reach the output cap. Capped outputs may lack a completed verdict. Missing backend measurements remain unavailable.",
    "output_limit_measurement_coverage": "Fraction of sample decisions with complete output-limit measurements. Use this to judge how much evidence supports the reported limit-hit rate.",
    "generation_errors_per_sample": "Mean failed generation calls used by the decision rule. Failures remain UNKNOWN outcomes and are not silently retried.",
    "paired_comparisons": "Compare predictions on the same samples, including label disagreement and metric differences. CVE-clustered intervals need at least two CVEs and positive bootstrap resamples; they are conditional on the run seed and do not correct for multiple comparisons.",
    "rankings": "Compare approach rankings across selected task wordings using F1, Recall, and EffectiveF1. Ties share a rank; results describe the selected templates, not universal strategy superiority.",
    "diagnostics": "Show decision-call cost, generation time, response-string diversity, token use, output-limit hits, and generation errors. Missing backend measurements stay unavailable.",
}


@dataclass
class Metrics:
    # ---------------------------
    # Raw confusion-matrix counts
    # ---------------------------
    TP: int = 0  # Predicted vulnerable AND gold vulnerable
    TN: int = 0  # Predicted safe AND gold safe
    FP: int = 0  # Predicted vulnerable but gold safe
    FN: int = 0  # Predicted safe but gold vulnerable
    UnFN: int = 0  # Vulnerable sample that yielded an unknown/abstaining response
    Incorrect: int = 0  # Non-vulnerable sample that yielded an unknown/abstaining response

    # ---------------------------
    # Derived performance metrics
    # ---------------------------
    Accuracy: float = 0.0
    Precision: float = 0.0
    Recall: float = 0.0
    F1: float = 0.0
    AbstentionRate: float = 0.0
    Coverage: float = 0.0
    EffectiveF1: float = 0.0

    # ---------------------------
    # Count of unrecognized labels
    # ---------------------------
    # The raw count of outputs that did not produce a definitive SAFE/VULNERABLE label.
    Unknown: int = 0

    def add(self, gold: str, pred: str):
        """Count one prediction, retaining abstentions for each gold class."""
        if gold not in {"safe", "vulnerable"}:
            raise ValueError("Gold labels must be safe or vulnerable; UNKNOWN is only a prediction outcome")
        if pred == "vulnerable":
            if gold == "vulnerable":
                self.TP += 1
            else:
                self.FP += 1

        elif pred == "safe":
            if gold == "safe":
                self.TN += 1
            else:
                self.FN += 1

        else:
            # Retain abstentions separately for each gold class.
            self.Unknown += 1
            if gold == "vulnerable":
                self.UnFN += 1
            else:
                self.Incorrect += 1

    def compute(self):
        """Derive the seven scores; empty denominators produce zero."""
        total = self.TP + self.TN + self.FP + self.FN + self.UnFN + self.Incorrect

        # Section 3.8 counts abstentions from both gold classes in the denominator.
        self.Accuracy = (self.TP + self.TN) / total if total else 0.0

        self.Precision = self.TP / (self.TP + self.FP) if (self.TP + self.FP) else 0.0

        # Recall includes vulnerable abstentions, matching the paper's UnFN definition.
        recall_denominator = self.TP + self.FN + self.UnFN
        self.Recall = self.TP / recall_denominator if recall_denominator else 0.0

        self.F1 = (
            2 * self.Precision * self.Recall / (self.Precision + self.Recall)
            if (self.Precision + self.Recall)
            else 0.0
        )
        abstentions = self.Incorrect + self.UnFN
        self.AbstentionRate = abstentions / total if total else 0.0
        self.Coverage = 1.0 - self.AbstentionRate if total else 0.0
        self.EffectiveF1 = self.F1 * self.Coverage

    def to_dict(self):
        """Return confusion counts and calculated scores for saved results."""
        return {
            "TP": self.TP,
            "TN": self.TN,
            "FP": self.FP,
            "FN": self.FN,
            "UnFN": self.UnFN,
            "Incorrect": self.Incorrect,
            "Accuracy": self.Accuracy,
            "Precision": self.Precision,
            "Recall": self.Recall,
            "F1": self.F1,
            "AbstentionRate": self.AbstentionRate,
            "Coverage": self.Coverage,
            "EffectiveF1": self.EffectiveF1,
            "Unknown": self.Unknown,
        }

    def load_state(self, state: dict | None):
        """Restore raw counters from a previously saved checkpoint state."""
        state = state or {}
        self.TP = int(state.get("TP", 0))
        self.TN = int(state.get("TN", 0))
        self.FP = int(state.get("FP", 0))
        self.FN = int(state.get("FN", 0))
        self.UnFN = int(state.get("UnFN", 0))
        self.Incorrect = int(state.get("Incorrect", 0))
        self.Unknown = int(state.get("Unknown", 0))
        self.compute()
        return self

    @classmethod
    def from_state(cls, state: dict | None):
        """Build a Metrics instance from a checkpointed raw-counter state."""
        return cls().load_state(state)


def refresh_record_accuracy(record):
    """Recalculate saved Accuracy when counts or sample predictions are available."""
    counts = ("TP", "TN", "FP", "FN", "UnFN", "Incorrect")
    if all(key in record for key in counts):
        tracker = Metrics.from_state(record)
    else:
        predictions = record.get("predictions")
        if not predictions or any(str(row.get("gold", "")).strip().lower() not in {"safe", "vulnerable"}
                                  for row in predictions):
            return dict(record)
        tracker = Metrics()
        for row in predictions:
            tracker.add(str(row["gold"]).strip().lower(), str(row.get("pred", "unknown")).strip().lower())
        tracker.compute()
    return {**record, "Accuracy": tracker.Accuracy}
