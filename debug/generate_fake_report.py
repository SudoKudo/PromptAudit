"""Generate synthetic experiment output for report-development work."""

import os
import random
import sys
import uuid
from collections import defaultdict
from datetime import datetime

# Ensure the project root (that contains `evaluation/`) is on sys.path.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.report import HtmlReport

random.seed(1234)

DATASETS = [
    "toy",
    "synthetic-small",
    "realworld-v1",
    "realworld-v2",
    "mixed-benchmark",
]

MODELS = [
    "gemma:7b-instruct",
    "codellama:7b-instruct",
    "mistral:latest",
    "falcon:7b-instruct",
]

PROMPTS = [
    "zero_shot",
    "few_shot",
    "cot",
    "self_consistency",
    "adaptive_cot",
]

LANGS = ["Python", "C", "C++", "Java", "JS"]

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
    "toy": +0.03,
    "synthetic-small": +0.01,
    "realworld-v1": -0.02,
    "realworld-v2": -0.03,
    "mixed-benchmark": -0.01,
}

LANG_NOISE = {
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
    """Compute F1 from precision and recall."""
    if prec + rec == 0:
        return 0.0
    return 2 * (prec * rec) / (prec + rec)


def make_combo_records(n_samples=20, vulnerable_prevalence=0.35):
    """
    Build one synthetic record per (dataset, model, prompt) combination.

    Each record mirrors the structure emitted by the real runner so the HTML
    report can be developed without running a full experiment matrix.
    """
    records = []

    for dataset in DATASETS:
        for model in MODELS:
            for prompt in PROMPTS:
                primary_lang = random.choice(LANGS)
                base_prob = clamp01(
                    MODEL_PRIOR.get(model, 0.80)
                    + PROMPT_BONUS.get(prompt, 0.0)
                    + DATASET_DIFFICULTY.get(dataset, 0.0)
                    + LANG_NOISE.get(primary_lang, 0.0)
                )

                preds = []
                counts = defaultdict(int)

                for _ in range(n_samples):
                    sample_id = str(uuid.uuid4())[:8]
                    language = random.choice(LANGS)
                    gold = "vulnerable" if random.random() < vulnerable_prevalence else "safe"
                    flip_noise = random.gauss(0, 0.06)

                    if gold == "safe":
                        safe_prob = clamp01(base_prob + LANG_NOISE.get(language, 0.0) + flip_noise)
                        pred = "safe" if random.random() < safe_prob else "vulnerable"
                    else:
                        vuln_prob = clamp01(base_prob + LANG_NOISE.get(language, 0.0) + flip_noise)
                        pred = "vulnerable" if random.random() < vuln_prob else "safe"

                    confidence = round(0.55 + random.random() * 0.4, 3)

                    if pred == "vulnerable" and gold == "vulnerable":
                        counts["TP"] += 1
                    elif pred == "vulnerable" and gold == "safe":
                        counts["FP"] += 1
                    elif pred == "safe" and gold == "safe":
                        counts["TN"] += 1
                    else:
                        counts["FN"] += 1

                    preds.append({
                        "id": sample_id,
                        "language": language,
                        "pred": pred,
                        "gold": gold,
                        "confidence": confidence,
                    })

                tp = counts["TP"]
                tn = counts["TN"]
                fp = counts["FP"]
                fn = counts["FN"]
                total = tp + tn + fp + fn if (tp + tn + fp + fn) > 0 else 1
                accuracy = (tp + tn) / total
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = compute_f1(precision, recall)

                records.append({
                    "dataset": dataset,
                    "model": model,
                    "prompt": prompt,
                    "language": primary_lang,
                    "predictions": preds,
                    "TP": tp,
                    "TN": tn,
                    "FP": fp,
                    "FN": fn,
                    "Accuracy": round(accuracy, 3),
                    "Precision": round(precision, 3),
                    "Recall": round(recall, 3),
                    "F1": round(f1, 3),
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
                        "experiment_name": "PromptAudit sample report",
                        "experiment_notes": "Auto-generated demo data for report UI testing",
                        "generated_at": datetime.utcnow().isoformat() + "Z",
                    },
                })

    return records


def main():
    """Generate a synthetic HTML report under the results directory."""
    out_dir = "results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "fake_report.html")
    records = make_combo_records(n_samples=15, vulnerable_prevalence=0.35)

    report = HtmlReport(records)
    report.write(
        output_path=out_path,
        records=records,
        metric_keys=["TP", "TN", "FP", "FN", "Accuracy", "Precision", "Recall", "F1"],
        version="v6.8-fakegen",
        author="PromptAudit Demo",
    )

    print(f"[INFO] Fake report written to: {out_path} (records: {len(records)})")


if __name__ == "__main__":
    main()
