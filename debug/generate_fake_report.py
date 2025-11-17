# generate_realistic_fake_report.py
# Realistic fake report generator for testing evaluation/report.py (Glacier UI / Code 2.0)
#
# I use this script to generate a fully-populated, realistic-looking HTML report
# without having to run the full experiment pipeline. It feeds synthetic data
# into HtmlReport so I can visually debug:
#   - Tables
#   - Charts
#   - Filters
#   - Leaderboards
#   - Export buttons
#
# It produces grouped records (one per model+prompt+dataset combo), each with:
#   - params (experiment settings)
#   - aggregate metrics: TP, TN, FP, FN, Accuracy, Precision, Recall, F1
#   - predictions: list of per-sample dicts {id, language, pred, gold, confidence}
#
# Output: results/fake_report.html (uses evaluation.report.HtmlReport)

import os
import sys
import random
import uuid
from datetime import datetime
from collections import defaultdict

# Ensure the project root (that contains `evaluation/`) is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.report import HtmlReport

# Fix the random seed so the fake report is deterministic across runs.
random.seed(1234)

# ----------------------------------------------------------------------
# Configuration: datasets, models, prompts, languages, and priors
# ----------------------------------------------------------------------

# Logical dataset names to appear in the report (not tied to real loaders here).
DATASETS = [
    "toy",
    "synthetic-small",
    "realworld-v1",
    "realworld-v2",
    "mixed-benchmark",
]

# Model identifiers as they would appear in my real experiments.
MODELS = [
    "gemma:7b-instruct",
    "codellama:7b-instruct",
    "mistral:latest",
    "falcon:7b-instruct",
]

# Prompting strategies used in Code 2.0.
PROMPTS = [
    "zero_shot",
    "few_shot",
    "cot",
    "self_consistency",
    "adaptive_cot",
]

# Example programming languages for sample snippets.
LANGS = ["Python", "C", "C++", "Java", "JS"]

# Realistic priors for plausibility
# I use these to nudge metrics so some models/prompts look slightly better.
MODEL_PRIOR = {
    "gemma:7b-instruct": 0.84,
    "codellama:7b-instruct": 0.82,
    "mistral:latest": 0.86,
    "falcon:7b-instruct": 0.80,
}
PROMPT_BONUS = {
    "zero_shot": 0.00,
    "few_shot": 0.01,
    "cot": 0.015,
    "self_consistency": 0.02,
    "adaptive_cot": 0.025,
}
DATASET_DIFFICULTY = {
    # Positive values make the dataset “easier” (higher expected performance).
    "toy": +0.03,
    "synthetic-small": +0.01,
    # Negative values make the dataset “harder”.
    "realworld-v1": -0.02,
    "realworld-v2": -0.03,
    "mixed-benchmark": -0.01,
}
LANG_NOISE = {
    # Small language-specific adjustments to the base probability.
    "Python": +0.005,
    "C": -0.010,
    "C++": -0.005,
    "Java": 0.000,
    "JS": +0.002,
}


def clamp01(x):
    """Clamp a numeric value into the closed interval [0.0, 1.0]."""
    return max(0.0, min(1.0, x))


def compute_f1(prec, rec):
    """
    Compute the F1 score given precision and recall.

    Args:
        prec (float): Precision value between 0 and 1.
        rec  (float): Recall value between 0 and 1.

    Returns:
        float: F1 score, or 0.0 if precision + recall is zero to avoid division by zero.
    """
    if prec + rec == 0:
        return 0.0
    return 2 * (prec * rec) / (prec + rec)


def make_combo_records(n_samples=20, vulnerable_prevalence=0.35):
    """
    Build one record per (dataset, model, prompt) combo with n_samples per record.

    Each record contains:
      - dataset, model, prompt, language (majority/primary language for header)
      - params (fake generation settings)
      - TP, TN, FP, FN, Accuracy, Precision, Recall, F1
      - predictions: list of per-sample dicts {
            id,        # short random UUID fragment
            language,  # randomly chosen language for that sample
            pred,      # "safe" or "vulnerable"
            gold,      # gold label for the sample
            confidence # pseudo probability/confidence value
        }

    I use this structure to closely match what the real experiment runner produces,
    so that the HTML report can be tested as if it were running on real results.
    """
    records = []

    # Iterate over all combinations of dataset, model, and prompt.
    for ds in DATASETS:
        for md in MODELS:
            for pr in PROMPTS:
                # Choose a primary language for this combo to display in headers.
                primary_lang = random.choice(LANGS)

                # Base performance probability combines:
                #   - model prior
                #   - prompt bonus
                #   - dataset difficulty
                #   - language-specific noise (for the primary language)
                base_prob = (
                    MODEL_PRIOR.get(md, 0.80)
                    + PROMPT_BONUS.get(pr, 0.0)
                    + DATASET_DIFFICULTY.get(ds, 0.0)
                    + LANG_NOISE.get(primary_lang, 0.0)
                )
                base_prob = clamp01(base_prob)

                # Simulate per-sample predictions
                preds = []
                # Track confusion-matrix counts as we go.
                counts = defaultdict(int)  # keys: "TP", "TN", "FP", "FN"

                for i in range(n_samples):
                    # Short unique ID for each synthetic sample.
                    sample_id = str(uuid.uuid4())[:8]

                    # Sample the language per example to show multi-language behavior in the report.
                    lang = random.choice(LANGS)

                    # Draw the gold (true) label based on a prevalence rate.
                    gold = "vulnerable" if random.random() < vulnerable_prevalence else "safe"

                    # Prediction: mimic base accuracy but add per-sample noise.
                    # If gold == "safe": probability of predicting "safe" is around base_prob.
                    # If gold == "vulnerable": probability of predicting "vulnerable" is around base_prob.
                    flip_noise = random.gauss(0, 0.06)  # Gaussian noise for each sample.

                    if gold == "safe":
                        p_safe_prob = clamp01(base_prob + LANG_NOISE.get(lang, 0.0) + flip_noise)
                        pred = "safe" if random.random() < p_safe_prob else "vulnerable"
                    else:
                        p_vuln_prob = clamp01(base_prob + LANG_NOISE.get(lang, 0.0) + flip_noise)
                        pred = "vulnerable" if random.random() < p_vuln_prob else "safe"

                    # Simulated confidence score in the range [0.55, 0.95].
                    if pred == "safe":
                        confidence = round(0.55 + random.random() * 0.4, 3)  # 0.55 - 0.95
                    else:
                        confidence = round(0.55 + random.random() * 0.4, 3)

                    # Update confusion matrix counts based on gold vs pred.
                    if pred == "vulnerable" and gold == "vulnerable":
                        counts["TP"] += 1
                    elif pred == "vulnerable" and gold == "safe":
                        counts["FP"] += 1
                    elif pred == "safe" and gold == "safe":
                        counts["TN"] += 1
                    elif pred == "safe" and gold == "vulnerable":
                        counts["FN"] += 1

                    # Store the per-sample prediction record.
                    preds.append({
                        "id": sample_id,
                        "language": lang,
                        "pred": pred,
                        "gold": gold,
                        "confidence": confidence
                    })

                # Compute aggregated metrics from counts for this combo.
                TP = counts["TP"]
                TN = counts["TN"]
                FP = counts["FP"]
                FN = counts["FN"]

                total = TP + TN + FP + FN if (TP + TN + FP + FN) > 0 else 1
                accuracy = (TP + TN) / total
                precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
                recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
                f1 = compute_f1(precision, recall)

                # Build the full record for this (dataset, model, prompt) combination.
                record = {
                    "dataset": ds,
                    "model": md,
                    "prompt": pr,
                    "language": primary_lang,
                    "predictions": preds,

                    # Aggregated counts and metrics so HtmlReport can build tables/leaderboards.
                    "TP": TP,
                    "TN": TN,
                    "FP": FP,
                    "FN": FN,
                    "Accuracy": round(accuracy, 3),
                    "Precision": round(precision, 3),
                    "Recall": round(recall, 3),
                    "F1": round(f1, 3),

                    # Parameters for the (simulated) experiment run.
                    "params": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "top_k": 40,
                        "max_new_tokens": 120,
                        "repetition_penalty": 1.0,
                        "num_beams": 1,
                        "sc_samples": 5,
                        "seed": 42,
                        "stop_sequences": ["SAFE", "VULNERABLE"],
                        "experiment_name": "Demo: Glacier realistic fake",
                        "experiment_notes": "Auto-generated realistic demo data for report UI testing",
                        # Timestamp of when the data was generated (UTC, ISO-8601).
                        "generated_at": datetime.utcnow().isoformat() + "Z"
                    }
                }

                records.append(record)

    return records


def main():
    """
    Main entry point for generating a fake HTML report.

    Steps:
      1. Ensure the output directory exists.
      2. Generate realistic synthetic records.
      3. Use HtmlReport to render the HTML report to disk.
    """
    out_dir = "results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fake_report.html")

    # Create realistic records for testing the report.
    # Here: ~5 datasets * 4 models * 5 prompts = 100 combos,
    # each with 15 samples => ~1500 per-sample predictions.
    records = make_combo_records(n_samples=15, vulnerable_prevalence=0.35)

    # Instantiate and write HTML using the existing HtmlReport class.
    report = HtmlReport(records)
    report.write(
        output_path=out_path,
        records=records,
        metric_keys=["TP", "TN", "FP", "FN", "Accuracy", "Precision", "Recall", "F1"],
        version="v6.8-fakegen",
        author="Steffen Camarato — University of Central Florida"
    )

    print(f"[INFO] Fake report written to: {out_path} (records: {len(records)})")


if __name__ == "__main__":
    # Allow the script to be run directly: `python generate_realistic_fake_report.py`
    main()
