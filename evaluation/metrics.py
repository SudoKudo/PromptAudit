<<<<<<< Updated upstream
# evaluation/metrics.py — Confusion matrix + derived metrics for PromptAudit v2.0
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

=======
"""Track confusion counts and derive PromptAudit evaluation metrics."""
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
    Incorrect: int = 0 # Predicted unknown but gold safe
    UNFN: int = 0 # Predicted vulnerable but gold vulnerable
=======
    UnFN: int = 0  # Vulnerable sample that yielded an unknown/abstaining response
    Incorrect: int = 0  # Non-vulnerable sample that yielded an unknown/abstaining response
>>>>>>> Stashed changes

    # ---------------------------
    # Derived performance metrics
    # ---------------------------
    Accuracy: float = 0.0
    Precision: float = 0.0
    Recall: float = 0.0
    F1: float = 0.0
<<<<<<< Updated upstream
    Effective_F1: float = 0.0
    Abstention: float = 0.0
    Coverage: float = 0.0
=======
    AbstentionRate: float = 0.0
    Coverage: float = 0.0
    EffectiveF1: float = 0.0
>>>>>>> Stashed changes

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
        Update TP, TN, FP, FN, Incorrect, UNFN counts based on the gold label and the predicted label.

        Args:
            gold (str): True label ("safe" or "vulnerable").
            pred (str): Model prediction ("safe", "vulnerable", "unknown", or something else).

        Behavior:
            - If pred == "vulnerable":
                * gold == "vulnerable" → TP
                * gold == "safe"       → FP
            - If pred == "safe":
                * gold == "safe"       → TN
                * gold == "vulnerable" → FN
<<<<<<< Updated upstream
            - If pred == "Unknwon":
                * gold == "safe"       → Incorrect
                * gold == "vulnerable" → UNFN    


            - Anything else increments the "Unknown" counter.
=======
            - Anything else increments the "Unknown" counter and is split into:
                * UnFN if the gold label is vulnerable
                * Incorrect otherwise
>>>>>>> Stashed changes
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

        elif pred == "Unknwon":
            if gold == "safe":
                self.Incorrect += 1
            else:
                self.UNFN += 1
        # else:
            # Unexpected label — useful for debugging model outputs.
<<<<<<< Updated upstream
        #    self.Unknown += 1
=======
            self.Unknown += 1
            if gold == "vulnerable":
                self.UnFN += 1
            else:
                self.Incorrect += 1
>>>>>>> Stashed changes

    # ---------------------------------------------------------------
    # Compute final metrics from accumulated confusion matrix values
    # ---------------------------------------------------------------
    def compute(self):
        """
        Compute abstention-aware metrics from the accumulated outcomes.

        Formulas:
<<<<<<< Updated upstream
            Accuracy  = (TP + TN) / (TP + TN + FP + FN + UNFN)
            Precision =  TP       / (TP + FP)
            Recall    =  TP       / (TP + FN + UNFN)
            F1        =  2 * (Precision * Recall) / (Precision + Recall)
            Abstention = (Incorrect + UNFN) / (TP + TN + FP + FN + UNFN + Incorrect) 
            Coverage = 1 - Abstention
            Effective_F1: F1 * Coverage
 
    

=======
            Accuracy  = (TP + TN) / (TP + TN + FP + FN + UnFN)
            Precision =  TP       / (TP + FP)
            Recall    =  TP       / (TP + FN + UnFN)
            F1        =  2 * (Precision * Recall) / (Precision + Recall)
            Abstention Rate = (Incorrect + UnFN) / Total Outcomes
            Coverage = 1 - Abstention Rate
            Effective F1 = F1 * Coverage
>>>>>>> Stashed changes

        Notes:
            - All divisions are guarded to avoid ZeroDivisionError.
            - If no samples were processed, all metrics remain at 0.0.
        """
        answered_total = self.TP + self.TN + self.FP + self.FN + self.UnFN
        total = answered_total + self.Incorrect

<<<<<<< Updated upstream
        # Guard: If no samples counted, accuracy should be 0.
        self.Accuracy = (self.TP + self.TN) / (self.TP + self.TN + self.FP + self.FN + self.UNFN) if (self.TP + self.TN + self.FP + self.FN + self.UNFN) else 0.0
=======
        # Accuracy follows the paper's definition and treats abstentions on
        # vulnerable samples as unknown false negatives.
        self.Accuracy = (self.TP + self.TN) / answered_total if answered_total else 0.0
>>>>>>> Stashed changes

        # Precision: How many predicted "vulnerable" were actually correct?
        self.Precision = self.TP / (self.TP + self.FP) if (self.TP + self.FP) else 0.0

<<<<<<< Updated upstream
        # Recall: How many gold "vulnerable" did we correctly identify?
        self.Recall = self.TP / (self.TP + self.FN + self.UNFN) if (self.TP + self.FN + self.UNFN) else 0.0
=======
        # Recall includes vulnerable abstentions, matching the paper's UnFN definition.
        recall_denominator = self.TP + self.FN + self.UnFN
        self.Recall = self.TP / recall_denominator if recall_denominator else 0.0
>>>>>>> Stashed changes

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

        # Abstention: The rate of missings
        self.Abstention = (
            ( self.Incorrect + self.Unknown )/ (self.TP + self.TN + self.FP + self.FN + self.Incorrect + self.UNFN)
            if (self.TP + self.TN + self.FP + self.FN + self.Incorrect + self.UNFN)
            else 0.0    
        )

        # Coverage: 1 - The rate of missings
        self.Coverage = (
            1 - self.Abstention   
        )

        # Effective F1: Done to evaluate model performance across multiple classes or datasets
        self.Effective_F1 = (
            self.F1 * self.Abstention
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
<<<<<<< Updated upstream
            "Incorrect": self.Incorrect,
            "UNFN": self.UNFN,
=======
            "UnFN": self.UnFN,
            "Incorrect": self.Incorrect,
>>>>>>> Stashed changes
            "Accuracy": self.Accuracy,
            "Precision": self.Precision,
            "Recall": self.Recall,
            "F1": self.F1,
<<<<<<< Updated upstream
            "Abstention Rate": self.Abstention,
            "Coverage": self.Coverage,
            "Effective F1": self.Effective_F1,
        }
=======
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
>>>>>>> Stashed changes
