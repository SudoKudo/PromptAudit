"""Collect matched template, component, and voting experiments."""

import copy
import hashlib
from importlib import metadata
import json
import os
import platform
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from code_datasets.dataset_loader import load_dataset
from code_datasets.validation import sample_identity, validate_samples
from evaluation.label_parser import AVAILABLE_PARSER_MODES, parse_verdict_details
from evaluation.output_protocol import AVAILABLE_OUTPUT_PROTOCOLS
from evaluation.voting import POLICIES, aggregate_votes
from models.model_loader import load_model
from models.base import merge_generation_settings
from utils.privacy import safe_settings as _safe_settings
from utils.power import SleepInhibitor
from core.inference import InferenceEngine, InferenceStateError, generation_diagnostics, performance_options
from prompts.template_variants import (
    CODE_SLOT, COMPONENTS, FAMILIES, VARIANTS, render_component_template,
    render_template, template_manifest, text_hash,
)


ROOT = Path(__file__).resolve().parent.parent


def json_hash(value):
    return text_hash(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _append_json(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _load_log(path, with_offsets=False):
    """Recover only an incomplete final write; corruption elsewhere is an error."""
    if not path.exists():
        return
    with path.open("rb+") as stream:
        while True:
            start = stream.tell()
            line = stream.readline()
            if not line:
                break
            try:
                row = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                if stream.read(1) or line.endswith(b"\n"):
                    raise ValueError(f"Invalid JSON record in {path} at byte {start}")
                stream.truncate(start)
                break
            yield (start, row) if with_offsets else row
            if not line.endswith(b"\n"):
                stream.seek(0, os.SEEK_END)
                stream.write(b"\n")
                break


class _CallStore:
    """Index saved calls on disk so long studies do not hold raw outputs in RAM."""

    def __init__(self, output):
        self.path = output / "generations.jsonl"
        index = output / "call_index.sqlite3"
        index.unlink(missing_ok=True)
        self.db = sqlite3.connect(index)
        self.db.execute("CREATE TABLE calls (id TEXT PRIMARY KEY, offset INTEGER NOT NULL)")
        for offset, row in _load_log(self.path, with_offsets=True):
            self.db.execute("INSERT INTO calls VALUES (?, ?)", (row["generation_id"], offset))
        self.db.commit()
        self.stream = self.path.open("rb+" if self.path.exists() else "wb+")
        self.pending = 0

    def get(self, generation_id):
        row = self.db.execute("SELECT offset FROM calls WHERE id = ?", (generation_id,)).fetchone()
        if row is None:
            return None
        self.stream.seek(row[0])
        return json.loads(self.stream.readline())

    def add(self, call):
        self.stream.seek(0, os.SEEK_END)
        offset = self.stream.tell()
        self.stream.write((json.dumps(call, ensure_ascii=False) + "\n").encode("utf-8"))
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.db.execute("INSERT INTO calls VALUES (?, ?)", (call["generation_id"], offset))
        self.pending += 1
        # The JSON log is durable above; this index is rebuilt after a restart.
        if self.pending >= 128:
            self.db.commit()
            self.pending = 0

    def __len__(self):
        return self.db.execute("SELECT COUNT(*) FROM calls").fetchone()[0]

    def close(self):
        try:
            self.db.commit()
        finally:
            self.stream.close()
            self.db.close()


def _choices(cfg, key, defaults, allowed=None, *, allow_empty=False):
    values = cfg.get(key, defaults)
    if not isinstance(values, list) or (not values and not allow_empty) or len(values) != len(set(values)):
        raise ValueError(f"{key} must be a {'nonempty ' if not allow_empty else ''}list without duplicates")
    if allowed and any(v not in allowed for v in values):
        raise ValueError(f"Unsupported {key}: {values}")
    return values


def build_conditions(cfg):
    """Expand the study matrix before generating anything."""
    section = str(cfg.get("section", "")).upper()
    protocols = _choices(cfg, "protocols", ["verdict_first"], AVAILABLE_OUTPUT_PROTOCOLS)
    conditions = []
    for protocol in protocols:
        if section == "B":
            if "reference" not in cfg.get("variants", VARIANTS):
                raise ValueError("Task-wording studies require the reference variant for matched comparisons")
            for family in _choices(cfg, "families", list(FAMILIES), FAMILIES):
                for variant in _choices(cfg, "variants", list(VARIANTS), VARIANTS):
                    conditions.append({
                        "id": f"{family}/{variant}/{protocol}", "comparison": "templates",
                        "family": family, "variant": variant, "protocol": protocol,
                        "template": render_template(family, variant, protocol),
                        "draws": cfg.get("votes", 5) if family == "self_consistency" else 1,
                        "policy": "majority_requested" if family == "self_consistency" else "first",
                    })
        elif section == "C":
            for component in _choices(cfg, "components", list(COMPONENTS), COMPONENTS, allow_empty=True):
                for enabled in (False, True):
                    conditions.append({
                        "id": f"{component}/{'on' if enabled else 'off'}/{protocol}",
                        "comparison": "components", "family": component,
                        "variant": "on" if enabled else "off", "protocol": protocol,
                        "template": render_component_template(component, enabled, protocol),
                        "draws": 1, "policy": "first",
                    })
            for family in _choices(cfg, "voting_bases", ["cot", "adaptive_cot"],
                                   ["cot", "adaptive_cot"], allow_empty=True):
                policies = _choices(cfg, "voting_policies", list(POLICIES), POLICIES)
                draws = 1 if policies == ["first"] else cfg.get("votes", 5)
                for policy in policies:
                    conditions.append({
                        "id": f"{family}/{policy}/{protocol}", "comparison": "voting",
                        "family": family, "variant": "reference", "protocol": protocol,
                        "template": render_template(family, "reference", protocol),
                        "draws": draws, "policy": policy,
                    })
        else:
            raise ValueError("section must be B or C")
    if not conditions:
        raise ValueError("Select at least one component comparison or voting base")
    return conditions


def template_definitions():
    catalog = template_manifest()
    for component in COMPONENTS:
        prompts = {p: {state: render_component_template(component, state == "on", p)
                       for state in ("off", "on")} for p in AVAILABLE_OUTPUT_PROTOCOLS}
        catalog["templates"].append({
            "id": f"component/{component}", "prompts": prompts,
            "sha256": json_hash(prompts),
        })
    return catalog


def _prepare_samples(dataset_items, loader, limit):
    cohorts = []
    for item in dataset_items:
        name = item if isinstance(item, str) else item["name"]
        inventory = {}
        rows = load_dataset(item, inventory=inventory) if loader is load_dataset else loader(item)
        if loader is not load_dataset:
            inventory = dict(getattr(loader, "dataset_inventory", {}).get(name, {}))
        if not rows:
            raise ValueError(f"Dataset {name} has no samples")
        selected = validate_samples(rows[:limit] if limit is not None else rows, name)
        inventory.setdefault("loaded_samples", len(rows))
        inventory["selected_samples"] = len(selected)
        inventory.setdefault("source_exclusions", inventory.get("excluded_code_files"))
        samples = []
        for index, row in enumerate(selected):
            code = row.get("code")
            sample = sample_identity(row, name, index)
            samples.append({**sample, "code": code})
        public = [{k: v for k, v in s.items() if k != "code"} for s in samples]
        cohorts.append({"name": name, "samples": samples, "fingerprint": json_hash(public),
                        "inventory": inventory or {"loaded_samples": len(selected), "source_exclusions": None}})
    if len({c["name"] for c in cohorts}) != len(cohorts):
        raise ValueError("Dataset names must be unique within a study")
    return cohorts


def draw_seed(run_seed, sample_uid, vote_index):
    # The same sample/draw gets the same seed across templates and policies.
    base = int(hashlib.sha256(f"{run_seed}:{sample_uid}".encode()).hexdigest()[:8], 16)
    return (base + vote_index) % (2 ** 31)


def _decision_diagnostics(calls):
    """Keep unavailable backend measurements distinct from measured zeros."""
    diagnostics = generation_diagnostics(calls)
    return {key: diagnostics[key] for key in (
        "decision_prompt_tokens", "decision_output_tokens", "decision_output_limit_hits",
        "decision_generation_errors")}


def run_study(cfg, output=None, *, pilot=False, limit=None, resume=False,
              dataset_loader=load_dataset, model_loader=load_model, progress=print, control=None,
              work_progress=None):
    """Save calls once, then parse and aggregate their outputs into matched rows."""
    cfg = json.loads(json.dumps(cfg))
    performance_options(cfg.get("performance"))
    cfg.pop("metrics", None)
    from evaluation.template_analysis import resolve_analysis_settings
    cfg["analysis"] = resolve_analysis_settings(cfg.get("analysis"))
    progress_every = cfg.get("progress_every_n_samples", 10)
    if type(progress_every) is not int or progress_every < 1:
        raise ValueError("progress_every_n_samples must be a positive integer")
    cfg["votes"] = cfg.get("votes", 5)
    if type(cfg["votes"]) is not int or not 1 <= cfg["votes"] <= 100:
        raise ValueError("votes must be an integer from 1 to 100")
    cfg["min_valid_votes"] = cfg.get("min_valid_votes", min(3, cfg["votes"]))
    if type(cfg["min_valid_votes"]) is not int or not 1 <= cfg["min_valid_votes"] <= cfg["votes"]:
        raise ValueError("min_valid_votes must be between 1 and votes")
    if limit is not None and (not pilot or limit < 1):
        raise ValueError("A positive --limit is allowed only for pilot runs")
    seeds = _choices(cfg, "seeds", [42])
    if any(type(seed) is not int for seed in seeds):
        raise ValueError("seeds must contain integers")
    modes = _choices(cfg, "parser_modes", list(AVAILABLE_PARSER_MODES), AVAILABLE_PARSER_MODES)
    conditions = build_conditions(cfg)
    models = cfg.get("models", [])
    datasets = cfg.get("datasets", [])
    if not models or not datasets:
        raise ValueError("Select at least one model and dataset")
    identities, model_settings = [], []
    for item in models:
        if not isinstance(item, dict) or not item.get("name"):
            raise ValueError("Each model needs a name and a backend")
        if item.get("backend") not in {"ollama", "hf", "huggingface", "dummy"}:
            raise ValueError("B/C studies currently support local Ollama, HF, and dummy backends")
        if not pilot and item["backend"] == "dummy":
            raise ValueError("Dummy models are for --pilot runs only")
        performance_options(cfg.get("performance"), item["backend"])
        effective = merge_generation_settings(cfg.get("generation", {}),
                                              {k: v for k, v in item.items() if k not in {"name", "backend"}})
        if "ollama_keep_alive" not in effective and cfg.get("performance", {}).get("ollama_keep_alive"):
            effective["ollama_keep_alive"] = cfg["performance"]["ollama_keep_alive"]
        if any(c["draws"] > 1 for c in conditions):
            if effective.get("temperature", 0.2) <= 0 or effective.get("num_beams", 1) != 1:
                raise ValueError("Repeated voting requires temperature > 0 and num_beams = 1; "
                                 "repeating greedy decoding does not sample different paths")
        identities.append(json_hash(_safe_settings(item)))
        model_settings.append(effective)
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate model selections")
    cohorts = _prepare_samples(datasets, dataset_loader, limit)
    source_files = [ROOT / "run_revision_study.py", ROOT / "core" / "revision_study.py",
                    *sorted((ROOT / "prompts").glob("*.py")), *sorted((ROOT / "models").glob("*.py")),
                    *sorted((ROOT / "code_datasets").glob("*.py")), ROOT / "config.yaml",
                    ROOT / "evaluation" / "voting.py", ROOT / "evaluation" / "output_protocol.py",
                    ROOT / "evaluation" / "label_parser.py", ROOT / "evaluation" / "metrics.py",
                    ROOT / "evaluation" / "template_analysis.py", ROOT / "utils" / "privacy.py",
                    ROOT / "core" / "inference.py"]
    source_hashes = {str(p.relative_to(ROOT)): text_hash(p.read_text(encoding="utf-8")) for p in source_files}
    versions = {}
    for package in ("transformers", "torch", "requests", "PyYAML"):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    manifest = {
        "schema_version": 3, "config": _safe_settings(cfg), "pilot": pilot,
        "pilot_limit": limit, "python": platform.python_version(), "source_hashes": source_hashes,
        "package_versions": versions,
        "model_selections": [{"model_id": model_id, "name": item["name"]}
                             for item, model_id in zip(models, identities)],
        "templates": template_definitions(), "conditions": conditions,
        "cohorts": [{"name": c["name"], "fingerprint": c["fingerprint"], "inventory": c["inventory"],
                     "samples": [{k: v for k, v in s.items() if k != "code"} for s in c["samples"]]}
                    for c in cohorts],
    }
    fingerprint = json_hash(manifest)
    output = Path(output) if output else ROOT / "results" / "revision" / (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8])
    manifest_path = output / "manifest.json"
    if resume:
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old["fingerprint"] != fingerprint:
            raise ValueError("Resume refused: configuration, sources, or cohort changed")
        manifest["created_at"] = old["created_at"]
    else:
        output.mkdir(parents=True, exist_ok=False)
        manifest["created_at"] = datetime.now(timezone.utc).isoformat()
    manifest["resolved_models"] = old.get("resolved_models", {}).copy() if resume else {}
    manifest["inference_namespaces"] = old.get("inference_namespaces", {}).copy() if resume else {}
    prompts_path = output / "prompts.jsonl"
    calls = _CallStore(output)
    new_calls = 0
    preserve_completed_manifest = False
    prediction_path = output / "predictions.jsonl"
    pending_predictions = output / "predictions.pending.jsonl"
    total_samples = len(models) * len(seeds) * sum(len(c["samples"]) for c in cohorts)
    completed_samples = 0
    calls_per_sample = len({(text_hash(c["template"]), index)
                            for c in conditions for index in range(c["draws"])})
    engine = None
    performance_summaries = []
    try:
        saved_prompts = {r["sha256"] for r in _load_log(prompts_path)}
        manifest.update(fingerprint=fingerprint, status="running")
        _write_json(manifest_path, manifest)
        study_name = "Task-wording study" if cfg["section"].upper() == "B" else "Component and voting study"
        progress(f"{study_name}: {len(conditions)} conditions; results in {output}")
        progress(f"[INFERENCE] Planned {total_samples * calls_per_sample} unique recorded requests; "
                 "saved responses and local cache hits avoid additional model calls.")
        with pending_predictions.open("w", encoding="utf-8") as predictions:
            for model_item, model_id, effective in zip(models, identities, model_settings):
                if control:
                    control()
                model = model_loader(model_item, effective.copy())
                snapshot = _safe_settings(model.get_model_info() if hasattr(model, "get_model_info") else {})
                engine = InferenceEngine(model, model_item, model_loader,
                                         performance=cfg.get("performance"), control=control, progress=progress,
                                         model_info=snapshot,
                                         on_response=(lambda key, result: work_progress("generation", key, 1))
                                         if work_progress else None)
                previous_snapshot = manifest["resolved_models"].get(model_id)
                if previous_snapshot is not None and previous_snapshot != snapshot:
                    raise ValueError("Resume refused: resolved model, runtime, or chat template changed")
                previous_namespace = manifest["inference_namespaces"].get(model_id)
                if previous_namespace is not None and previous_namespace != engine.namespace:
                    raise InferenceStateError("Resume refused: inference execution environment changed; start a new study")
                manifest["resolved_models"][model_id] = snapshot
                manifest["inference_namespaces"][model_id] = engine.namespace
                _write_json(manifest_path, manifest)
                for cohort in cohorts:
                    for run_seed in seeds:
                        for sample in cohort["samples"]:
                            if control:
                                control()
                            requests, request_calls, pools = [], [], {}
                            for condition in conditions:
                                prompt = condition["template"].replace(CODE_SLOT, sample["code"])
                                prompt_hash = text_hash(prompt)
                                if prompt_hash not in saved_prompts:
                                    _append_json(prompts_path, {"sha256": prompt_hash, "text": prompt})
                                    saved_prompts.add(prompt_hash)
                                pool_ids = []
                                for vote_index in range(condition["draws"]):
                                    seed = draw_seed(run_seed, sample["sample_uid"], vote_index)
                                    settings = {**model.gen_cfg, "seed": seed}
                                    generation_id = json_hash({
                                        "model": model_id, "cohort": cohort["fingerprint"],
                                        "sample": sample["sample_uid"], "prompt": prompt_hash,
                                        "settings": _safe_settings(settings), "run_seed": run_seed,
                                        "vote_index": vote_index,
                                    })
                                    pool_ids.append(generation_id)
                                    if generation_id not in pools:
                                        existing = calls.get(generation_id)
                                        if existing is not None and work_progress:
                                            work_progress("generation", engine.key(prompt, settings), 1)
                                        pools[generation_id] = existing
                                        if existing is None:
                                            requests.append((prompt, settings))
                                            request_calls.append({"generation_id": generation_id, "model_id": model_id,
                                                "dataset": cohort["name"], "sample_uid": sample["sample_uid"],
                                                "run_seed": run_seed, "vote_index": vote_index, "seed": seed,
                                                "prompt_sha256": prompt_hash, "settings": _safe_settings(settings)})
                                condition["_pool"] = pool_ids

                            def save_call(index, result):
                                nonlocal new_calls
                                call = {**request_calls[index], **result}
                                calls.add(call)
                                pools[call["generation_id"]] = call
                                new_calls += 1

                            engine.generate_many(requests, on_result=save_call)
                            parsed_labels = {}
                            for condition in conditions:
                                pool = [pools[key] for key in condition.pop("_pool")]
                                for mode in modes:
                                    labels = []
                                    for call in pool:
                                        key = (call["generation_id"], mode, condition["protocol"])
                                        if key not in parsed_labels:
                                            parsed_labels[key] = parse_verdict_details(call["raw_output"], mode=mode,
                                                output_protocol=condition["protocol"])
                                        labels.append(parsed_labels[key]["label"])
                                    decision = aggregate_votes(labels, condition["policy"], cfg["min_valid_votes"])
                                    used = pool[:1] if condition["policy"] == "first" else pool
                                    row = {k: v for k, v in sample.items() if k != "code"}
                                    row.update(dataset=cohort["name"], model=model_item["name"], model_id=model_id,
                                               run_seed=run_seed, condition=condition["id"],
                                               comparison=condition["comparison"], family=condition["family"],
                                               variant=condition["variant"], protocol=condition["protocol"],
                                               parser_mode=mode, pred=decision["label"], aggregation=decision,
                                               generation_ids=[c["generation_id"] for c in pool],
                                               decision_generation_ids=[c["generation_id"] for c in used],
                                               parsed_votes=[{"generation_id": call["generation_id"],
                                                   "label": parsed_labels[(call["generation_id"], mode, condition["protocol"])]["label"],
                                                   "tier": parsed_labels[(call["generation_id"], mode, condition["protocol"])]["tier"]}
                                                   for call in pool],
                                               pool_calls=len(pool), decision_calls=len(used),
                                               distinct_responses=len({c["raw_output"] for c in pool}),
                                               **_decision_diagnostics(used),
                                               decision_seconds=sum(c["seconds"] for c in used))
                                    predictions.write(json.dumps(row, ensure_ascii=False) + "\n")
                            predictions.flush()
                            if work_progress:
                                work_key = json_hash([model_id, cohort["fingerprint"], run_seed, sample["sample_uid"]])
                                work_progress("prediction", work_key, len(conditions) * len(modes) * 0.05)
                            completed_samples += 1
                            if completed_samples == 1 or completed_samples % progress_every == 0 or completed_samples == total_samples:
                                progress(f"Finished sample {completed_samples} / {total_samples}")
                        progress(f"Finished {model_item['name']} on {cohort['name']}, run seed {run_seed}")
                performance_summaries.append({"model_id": model_id, **engine.summary()})
                progress(f"[INFERENCE] {model_item['name']}: {engine.stats}")
                engine.close()
                engine = None
                # Release local HF weights before loading the next model.
                del model
        pending_predictions.replace(prediction_path)
        manifest["status"] = "completed"
    except BaseException:
        preserve_completed_manifest = resume and old["status"] == "completed" and new_calls == 0
        manifest["status"] = "interrupted"
        raise
    finally:
        if engine is not None:
            performance_summaries.append({"model_id": model_id, **engine.summary()})
            engine.close()
        for condition in conditions:
            condition.pop("_pool", None)
        if pending_predictions.exists():
            if not prediction_path.exists():
                pending_predictions.replace(prediction_path)
            else:
                pending_predictions.unlink()
        if preserve_completed_manifest:
            manifest = old
        else:
            manifest.update(total_saved_calls=len(calls), new_calls_this_session=new_calls,
                            updated_at=datetime.now(timezone.utc).isoformat(),
                            inference_performance=performance_summaries)
        try:
            _write_json(manifest_path, manifest)
        finally:
            calls.close()
    return output


class StudyStopped(Exception):
    """Signal a cooperative stop between study requests."""


class StudyRunner:
    """Connect matched studies to dashboard progress, pause, stop, and resume."""

    def __init__(self, cfg, progress=None, *, dataset_loader=load_dataset, model_loader=load_model,
                 work_progress=None):
        self.cfg = copy.deepcopy(cfg)
        self.progress = progress or print
        self.dataset_loader = dataset_loader
        self.model_loader = model_loader
        self.work_progress = work_progress
        self.output_dir = None
        self.report_html_path = None
        self.final_status = "idle"
        self._running = threading.Event()
        self._running.set()
        self._stop = threading.Event()

    @staticmethod
    def find_latest_resumable_checkpoint(cfg):
        root = Path(cfg.get("output", {}).get("run_root", "results/runs"))
        candidates = []
        for path in root.glob("study_*/manifest.json"):
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                needs_analysis = manifest.get("status") == "completed" and not (path.parent / "report.html").exists()
                if (manifest.get("status") in {"running", "interrupted"} or needs_analysis) and manifest.get("schema_version") == 3:
                    candidates.append(path)
            except (OSError, ValueError):
                continue
        return str(max(candidates, key=lambda path: path.stat().st_mtime)) if candidates else None

    def request_pause(self):
        self._running.clear()

    def request_resume(self):
        self._running.set()

    def request_stop(self):
        self._stop.set()
        self._running.set()

    def _control(self):
        if self._stop.is_set():
            raise StudyStopped()
        if not self._running.is_set():
            self.progress("Run paused. Saved calls will be reused when resuming.")
            while not self._running.wait(0.2):
                if self._stop.is_set():
                    raise StudyStopped()
            if self._stop.is_set():
                raise StudyStopped()
            self.progress("Resuming run...")

    def run_study(self, study_cfg, *, pilot=False, limit=None, bootstrap=1000, resume_manifest=None):
        if type(bootstrap) is not int or bootstrap < 0:
            raise ValueError("bootstrap must be a nonnegative integer")
        generated = False
        if resume_manifest:
            path = Path(resume_manifest)
            saved = json.loads(path.read_text(encoding="utf-8"))
            study_cfg = saved["config"]
            pilot, limit = saved["pilot"], saved.get("pilot_limit")
            bootstrap = study_cfg.get("bootstrap_resamples", bootstrap)
            output = path.parent
            generated = saved.get("status") == "completed"
        else:
            study_cfg = copy.deepcopy(study_cfg)
            study_cfg["bootstrap_resamples"] = bootstrap
            study_cfg.setdefault("progress_every_n_samples",
                                 self.cfg.get("performance", {}).get("progress_every_n_samples", 10))
            root = Path(self.cfg.get("output", {}).get("run_root", "results/runs"))
            output = root / ("study_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8])
        self.output_dir = str(output)
        self.report_html_path = str(output / "report.html")
        perf = self.cfg.get("performance", {})
        inhibitor = SleepInhibitor(perf.get("prevent_system_sleep", True), perf.get("keep_display_awake", False))
        self.final_status = "running"
        try:
            inhibitor.acquire()
            if not generated:
                run_study(study_cfg, output, pilot=pilot, limit=limit, resume=bool(resume_manifest),
                          dataset_loader=self.dataset_loader, model_loader=self.model_loader,
                          progress=self.progress, control=self._control, work_progress=self.work_progress)
            if not resume_manifest and performance_options(study_cfg.get("performance"))["defer_analysis"]:
                self.final_status = "generated"
                self.progress("Generation complete; analysis deferred. Resume this saved run to analyze its predictions.")
                return self.final_status
            from evaluation.template_analysis import analyze_study
            self.progress("Analyzing saved predictions...")
            analyze_study(output, bootstrap, control=self._control)
            self.final_status = "completed"
            return self.final_status
        except StudyStopped:
            self.final_status = "stopped"
            self.progress("Study stopped. Saved calls can be resumed from the manifest.")
            return self.final_status
        except BaseException:
            self.final_status = "failed"
            raise
        finally:
            inhibitor.release()
