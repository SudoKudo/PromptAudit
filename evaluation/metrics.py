"""Track confusion counts and derive PromptAudit evaluation metrics."""

from dataclasses import dataclass


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

    # ---------------------------------------------------------------
    # Update counters for a single prediction / gold-label comparison
    # ---------------------------------------------------------------
    def add(self, gold: str, pred: str):
        """
        Update TP, TN, FP, FN counts based on the gold label and the predicted label.

        Args:
            gold (str): True label ("safe" or "vulnerable").
            pred (str): Model prediction ("safe", "vulnerable", or something else).

        Behavior:
            - If pred == "vulnerable":
                * gold == "vulnerable" → TP
                * gold == "safe"       → FP
            - If pred == "safe":
                * gold == "safe"       → TN
                * gold == "vulnerable" → FN
            - Anything else increments the "Unknown" counter and is split into:
                * UnFN if the gold label is vulnerable
                * Incorrect otherwise
        """
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
            # Unexpected label — useful for debugging model outputs.
            self.Unknown += 1
            if gold == "vulnerable":
                self.UnFN += 1
            else:
                self.Incorrect += 1

    # ---------------------------------------------------------------
    # Compute final metrics from accumulated confusion matrix values
    # ---------------------------------------------------------------
    def compute(self):
        """
        Compute abstention-aware metrics from the accumulated outcomes.

        Formulas:
            Accuracy  = (TP + TN) / (TP + TN + FP + FN + UnFN)
            Precision =  TP       / (TP + FP)
            Recall    =  TP       / (TP + FN + UnFN)
            F1        =  2 * (Precision * Recall) / (Precision + Recall)
            Abstention Rate = (Incorrect + UnFN) / Total Outcomes
            Coverage = 1 - Abstention Rate
            Effective F1 = F1 * Coverage

        Notes:
            - All divisions are guarded to avoid ZeroDivisionError.
            - If no samples were processed, all metrics remain at 0.0.
        """
        answered_total = self.TP + self.TN + self.FP + self.FN + self.UnFN
        total = answered_total + self.Incorrect

        # Accuracy follows the paper's definition and treats abstentions on
        # vulnerable samples as unknown false negatives.
        self.Accuracy = (self.TP + self.TN) / answered_total if answered_total else 0.0

        # Precision: How many predicted "vulnerable" were actually correct?
        self.Precision = self.TP / (self.TP + self.FP) if (self.TP + self.FP) else 0.0

        # Recall includes vulnerable abstentions, matching the paper's UnFN definition.
        recall_denominator = self.TP + self.FN + self.UnFN
        self.Recall = self.TP / recall_denominator if recall_denominator else 0.0

        # F1: Harmonic mean of precision and recall.
        self.F1 = (
            2 * self.Precision * self.Recall / (self.Precision + self.Recall)
            if (self.Precision + self.Recall)
            else 0.0
        )
        abstentions = self.Incorrect + self.UnFN
        self.AbstentionRate = abstentions / total if total else 0.0
        self.Coverage = 1.0 - self.AbstentionRate if total else 0.0
        self.EffectiveF1 = self.F1 * self.Coverage

    # ---------------------------------------------------------------
    # Export the metrics in a dictionary so the report can format them
    # ---------------------------------------------------------------
    def to_dict(self):
        """
        Return all metric values as a dictionary.

        This is used by:
            - ExperimentRunner (for CSV summaries)
            - HtmlReport (for tables, charts, and leaderboards)
        """
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
