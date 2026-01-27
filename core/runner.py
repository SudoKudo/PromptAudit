# core/runner.py — PromptAudit v2.0 

# Purpose: Orchestrates the full experiment lifecycle with self-consistency,
# adaptive prompt strategies, and graceful stop behavior.
#
# High-level responsibilities:
#   - Load datasets, models, and prompt strategies based on configuration/GUI selections
#   - Run every selected combination (dataset × model × prompt)
#   - Collect per-sample predictions and compute aggregate metrics
#   - Emit both CSV summaries and an interactive HTML report for analysis

import os
import csv
import time
import traceback
from evaluation.label_parser import parse_verdict  # Centralized SAFE/VULNERABLE/UNKNOWN parser
from evaluation.metrics import Metrics as MetricTracker   # Tracks confusion-matrix counts and derived metrics
from evaluation.report import HtmlReport                  # Renders the interactive HTML report
from code_datasets.dataset_loader import load_dataset     # Central dataset loader (local files + HF-based datasets)
from code_datasets._local_cve_dataset_loader import load_cvefixes_dataset
from models.model_loader import load_model                # Central model loader (Ollama, HF, API backends)
from prompts.prompt_loader import load_prompt_strategy as load_prompt  # Loads the configured prompt strategy object

class ExperimentRunner:
    """Coordinates execution of experiments across datasets, models, and prompts.

    The GUI (or CLI) passes:
        - Selected datasets
        - Selected models
        - Selected prompt strategies

    This runner then:
        - Iterates over every combination
        - Evaluates all samples for that combination
        - Accumulates metrics and predictions for downstream reporting
    """

    def __init__(self, cfg, progress=None):
        """
        Initialize the experiment runner.

        Args:
            cfg (dict): Configuration loaded from config.yaml
                        (generation defaults, model list, output paths, etc.).
            progress (callable): Callback for status messages (GUI/CLI logging).
                                 If omitted, defaults to printing to stdout.

        Internal state is initialized here so that multiple experiment runs can
        reuse the same runner instance with updated selections.
        """
        self.cfg = cfg
        # Snapshot of default generation settings (temperature, top_p, etc.) that
        # can be overridden or updated via the GUI before each run.
        self.gen_cfg = self.cfg.get("generation", {}).copy()
        self.models_cfg = self.cfg.get("models", [])
        self.prompts_cfg = self.cfg.get("prompts", [])
        # Stop flags are used by the GUI to interrupt long-running experiments cleanly.
        self.stop_flag = False
        self.stop_requested = False
        # These are populated by the GUI with the user’s specific run selections.
        self.selected_datasets = []     # Selected datasets
        self.selected_models = []       # Selected models
        self.selected_prompts = []      # Selected prompt strategies
        # progress is a callback that accepts a string; default behavior is print().
        self.progress = progress or (lambda msg: print(msg))
        # Each record represents one (dataset, model, prompt) run with metrics and predictions.
        self.records = []
        self.start_time = None

        # When True, log raw prompts/outputs for early samples.
        # This reads the top-level `debug_raw_outputs` from config.yaml.
        self.debug_raw_outputs = bool(self.cfg.get("debug_raw_outputs", True))

    # -----------------------------------------------------------------
    def run_all(self, selected_datasets, selected_models, selected_prompts):
        """Run all combinations of dataset, model, and prompt.

        Overall flow:
            for each dataset:
                load dataset
                for each model:
                    for each prompt:
                        run experiment and store a result record

        At the end of the loop, CSV and HTML artifacts are written from self.records.
        """
        self.start_time = time.time()
        # Reset records at the beginning of each experiment batch.
        self.records = []

        for dataset_item in selected_datasets:
            # Check stop flags so a user-initiated stop in the GUI halts at safe boundaries.
            if self.stop_requested or self.stop_flag:
                self.progress(f"⛔ Stopped before dataset {dataset_item}")
                break

            # Normalize dataset name:
            # - If a string is provided, use it directly.
            # - If a dict is provided, fall back to the "name" field.
            dataset_name = (
                dataset_item if isinstance(dataset_item, str)
                else dataset_item.get("name", str(dataset_item))
            )
            self.progress(f"Loading dataset: {dataset_name}")
            try:
                # Centralized dataset loader abstracts away data source details.
                dataset = load_dataset(dataset_name)
                self.progress(f"Loaded dataset: {dataset_name} (samples: {len(dataset)})")
            except Exception as e:
                # If a dataset fails to load, log and continue with remaining datasets.
                self.progress(f"❌ Failed to load {dataset_name}: {e}")
                continue

            if not dataset:
                # If the dataset is empty, there is nothing to evaluate.
                self.progress(f"⚠️ Dataset {dataset_name} returned no samples.")
                continue

            for model_name in selected_models:
                if self.stop_requested or self.stop_flag:
                    break

                for prompt_name in selected_prompts:
                    if self.stop_requested or self.stop_flag:
                        break

                    # Explicitly log the current (dataset, model, prompt) triple for traceability.
                    self.progress(f"Running {model_name} with prompt {prompt_name} on {dataset_name}")
                    try:
                        # _run_single performs the full evaluation for this combination.
                        result_record = self._run_single(dataset_name, dataset, model_name, prompt_name)
                        if result_record:
                            # Only append fully-completed runs to the global record list.
                            self.records.append(result_record)
                    except Exception as e:
                        # A failure for one combination should not terminate the entire batch.
                        self.progress(f"❌ Error during run: {e}")
                        traceback.print_exc()
                        continue

        # -----------------------------------------------------------------
        # Write CSV and HTML outputs
        # -----------------------------------------------------------------
        if not self.records:
            # No successful runs means no artifacts to generate.
            self.progress("⚠️ No valid records produced; skipping write.")
            return

        # First, write a CSV representation (metrics + per-sample predictions).
        self._write_csv(self.records)
        # Then, build the interactive HTML report from the same record set.
        self._write_report(self.records)

        # Summarize total wall-clock runtime for the entire experiment batch.
        elapsed = (time.time() - self.start_time) / 60
        self.progress(f"✅ All experiments finished in {elapsed:.1f} min")
        self.progress("✅ Run completed successfully")

    # -----------------------------------------------------------------
    def _run_single(self, dataset_name, dataset, model_name, prompt_name):
        """Run a single model/prompt combination on one dataset.

        For this specific (dataset, model, prompt) triple, the workflow is:
            - Prepare generation settings (GUI-driven)
            - Load the selected model backend
            - Iterate over every sample in the dataset
            - Ask the model to classify each sample as SAFE or VULNERABLE
            - Parse the label from the raw model output in a standardized way
            - Update aggregate metrics and store per-sample predictions
        """
        # Use the current GUI-driven generation configuration (not raw YAML defaults).
        # This ensures changes in the GUI immediately affect this run.
        gen_cfg = self.gen_cfg.copy()

        # This runner uses a single strict label protocol for all models:
        # the model must put SAFE or VULNERABLE as the first token on the
        # first non-empty line. Anything else is treated as invalid.
        label_protocol = "strict"
        self.progress(f"[MODE] Using '{label_protocol}' label protocol for {model_name}")

        # --- Output format behavior for binary SAFE/VULNERABLE labels ---
        # Do NOT override stop_sequences here. They remain whatever the GUI/config
        # specified. The SAFE/VULNERABLE protocol is enforced by:
        #   1) A strict natural-language instruction added to the prompt, and
        #   2) The parser below that only accepts SAFE/VULNERABLE labels.
        force_label_stop = True

        # Load the model with the generation configuration to ensure consistent behavior.
        model = load_model(model_name, gen_cfg)



        # Log effective generation parameters for transparency and reproducibility.
        import json
        self.progress(f"[PARAMS] {json.dumps(gen_cfg, indent=2)}")

        # Load the prompt strategy object (zero_shot, few_shot, cot, etc.).
        prompt_obj = load_prompt(prompt_name)
        
        # Some strategies (e.g., SelfConsistency) return a FINAL label instead
        # of a prompt string. We detect this via an optional flag.
        returns_label = getattr(prompt_obj, "returns_label", False)

        # MetricTracker accumulates confusion matrix and derived metrics over the dataset.
        m = MetricTracker()
        # Per-sample predictions are stored for detailed CSV export and error analysis.
        preds = []

        total = len(dataset)
        for i, sample in enumerate(dataset, start=1):
            # Respect stop flags on each sample so long-running runs can terminate promptly.
            if self.stop_requested or self.stop_flag:
                self.progress(f"⛔ Run stopped at sample {i}/{total}")
                break

            # -------------------------------------------------------------
            # Extract code and label
            # -------------------------------------------------------------
            # Normalize sample structure into (code, gold_label) pairs.
            if isinstance(sample, dict):
                # Dict-style sample: expects keys "code" and "label".
                code = sample.get("code", "")
                gold = sample.get("label", "").strip().lower()
            elif isinstance(sample, (list, tuple)) and len(sample) >= 2:
                # Sequence-style sample: index 0 is code, index 1 is label.
                code, gold = sample[0], str(sample[1]).strip().lower()
            else:
                # Fallback for unexpected sample formats.
                code, gold = str(sample), "unknown"

            # -------------------------------------------------------------
            # Prompt application and model inference
            # -------------------------------------------------------------
            try:
                # Each prompt strategy exposes an .apply() method that:
                #   - Either returns a prompt string to send to the model, or
                #   - Directly calls the model and returns a prediction object.
                result = prompt_obj.apply(model, code, gen_cfg)

                # For SAFE/VULNERABLE experiments, append a final instruction that
                # constrains the model to output a single word as the visible label.
                #
                # IMPORTANT:
                #   If a strategy returns_label=True (e.g., SelfConsistency),
                #   its output is already a FINAL verdict ("safe"/"vulnerable"/"unknown"),
                #   not a prompt. In that case we must NOT send it back to the model.
                if isinstance(result, str) and force_label_stop and not returns_label:
                    result = result.rstrip() + (
                        "\n\nTASK: Classify the code's security.\n"
                        "On the FIRST LINE ONLY, output exactly one of these words: SAFE or VULNERABLE.\n"
                        "Do not add any other words, punctuation, or symbols on that first line.\n"
                        "If you want to explain your reasoning, you may write it starting from the SECOND line.\n"
                    )

                    # If debug mode is enabled, log what is being sent into the model.
                    if self.debug_raw_outputs and i == 1:
                        self.progress(
                            "[DEBUG] Prompt sent to model.generate(...) "
                            f"(model={model_name}, sample={i}/{total}, "
                            f"type={type(result)}): {repr(result[:300])}"
                        )

                    # Generate the model prediction using the fully constructed prompt.
                    pred = model.generate(result)

                    # If debug is enabled, also log the raw model output for early samples.
                    if self.debug_raw_outputs and i <= 3:
                        self.progress(
                            "[DEBUG] Raw output from model.generate(...) "
                            f"(model={model_name}, sample={i}/{total}, type={type(pred)}): {repr(pred)[:200]}"
                        )
                        self.progress(
                            f"[DEBUG] Raw output (model={model_name}, sample={i}/{total}):\n"
                            f"{str(pred)}\n"
                            "-------------------------------------------------------------"
                        )

                else:
                    # Either:
                    #   - The strategy already performed generation and returned raw output, OR
                    #   - The strategy returned a FINAL label (returns_label=True).
                    pred = result

                    if self.debug_raw_outputs and i <= 3:
                        self.progress(
                            "[DEBUG] Raw output from prompt strategy "
                            f"(model={model_name}, sample={i}/{total}, type={type(pred)}): {repr(pred)[:200]}"
                        )
                        self.progress(
                            f"[DEBUG] Raw output (strategy) (model={model_name}, sample={i}/{total}):\n"
                            f"{str(pred)}\n"
                            "-------------------------------------------------------------"
                        )

            except Exception as e:
                # If prompting or generation fails for this sample, log and continue.
                self.progress(f"❌ Prompt or generation failed at sample {i}: {e}")
                continue

            if not pred:
                # Model returned an empty or falsy response.
                # Log it, but still feed it into the centralized parser,
                # which will convert it into an "unknown" verdict.
                self.progress(f"⚠️ Empty response for sample {i}, will treat as UNKNOWN verdict")
                # Do not `continue` here, let parse_verdict handle it.

            # -------------------------------------------------------------
            # LABEL PARSING (delegated to centralized parser)
            # -------------------------------------------------------------
            pred_label = parse_verdict(pred, model_name=model_name)

            # -------------------------------------------------------------
            # Metrics update
            # -------------------------------------------------------------
            m.add(gold, pred_label)
            preds.append(
                {
                    "id": i,          # dataset sample index
                    "gold": gold,    # ground truth label from the dataset
                    "pred": pred_label,  # normalized model verdict
                }
            )

            # Periodically emit progress updates so the user can track long runs.
            if i % 5 == 0 or i == total:
                self.progress(
                    f"Processing sample {i}/{total} — {dataset_name} | {model_name} | {prompt_name}"
                )

        # -------------------------------------------------------------
        # Compute and record metrics
        # -------------------------------------------------------------
        # Finalize aggregate metrics (Accuracy, Precision, Recall, F1, etc.).
        m.compute()
        metrics = m.to_dict()
        # Log a concise performance summary for this (dataset, model, prompt) triple.
        self.progress(
            f"✅ Finished {model_name} | {prompt_name} on {dataset_name}: "
            f"Acc={metrics['Accuracy']:.3f}, P={metrics['Precision']:.3f}, "
            f"R={metrics['Recall']:.3f}, F1={metrics['F1']:.3f}"
        )

        # Construct a record capturing configuration, metrics, and detailed predictions.
        record = {
            "dataset": dataset_name,
            "model": model_name,
            "prompt": prompt_name,
            **metrics,
            "predictions": preds,
            "params": gen_cfg,             # Generation configuration used for this run (for reproducibility)
            "label_protocol": label_protocol,  # Currently "strict" first-line with structured and lexical fallbacks
            "valid_samples": sum(1 for p in preds if p["pred"] in ("safe", "vulnerable")),  # How many samples produced a valid SAFE/VULNERABLE label
            "total_samples": total,            # Total dataset size attempted

            # A sorted list of the *distinct* predicted labels the model actually produced
            # during this run. Useful for debugging model behavior:
            #   - If it only contains ["safe"] → the model collapsed to a single-class output
            #   - If it is [] → the model produced no valid strict labels
            #   - Helps identify whether the model followed the strict SAFE/VULNERABLE protocol
            "unique_pred_labels": sorted({p["pred"] for p in preds}) if preds else [],
        }
        return record


    # -----------------------------------------------------------------
    def _write_csv(self, records):
        """Write results to CSV files.

        Produces:
            - A master metrics CSV aggregating metrics per (dataset, model, prompt)
            - Per-(dataset, model) CSVs containing per-sample predictions (id, gold, pred)

        These CSVs enable offline analysis in Excel, pandas, or other tooling.
        """
        try:
            output_cfg = self.cfg.get("output", {})
            # Determine the directory for CSV outputs based on the configured master path.
            csv_dir = os.path.dirname(output_cfg.get("results_csv", "results/csv/metrics.csv"))
            os.makedirs(csv_dir, exist_ok=True)

            csv_path = output_cfg.get("results_csv", "results/csv/metrics.csv")
            # Columns to include in the master metrics summary file.
            fieldnames = ["dataset", "model", "prompt", "Accuracy", "Precision", "Recall", "F1"]

            # Write master metrics CSV (one row per record).
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in records:
                    writer.writerow({k: r.get(k, "") for k in fieldnames})

            # Write per-(dataset, model) CSVs containing all sample-level predictions.
            for r in records:
                subpath = os.path.join(csv_dir, f"{r['dataset']}_{r['model'].replace(':','_')}.csv")
                with open(subpath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["id", "gold", "pred"])
                    writer.writeheader()
                    for p in r["predictions"]:
                        writer.writerow(p)

            self.progress(f"📊 Combined all results into {csv_path}")

        except Exception as e:
            # Log any CSV-writing issues with a full traceback to simplify debugging.
            self.progress(f"❌ CSV write failed: {e}")
            traceback.print_exc()

    # -----------------------------------------------------------------
    def _write_report(self, records):
        """Generate interactive HTML report.

        The HtmlReport helper:
            - Aggregates metrics across all runs
            - Builds metric tables and charts
            - Exposes filters and interactive controls

        The HTML report serves as the primary exploratory interface for experiment results.
        """
        try:
            output_cfg = self.cfg.get("output", {})
            html_path = output_cfg.get("report_html", "results/report.html")
            # Metric keys to expose in the HTML report.
            metric_keys = ["TP", "TN", "FP", "FN", "Accuracy", "Precision", "Recall", "F1"]

            # Construct and write the report from the full record set.
            report = HtmlReport(records)
            report.write(
                html_path,
                records,
                metric_keys,
                version="v2.0",
                author="Anon"
            )
            self.progress(f"🌐 HTML report written to {html_path}")

        except Exception as e:
            # Report-generation failures should not crash the pipeline; log and continue.
            self.progress(f"[WARN] Failed to write HTML report: {e}")
            traceback.print_exc()
