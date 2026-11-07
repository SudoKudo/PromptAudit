"""Run selected experiment types together with a shared response cache."""

import copy
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
from uuid import uuid4

from core import __version__
from core.inference import InferenceStateError, performance_options
from core.runner import ExperimentRunner
from core.revision_study import ROOT, StudyRunner, build_conditions, json_hash, text_hash
from code_datasets.dataset_loader import load_dataset
from code_datasets.validation import validate_samples
from models.base import merge_generation_settings
from models.model_loader import load_model
from prompts.adaptive_cot import AdaptiveCoT
from prompts.prompt_loader import load_prompt_strategy
from prompts.template_variants import CODE_SLOT
from evaluation.output_protocol import build_output_instruction
from utils.privacy import safe_settings, safe_text


PREDICTION_WEIGHT = 0.05
TYPE_NAMES = {"standard": "Standard prompts", "B": "Task wordings", "C": "Components and voting"}


class BatchStopped(Exception):
    """Stop between jobs or while planning a batch."""


def _write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(safe_settings(value), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _fingerprint(samples):
    digest = hashlib.sha256()
    for sample in samples:
        payload = json.dumps(sample, sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _standard_shapes(job, generation):
    """Count distinct prompt/settings shapes, preserving Standard's seed rules."""
    totals = []
    for model in job["models"]:
        overrides = {key: value for key, value in model.items() if key not in {"name", "backend"}}
        settings = merge_generation_settings(generation, overrides)
        shapes = set()
        for name in job["prompts"]:
            strategy = load_prompt_strategy(name)
            draws = int(generation.get("sc_samples", 5)) if name == "self_consistency" else 1
            if draws < 1:
                raise ValueError("Requested draws must be positive")
            if draws > 1 and (settings.get("temperature", 0.2) <= 0 or settings.get("num_beams", 1) != 1):
                raise ValueError("Self-consistency requires temperature above zero and one beam")
            if name == "self_consistency":
                strategy = AdaptiveCoT()
            for protocol in job["protocols"]:
                for parser in job["parsers"]:
                    if hasattr(strategy, "apply_with_context"):
                        body = strategy.apply_with_context(None, CODE_SLOT, generation,
                            output_protocol=protocol, parser_mode=parser)
                    else:
                        body = strategy.apply(None, CODE_SLOT, generation)
                    prompt = body.rstrip() + build_output_instruction(protocol)
                    for draw in range(draws):
                        seed = (int(settings.get("seed", 42)) + draw) % (2 ** 31)
                        shapes.add((prompt, seed))
        totals.append(len(shapes))
    return sum(totals)


class BatchRunner:
    """Keep a batch resumable without changing individual experiment definitions."""

    def __init__(self, cfg, progress=None, overall_progress=None, *, dataset_loader=None, model_loader=None):
        self.cfg = copy.deepcopy(cfg)
        self.progress = lambda message: (progress or print)(safe_text(message))
        self.overall_progress = overall_progress or (lambda payload: None)
        self.dataset_loader = dataset_loader or load_dataset
        self.model_loader = model_loader or load_model
        self.output_dir = None
        self.report_html_path = None
        self.final_status = "idle"
        self.active_runner = None
        self._running = threading.Event()
        self._running.set()
        self._stop = threading.Event()
        self._ledger = None
        self._manifest = None
        self._manifest_path = None
        self._last_emit = 0.0
        self._last_percent = 0.0
        self._job_index = 0
        self._work_totals = {}
        self._pending_work = 0
        self._last_ledger_flush = 0.0

    @staticmethod
    def find_latest_resumable_checkpoint(cfg):
        root = Path(cfg.get("output", {}).get("run_root", "results/runs"))
        candidates = []
        for path in root.glob("batch_*/batch_manifest.json"):
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved.get("schema_version") == 1 and saved.get("status") in {"running", "stopped", "failed", "generated"}:
                    candidates.append(path)
            except (OSError, ValueError):
                continue
        return str(max(candidates, key=lambda path: path.stat().st_mtime)) if candidates else None

    def request_pause(self):
        self._running.clear()
        if self.active_runner:
            self.active_runner.request_pause()

    def request_resume(self):
        self._running.set()
        if self.active_runner:
            self.active_runner.request_resume()

    def request_stop(self):
        self._stop.set()
        self._running.set()
        if self.active_runner:
            self.active_runner.request_stop()

    def _control(self):
        if self._stop.is_set():
            raise BatchStopped()
        if not self._running.is_set():
            self.progress("Run paused. Saved responses will be reused on resume.")
            self._emit("Paused", force=True)
            while not self._running.wait(0.2):
                if self._stop.is_set():
                    raise BatchStopped()
            if self._stop.is_set():
                raise BatchStopped()
            self.progress("Resuming run...")

    @staticmethod
    def _sources():
        files = [*sorted((ROOT / "core").glob("*.py")), *sorted((ROOT / "models").glob("*.py")),
                 *sorted((ROOT / "prompts").glob("*.py")), *sorted((ROOT / "code_datasets").glob("*.py")),
                 ROOT / "evaluation/output_protocol.py", ROOT / "evaluation/label_parser.py",
                 ROOT / "evaluation/voting.py", ROOT / "evaluation/metrics.py", ROOT / "config.yaml"]
        return {str(path.relative_to(ROOT)): text_hash(path.read_text(encoding="utf-8")) for path in files}

    def _plan(self, jobs):
        if not isinstance(jobs, list) or not jobs:
            raise ValueError("Select at least one experiment type")
        if len({job.get("type") for job in jobs}) != len(jobs):
            raise ValueError("Select each experiment type only once")
        planned = []
        cohort_cache = {}
        for index, original in enumerate(jobs):
            self._control()
            job = copy.deepcopy(original)
            kind = job.get("type")
            if kind not in TYPE_NAMES:
                raise ValueError("Unsupported experiment type")
            config = job if kind == "standard" else job.get("config", {})
            models, datasets = config.get("models", []), config.get("datasets", [])
            if not models or not datasets:
                raise ValueError("Each experiment needs a model and dataset")
            limit = job.get("limit")
            if limit is not None and (type(limit) is not int or limit < 1 or not job.get("pilot")):
                raise ValueError("A positive sample limit is available only for pilots")
            generation = self.cfg.get("generation", {}) if kind == "standard" else config.get("generation", {})
            perf = self.cfg.get("performance", {}) if kind == "standard" else config.get("performance", {})
            for model in models:
                if not isinstance(model, dict) or not model.get("name"):
                    raise ValueError("Each model needs a name and backend")
                performance_options(perf, model.get("backend", "ollama"))
                if model.get("backend") == "dummy" and kind != "standard" and not job.get("pilot"):
                    raise ValueError("Dummy models are available only for pilots")
            cohorts = []
            for dataset in datasets:
                self._control()
                name = dataset if isinstance(dataset, str) else dataset.get("name")
                if not name:
                    raise ValueError("Each dataset needs a name")
                cohort_key = (json_hash(dataset), limit)
                if cohort_key in cohort_cache:
                    cohorts.append(dict(cohort_cache[cohort_key]))
                    continue
                self.progress(f"Planning {TYPE_NAMES[kind]}: reading {name}")
                inventory = {}
                if self.dataset_loader is load_dataset:
                    samples = self.dataset_loader(dataset, inventory=inventory)
                else:
                    samples = self.dataset_loader(dataset)
                    inventory = copy.deepcopy(getattr(self.dataset_loader, "dataset_inventory", {}).get(name, {}))
                samples = validate_samples(samples[:limit] if limit else samples, name)
                if not samples:
                    raise ValueError(f"Dataset {name} has no samples")
                inventory.setdefault("loaded_samples", len(samples))
                inventory["selected_samples"] = len(samples)
                inventory.setdefault("source_exclusions", inventory.get("excluded_code_files"))
                cohort = {"name": name, "samples": len(samples), "fingerprint": _fingerprint(samples),
                          "inventory": inventory}
                cohort_cache[cohort_key] = cohort
                cohorts.append(dict(cohort))
                del samples
            count = sum(cohort["samples"] for cohort in cohorts)
            if kind == "standard":
                if not job.get("prompts") or not job.get("protocols") or not job.get("parsers"):
                    raise ValueError("Select a prompt, verdict protocol, and parser")
                generation_units = count * _standard_shapes(job, generation)
                predictions = count * len(models) * len(job["prompts"]) * len(job["protocols"]) * len(job["parsers"])
            else:
                conditions = build_conditions(config)
                draws = {(text_hash(condition["template"]), draw)
                         for condition in conditions for draw in range(condition["draws"])}
                seeds = config.get("seeds", [42])
                if not seeds or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
                    raise ValueError("Run seeds must be unique integers")
                generation_units = count * len(models) * len(seeds) * len(draws)
                predictions = count * len(models) * len(seeds) * len(conditions) * len(config.get("parser_modes", ["strict", "structured", "full"]))
            prediction_units = predictions * PREDICTION_WEIGHT
            # Processing is reserved separately; this percentage is not a time prediction.
            finalize_units = max(1.0, (generation_units + prediction_units) * 0.05)
            planned.append({"type": kind, "job": safe_settings(job), "cohorts": cohorts,
                            "generation_units": generation_units, "prediction_units": prediction_units,
                            "finalize_units": finalize_units,
                            "total_units": generation_units + prediction_units + finalize_units,
                            "status": "pending", "output_root": f"job_{index + 1}_{kind.lower()}"})
        return planned

    def _emit(self, stage, detail="", *, force=False):
        now = time.monotonic()
        if not force and now - self._last_emit < 0.2:
            return
        done = 0.0
        if self._ledger is not None:
            for index, job in enumerate(self._manifest["jobs"]):
                done += min(self._work_totals.get(index, 0.0), job["total_units"])
        total = sum(job["total_units"] for job in self._manifest["jobs"]) if self._manifest else 0
        percent = min(99.0, 100 * done / total) if total else 0.0
        if self.final_status == "completed":
            done, percent = total, 100.0
        self._last_percent = max(self._last_percent, percent)
        self.overall_progress({"percent": self._last_percent, "done": done, "total": total,
                               "stage": stage, "detail": detail})
        self._last_emit = now

    def _mark_work(self, kind, key, units):
        work_id = f"{kind}:{text_hash(key)}"
        inserted = self._ledger.execute("INSERT OR IGNORE INTO work VALUES (?, ?, ?)",
                                        (self._job_index, work_id, units)).rowcount
        if inserted:
            self._work_totals[self._job_index] = self._work_totals.get(self._job_index, 0.0) + units
            self._pending_work += 1
        if self._pending_work >= 128 or time.monotonic() - self._last_ledger_flush >= 1:
            self._flush_progress()
        stage = "Generating responses" if kind == "generation" else "Processing predictions"
        self._emit(stage, TYPE_NAMES[self._manifest["jobs"][self._job_index]["type"]])

    def _flush_progress(self):
        if self._ledger is not None:
            self._ledger.commit()
            self._pending_work = 0
            self._last_ledger_flush = time.monotonic()

    def _save(self):
        self._flush_progress()
        self._manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._manifest["status"] = self.final_status
        _write_json(self._manifest_path, self._manifest)
        self._write_report()

    def _write_report(self):
        rows = []
        root = Path(self.output_dir)
        for entry in self._manifest["jobs"]:
            report = entry.get("report")
            link = "Report pending"
            if report and Path(report).exists():
                relative = Path(report).resolve().relative_to(root.resolve()).as_posix()
                link = f'<a href="{escape(relative, quote=True)}">Open report</a>'
                paper = Path(report).parent / "paper" / "index.html"
                if paper.exists():
                    relative = paper.resolve().relative_to(root.resolve()).as_posix()
                    link += f' | <a href="{escape(relative, quote=True)}">Paper tables</a>'
            rows.append(f'<tr><td>{escape(TYPE_NAMES[entry["type"]])}</td>'
                        f'<td>{escape(entry["status"])}</td><td>{link}</td></tr>')
        document = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                    '<meta name="viewport" content="width=device-width, initial-scale=1">'
                    f'<title>PromptAudit {__version__} batch</title><style>'
                    'body{font:16px system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#172a3a}'
                    'table{width:100%;border-collapse:collapse}th,td{text-align:left;border:1px solid #cbd6df;padding:.8rem}'
                    'th{background:#e9f2fa}</style>'
                    f'<h1>PromptAudit {__version__} batch</h1><p>Status: {escape(self.final_status)}</p>'
                    '<p>Each report keeps its experiment definitions and metrics. Identical model requests can share '
                    'recorded responses within this batch. Different seeds, prompts, or settings remain separate.</p>'
                    '<table><thead><tr><th>Experiment type</th><th>Status</th><th>Results</th></tr></thead><tbody>'
                    + ''.join(rows) + '</tbody></table>'
                    '<p>Completion is an estimate of planned request resolutions and processing, not elapsed time. '
                    'Reused responses count as completed work. Keep this directory together for resume.</p></html>')
        path = Path(self.report_html_path)
        temporary = path.with_suffix(".html.tmp")
        temporary.write_text(document, encoding="utf-8")
        temporary.replace(path)

    def _loader_for(self, entry):
        by_name = {cohort["name"]: cohort for cohort in entry["cohorts"]}
        limit = entry["job"].get("limit")

        def read(dataset):
            try:
                samples = self.dataset_loader(dataset)
            except Exception as exc:
                raise InferenceStateError("A selected dataset could not be loaded") from exc
            samples = list(samples[:limit] if limit else samples)
            name = dataset if isinstance(dataset, str) else dataset["name"]
            samples = validate_samples(samples, name)
            if _fingerprint(samples) != by_name[name]["fingerprint"]:
                raise InferenceStateError("A selected dataset changed after the batch was planned")
            return samples
        read.dataset_inventory = {name: copy.deepcopy(cohort.get("inventory", {}))
                                  for name, cohort in by_name.items()}
        return read

    def _record_failure(self, error):
        """Save failure context without exception text or absolute source paths."""
        failure = {"timestamp": datetime.now(timezone.utc).isoformat(),
                   "exception_type": type(error).__name__, "batch_status": self.final_status}
        frames = error.__traceback__
        while frames is not None:
            filename = frames.tb_frame.f_code.co_filename
            if not filename.startswith("<"):
                try:
                    relative = Path(filename).resolve().relative_to(ROOT.resolve())
                    if relative.parts and relative.parts[0] not in {".venv", "venv", "results", ".git", ".codex"}:
                        failure["source"] = {"file": relative.as_posix(), "line": frames.tb_lineno,
                                             "function": frames.tb_frame.f_code.co_name}
                except (OSError, ValueError):
                    pass
            frames = frames.tb_next
        jobs = self._manifest.get("jobs", [])
        if 0 <= self._job_index < len(jobs):
            entry = jobs[self._job_index]
            failure.update(job_index=self._job_index, job_type=entry["type"], job_status=entry["status"])
            entry["last_failure"] = failure
        self._manifest["last_failure"] = failure

    def _run_job(self, entry):
        kind, job = entry["type"], entry["job"]
        cfg = copy.deepcopy(self.cfg)
        cfg.setdefault("output", {})["run_root"] = str(Path(self.output_dir) / entry["output_root"])
        cfg.setdefault("performance", {})["batch_cache_path"] = str(Path(self.output_dir) / "responses.sqlite3")
        loader = self._loader_for(entry)
        if kind == "standard":
            cfg["pilot"] = job.get("pilot", False)
            child = ExperimentRunner(cfg, progress=self.progress, dataset_loader=loader,
                                     model_loader=self.model_loader, work_progress=self._mark_work)
            checkpoint = entry.get("checkpoint") or child.find_latest_resumable_checkpoint(cfg)
        else:
            child = StudyRunner(cfg, progress=self.progress, dataset_loader=loader,
                                model_loader=self.model_loader, work_progress=self._mark_work)
            checkpoint = entry.get("checkpoint") or child.find_latest_resumable_checkpoint(cfg)
        self.active_runner = child
        if not self._running.is_set():
            child.request_pause()
        if self._stop.is_set():
            child.request_stop()
        try:
            if kind == "standard":
                status = child.run_all(job["datasets"], job["models"], job["prompts"], job["protocols"],
                                       job["parsers"], resume_checkpoint=checkpoint)
            else:
                study = copy.deepcopy(job["config"])
                study.setdefault("performance", {})["batch_cache_path"] = cfg["performance"]["batch_cache_path"]
                status = child.run_study(study, pilot=job.get("pilot", False), limit=job.get("limit"),
                                         bootstrap=job.get("bootstrap", 1000), resume_manifest=checkpoint)
            return status
        except BaseException:
            entry["status"] = "failed"
            raise
        finally:
            entry["report"] = child.report_html_path
            if kind == "standard":
                entry["checkpoint"] = child.checkpoint_path
            elif child.output_dir:
                entry["checkpoint"] = str(Path(child.output_dir) / "manifest.json")
            if entry.get("status") == "failed" and entry.get("checkpoint"):
                saved = json.loads(Path(entry["checkpoint"]).read_text(encoding="utf-8"))
                if (kind == "standard" and saved.get("status") == "generated"
                        or kind != "standard" and saved.get("status") == "completed"):
                    entry["status"] = "generated"
            self.active_runner = None

    def run_batch(self, jobs, *, resume_manifest=None):
        self.final_status = "running"
        validated = False
        analysis_only = False
        try:
            if resume_manifest:
                self._manifest_path = Path(resume_manifest)
                self.output_dir = str(self._manifest_path.parent)
                self._manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
                if self._manifest.get("schema_version") != 1:
                    raise InferenceStateError("Unsupported batch format")
                analysis_only = all(entry["status"] in {"completed", "generated"}
                                    for entry in self._manifest["jobs"])
                if not analysis_only and self._manifest["sources"] != self._sources():
                    raise InferenceStateError("Batch sources changed; start a new batch")
                current_api = self.cfg.get("api", {})
                self.cfg = copy.deepcopy(self._manifest["config"])
                for key in ("api_key", "token", "access_token"):
                    if key in current_api:
                        self.cfg.setdefault("api", {})[key] = current_api[key]
                if analysis_only:
                    self._manifest["analysis_resume_sources"] = self._sources()
                else:
                    planned = self._plan([entry["job"] for entry in self._manifest["jobs"]])
                    if [entry["cohorts"] for entry in planned] != [entry["cohorts"] for entry in self._manifest["jobs"]]:
                        raise InferenceStateError("Batch datasets changed; start a new batch")
            else:
                self._emit("Planning", "Reading selected datasets", force=True)
                planned = self._plan(jobs)
                root = Path(self.cfg.get("output", {}).get("run_root", "results/runs"))
                output = root / ("batch_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8])
                output.mkdir(parents=True, exist_ok=False)
                self.output_dir = str(output)
                self._manifest_path = output / "batch_manifest.json"
                self._manifest = {"schema_version": 1, "version": __version__, "config": safe_settings(self.cfg),
                                  "created_at": datetime.now(timezone.utc).isoformat(), "sources": self._sources(),
                                  "jobs": planned, "work_estimate": {
                                      "generation": "One unit per distinct request resolution within each experiment type; cache hits count as completed",
                                      "prediction": "0.05 units per parsed prediction",
                                      "finalization": "Five percent of planned request and prediction work, at least one unit per report"}}
            self.report_html_path = str(Path(self.output_dir) / "report.html")
            requested = sum(entry["generation_units"] for entry in self._manifest["jobs"])
            self._manifest["work_estimate"]["generation_requests_before_cross_job_reuse"] = requested
            self.progress(f"Planned generation requests before cross-job/cache reuse: {requested:,.0f}. "
                          "Parser selections reuse responses; different prompts, seeds, and verdict orders need separate requests.")
            ledger_path = Path(self.output_dir) / "progress.sqlite3"
            new_ledger = not ledger_path.exists()
            if resume_manifest and new_ledger and not analysis_only:
                raise InferenceStateError("The batch progress file is missing; keep the batch directory together")
            self._ledger = sqlite3.connect(ledger_path)
            self._ledger.execute("PRAGMA journal_mode=WAL")
            self._ledger.execute("PRAGMA synchronous=NORMAL")
            self._ledger.execute("CREATE TABLE IF NOT EXISTS work (job INTEGER, id TEXT, units REAL, PRIMARY KEY(job,id))")
            if analysis_only and new_ledger:
                for index, entry in enumerate(self._manifest["jobs"]):
                    units = entry["total_units"] - (entry["finalize_units"] if entry["status"] == "generated" else 0)
                    self._ledger.execute("INSERT INTO work VALUES (?, ?, ?)", (index, "saved_generation", units))
            self._ledger.commit()
            self._work_totals = dict(self._ledger.execute("SELECT job, SUM(units) FROM work GROUP BY job"))
            self._last_ledger_flush = time.monotonic()
            if resume_manifest and not analysis_only and not (Path(self.output_dir) / "responses.sqlite3").exists():
                responses = self._ledger.execute("SELECT COUNT(*) FROM work WHERE id LIKE 'generation:%'").fetchone()[0]
                if responses:
                    raise InferenceStateError("The batch response cache is missing; keep the batch directory together")
            validated = True
            self._save()
            for self._job_index, entry in enumerate(self._manifest["jobs"]):
                self._control()
                if entry["status"] == "completed":
                    continue
                entry["status"] = "running"
                self._save()
                self._emit(TYPE_NAMES[entry["type"]], "Starting experiment", force=True)
                status = self._run_job(entry)
                entry["status"] = status
                if status == "stopped":
                    if entry.get("checkpoint"):
                        saved = json.loads(Path(entry["checkpoint"]).read_text(encoding="utf-8"))
                        if (entry["type"] != "standard" and saved.get("status") == "completed"
                                or entry["type"] == "standard" and saved.get("status") == "generated"):
                            entry["status"] = "generated"
                    self.final_status = "stopped"
                    break
                if status not in {"completed", "generated"}:
                    raise RuntimeError(f"{TYPE_NAMES[entry['type']]} did not finish")
                known = self._work_totals.get(self._job_index, 0.0)
                target = entry["total_units"] - (entry["finalize_units"] if status == "generated" else 0)
                self._mark_work("finalize", status, max(0, target - known))
                self._save()
            else:
                self.final_status = "generated" if any(entry["status"] == "generated" for entry in self._manifest["jobs"]) else "completed"
            self._save()
            self._emit("Completed" if self.final_status == "completed" else "Analysis pending" if self.final_status == "generated" else "Stopped",
                       force=True)
            return self.final_status
        except BatchStopped:
            self.final_status = "stopped"
            if validated and self._manifest:
                self._save()
            return self.final_status
        except BaseException as error:
            self.final_status = "failed"
            if validated and self._manifest and self._manifest_path and Path(self.output_dir).exists():
                self._record_failure(error)
                self._save()
            raise
        finally:
            if self._ledger is not None:
                try:
                    self._flush_progress()
                finally:
                    self._ledger.close()
                    self._ledger = None
