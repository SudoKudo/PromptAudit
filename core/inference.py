"""Bounded inference requests and local, versioned response reuse."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import copy
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import threading
import time
import uuid

from models.base import BaseModel
from utils.privacy import safe_settings, safe_text


_ANNOTATIONS = {"experiment_name", "experiment_notes", "sc_samples", "sc_vote_delay_seconds", "ollama_keep_alive"}
STANDARD_PREFETCH_BATCHES = 4

GENERATION_DIAGNOSTIC_FIELDS = (
    "decision_calls", "decision_seconds", "decision_prompt_tokens", "decision_output_tokens",
    "decision_output_limit_hits", "decision_generation_errors", "distinct_responses",
)


def generation_diagnostics(calls):
    """Summarize decision calls without turning missing measurements into zeros."""
    def total(field):
        values = [call.get("generation_info", {}).get(field) for call in calls]
        return sum(values) if all(type(value) in (int, float) for value in values) else None

    seconds = [call.get("seconds", call.get("generation_info", {}).get("generation_seconds"))
               for call in calls]
    limits = []
    for call in calls:
        info = call.get("generation_info", {})
        hit = info.get("output_limit_reached")
        if hit is None and info.get("done_reason") in {"stop", "length", "stop_sequence"}:
            hit = info["done_reason"] == "length"
        limits.append(hit)
    return {
        "decision_calls": len(calls),
        "decision_seconds": sum(seconds) if all(type(value) in (int, float) for value in seconds) else None,
        "decision_prompt_tokens": total("prompt_eval_count"),
        "decision_output_tokens": total("eval_count"),
        "decision_output_limit_hits": sum(limits) if all(type(value) is bool for value in limits) else None,
        "decision_generation_errors": sum(bool(call.get("error") or call.get("generation_info", {}).get("status") == "error")
                                          for call in calls),
        "distinct_responses": (len({call["raw_output"] for call in calls})
                               if all("raw_output" in call for call in calls) else None),
    }


class InferenceStateError(ValueError):
    """A saved inference identity or cache cannot be used safely."""


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def performance_options(settings=None, backend=None):
    settings = {} if settings is None else settings
    if not isinstance(settings, dict):
        raise ValueError("performance must be a dictionary")
    workers = settings.get("inference_workers", 1)
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("inference_workers must be an integer from 1 to 8")
    if workers > 1 and backend not in {None, "ollama", "dummy"}:
        raise ValueError("Parallel inference supports Ollama and dummy backends; use one worker for HF or API models")
    for name in ("response_cache", "defer_analysis"):
        if name in settings and type(settings[name]) is not bool:
            raise ValueError(f"{name} must be true or false")
    profile = settings.get("cache_profile", "")
    if not isinstance(profile, str):
        raise ValueError("cache_profile must be a string")
    return {"inference_workers": workers, "response_cache": settings.get("response_cache", True),
            "cache_root": settings.get("cache_root", "results/cache"),
            "batch_cache_path": settings.get("batch_cache_path"),
            "cache_profile": profile.strip(),
            "defer_analysis": settings.get("defer_analysis", False)}


class ResponseCache:
    """SQLite is accessed only by the runner thread, never by inference workers."""

    def __init__(self, path, *, shared=False):
        path = Path(path)
        self.db = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(path, timeout=30)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
            self.db.execute("CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, payload TEXT, checksum TEXT)")
            self.db.commit()
        except (OSError, sqlite3.Error) as exc:
            if self.db is not None:
                self.db.close()
            raise InferenceStateError("Cannot open the response cache") from exc
        self.shared = shared
        self.pending = 0

    def get(self, key):
        try:
            row = self.db.execute("SELECT payload, checksum FROM responses WHERE key = ?", (key,)).fetchone()
        except sqlite3.Error as exc:
            raise InferenceStateError("Cannot read the response cache") from exc
        if row is None:
            return None
        if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise InferenceStateError("Response cache failed its integrity check; use a new cache directory")
        try:
            return json.loads(row[0])
        except ValueError as exc:
            raise InferenceStateError("Response cache contains invalid JSON") from exc

    def put(self, key, value):
        payload = json.dumps(value, ensure_ascii=False)
        try:
            self.db.execute("INSERT OR REPLACE INTO responses VALUES (?, ?, ?)",
                            (key, payload, hashlib.sha256(payload.encode()).hexdigest()))
        except sqlite3.Error as exc:
            raise InferenceStateError("Cannot save the response cache") from exc
        self.pending += 1
        if self.shared or self.pending >= 128:
            self.flush()

    def flush(self):
        try:
            self.db.commit()
        except sqlite3.Error as exc:
            raise InferenceStateError("Cannot flush the response cache") from exc
        self.pending = 0

    def close(self):
        try:
            self.flush()
        finally:
            self.db.close()


class InferenceEngine:
    """Execute immutable requests while keeping client state private per worker."""

    def __init__(self, model, model_item, loader, *, performance=None, run_cache=None, control=None, progress=None,
                 model_info=None, on_response=None):
        self.model = model
        self.model_item = copy.deepcopy(model_item)
        self.backend = str(model_item.get("backend", "ollama") if isinstance(model_item, dict) else "ollama").lower()
        self.options = performance_options(performance, self.backend)
        self.workers = self.options["inference_workers"]
        self.standard_prefetch_samples = self.workers * STANDARD_PREFETCH_BATCHES if self.workers > 1 else 1
        self.loader = loader
        self.control = control
        self.progress = progress
        self._last_report = 0.0
        self.run_cache = run_cache
        self.on_response = on_response
        batch_path = self.options["batch_cache_path"]
        self.batch_cache = ResponseCache(batch_path, shared=True) if batch_path else None
        self._local = threading.local()
        self._clients = []
        self._client_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=self.workers) if self.workers > 1 else None
        info = safe_settings(model_info if model_info is not None else
                             model.get_model_info() if hasattr(model, "get_model_info") else {})
        self.model_info = copy.deepcopy(info)
        root = Path(__file__).resolve().parents[1]
        sources = [Path(__file__), *sorted((root / "models").glob("*.py")),
                   *sorted((root / "prompts").glob("*.py")), root / "evaluation/output_protocol.py",
                   root / "utils/privacy.py"]
        versions = {}
        for package in ("requests", "torch", "transformers"):
            try:
                versions[package] = metadata.version(package)
            except metadata.PackageNotFoundError:
                versions[package] = None
        # Hash machine identifiers; neither a hostname nor a MAC address is saved.
        machine = hashlib.sha256(f"{platform.node()}:{uuid.getnode()}".encode()).hexdigest()
        selection = safe_settings(self.model_item)
        self.namespace = _hash({"schema": 1, "model": selection, "resolved": info,
                               "python": platform.python_version(), "platform": platform.platform(),
                               "machine": machine, "packages": versions,
                               "profile": self.options["cache_profile"],
                               "execution_environment": {key: os.environ.get(key) for key in (
                                   "CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES",
                                   "GGML_VK_VISIBLE_DEVICES", "OLLAMA_VULKAN", "OLLAMA_FLASH_ATTENTION",
                                   "OLLAMA_KV_CACHE_TYPE", "OLLAMA_NUM_PARALLEL", "OLLAMA_CONTEXT_LENGTH")},
                               "sources": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in sources}})
        strong_identity = ((self.backend == "ollama" and info.get("digest") and info.get("runtime_version")
                            and not info.get("metadata_error") and self.options["cache_profile"]
                            and (model.gen_cfg.get("context_window") or model.gen_cfg.get("num_ctx")))
                           or (self.backend in {"hf", "huggingface"} and info.get("resolved_revision"))
                           or (self.backend == "dummy" and info.get("cache_identity")))
        self.shared_cache = None
        cache_warning = None
        if self.options["response_cache"] and strong_identity:
            try:
                self.shared_cache = ResponseCache(Path(self.options["cache_root"]) / "responses.sqlite3", shared=True)
            except (sqlite3.Error, OSError, InferenceStateError) as exc:
                cache_warning = type(exc).__name__
        self.stats = {"generated_calls": 0, "run_reuses": 0, "batch_cache_hits": 0, "shared_cache_hits": 0,
                      "generation_seconds": 0.0, "workers": self.workers,
                      "persistent_cache_enabled": self.shared_cache is not None}
        if cache_warning:
            self.stats["shared_cache_warning"] = cache_warning
        self.started = time.perf_counter()

    def key(self, prompt, settings):
        effective = {k: v for k, v in safe_settings(settings).items() if k not in _ANNOTATIONS}
        return _hash({"namespace": self.namespace, "prompt": prompt, "settings": effective})

    def _shareable(self, settings):
        return self.backend != "ollama" or bool(settings.get("context_window") or settings.get("num_ctx"))

    def _lookup(self, key, settings):
        for cache, source in ((self.run_cache, "run"), (self.batch_cache, "batch"), (self.shared_cache, "shared")):
            if source == "shared" and not self._shareable(settings):
                continue
            try:
                found = cache.get(key) if cache else None
            except (sqlite3.Error, OSError, InferenceStateError) as exc:
                if source != "shared":
                    raise
                self._disable_shared_cache(exc)
                continue
            if found is not None:
                found["cache_status"] = source
                counter = {"run": "run_reuses", "batch": "batch_cache_hits", "shared": "shared_cache_hits"}[source]
                self.stats[counter] += 1
                if source != "run" and self.run_cache:
                    self.run_cache.put(key, {k: v for k, v in found.items() if k != "cache_status"})
                return found
        return None

    def _disable_shared_cache(self, exc):
        self.stats["shared_cache_warning"] = type(exc).__name__
        self.stats["persistent_cache_enabled"] = False
        try:
            self.shared_cache.close()
        except (sqlite3.Error, OSError, InferenceStateError):
            pass
        self.shared_cache = None

    def _execute(self, prompt, settings):
        if self.workers == 1:
            model = self.model
        else:
            model = getattr(self._local, "model", None)
            if model is None:
                model = self.loader(self.model_item, copy.deepcopy(settings))
                self._local.model = model
                with self._client_lock:
                    self._clients.append(model)
        previous = model.gen_cfg
        started = time.perf_counter()
        raw, error, info = "", None, {}
        error_type = None
        try:
            model.gen_cfg = copy.deepcopy(settings)
            raw = str(model.generate(prompt) or "")
        except Exception as exc:
            error = safe_text(f"{type(exc).__name__}: {exc}")
            error_type = type(exc).__name__
        finally:
            model.gen_cfg = previous
            if hasattr(model, "consume_generation_info"):
                info = safe_settings(model.consume_generation_info() or {})
        if error is not None:
            info.update(status="error")
            info.setdefault("error_type", error_type)
            info.setdefault("error_message", error)
        return {"raw_output": raw, "error": error, "generation_info": info,
                "seconds": time.perf_counter() - started, "cache_status": "generated"}

    def _save(self, key, result, settings):
        self.stats["generated_calls"] += 1
        self.stats["generation_seconds"] += result["seconds"]
        payload = {k: v for k, v in result.items() if k != "cache_status"}
        if self.run_cache:
            self.run_cache.put(key, payload)
        if self.batch_cache:
            # A batch replays failures too, so a later experiment does not retry a draw.
            self.batch_cache.put(key, payload)
        if (self.shared_cache and self._shareable(settings) and not result["error"] and result["raw_output"].strip()
                and result["generation_info"].get("status") != "error"):
            try:
                self.shared_cache.put(key, payload)
            except (sqlite3.Error, OSError, InferenceStateError) as exc:
                self._disable_shared_cache(exc)

    def _report(self):
        now = time.perf_counter()
        if self.progress and now - self._last_report >= 5:
            self.progress(f"[INFERENCE] {self.model.name}: generated={self.stats['generated_calls']}, "
                          f"run_reuses={self.stats['run_reuses']}, shared_cache_hits={self.stats['shared_cache_hits']}")
            self._last_report = now

    def generate_many(self, requests, on_result=None, *, stop_requested=None):
        """Keep workers requests in flight; stopped, unstarted requests remain None."""
        requests = [(str(prompt), copy.deepcopy(settings)) for prompt, settings in requests]
        results = [None] * len(requests)
        pending = {}
        for index, (prompt, settings) in enumerate(requests):
            key = self.key(prompt, settings)
            pending.setdefault(key, []).append(index)

        def finish(key, result):
            for index in pending[key]:
                results[index] = copy.deepcopy(result)
                if on_result:
                    on_result(index, results[index])
            if self.on_response:
                self.on_response(key, result)

        missing = []
        for key, indexes in pending.items():
            if self.control:
                self.control()
            result = self._lookup(key, requests[indexes[0]][1])
            if result is not None:
                finish(key, result)
                self._report()
            else:
                missing.append((key, requests[indexes[0]]))
        if self.workers == 1:
            for key, (prompt, settings) in missing:
                if stop_requested and stop_requested():
                    break
                if self.control:
                    self.control()
                result = self._execute(prompt, settings)
                finish(key, result)
                self._save(key, result, settings)
                self._report()
            return results
        iterator = iter(missing)
        active = {}

        def submit_one():
            if stop_requested and stop_requested():
                return
            item = next(iterator, None)
            if item is None:
                return
            if self.control:
                self.control()
            key, (prompt, settings) = item
            active[self._executor.submit(self._execute, prompt, settings)] = (key, settings)

        try:
            for _ in range(self.workers):
                submit_one()
            while active:
                finished, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in finished:
                    key, settings = active.pop(future)
                    result = future.result()
                    finish(key, result)
                    self._save(key, result, settings)
                    self._report()
                    submit_one()
        except BaseException:
            # Already-running requests finish once and are saved before stopping.
            persistence_error = None
            for future, (key, settings) in active.items():
                if not future.cancel():
                    try:
                        result = future.result()
                    except BaseException:
                        continue  # An interrupted request has no returned outcome to save.
                    try:
                        finish(key, result)
                        self._save(key, result, settings)
                    except Exception as exc:
                        persistence_error = exc
            if persistence_error is not None:
                raise persistence_error
            raise
        finally:
            for future in active:
                future.cancel()
        return results

    def summary(self):
        return {**self.stats, "wall_seconds": time.perf_counter() - self.started,
                "cache_namespace": self.namespace,
                "standard_prefetch_samples": self.standard_prefetch_samples}

    def close(self):
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
        for model in self._clients:
            session = getattr(model, "session", None)
            if session:
                session.close()
        if self.shared_cache:
            try:
                self.shared_cache.close()
            except (sqlite3.Error, OSError, InferenceStateError) as exc:
                self._disable_shared_cache(exc)
        if self.batch_cache:
            self.batch_cache.close()
            self.batch_cache = None
        session = getattr(self.model, "session", None)
        if session:
            session.close()


class ManagedModel(BaseModel):
    """Preserve the prompt API while replaying raw responses across parsers."""

    def __init__(self, engine):
        super().__init__(engine.model.name, engine.model.gen_cfg)
        self.engine = engine
        self._ready = {}
        self._request_trace = []

    def begin_sample_trace(self):
        self._request_trace = []

    def consume_request_trace(self):
        trace, self._request_trace = self._request_trace, []
        return trace

    def get_model_info(self):
        return copy.deepcopy(self.engine.model_info)

    def prefetch(self, requests, *, stop_requested=None):
        results = self.engine.generate_many(requests, stop_requested=stop_requested)
        for (prompt, settings), result in zip(requests, results):
            if result is not None:
                self._ready[self.engine.key(prompt, settings)] = result
        return all(result is not None for result in results)

    def generate(self, prompt):
        key = self.engine.key(prompt, self.gen_cfg)
        result = self._ready.pop(key, None)
        if result is None:
            result = self.engine.generate_many([(prompt, self.gen_cfg)])[0]
        self._request_trace.append(key)
        info = {**result["generation_info"], "cache_status": result["cache_status"],
                "generation_seconds": result["seconds"], "response_key": key}
        self._set_generation_info(info)
        if result["error"]:
            raise RuntimeError(result["error"])
        return result["raw_output"]
