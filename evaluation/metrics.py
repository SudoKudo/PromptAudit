# evaluation/metrics.py — Confusion matrix + derived metrics for Glacier Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# This dataclass tracks all components of the confusion matrix:
#   - TP: True Positives
#   - TN: True Negatives
#   - FP: False Positives
#   - FN: False Negatives
#
# From these, I compute:
#   - Accuracy
#   - Precision
#   - Recall
#   - F1
#
# This class is used by the experiment runner and by the report generator.
# It provides a unified, consistent source of metric values for all models.


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

    # ---------------------------
    # Derived performance metrics
    # ---------------------------
    Accuracy: float = 0.0
    Precision: float = 0.0
    Recall: float = 0.0
    F1: float = 0.0

    # ---------------------------
    # Count of unrecognized labels
    # ---------------------------
    # If a prediction label is neither "safe" nor "vulnerable", I consider it Unknown.
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
            - Anything else increments the "Unknown" counter.
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

    # ---------------------------------------------------------------
    # Compute final metrics from accumulated confusion matrix values
    # ---------------------------------------------------------------
    def compute(self):
        """
        Compute Accuracy, Precision, Recall, and F1 from the confusion matrix.

        Formulas:
            Accuracy  = (TP + TN) / (TP + TN + FP + FN)
            Precision =  TP       / (TP + FP)
            Recall    =  TP       / (TP + FN)
            F1        =  2 * (Precision * Recall) / (Precision + Recall)

        Notes:
            - All divisions are guarded to avoid ZeroDivisionError.
            - If no samples were processed, all metrics remain at 0.0.
        """
        total = self.TP + self.TN + self.FP + self.FN

        # Guard: If no samples counted, accuracy should be 0.
        self.Accuracy = (self.TP + self.TN) / total if total else 0.0

        # Precision: How many predicted "vulnerable" were actually correct?
        self.Precision = self.TP / (self.TP + self.FP) if (self.TP + self.FP) else 0.0

        # Recall: How many gold "vulnerable" did we correctly identify?
        self.Recall = self.TP / (self.TP + self.FN) if (self.TP + self.FN) else 0.0

        # F1: Harmonic mean of precision and recall.
        self.F1 = (
            2 * self.Precision * self.Recall / (self.Precision + self.Recall)
            if (self.Precision + self.Recall)
            else 0.0
        )

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
            "Accuracy": self.Accuracy,
            "Precision": self.Precision,
            "Recall": self.Recall,
            "F1": self.F1,
            "Unknown": self.Unknown,
        }