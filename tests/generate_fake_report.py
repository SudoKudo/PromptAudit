"""Generate synthetic experiment output to check HTML report rendering."""

import os
import random
import sys
import uuid
from datetime import datetime, timezone

# Ensure the project root (that contains `evaluation/`) is on sys.path.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from evaluation.report import HtmlReport
from evaluation.metrics import Metrics
from core import __version__

random.seed(1234)

DATASETS = [
    "cvefixes_1000 (synthetic)",
    "bigvul_1000 (synthetic)",
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
    "self_verification",
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


def make_combo_records(n_samples=20, vulnerable_prevalence=0.35):
    """
    Build synthetic records for dataset, model, prompt, protocol, and parser choices.

    Each record mirrors the structure emitted by the real runner so the HTML
    report can be developed without running a full experiment matrix.
    """
    records = []
    generated_at = datetime.now(timezone.utc).isoformat()

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

                    if len(preds) % 7 == 0:
                        pred = "unknown"
                    calls = 5 if prompt == "self_consistency" else 1
                    measured = len(preds) % 13 != 0

                    preds.append({
                        "id": sample_id,
                        "language": language,
                        "pred": pred,
                        "gold": gold,
                        "cve_id": f"CVE-DEMO-{len(preds) // 2:04d}",
                        "pair_id": len(preds) // 2,
                        "parse_tier": "unknown" if pred == "unknown" else "strict_line",
                        "decision_calls": calls,
                        "decision_seconds": calls * .5,
                        "decision_prompt_tokens": calls * 500 if measured else None,
                        "decision_output_tokens": calls * 80 if measured else None,
                        "decision_output_limit_hits": int(len(preds) % 9 == 0) if measured else None,
                        "decision_generation_errors": int(len(preds) == 0),
                        "distinct_responses": min(calls, 1 + len(preds) % 4),
                    })

                tracker = Metrics()
                for row in preds:
                    tracker.add(row["gold"], row["pred"])
                tracker.compute()

                records.append({
                    "dataset": dataset,
                    "model": model,
                    "prompt": prompt,
                    "language": "mixed",
                    "languages_present": sorted({row["language"] for row in preds}),
                    "language_counts": {lang: sum(row["language"] == lang for row in preds) for lang in LANGS},
                    "predictions": preds,
                    **tracker.to_dict(),
                    "completed_samples": len(preds),
                    "total_samples": len(preds),
                    "is_partial": False,
                    "params": {
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "top_k": 40,
                        "max_new_tokens": 1024,
                        "context_window": 2048 if model.startswith("falcon:") else 16384,
                        "repetition_penalty": 1.0,
                        "num_beams": 1,
                        "sc_samples": 5,
                        "seed": 42,
                        "stop_sequences": [],
                        "experiment_name": "Synthetic report preview",
                        "experiment_notes": "Simulated values for checking layout and controls.",
                        "generated_at": generated_at,
                    },
                })

    expanded = []
    for record in records:
        calls = sum(row["decision_calls"] for row in record["predictions"])
        for protocol in ("verdict_first", "verdict_last"):
            for parser_index, parser in enumerate(("strict", "structured", "full")):
                fresh = calls if parser_index == 0 and record["prompt"] != "adaptive_cot" else 0
                shared = min(3, calls) if parser_index == 0 and record["prompt"] == "zero_shot" else 0
                fresh -= shared
                expanded.append({**record, "output_protocol": protocol, "parser_mode": parser,
                    "inference_performance": {
                        "generated_calls": fresh, "run_reuses": calls - fresh - shared, "shared_cache_hits": shared,
                        "generation_seconds": fresh * .5, "wall_seconds": fresh * .25 + .04, "workers": 2,
                    }})
    return expanded


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
        version=f"v{__version__} synthetic preview",
        author="PromptAudit",
    )

    print(f"[INFO] Fake report written to: {out_path} (records: {len(records)})")


if __name__ == "__main__":
    main()
