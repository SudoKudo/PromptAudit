"""Run PromptAudit experiments across datasets, models, prompts, and ablations."""

import csv
import json
import os
import time
import traceback
from datetime import datetime

from code_datasets.dataset_loader import load_dataset
from evaluation.label_parser import normalize_parser_mode, parse_verdict_details
from evaluation.metrics import Metrics as MetricTracker
from evaluation.output_protocol import build_output_instruction, normalize_output_protocol
from evaluation.report import HtmlReport
from models.model_loader import load_model
from prompts.prompt_loader import load_prompt_strategy as load_prompt
from utils.power import SleepInhibitor


def _model_name(model_item):
    """Return a human-readable model name regardless of selection format."""
    if isinstance(model_item, dict):
        return model_item.get("name", "unnamed")
    return str(model_item)


def _model_backend(model_item):
    """Return the configured backend for a model selection."""
    if isinstance(model_item, dict):
        return str(model_item.get("backend", "ollama")).strip().lower()
    return "ollama"


def _slugify_component(value):
    """Create a filesystem-safe filename component."""
    cleaned = str(value)
    for ch in '<>:"/\\|?* ':
        cleaned = cleaned.replace(ch, "_")
    return cleaned.strip("._") or "item"


def _combo_key(dataset_name, model_item, prompt_name, output_protocol, parser_mode):
    """Stable identifier for one evaluated dataset/model/prompt/ablation combination."""
    return (
        str(dataset_name),
        _model_name(model_item),
        _model_backend(model_item),
        str(prompt_name),
        normalize_output_protocol(output_protocol),
        normalize_parser_mode(parser_mode),
    )


def _language_metadata(predictions):
    """Summarize the languages represented by a record's per-sample predictions."""
    counts = {}
    for pred in predictions or []:
        language = str(pred.get("language", "unknown")).strip() or "unknown"
        counts[language] = counts.get(language, 0) + 1

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
    languages_present = [name for name, _count in ordered]
    return {
        "language": ", ".join(languages_present) if languages_present else "unknown",
        "languages_present": languages_present,
        "language_counts": counts,
    }


class ExperimentRunner:
    """Coordinates execution of experiments across datasets, models, prompts, and ablations."""

    def __init__(self, cfg, progress=None):
        self.cfg = cfg
        perf_cfg = self.cfg.get("performance", {})
        self.gen_cfg = self.cfg.get("generation", {}).copy()
        self.gen_cfg.update(self.cfg.get("api", {}))
        if "sc_vote_delay_seconds" in perf_cfg:
            self.gen_cfg["sc_vote_delay_seconds"] = perf_cfg.get("sc_vote_delay_seconds", 0.0)
        if "ollama_keep_alive" in perf_cfg:
            self.gen_cfg["ollama_keep_alive"] = perf_cfg.get("ollama_keep_alive")
        self.models_cfg = self.cfg.get("models", [])
        self.prompts_cfg = self.cfg.get("prompts", [])
        self.stop_flag = False
        self.stop_requested = False
        self.pause_requested = False
        self.paused = False
        self.selected_datasets = []
        self.selected_models = []
        self.selected_prompts = []
        self.selected_output_protocols = []
        self.selected_parser_modes = []
        self.progress = progress or (lambda msg: print(msg))
        self.records = []
        self.start_time = None
        self.debug_raw_outputs = bool(self.cfg.get("debug_raw_outputs", True))
        self.current_run_id = None
        self.output_dir = None
        self.metrics_csv_path = None
        self.report_html_path = None
        self.predictions_dir = None
        self.records_jsonl_path = None
        self.checkpoint_path = None
        self.current_combo_state = None
        self.final_status = "idle"
        self.cache_models = bool(perf_cfg.get("cache_models", True))
        self.cache_prompts = bool(perf_cfg.get("cache_prompts", True))
        self.checkpoint_every_n_samples = max(0, int(perf_cfg.get("checkpoint_every_n_samples", 10)))
        self.checkpoint_every_seconds = max(0.0, float(perf_cfg.get("checkpoint_every_seconds", 15.0)))
        self.progress_every_n_samples = max(1, int(perf_cfg.get("progress_every_n_samples", 10)))
        self.prevent_system_sleep = bool(perf_cfg.get("prevent_system_sleep", True))
        self.keep_display_awake = bool(perf_cfg.get("keep_display_awake", False))
        self.model_cache = {}
        self.prompt_cache = {}
        self._combo_last_checkpoint_index = 0
        self._combo_last_checkpoint_at = 0.0
        self.sleep_inhibitor = SleepInhibitor(
            enabled=self.prevent_system_sleep,
            keep_display_awake=self.keep_display_awake,
        )
        self._power_support_reported = False

    @staticmethod
    def find_latest_resumable_checkpoint(cfg):
        """Return the newest resumable checkpoint path, or None if none exist."""
        run_root = cfg.get("output", {}).get("run_root", "results/runs")
        if not os.path.isdir(run_root):
            return None

        candidates = []
        for entry in os.scandir(run_root):
            if not entry.is_dir():
                continue
            checkpoint_path = os.path.join(entry.path, "checkpoint.json")
            if not os.path.exists(checkpoint_path):
                continue
            try:
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if state.get("status") in {"running", "paused", "stopped"}:
                    candidates.append((state.get("updated_at", ""), checkpoint_path))
            except Exception:
                continue

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def request_pause(self):
        """Ask the runner to pause at the next safe boundary."""
        self.pause_requested = True

    def request_resume(self):
        """Resume a paused run."""
        self.pause_requested = False
        self.paused = False

    def request_stop(self):
        """Stop the run at the next safe boundary while preserving checkpoint state."""
        self.stop_flag = True
        self.stop_requested = True
        self.pause_requested = False
        self.paused = False

    def _default_output_protocols(self):
        ablations = self.cfg.get("ablations", {})
        raw = ablations.get("default_output_protocols", ["verdict_first"])
        return [normalize_output_protocol(item) for item in raw]

    def _default_parser_modes(self):
        ablations = self.cfg.get("ablations", {})
        raw = ablations.get("default_parser_modes", ["full"])
        return [normalize_parser_mode(item) for item in raw]

    def _load_records_jsonl(self):
        """Load already-completed records from the per-run JSONL file."""
        if not self.records_jsonl_path or not os.path.exists(self.records_jsonl_path):
            return []
        loaded = []
        with open(self.records_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    loaded.append(json.loads(line))
                except Exception:
                    continue
        return loaded

    def _get_model(self, model_item, gen_cfg):
        """Load or reuse a model backend for this run."""
        if not self.cache_models:
            return load_model(model_item, gen_cfg)

        cache_key = json.dumps(
            {
                "model_item": model_item,
                "gen_cfg": gen_cfg,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        model = self.model_cache.get(cache_key)
        if model is None:
            model = load_model(model_item, gen_cfg)
            self.model_cache[cache_key] = model
        return model

    def _get_prompt(self, prompt_name):
        """Load or reuse a prompt strategy instance for this run."""
        if not self.cache_prompts:
            return load_prompt(prompt_name)

        key = str(prompt_name).strip().lower()
        prompt_obj = self.prompt_cache.get(key)
        if prompt_obj is None:
            prompt_obj = load_prompt(prompt_name)
            self.prompt_cache[key] = prompt_obj
        return prompt_obj

    def _prediction_csv_path(self, record):
        """Return the per-combination prediction CSV path for a record."""
        return os.path.join(
            self.predictions_dir,
            (
                f"{_slugify_component(record['dataset'])}_"
                f"{_slugify_component(record['model'])}_"
                f"{_slugify_component(record['prompt'])}_"
                f"{_slugify_component(record['output_protocol'])}_"
                f"{_slugify_component(record['parser_mode'])}.csv"
            ),
        )

    def _write_single_prediction_csv(self, record):
        """Persist one record's per-sample predictions immediately after completion."""
        os.makedirs(self.predictions_dir, exist_ok=True)
        subpath = self._prediction_csv_path(record)
        with open(subpath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["id", "language", "gold", "pred", "parse_tier"],
            )
            writer.writeheader()
            for p in record.get("predictions", []):
                writer.writerow({k: p.get(k, "") for k in writer.fieldnames})

    def _append_record(self, record):
        """Append a completed record to memory and to the per-run JSONL store."""
        self.records.append(record)
        os.makedirs(os.path.dirname(self.records_jsonl_path), exist_ok=True)
        with open(self.records_jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._write_single_prediction_csv(record)

    def _build_partial_record(self):
        """Build a synthetic record for the currently in-progress combination."""
        state = self.current_combo_state or {}
        preds = list(state.get("preds", []))
        if not preds:
            return None

        dataset_name = state.get("dataset_name") or state.get("dataset_item") or "unknown"
        model_item = state.get("model_item")
        prompt_name = state.get("prompt_name", "unknown")
        output_protocol = normalize_output_protocol(state.get("output_protocol", "verdict_first"))
        parser_mode = normalize_parser_mode(state.get("parser_mode", "full"))
        total_samples = int(state.get("total_samples", len(preds)))
        completed_samples = int(state.get("next_sample_index", len(preds)))
        metrics = MetricTracker.from_state(state.get("metrics_state")).to_dict()
        parse_tier_counts = dict(state.get("parse_tier_counts", {}))
        language_meta = _language_metadata(preds)

        return {
            "run_id": self.current_run_id,
            "dataset": dataset_name,
            "model": _model_name(model_item),
            "model_backend": _model_backend(model_item),
            "language": language_meta["language"],
            "languages_present": language_meta["languages_present"],
            "language_counts": language_meta["language_counts"],
            "prompt": prompt_name,
            "output_protocol": output_protocol,
            "parser_mode": parser_mode,
            **metrics,
            "predictions": preds,
            "params": self.gen_cfg.copy(),
            "label_protocol": output_protocol,
            "parse_tier_counts": parse_tier_counts,
            "valid_samples": sum(1 for p in preds if p.get("pred") in ("safe", "vulnerable")),
            "completed_samples": completed_samples,
            "total_samples": total_samples,
            "unique_pred_labels": sorted({p.get("pred") for p in preds}) if preds else [],
            "is_partial": True,
        }

    def _records_for_artifacts(self, include_partial=True):
        """Return completed records plus the current in-progress combo when requested."""
        records = list(self.records)
        if not include_partial:
            return records

        partial = self._build_partial_record()
        if not partial:
            return records

        partial_key = _combo_key(
            partial.get("dataset"),
            {"name": partial.get("model"), "backend": partial.get("model_backend", "ollama")},
            partial.get("prompt"),
            partial.get("output_protocol", "verdict_first"),
            partial.get("parser_mode", "full"),
        )
        filtered = []
        for record in records:
            record_key = _combo_key(
                record.get("dataset"),
                {"name": record.get("model"), "backend": record.get("model_backend", "ollama")},
                record.get("prompt"),
                record.get("output_protocol", "verdict_first"),
                record.get("parser_mode", "full"),
            )
            if record_key != partial_key:
                filtered.append(record)
        filtered.append(partial)
        return filtered

    def _write_partial_artifacts(self, reason):
        """Write metrics/report snapshots from all progress accumulated so far."""
        records = self._records_for_artifacts(include_partial=True)
        if not records:
            return
        self._write_csv(records)
        self._write_report(records)
        self.progress(
            f"[PARTIAL] Wrote partial results after {reason} to "
            f"{self.metrics_csv_path} and {self.report_html_path}"
        )

    def _build_run_paths(self, run_id):
        """Compute output artifact paths for a run id."""
        output_cfg = self.cfg.get("output", {})
        run_root = output_cfg.get("run_root", "results/runs")
        self.output_dir = os.path.join(run_root, run_id)
        os.makedirs(self.output_dir, exist_ok=True)
        metrics_name = os.path.basename(output_cfg.get("results_csv", "metrics.csv"))
        report_name = os.path.basename(output_cfg.get("report_html", "report.html"))
        self.metrics_csv_path = os.path.join(self.output_dir, metrics_name)
        self.report_html_path = os.path.join(self.output_dir, report_name)
        self.predictions_dir = os.path.join(self.output_dir, "predictions")
        self.records_jsonl_path = os.path.join(self.output_dir, "records.jsonl")
        self.checkpoint_path = os.path.join(self.output_dir, "checkpoint.json")

    def _start_new_run_state(
        self,
        selected_datasets,
        selected_models,
        selected_prompts,
        selected_output_protocols,
        selected_parser_modes,
    ):
        """Initialize a fresh run directory and checkpoint scaffold."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_name = _slugify_component(self.gen_cfg.get("experiment_name", "run"))
        self.current_run_id = f"{timestamp}_{exp_name}"
        self._build_run_paths(self.current_run_id)
        self.records = []
        self.current_combo_state = None
        self.progress(f"Artifacts for this run will be written to {self.output_dir}")
        self._save_checkpoint(
            status="running",
            selected_datasets=selected_datasets,
            selected_models=selected_models,
            selected_prompts=selected_prompts,
            selected_output_protocols=selected_output_protocols,
            selected_parser_modes=selected_parser_modes,
        )

    def _load_checkpoint_state(self, checkpoint_path):
        """Load a previously saved checkpoint and restore run-path metadata."""
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.current_run_id = state["run_id"]
        self.output_dir = state["output_dir"]
        self.metrics_csv_path = state["metrics_csv_path"]
        self.report_html_path = state["report_html_path"]
        self.predictions_dir = state["predictions_dir"]
        self.records_jsonl_path = state["records_jsonl_path"]
        self.checkpoint_path = checkpoint_path
        self.current_combo_state = state.get("current_combo")
        self.final_status = state.get("status", "running")
        self.records = self._load_records_jsonl()
        return state

    def _save_checkpoint(
        self,
        *,
        status="running",
        selected_datasets=None,
        selected_models=None,
        selected_prompts=None,
        selected_output_protocols=None,
        selected_parser_modes=None,
    ):
        """Persist resumable run state to disk."""
        if not self.checkpoint_path:
            return

        state = {
            "version": 1,
            "status": status,
            "run_id": self.current_run_id,
            "output_dir": self.output_dir,
            "metrics_csv_path": self.metrics_csv_path,
            "report_html_path": self.report_html_path,
            "predictions_dir": self.predictions_dir,
            "records_jsonl_path": self.records_jsonl_path,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "selected_datasets": selected_datasets or self.selected_datasets,
            "selected_models": selected_models or self.selected_models,
            "selected_prompts": selected_prompts or self.selected_prompts,
            "selected_output_protocols": selected_output_protocols or self.selected_output_protocols,
            "selected_parser_modes": selected_parser_modes or self.selected_parser_modes,
            "gen_cfg": self.gen_cfg,
            "current_combo": self.current_combo_state,
        }
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _mark_checkpoint_saved(self, next_sample_index=0):
        """Track the last point at which combo progress was checkpointed."""
        self._combo_last_checkpoint_index = int(next_sample_index or 0)
        self._combo_last_checkpoint_at = time.time()

    def _should_save_progress_checkpoint(self, next_sample_index, total_samples):
        """Return True when in-progress combo state should be flushed to disk."""
        next_sample_index = int(next_sample_index or 0)
        total_samples = int(total_samples or 0)
        if total_samples and next_sample_index >= total_samples:
            return True
        # Sample-count and time-based gates work together so we still persist
        # long-running samples even when the dataset itself is small.
        if self.checkpoint_every_n_samples and (
            next_sample_index - self._combo_last_checkpoint_index
        ) >= self.checkpoint_every_n_samples:
            return True
        if self.checkpoint_every_seconds and (
            time.time() - self._combo_last_checkpoint_at
        ) >= self.checkpoint_every_seconds:
            return True
        return False

    def _wait_if_paused(self):
        """Block progress while paused, preserving checkpoint state for resumption."""
        while self.pause_requested and not self.stop_requested and not self.stop_flag:
            if not self.paused:
                self.paused = True
                # Release the keep-awake request while paused so the machine can
                # sleep normally if the user leaves the run suspended.
                self._release_sleep_inhibition("pause")
                self._save_checkpoint(status="paused")
                self._mark_checkpoint_saved(self.current_combo_state.get("next_sample_index", 0) if self.current_combo_state else 0)
                self._write_partial_artifacts(reason="pause")
                self.progress("Run paused. Checkpoint saved; waiting to resume...")
            time.sleep(0.25)

        if self.paused and not self.pause_requested:
            self.paused = False
            self._acquire_sleep_inhibition("resume")
            self.progress("Resuming run from checkpointed state...")

    def _acquire_sleep_inhibition(self, reason="run"):
        """Ask the OS to keep the machine awake while the run is active."""
        if not self.prevent_system_sleep:
            return
        if not self.sleep_inhibitor.supported:
            if not self._power_support_reported:
                self.progress("[POWER] Sleep prevention is not supported on this platform; continuing without it.")
                self._power_support_reported = True
            return
        if self.sleep_inhibitor.acquire():
            target = "system and display" if self.keep_display_awake else "system"
            if reason == "resume":
                self.progress(f"[POWER] Resumed {target} sleep prevention.")
            else:
                self.progress(f"[POWER] Preventing {target} sleep while the run is active.")

    def _release_sleep_inhibition(self, reason="stop"):
        """Release any active keep-awake request."""
        if self.sleep_inhibitor.release():
            if reason == "pause":
                self.progress("[POWER] Sleep prevention released while the run is paused.")
            elif reason == "completed":
                self.progress("[POWER] Sleep prevention released after the run completed.")
            elif reason == "error":
                self.progress("[POWER] Sleep prevention released after the run ended with an error.")
            else:
                self.progress("[POWER] Sleep prevention released.")

    def run_all(
        self,
        selected_datasets,
        selected_models,
        selected_prompts,
        selected_output_protocols=None,
        selected_parser_modes=None,
        resume_checkpoint=None,
    ):
        """Run all selected dataset/model/prompt combinations plus ablation settings."""
        self.start_time = time.time()
        self.final_status = "running"
        self._acquire_sleep_inhibition("run")
        try:
            if resume_checkpoint:
                state = self._load_checkpoint_state(resume_checkpoint)
                selected_datasets = state.get("selected_datasets", selected_datasets)
                selected_models = state.get("selected_models", selected_models)
                selected_prompts = state.get("selected_prompts", selected_prompts)
                selected_output_protocols = state.get("selected_output_protocols", selected_output_protocols)
                selected_parser_modes = state.get("selected_parser_modes", selected_parser_modes)
                self.gen_cfg.update(state.get("gen_cfg", {}))
                resume_state = self.current_combo_state
                self.progress(f"Resuming run from {resume_checkpoint}")
            else:
                selected_output_protocols = selected_output_protocols or self._default_output_protocols()
                selected_parser_modes = selected_parser_modes or self._default_parser_modes()
                self._start_new_run_state(
                    selected_datasets,
                    selected_models,
                    selected_prompts,
                    selected_output_protocols,
                    selected_parser_modes,
                )
                resume_state = None

            self.selected_datasets = selected_datasets
            self.selected_models = selected_models
            self.selected_prompts = selected_prompts
            self.selected_output_protocols = [normalize_output_protocol(item) for item in (selected_output_protocols or [])]
            self.selected_parser_modes = [normalize_parser_mode(item) for item in (selected_parser_modes or [])]
            self.records = self._load_records_jsonl()

            completed_keys = {
                _combo_key(
                    record.get("dataset"),
                    {"name": record.get("model"), "backend": record.get("model_backend", "ollama")},
                    record.get("prompt"),
                    record.get("output_protocol", "verdict_first"),
                    record.get("parser_mode", "full"),
                )
                for record in self.records
            }

            for dataset_item in selected_datasets:
                if self.stop_requested or self.stop_flag:
                    self.progress(f"Stopped before dataset {dataset_item}")
                    break

                dataset_name = dataset_item if isinstance(dataset_item, str) else dataset_item.get("name", str(dataset_item))
                self.progress(f"Loading dataset: {dataset_name}")
                try:
                    dataset = load_dataset(dataset_item)
                    self.progress(f"Loaded dataset: {dataset_name} (samples: {len(dataset)})")
                except Exception as e:
                    self.progress(f"Failed to load {dataset_name}: {e}")
                    continue

                if not dataset:
                    self.progress(f"Dataset {dataset_name} returned no samples.")
                    continue

                for model_item in selected_models:
                    if self.stop_requested or self.stop_flag:
                        break
                    model_name = _model_name(model_item)

                    for prompt_name in selected_prompts:
                        if self.stop_requested or self.stop_flag:
                            break

                        for output_protocol in self.selected_output_protocols:
                            if self.stop_requested or self.stop_flag:
                                break

                            for parser_mode in self.selected_parser_modes:
                                if self.stop_requested or self.stop_flag:
                                    break

                                combo_key = _combo_key(
                                    dataset_name,
                                    model_item,
                                    prompt_name,
                                    output_protocol,
                                    parser_mode,
                                )
                                if combo_key in completed_keys:
                                    continue

                                active_resume = (
                                    resume_state
                                    if resume_state and tuple(resume_state.get("combo_key", [])) == combo_key
                                    else None
                                )

                                self.progress(
                                    f"Running {model_name} with prompt {prompt_name} "
                                    f"[{output_protocol} | {parser_mode}] on {dataset_name}"
                                )
                                try:
                                    result_record = self._run_single(
                                        dataset_name,
                                        dataset,
                                        model_item,
                                        prompt_name,
                                        output_protocol,
                                        parser_mode,
                                        resume_state=active_resume,
                                    )
                                    resume_state = None
                                    if result_record:
                                        self._append_record(result_record)
                                        completed_keys.add(combo_key)
                                except Exception as e:
                                    self.progress(f"Error during run: {e}")
                                    traceback.print_exc()
                                    continue

            records_to_write = self._records_for_artifacts(include_partial=bool(self.current_combo_state))
            if not records_to_write:
                self.progress("No valid records produced; skipping write.")
                self.final_status = "stopped" if (self.stop_requested or self.stop_flag) else "completed"
                self._save_checkpoint(status=self.final_status)
                return self.final_status

            self._write_csv(records_to_write)
            self._write_report(records_to_write)

            elapsed = (time.time() - self.start_time) / 60
            if self.stop_requested or self.stop_flag:
                self.final_status = "stopped"
                self.progress(f"Run stopped after {elapsed:.1f} min")
            else:
                self.final_status = "completed"
                self.progress(f"All experiments finished in {elapsed:.1f} min")
                self.progress("Run completed successfully")

            self.current_combo_state = None
            self._save_checkpoint(status=self.final_status)
            return self.final_status
        finally:
            reason = "completed"
            if self.final_status == "stopped":
                reason = "stop"
            elif self.final_status == "running":
                reason = "error" if self.current_combo_state or self.stop_flag else "completed"
            self._release_sleep_inhibition(reason)

    def _run_single(
        self,
        dataset_name,
        dataset,
        model_item,
        prompt_name,
        output_protocol,
        parser_mode,
        *,
        resume_state=None,
    ):
        """Run a single model/prompt/protocol/parser combination on one dataset."""
        model_name = _model_name(model_item)
        model_backend = _model_backend(model_item)
        output_protocol = normalize_output_protocol(output_protocol)
        parser_mode = normalize_parser_mode(parser_mode)

        gen_cfg = self.gen_cfg.copy()
        self.progress(f"[MODE] Using '{output_protocol}' output protocol and '{parser_mode}' parser for {model_name}")
        model = self._get_model(model_item, gen_cfg)

        if self.debug_raw_outputs:
            self.progress(f"[PARAMS] {json.dumps(gen_cfg, sort_keys=True)}")
        prompt_obj = self._get_prompt(prompt_name)
        returns_label = getattr(prompt_obj, "returns_label", False)

        m = MetricTracker.from_state(resume_state.get("metrics_state")) if resume_state else MetricTracker()
        preds = list(resume_state.get("preds", [])) if resume_state else []
        parse_tier_counts = dict(resume_state.get("parse_tier_counts", {})) if resume_state else {}
        total = len(dataset)
        start_index = int(resume_state.get("next_sample_index", 0)) if resume_state else 0
        start_index = max(0, min(start_index, total))

        combo_key = list(_combo_key(dataset_name, model_item, prompt_name, output_protocol, parser_mode))
        self.current_combo_state = {
            "combo_key": combo_key,
            "dataset_item": dataset_name,
            "dataset_name": dataset_name,
            "model_item": model_item,
            "prompt_name": prompt_name,
            "output_protocol": output_protocol,
            "parser_mode": parser_mode,
            "next_sample_index": start_index,
            "preds": preds,
            "metrics_state": m.to_dict(),
            "parse_tier_counts": parse_tier_counts,
            "total_samples": total,
        }
        self._save_checkpoint(status="running")
        self._mark_checkpoint_saved(start_index)

        if start_index:
            self.progress(
                f"Resuming {model_name} | {prompt_name} | {output_protocol} | "
                f"{parser_mode} at sample {start_index + 1}/{total}"
            )

        for idx in range(start_index, total):
            self._wait_if_paused()
            if self.stop_requested or self.stop_flag:
                self.progress(f"Run stopped at sample {idx + 1}/{total}")
                self._save_checkpoint(status="stopped")
                self._mark_checkpoint_saved(idx)
                self._write_partial_artifacts(reason="stop")
                return None

            sample = dataset[idx]
            if isinstance(sample, dict):
                code = sample.get("code", "")
                gold = sample.get("label", "").strip().lower()
                language = sample.get("language", "unknown")
            elif isinstance(sample, (list, tuple)) and len(sample) >= 2:
                code, gold = sample[0], str(sample[1]).strip().lower()
                language = "unknown"
            else:
                code, gold = str(sample), "unknown"
                language = "unknown"

            try:
                if hasattr(prompt_obj, "apply_with_context"):
                    result = prompt_obj.apply_with_context(
                        model,
                        code,
                        gen_cfg,
                        output_protocol=output_protocol,
                        parser_mode=parser_mode,
                    )
                else:
                    result = prompt_obj.apply(model, code, gen_cfg)

                if isinstance(result, str) and not returns_label:
                    result = result.rstrip() + build_output_instruction(output_protocol)
                    if self.debug_raw_outputs and idx == start_index:
                        self.progress(
                            "[DEBUG] Prompt sent to model.generate(...) "
                            f"(model={model_name}, sample={idx + 1}/{total}, "
                            f"type={type(result)}): {repr(result[:300])}"
                        )
                    pred = model.generate(result)
                    if self.debug_raw_outputs and idx < min(total, start_index + 3):
                        self.progress(
                            "[DEBUG] Raw output from model.generate(...) "
                            f"(model={model_name}, sample={idx + 1}/{total}, type={type(pred)}): {repr(pred)[:200]}"
                        )
                    parse_details = parse_verdict_details(
                        pred,
                        model_name=model_name,
                        mode=parser_mode,
                        output_protocol=output_protocol,
                    )
                    pred_label = parse_details["label"]
                    parse_tier = parse_details.get("tier") or "unknown"
                elif returns_label and isinstance(result, dict):
                    pred = result.get("label", "unknown")
                    pred_label = str(result.get("label", "unknown")).strip().lower()
                    parse_tier = result.get("parse_tier") or result.get("tier") or "unknown"
                    if self.debug_raw_outputs and idx < min(total, start_index + 3):
                        self.progress(
                            "[DEBUG] Structured output from prompt strategy "
                            f"(model={model_name}, sample={idx + 1}/{total}): {repr(result)[:300]}"
                        )
                else:
                    pred = result
                    if self.debug_raw_outputs and idx < min(total, start_index + 3):
                        self.progress(
                            "[DEBUG] Raw output from prompt strategy "
                            f"(model={model_name}, sample={idx + 1}/{total}, type={type(pred)}): {repr(pred)[:200]}"
                        )
                    parse_details = parse_verdict_details(
                        pred,
                        model_name=model_name,
                        mode=parser_mode,
                        output_protocol=output_protocol,
                    )
                    pred_label = parse_details["label"]
                    parse_tier = parse_details.get("tier") or "unknown"
            except Exception as e:
                self.progress(f"Prompt or generation failed at sample {idx + 1}: {e} (counting as UNKNOWN)")
                pred = ""
                pred_label = "unknown"
                parse_tier = "unknown"

            if not pred:
                self.progress(f"Empty response for sample {idx + 1}, will treat as UNKNOWN verdict")

            m.add(gold, pred_label)
            parse_tier_counts[parse_tier] = parse_tier_counts.get(parse_tier, 0) + 1
            preds.append(
                {
                    "id": idx + 1,
                    "gold": gold,
                    "pred": pred_label,
                    "language": language,
                    "parse_tier": parse_tier,
                }
            )

            self.current_combo_state = {
                "combo_key": combo_key,
                "dataset_item": dataset_name,
                "dataset_name": dataset_name,
                "model_item": model_item,
                "prompt_name": prompt_name,
                "output_protocol": output_protocol,
                "parser_mode": parser_mode,
                "next_sample_index": idx + 1,
                "preds": preds,
                "metrics_state": m.to_dict(),
                "parse_tier_counts": parse_tier_counts,
                "total_samples": total,
            }
            # Keep the resumable checkpoint lightweight most of the time and
            # only flush it when one of the configured cadence thresholds trips.
            if self._should_save_progress_checkpoint(idx + 1, total):
                self._save_checkpoint(status="running")
                self._mark_checkpoint_saved(idx + 1)

            if (idx + 1) % self.progress_every_n_samples == 0 or idx + 1 == total:
                self.progress(
                    f"Processing sample {idx + 1}/{total} - {dataset_name} | "
                    f"{model_name} | {prompt_name} | {output_protocol} | {parser_mode}"
                )

        m.compute()
        metrics = m.to_dict()
        language_meta = _language_metadata(preds)
        self.progress(
            f"Finished {model_name} | {prompt_name} | {output_protocol} | {parser_mode} on {dataset_name}: "
            f"Acc={metrics['Accuracy']:.3f}, P={metrics['Precision']:.3f}, "
            f"R={metrics['Recall']:.3f}, F1={metrics['F1']:.3f}, "
            f"Cov={metrics['Coverage']:.3f}, EffF1={metrics['EffectiveF1']:.3f}"
        )

        record = {
            "run_id": self.current_run_id,
            "dataset": dataset_name,
            "model": model_name,
            "model_backend": model_backend,
            "language": language_meta["language"],
            "languages_present": language_meta["languages_present"],
            "language_counts": language_meta["language_counts"],
            "prompt": prompt_name,
            "output_protocol": output_protocol,
            "parser_mode": parser_mode,
            **metrics,
            "predictions": preds,
            "params": gen_cfg,
            "label_protocol": output_protocol,
            "parse_tier_counts": parse_tier_counts,
            "valid_samples": sum(1 for p in preds if p["pred"] in ("safe", "vulnerable")),
            "completed_samples": total,
            "total_samples": total,
            "unique_pred_labels": sorted({p["pred"] for p in preds}) if preds else [],
            "is_partial": False,
        }
        self.current_combo_state = None
        self._save_checkpoint(status="running")
        self._mark_checkpoint_saved(total)
        return record

    def _write_csv(self, records):
        """Write run-level metrics and per-sample predictions to this run's artifact directory."""
        try:
            os.makedirs(os.path.dirname(self.metrics_csv_path), exist_ok=True)
            fieldnames = [
                "run_id",
                "dataset",
                "model",
                "model_backend",
                "prompt",
                "output_protocol",
                "parser_mode",
                "language",
                "TP",
                "TN",
                "FP",
                "FN",
                "UnFN",
                "Incorrect",
                "Accuracy",
                "Precision",
                "Recall",
                "F1",
                "Coverage",
                "AbstentionRate",
                "EffectiveF1",
                "Unknown",
                "completed_samples",
                "total_samples",
                "is_partial",
            ]

            with open(self.metrics_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for r in records:
                    writer.writerow({k: r.get(k, "") for k in fieldnames})

            for r in records:
                prediction_path = self._prediction_csv_path(r)
                if r.get("is_partial") or not os.path.exists(prediction_path):
                    self._write_single_prediction_csv(r)

            self.progress(f"Combined all results into {self.metrics_csv_path}")
        except Exception as e:
            self.progress(f"CSV write failed: {e}")
            traceback.print_exc()

    def _write_report(self, records):
        """Generate the interactive HTML report for this run."""
        try:
            metric_keys = [
                "TP",
                "TN",
                "FP",
                "FN",
                "UnFN",
                "Incorrect",
                "Accuracy",
                "Precision",
                "Recall",
                "F1",
                "Coverage",
                "AbstentionRate",
                "EffectiveF1",
            ]
            report = HtmlReport(records)
            report.write(
                self.report_html_path,
                records,
                metric_keys,
                version="v2.0",
                author="PromptAudit",
            )
            self.progress(f"HTML report written to {self.report_html_path}")
        except Exception as e:
            self.progress(f"[WARN] Failed to write HTML report: {e}")
            traceback.print_exc()
