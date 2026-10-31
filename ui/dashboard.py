"""Main ttkbootstrap dashboard for configuring and running PromptAudit experiments."""

import copy
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import webbrowser
import tkinter as tk

import yaml
import ttkbootstrap as tb
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.tooltip import ToolTip
from tkinter import IntVar, DoubleVar, StringVar

# --- Project path wiring -----------------------------------------------------
# Ensure the project root is on sys.path so imports like core.runner work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.runner import ExperimentRunner
from core.revision_study import StudyRunner
from core.batch_runner import BatchRunner
from core import __version__
from evaluation.metrics import DIAGNOSTIC_HELP
from evaluation.template_analysis import resolve_analysis_settings
from prompts.template_variants import COMPONENTS, FAMILIES, VARIANTS, template_manifest
from evaluation.voting import POLICIES
from utils.privacy import safe_settings, safe_text

# --- Global constants / metadata ---------------------------------------------
VERSION_TAG = f"PromptAudit {__version__}"
STUDY_MODES = {
    "standard": "Standard prompts",
    "B": "Task wordings",
    "C": "Components and voting",
}

# Where user preferences and presets are stored on disk
PREFS_PATH = "ui/user_prefs.yaml"
PRESETS_DIR = "ui/presets"

# ---------------------------------------------------------------------
# YAML Helpers (load/save prefs and presets)
# ---------------------------------------------------------------------
def load_yaml(path: str):
    """
    Load YAML from a given path.

    Returns:
        dict: Parsed YAML dictionary, or {} if file is missing/empty.
    """
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_yaml(path: str, data: dict):
    """
    Save a dictionary as YAML to the given path, creating directories as needed.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(safe_settings(data), f)


def parse_run_seeds(value):
    """Accept an explicit list so a study never silently drops a requested seed."""
    parts = str(value).split(",")
    try:
        seeds = [int(part.strip()) for part in parts if part.strip()]
    except ValueError as exc:
        raise ValueError("Run seeds must be comma-separated integers, such as 42, 43.") from exc
    if not seeds or any(not part.strip() for part in parts) or len(seeds) != len(set(seeds)):
        raise ValueError("Run seeds must be a nonempty list without duplicates.")
    return seeds


def preset_path(name):
    """Keep preset filenames inside the local preset directory."""
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}", name)
            or name.endswith((".", " "))
            or name.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)],
                                                 *[f"LPT{i}" for i in range(1, 10)]}):
        raise ValueError("Use a preset name with letters, numbers, spaces, dots, underscores, or hyphens.")
    return os.path.join(PRESETS_DIR, f"{name}.yaml")


def build_runtime_config(base, prefs):
    """Freeze GUI settings before the worker starts; Tk stays on its own thread."""
    cfg = copy.deepcopy(base)
    cfg["debug_raw_outputs"] = prefs["debug_raw_outputs"]
    cfg.setdefault("performance", {}).update({key: prefs[key] for key in (
        "save_debug_log", "checkpoint_every_n_samples", "checkpoint_every_seconds", "progress_every_n_samples",
        "sc_vote_delay_seconds", "prevent_system_sleep", "keep_display_awake")})
    workers = prefs.get("inference_workers", cfg["performance"].get("inference_workers", 1))
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError("Inference workers must be an integer from one to eight.")
    cfg["performance"]["inference_workers"] = workers
    for name, default in (("response_cache", True), ("defer_analysis", False)):
        value = prefs.get(name, cfg["performance"].get(name, default))
        if type(value) is not bool:
            raise ValueError(f"{name.replace('_', ' ').capitalize()} must be enabled or disabled.")
        cfg["performance"][name] = value
    cfg["performance"].setdefault("cache_root", "results/cache")
    profile = prefs.get("cache_profile", cfg["performance"].get("cache_profile", ""))
    if not isinstance(profile, str):
        raise ValueError("Cache profile must be text.")
    cfg["performance"]["cache_profile"] = profile.strip()
    cfg.setdefault("generation", {}).update({key: copy.deepcopy(prefs[key]) for key in (
        "temperature", "top_p", "top_k", "max_new_tokens", "repetition_penalty", "frequency_penalty",
        "presence_penalty", "num_beams", "seed", "stop_sequences", "sc_samples", "experiment_name", "experiment_notes")})
    context = prefs.get("context_window", cfg["generation"].get("context_window", cfg["generation"].get("num_ctx", "")))
    context = "" if context is None else str(context).strip()
    cfg["generation"].pop("context_window", None)
    cfg["generation"].pop("num_ctx", None)
    if context:
        try:
            context_tokens = int(context)
        except ValueError as exc:
            raise ValueError("Context window must be a positive integer or blank.") from exc
        if context_tokens < 1:
            raise ValueError("Context window must be a positive integer or blank.")
        cfg["generation"]["context_window"] = context_tokens
    cfg.pop("metrics", None)
    analysis = copy.deepcopy(cfg.get("analysis", {}))
    analysis.update(copy.deepcopy(prefs.get("study_analysis", {})))
    analysis.setdefault("enabled", True)
    analysis["bootstrap_resamples"] = prefs.get("study_bootstrap", analysis.get("bootstrap_resamples", 1000))
    cfg["analysis"] = resolve_analysis_settings(analysis)
    return cfg


def selected_experiment_types(prefs):
    """Read the current selection, including preferences saved before multi-select."""
    selected = prefs.get("experiment_types")
    if selected is None:
        previous = prefs.get("study_mode", "standard")
        selected = [previous if previous in STUDY_MODES else "standard"]
    if (not isinstance(selected, list) or any(type(name) is not str for name in selected)
            or len(selected) != len(set(selected)) or any(name not in STUDY_MODES for name in selected)):
        raise ValueError("Choose experiment types from Standard prompts, Task wordings, and Components and voting.")
    return [name for name in STUDY_MODES if name in selected]


def build_gui_study_config(runtime, prefs, models, prompts, datasets, protocols, parsers, *, mode):
    if mode not in {"B", "C"}:
        raise ValueError("Choose a task-wording or component study.")
    votes = prefs["sc_samples"]
    if not 1 <= votes <= 100:
        raise ValueError("Requested draws must be between 1 and 100.")
    bootstrap = prefs["study_bootstrap"]
    if bootstrap < 0:
        raise ValueError("Bootstrap resamples must be zero or greater.")
    limit_text = prefs["study_limit"] if prefs["study_pilot"] else ""
    try:
        limit = int(limit_text) if limit_text else None
    except ValueError as exc:
        raise ValueError("Pilot sample limit must be a positive integer or blank.") from exc
    if limit is not None and (not prefs["study_pilot"] or limit < 1):
        raise ValueError("A positive sample limit is available only for pilots.")
    study = {
        "section": mode, "name": prefs["experiment_name"], "models": models, "datasets": datasets,
        "protocols": protocols, "parser_modes": parsers, "seeds": parse_run_seeds(prefs["study_seeds"]),
        "votes": votes, "min_valid_votes": min(3, votes), "generation": copy.deepcopy(runtime["generation"]),
        "analysis": copy.deepcopy(runtime["analysis"]),
        "performance": copy.deepcopy(runtime["performance"]),
    }
    if mode == "B":
        study["families"] = [name for name in prompts if name in FAMILIES]
        study["variants"] = list(prefs["study_wordings"])
        if not study["families"]:
            raise ValueError("Select at least one supported prompting approach for the wording study.")
        if "reference" not in study["variants"]:
            raise ValueError("Include Reference in the selected task wordings.")
    else:
        study.update(components=list(prefs["study_components"]), voting_bases=list(prefs["study_voting_bases"]),
                     voting_policies=list(prefs["study_voting_policies"]))
        study["analysis"]["rankings"] = False
        if not study["components"] and not study["voting_bases"]:
            raise ValueError("Select a component comparison or a voting base.")
        if study["voting_bases"] and not study["voting_policies"]:
            raise ValueError("Select at least one policy for the voting comparison.")
        if "majority_valid" in study["voting_policies"] and study["voting_bases"]:
            study["min_valid_votes"] = prefs["study_min_valid_votes"]
            if not 1 <= study["min_valid_votes"] <= votes:
                raise ValueError("Minimum valid draws must be between one and the requested draw count.")
    return copy.deepcopy(study), {"pilot": prefs["study_pilot"], "limit": limit, "bootstrap": bootstrap}


def build_gui_jobs(runtime, prefs, models, prompts, datasets, protocols, parsers):
    """Build the selected jobs before handing them to the background thread."""
    selected = selected_experiment_types(prefs)
    if not selected:
        raise ValueError("Select at least one experiment type.")
    if not (models and datasets and protocols and parsers):
        raise ValueError("Select a model, dataset, output protocol, and parser mode.")
    if any(name in selected for name in ("standard", "B")) and not prompts:
        raise ValueError("Select at least one prompt approach for Standard prompts or Task wordings.")
    jobs = []
    for mode in selected:
        if mode == "standard":
            limit = None
            if prefs["study_pilot"] and prefs["study_limit"].strip():
                try:
                    limit = int(prefs["study_limit"])
                except ValueError as exc:
                    raise ValueError("Pilot sample limit must be a positive integer or blank.") from exc
                if limit < 1:
                    raise ValueError("Pilot sample limit must be a positive integer or blank.")
            jobs.append({"type": mode, "models": models, "datasets": datasets, "prompts": prompts,
                         "protocols": protocols, "parsers": parsers,
                         "pilot": prefs["study_pilot"], "limit": limit})
        else:
            config, options = build_gui_study_config(runtime, prefs, models, prompts, datasets,
                                                       protocols, parsers, mode=mode)
            jobs.append({"type": mode, "config": config, **options})
    return copy.deepcopy(jobs)


# ---------------------------------------------------------------------
# Model Helpers
# ---------------------------------------------------------------------
def model_key(model_cfg: dict) -> str:
    """Stable selection key that preserves backend metadata across the GUI."""
    backend = str(model_cfg.get("backend", "ollama")).strip().lower()
    name = str(model_cfg.get("name", "unnamed")).strip()
    return f"{backend}::{name}"


def model_label(model_cfg: dict) -> str:
    """User-facing model label shown in the GUI."""
    backend = str(model_cfg.get("backend", "ollama")).strip().lower()
    name = str(model_cfg.get("name", "unnamed")).strip()
    return f"{name} [{backend}]"


def list_available_models(model_cfgs):
    """
    Return models from config.yaml, filtering Ollama entries by local availability.

    Strategy:
        - Read the configured model list from config.yaml.
        - Show all non-Ollama backends directly.
        - For Ollama backends, intersect the configured names with `ollama list`
          when the CLI is available.
        - Preserve the config order so experiments remain reproducible.

    Fallback:
        - If any error occurs (e.g., Ollama CLI not available),
          return all configured models.
    """
    normalized = []
    for cfg in model_cfgs:
        if not isinstance(cfg, dict) or not cfg.get("name"):
            continue
        copy = dict(cfg)
        copy["backend"] = str(copy.get("backend", "ollama")).strip().lower()
        normalized.append(copy)

    ollama_cfgs = [cfg for cfg in normalized if cfg["backend"] == "ollama"]
    non_ollama_cfgs = [cfg for cfg in normalized if cfg["backend"] != "ollama"]

    if not ollama_cfgs:
        return non_ollama_cfgs

    try:
        out = subprocess.check_output(["ollama", "list"], stderr=subprocess.STDOUT, text=True, timeout=5)
        # Skip header line, extract first column = model name/tag
        lines = [ln.split()[0].strip().lower() for ln in out.splitlines()[1:] if ln.strip()]
        found = []
        for cfg in ollama_cfgs:
            tag = cfg["name"].lower()
            base = tag.split(":")[0]
            if ":" in tag:
                matches = any(tag == ln for ln in lines)
            else:
                matches = any(ln == tag or ln.startswith(f"{base}:") for ln in lines)
            if matches:
                found.append(cfg)
        return found + non_ollama_cfgs
    except Exception:
        # If detection fails, just show the configured list
        return normalized


# ---------------------------------------------------------------------
# Dashboard Class
# ---------------------------------------------------------------------
class PromptAuditDashboard(tb.Window):
    """Configure experiments, run them in a worker thread, and display progress."""

    def __init__(self):
        super().__init__(themename="flatly")
        self.title(VERSION_TAG)
        self.geometry("1360x820")
        self.minsize(1280, 760)

        # --- Config and user prefs ------------------------------------------
        self.cfg = load_yaml("config.yaml")

        self.prefs = load_yaml(PREFS_PATH)

        os.makedirs(PRESETS_DIR, exist_ok=True)

        # --- Async / state ---------------------------------------------------
        # Thread-safe queue for messages from the worker thread
        self.msg_queue = queue.Queue()

        self._start_time = None

        self.runner = None
        self._pending_pause = False
        self._pending_stop = False
        self.max_log_lines = 2000
        self._persist_after_id = None
        self._last_prefs_snapshot = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # --- Selections for models / prompts / datasets ----------------------
        self.model_options = list_available_models(self.cfg.get("models", []))
        self.model_cfg_by_key = {model_key(cfg): cfg for cfg in self.model_options}
        self.model_label_by_key = {key: model_label(cfg) for key, cfg in self.model_cfg_by_key.items()}
        saved_models = set(self.prefs.get("models", []))

        # Prompt strategy names from config.yaml (e.g., ["zero_shot", "few_shot", ...])
        self.available_prompts = list(self.cfg.get("prompts", []))

        # Dataset names (only those with a "name" field in config.yaml)
        self.available_datasets = [d.get("name") for d in self.cfg.get("datasets", []) if d.get("name")]

        # Model selection: IntVar(1/0) for each configured model.
        self.sel_models = {
            key: IntVar(
                value=1
                if key in saved_models or self.model_cfg_by_key[key].get("name") in saved_models
                else 0
            )
            for key in self.model_cfg_by_key
        }

        # Prompt selection: IntVar(1/0) for each prompt strategy
        self.sel_prompts = {
            p: IntVar(value=1 if p in self.prefs.get("prompts", []) else 0)
            for p in self.available_prompts
        }

        # Dataset selection: IntVar(1/0) for each dataset
        self.sel_datasets = {
            d: IntVar(value=1 if d in self.prefs.get("datasets", []) else 0)
            for d in self.available_datasets
        }

        # Ablation selections: output protocols and parser modes
        ablation_cfg = self.cfg.get("ablations", {})
        self.available_output_protocols = list(
            ablation_cfg.get("available_output_protocols", ["verdict_first", "verdict_last"])
        )
        self.available_parser_modes = list(
            ablation_cfg.get("available_parser_modes", ["strict", "structured", "full"])
        )
        saved_output_protocols = set(
            self.prefs.get("output_protocols", ablation_cfg.get("default_output_protocols", ["verdict_first"]))
        )
        saved_parser_modes = set(
            self.prefs.get("parser_modes", ablation_cfg.get("default_parser_modes", ["full"]))
        )
        self.sel_output_protocols = {
            name: IntVar(value=1 if name in saved_output_protocols else 0)
            for name in self.available_output_protocols
        }
        self.sel_parser_modes = {
            name: IntVar(value=1 if name in saved_parser_modes else 0)
            for name in self.available_parser_modes
        }

        saved_types = selected_experiment_types(self.prefs)
        self.sel_experiment_types = {name: IntVar(value=name in saved_types) for name in STUDY_MODES}
        self.sel_wordings = {name: IntVar(value=name in self.prefs.get("study_wordings", VARIANTS))
                             for name in VARIANTS}
        self.sel_components = {name: IntVar(value=name in self.prefs.get("study_components", COMPONENTS))
                               for name in COMPONENTS}
        self.sel_voting_bases = {name: IntVar(value=name in self.prefs.get("study_voting_bases", ["cot", "adaptive_cot"]))
                                 for name in ("cot", "adaptive_cot")}
        self.sel_voting_policies = {name: IntVar(value=name in self.prefs.get("study_voting_policies", POLICIES))
                                    for name in POLICIES}
        analysis_cfg = resolve_analysis_settings({**self.cfg.get("analysis", {}),
                                                  **self.prefs.get("study_analysis", {})})
        self.sel_analysis = {name: IntVar(value=analysis_cfg[name])
                             for name in ("paired_comparisons", "rankings", "prevalence", "output_audit", "dataset_audit")}
        self.var_analysis_group = StringVar(value={"cve_id": "CVE", "repository": "Repository"}[analysis_cfg["group_by"]])
        self.var_prevalence_repeats = IntVar(value=analysis_cfg["prevalence_repeats"])
        self.var_prevalence_size = IntVar(value=analysis_cfg["prevalence_size"])
        self.var_review_limit = IntVar(value=analysis_cfg["review_case_limit"])
        self.var_study_seeds = StringVar(value=self.prefs.get("study_seeds", str(self.cfg.get("generation", {}).get("seed", 42))))
        self.var_study_min_valid = IntVar(value=int(self.prefs.get("study_min_valid_votes", 3)))
        self.var_study_bootstrap = IntVar(value=int(self.prefs.get("study_bootstrap", analysis_cfg["bootstrap_resamples"])))
        self.var_study_pilot = IntVar(value=bool(self.prefs.get("study_pilot", False)))
        self.var_study_limit = StringVar(value=str(self.prefs.get("study_limit", "")))

        # Resume metadata shown in the controls.
        self.latest_checkpoint_path = None

        # --- Metadata (experiment name + notes) ------------------------------
        self.var_exp_name = StringVar(value=self.prefs.get("experiment_name", "Untitled Experiment"))
        self.var_exp_notes = tk.StringVar(value=self.prefs.get("experiment_notes", ""))

        # --- Generation variables (synced with config.yaml + prefs) ----------
        gen_cfg = self.cfg.get("generation", {})
        perf_cfg = self.cfg.get("performance", {})

        # Temperature slider (float)
        self.var_temp = DoubleVar(
            value=float(self.prefs.get("temperature", gen_cfg.get("temperature", 0.2)))
        )

        # Top-p slider (float)
        self.var_top_p = DoubleVar(
            value=float(self.prefs.get("top_p", gen_cfg.get("top_p", 0.9)))
        )

        # Max new tokens spinbox (int)
        self.var_maxnew = IntVar(
            value=int(self.prefs.get("max_new_tokens", gen_cfg.get("max_new_tokens", 1024)))
        )

        # Frequency penalty slider (float)
        self.var_freq_pen = DoubleVar(
            value=float(self.prefs.get("frequency_penalty", gen_cfg.get("frequency_penalty", 0.0)))
        )

        # Presence penalty slider (float)
        self.var_pres_pen = DoubleVar(
            value=float(self.prefs.get("presence_penalty", gen_cfg.get("presence_penalty", 0.0)))
        )

        # Stop sequences: stored as list internally, edited as comma-separated string
        stops = self.prefs.get("stop_sequences", gen_cfg.get("stop_sequences", []))
        if isinstance(stops, (list, tuple)):
            stops_str = ", ".join(str(s) for s in stops)
        else:
            stops_str = str(stops or "")
        self.var_stop = StringVar(value=stops_str)
        saved_context = self.prefs.get("context_window", gen_cfg.get("context_window", gen_cfg.get("num_ctx", "")))
        self.var_context_window = StringVar(value="" if saved_context is None else str(saved_context))

        # Self-consistency samples: how many votes for SelfConsistency prompt
        self.var_sc_samples = IntVar(
            value=int(self.prefs.get("sc_samples", gen_cfg.get("sc_samples", 5)))
        )

        # --- Performance / runtime controls ---------------------------------
        self.var_debug_raw_outputs = IntVar(
            value=1 if self.prefs.get("debug_raw_outputs", self.cfg.get("debug_raw_outputs", False)) else 0
        )
        self.var_save_debug_log = IntVar(
            value=1 if self.prefs.get("save_debug_log", perf_cfg.get("save_debug_log", False)) else 0
        )
        self.var_checkpoint_every_n_samples = IntVar(
            value=int(self.prefs.get("checkpoint_every_n_samples", perf_cfg.get("checkpoint_every_n_samples", 10)))
        )
        self.var_checkpoint_every_seconds = DoubleVar(
            value=float(self.prefs.get("checkpoint_every_seconds", perf_cfg.get("checkpoint_every_seconds", 15.0)))
        )
        self.var_progress_every_n_samples = IntVar(
            value=int(self.prefs.get("progress_every_n_samples", perf_cfg.get("progress_every_n_samples", 10)))
        )
        self.var_sc_vote_delay_seconds = DoubleVar(
            value=float(self.prefs.get("sc_vote_delay_seconds", perf_cfg.get("sc_vote_delay_seconds", 0.0)))
        )
        self.var_prevent_system_sleep = IntVar(
            value=1 if self.prefs.get("prevent_system_sleep", perf_cfg.get("prevent_system_sleep", True)) else 0
        )
        self.var_keep_display_awake = IntVar(
            value=1 if self.prefs.get("keep_display_awake", perf_cfg.get("keep_display_awake", False)) else 0
        )
        self.var_inference_workers = IntVar(
            value=int(self.prefs.get("inference_workers", perf_cfg.get("inference_workers", 1)))
        )
        self.var_response_cache = IntVar(
            value=bool(self.prefs.get("response_cache", perf_cfg.get("response_cache", True)))
        )
        self.var_defer_analysis = IntVar(
            value=bool(self.prefs.get("defer_analysis", perf_cfg.get("defer_analysis", False)))
        )
        self.var_cache_profile = StringVar(
            value=str(self.prefs.get("cache_profile", perf_cfg.get("cache_profile", "")))
        )

        # --- Preset UI state -------------------------------------------------
        self.var_preset_name = StringVar()
        self.var_preset_select = StringVar(value="(select preset)")

        # Build controls before starting the queue poller.
        self._build_ui()
        self._refresh_performance_controls()
        self._refresh_study_controls()
        self._refresh_resume_checkpoint_ui()

        # Start polling for messages from the worker thread
        self.after(150, self._poll_msgs)

    # -----------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------
    def _build_ui(self):
        """
        Construct the two-pane layout:
            - Left: Experiment controls and presets
            - Right: Active run monitor (progress, logs, report access)
        """
        # Root layout: a control column plus a single run-monitor column.
        root = tb.Panedwindow(self, orient="horizontal")
        root.pack(fill="both", expand=True, padx=8, pady=8)

        # LEFT: Control column -------------------------------------------------
        left_col = tb.Labelframe(root, text="Experiment Control", padding=8)
        left_col.configure(width=560)
        root.add(left_col, weight=0)

        # Scrollable container for all left-side widgets
        left_scroll = ScrolledFrame(left_col, autohide=True, width=540, height=720)
        left_scroll.pack(fill="both", expand=True)
        left_inner = tb.Frame(left_scroll)
        left_inner.pack(fill="both", expand=True)

        tb.Label(
            left_inner,
            text="Select one or more experiment types, then choose the models, datasets, prompts, and run settings.",
            bootstyle="secondary",
            wraplength=500,
            justify="left",
        ).pack(fill="x", pady=(0, 8))

        # --- Experiment Metadata --------------------------------------------
        meta = tb.Labelframe(left_inner, text="Experiment Metadata", padding=8, bootstyle="primary")
        meta.pack(fill="x")

        lbl_name = tb.Label(meta, text="Name")
        lbl_name.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_name, text="Run name shown in saved results and reports.")
        self.entry_exp_name = tb.Entry(meta, textvariable=self.var_exp_name)
        self.entry_exp_name.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.entry_exp_name.bind("<FocusOut>", self._schedule_persist_prefs)
        self.entry_exp_name.bind("<Return>", self._schedule_persist_prefs)

        lbl_notes = tb.Label(meta, text="Notes")
        lbl_notes.grid(row=1, column=0, sticky="nw", padx=4, pady=4)
        ToolTip(lbl_notes, text="Any context about goals, changes, or hypotheses for this run.")
        self.txt_notes = tk.Text(meta, height=2, wrap="word")
        self.txt_notes.insert("1.0", self.var_exp_notes.get())
        self.txt_notes.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self.txt_notes.bind("<FocusOut>", self._schedule_persist_prefs)
        meta.grid_columnconfigure(1, weight=1)

        # --- Quick actions ---------------------------------------------------
        quick_actions = tb.Frame(left_inner)
        quick_actions.pack(fill="x", pady=(8, 0))

        presets = tb.Labelframe(quick_actions, text="Presets", padding=8, bootstyle="secondary")
        presets.pack(fill="x")

        lbl_save = tb.Label(presets, text="Save as")
        lbl_save.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_save, text="Save current selections and tuning values as a reusable preset.")
        tb.Entry(presets, textvariable=self.var_preset_name).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        tb.Button(presets, text="Save Preset", command=self._on_save_preset).grid(
            row=0, column=2, padx=4, pady=4
        )

        lbl_load = tb.Label(presets, text="Load")
        lbl_load.grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_load, text="Load a previously saved preset.")
        self.combo_presets = tb.Combobox(
            presets,
            textvariable=self.var_preset_select,
            state="readonly",
            values=self._list_presets(),
        )
        self.combo_presets.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        tb.Button(presets, text="Load Preset", command=self._on_load_preset).grid(
            row=1, column=2, padx=4, pady=4
        )
        presets.grid_columnconfigure(1, weight=1)

        run_box = tb.Labelframe(quick_actions, text="Run Controls", padding=8, bootstyle="success")
        run_box.pack(fill="x", pady=(8, 0))
        button_row = tb.Frame(run_box)
        button_row.pack(fill="x")
        self.run_btn = tb.Button(
            button_row,
            text="Run Selected Experiments",
            command=self._on_run,
            width=24,
            bootstyle="success",
        )
        self.run_btn.pack(side="left", padx=(0, 6))
        self.pause_btn = tb.Button(
            button_row, text="Pause", command=self._on_pause, width=9, state="disabled", bootstyle="warning-outline"
        )
        self.pause_btn.pack(side="left", padx=(0, 6))
        self.resume_btn = tb.Button(
            button_row, text="Resume", command=self._on_resume_active, width=9, state="disabled", bootstyle="info-outline"
        )
        self.resume_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = tb.Button(
            button_row, text="Stop", command=self._on_stop, width=9, state="disabled", bootstyle="danger"
        )
        self.stop_btn.pack(side="left")

        resume_saved_box = tb.Frame(run_box, padding=(0, 8, 0, 0))
        resume_saved_box.pack(fill="x")
        self.resume_saved_btn = tb.Button(
            resume_saved_box,
            text="Resume Saved Run",
            command=self._on_resume_saved,
            width=16,
            state="normal" if self.latest_checkpoint_path else "disabled",
            bootstyle="secondary-outline",
        )
        self.resume_saved_btn.pack(side="left", padx=(0, 6))
        resume_text = (
            os.path.basename(os.path.dirname(self.latest_checkpoint_path))
            if self.latest_checkpoint_path
            else "No resumable checkpoint found"
        )
        self.resume_saved_label = tb.Label(resume_saved_box, text=resume_text, bootstyle="secondary")
        self.resume_saved_label.pack(side="left", fill="x", expand=True)

        # --- Selection grid --------------------------------------------------
        selection_row = tb.Frame(left_inner)
        selection_row.pack(fill="x", pady=(8, 0))
        selection_row.grid_columnconfigure(0, weight=1, uniform="select")
        selection_row.grid_columnconfigure(1, weight=1, uniform="select")

        select_left = tb.Frame(selection_row)
        select_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        select_right = tb.Frame(selection_row)
        select_right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # --- Models ----------------------------------------------------------
        models_box = tb.Labelframe(select_left, text="Models", padding=8, bootstyle="primary")
        models_box.pack(fill="x")
        lbl_models = tb.Label(models_box, text="Select Models")
        lbl_models.pack(anchor="w")
        ToolTip(
            lbl_models,
            text="Choose one or more configured models to evaluate. Ollama entries are filtered by local availability when the CLI is reachable.",
        )
        for key, var in self.sel_models.items():
            tb.Checkbutton(
                models_box,
                text=self.model_label_by_key[key],
                variable=var,
                command=self._schedule_persist_prefs,
            ).pack(anchor="w")

        # --- Datasets --------------------------------------------------------
        data_box = tb.Labelframe(select_left, text="Datasets", padding=8, bootstyle="primary")
        data_box.pack(fill="x", pady=(8, 0))
        lbl_data = tb.Label(data_box, text="Select Datasets")
        lbl_data.pack(anchor="w")
        ToolTip(lbl_data, text="Datasets of code samples (toy, cvefixes, bigvul, etc.).")
        for name, var in self.sel_datasets.items():
            tb.Checkbutton(
                data_box,
                text=name,
                variable=var,
                command=self._schedule_persist_prefs,
            ).pack(anchor="w")

        # --- Prompts ---------------------------------------------------------
        prompts_box = tb.Labelframe(select_right, text="Prompt Strategies", padding=8, bootstyle="primary")
        self.prompts_box = prompts_box
        prompts_box.pack(fill="x")
        lbl_prompts = tb.Label(prompts_box, text="Select Prompts")
        lbl_prompts.pack(anchor="w")
        ToolTip(
            lbl_prompts,
            text="Different prompting modes (Zero-Shot, Few-Shot, CoT, Self-Consistency, etc.).",
        )
        self.prompt_buttons = {}
        for name, var in self.sel_prompts.items():
            button = tb.Checkbutton(
                prompts_box,
                text=name,
                variable=var,
                command=self._schedule_persist_prefs,
            )
            button.pack(anchor="w")
            self.prompt_buttons[name] = button

        # --- Ablations -------------------------------------------------------
        ablation_box = tb.Labelframe(select_right, text="Ablations", padding=8, bootstyle="warning")
        self.ablation_box = ablation_box
        ablation_box.pack(fill="x", pady=(8, 0))

        lbl_protocol = tb.Label(ablation_box, text="Output Protocols")
        lbl_protocol.pack(anchor="w")
        ToolTip(
            lbl_protocol,
            text="Verdict-first requests SAFE or VULNERABLE on the first line. Verdict-last requests it on the final line. Both keep the classification task fixed.",
        )
        for name, var in self.sel_output_protocols.items():
            tb.Checkbutton(
                ablation_box,
                text=name,
                variable=var,
                command=self._schedule_persist_prefs,
            ).pack(anchor="w")

        lbl_parser = tb.Label(ablation_box, text="Parser Modes")
        lbl_parser.pack(anchor="w", pady=(6, 0))
        ToolTip(
            lbl_parser,
            text="Apply each selected parser to the same saved response. Strict checks the required verdict line. Structured also checks explicit verdict patterns. Full adds keyword fallback.",
        )
        for name, var in self.sel_parser_modes.items():
            tb.Checkbutton(
                ablation_box,
                text=name,
                variable=var,
                command=self._schedule_persist_prefs,
            ).pack(anchor="w")

        mode_box = tb.Labelframe(left_inner, text="Experiment Types", padding=8, bootstyle="primary")
        mode_box.pack(fill="x", pady=(8, 0), before=selection_row)
        mode_help = {
            "standard": "Generate responses for the selected complete prompt strategies.",
            "B": "Compare selected task wordings for each approach. Role, technique instructions, examples, target code, and output protocol stay fixed within each comparison.",
            "C": "Compare components on one shared prompt scaffold and compare voting policies using saved response pools. These controls are separate from the selected complete prompt strategies.",
        }
        for name, label in STUDY_MODES.items():
            button = tb.Checkbutton(mode_box, text=label, variable=self.sel_experiment_types[name],
                                    command=self._on_experiment_types_change)
            button.pack(anchor="w")
            ToolTip(button, text=mode_help[name])

        self._build_study_controls(left_inner)

        # --- Generation settings -------------------------------------------
        gen = tb.Labelframe(left_inner, text="Generation Settings", padding=8, bootstyle="info")
        self.generation_box = gen
        gen.pack(fill="x", pady=(8, 0))

        # Temperature ---------------------------------------------------------
        lbl_temp = tb.Label(gen, text="Temperature")
        lbl_temp.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_temp,
            text="Controls sampling randomness. Zero uses greedy decoding. Self-consistency and repeated voting need a value above zero.",
        )
        tb.Scale(
            gen,
            from_=0.0,
            to=2.0,
            orient="horizontal",
            variable=self.var_temp,
            command=self._schedule_persist_prefs,
        ).grid(row=0, column=1, sticky="ew", padx=4)
        self.lbl_temp_val = tb.Label(gen, text=f"{self.var_temp.get():.2f}")
        self.lbl_temp_val.grid(row=0, column=2, sticky="w", padx=4)

        # Top-P ---------------------------------------------------------------
        lbl_topp = tb.Label(gen, text="Top-P")
        lbl_topp.grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_topp, text="Nucleus sampling. Lower values consider fewer, more likely tokens.")
        tb.Scale(
            gen,
            from_=0.0,
            to=1.0,
            orient="horizontal",
            variable=self.var_top_p,
            command=self._schedule_persist_prefs,
        ).grid(row=1, column=1, sticky="ew", padx=4)
        self.lbl_topp_val = tb.Label(gen, text=f"{self.var_top_p.get():.2f}")
        self.lbl_topp_val.grid(row=1, column=2, sticky="w", padx=4)

        # Top-K ---------------------------------------------------------------
        lbl_topk = tb.Label(gen, text="Top-K")
        lbl_topk.grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_topk, text="Restricts sampling to the top K most probable tokens.")
        self.var_top_k = tk.IntVar(
            value=int(self.prefs.get("top_k", self.cfg.get("generation", {}).get("top_k", 40)))
        )
        self.spin_top_k = tb.Spinbox(
            gen,
            from_=1,
            to=200,
            textvariable=self.var_top_k,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_top_k.grid(row=2, column=1, sticky="w", padx=4)
        self.spin_top_k.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_top_k.bind("<Return>", self._schedule_persist_prefs)

        # Max New Tokens ------------------------------------------------------
        lbl_max = tb.Label(gen, text="Max New Tokens")
        lbl_max.grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_max, text="Limits the maximum number of tokens the model can generate.")
        self.spin_max_tokens = tb.Spinbox(
            gen,
            from_=16,
            to=8192,
            textvariable=self.var_maxnew,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_max_tokens.grid(row=3, column=1, sticky="w", padx=4)
        self.spin_max_tokens.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_max_tokens.bind("<Return>", self._schedule_persist_prefs)

        # Repetition Penalty --------------------------------------------------
        lbl_rep = tb.Label(gen, text="Repetition Penalty")
        lbl_rep.grid(row=4, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_rep,
            text="Discourages repeating identical phrases. 1.0 = neutral, >1.0 = stronger penalty.",
        )
        self.var_rep_pen = tk.DoubleVar(
            value=float(
                self.prefs.get(
                    "repetition_penalty",
                    self.cfg.get("generation", {}).get("repetition_penalty", 1.0),
                )
            )
        )
        tb.Scale(
            gen,
            from_=0.5,
            to=2.0,
            orient="horizontal",
            variable=self.var_rep_pen,
            command=self._schedule_persist_prefs,
        ).grid(row=4, column=1, sticky="ew", padx=4)
        self.lbl_rep_val = tb.Label(gen, text=f"{self.var_rep_pen.get():.2f}")
        self.lbl_rep_val.grid(row=4, column=2, sticky="w", padx=4)

        # Frequency Penalty ---------------------------------------------------
        lbl_freq = tb.Label(gen, text="Frequency Penalty")
        lbl_freq.grid(row=5, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_freq, text="API backend only. Penalizes tokens according to how often they have already appeared.")
        tb.Scale(
            gen,
            from_=0.0,
            to=2.0,
            orient="horizontal",
            variable=self.var_freq_pen,
            command=self._schedule_persist_prefs,
        ).grid(row=5, column=1, sticky="ew", padx=4)
        self.lbl_freq_val = tb.Label(gen, text=f"{self.var_freq_pen.get():.2f}")
        self.lbl_freq_val.grid(row=5, column=2, sticky="w", padx=4)

        # Presence Penalty ----------------------------------------------------
        lbl_pres = tb.Label(gen, text="Presence Penalty")
        lbl_pres.grid(row=6, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_pres, text="API backend only. Penalizes tokens that have already appeared, regardless of their frequency.")
        tb.Scale(
            gen,
            from_=0.0,
            to=2.0,
            orient="horizontal",
            variable=self.var_pres_pen,
            command=self._schedule_persist_prefs,
        ).grid(row=6, column=1, sticky="ew", padx=4)
        self.lbl_pres_val = tb.Label(gen, text=f"{self.var_pres_pen.get():.2f}")
        self.lbl_pres_val.grid(row=6, column=2, sticky="w", padx=4)

        # Num Beams -----------------------------------------------------------
        lbl_beams = tb.Label(gen, text="Num Beams")
        lbl_beams.grid(row=7, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_beams, text="Beam search width for Hugging Face models. One beam is required for sampled voting; temperature determines whether generation samples tokens or uses greedy decoding.")
        self.var_num_beams = tk.IntVar(
            value=int(self.prefs.get("num_beams", self.cfg.get("generation", {}).get("num_beams", 1)))
        )
        self.spin_num_beams = tb.Spinbox(
            gen,
            from_=1,
            to=10,
            textvariable=self.var_num_beams,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_num_beams.grid(row=7, column=1, sticky="w", padx=4)
        self.spin_num_beams.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_num_beams.bind("<Return>", self._schedule_persist_prefs)

        # Seed ----------------------------------------------------------------
        lbl_seed = tb.Label(gen, text="Seed")
        lbl_seed.grid(row=8, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_seed, text="Base seed for the standard workflow. Sampled voting uses a distinct seed per draw. Matching seeds support repeatability but do not guarantee identical results across hardware or runtime versions. Study modes use the run-seed list above.")
        self.var_seed = tk.IntVar(
            value=int(self.prefs.get("seed", self.cfg.get("generation", {}).get("seed", 42)))
        )
        self.spin_seed = tb.Spinbox(
            gen,
            from_=0,
            to=9999,
            textvariable=self.var_seed,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_seed.grid(row=8, column=1, sticky="w", padx=4)
        self.spin_seed.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_seed.bind("<Return>", self._schedule_persist_prefs)

        # Stop Sequences ------------------------------------------------------
        lbl_stop = tb.Label(gen, text="Stop Sequences")
        lbl_stop.grid(row=9, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_stop, text="Comma-separated strings where generation should stop.")
        self.entry_stop = tb.Entry(gen, textvariable=self.var_stop)
        self.entry_stop.grid(row=9, column=1, sticky="ew", padx=4)
        self.entry_stop.bind("<FocusOut>", self._schedule_persist_prefs)
        self.entry_stop.bind("<Return>", self._schedule_persist_prefs)

        # Self-Consistency Samples -------------------------------------------
        lbl_sc = tb.Label(gen, text="SC Samples")
        lbl_sc.grid(row=10, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_sc,
            text="Requested draws for self-consistency and study voting pools. Each draw uses a distinct seed; responses can still agree or repeat. Repeated sampling requires temperature above zero and one beam.",
        )
        self.spin_sc_samples = tb.Spinbox(
            gen,
            from_=1,
            to=20,
            textvariable=self.var_sc_samples,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_sc_samples.grid(row=10, column=1, sticky="w", padx=4)
        self.spin_sc_samples.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_sc_samples.bind("<Return>", self._schedule_persist_prefs)

        lbl_context = tb.Label(gen, text="Context window (tokens)")
        lbl_context.grid(row=11, column=0, sticky="w", padx=4, pady=4)
        self.entry_context_window = tb.Entry(gen, textvariable=self.var_context_window)
        self.entry_context_window.grid(row=11, column=1, sticky="ew", padx=4)
        self.entry_context_window.bind("<FocusOut>", self._schedule_persist_prefs)
        self.entry_context_window.bind("<Return>", self._schedule_persist_prefs)
        context_help = (
            "Optional positive token window, with room for both input and output. Blank leaves model-specific "
            "settings or the server default in place. Ollama cross-run reuse requires an explicit effective window "
            "and a cache profile. Setting this does not shorten the code. "
            "Choose a window that fits representative and long inputs during a pilot, then keep it fixed across "
            "matched conditions. Larger windows and more parallel workers require additional GPU memory. "
            "Check the loaded window with ollama ps; blank does not mean a fixed 4K window."
        )
        ToolTip(lbl_context, text=context_help)
        ToolTip(self.entry_context_window, text=context_help)

        # Allow column 1 (the controls) to stretch
        gen.grid_columnconfigure(1, weight=1)

        # --- Run Performance -------------------------------------------------
        perf = tb.Labelframe(left_inner, text="Run Performance", padding=8, bootstyle="success")
        perf.pack(fill="x", pady=(8, 0))

        self.chk_debug = tb.Checkbutton(
            perf,
            text="Verbose debug logging",
            variable=self.var_debug_raw_outputs,
            command=self._on_toggle_debug_controls,
        )
        self.chk_debug.grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ToolTip(
            self.chk_debug,
            text="Log raw prompts and model outputs. Useful for debugging, but slower and much noisier.",
        )

        self.chk_save_debug_log = tb.Checkbutton(
            perf,
            text="Save debug log to file",
            variable=self.var_save_debug_log,
            command=self._persist_prefs,
        )
        self.chk_save_debug_log.grid(row=1, column=0, columnspan=2, sticky="w", padx=24, pady=2)
        ToolTip(
            self.chk_save_debug_log,
            text="When verbose debug logging is enabled, also save the run monitor log to debug.log in the run folder.",
        )

        lbl_ckpt_samples = tb.Label(perf, text="Checkpoint every N samples")
        lbl_ckpt_samples.grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_ckpt_samples,
            text="How often to persist in-progress combo state. Higher values reduce disk I/O. 0 disables sample-count checkpointing.",
        )
        self.spin_ckpt_samples = tb.Spinbox(
            perf,
            from_=0,
            to=5000,
            textvariable=self.var_checkpoint_every_n_samples,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_ckpt_samples.grid(row=2, column=1, sticky="w", padx=4)
        self.spin_ckpt_samples.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_ckpt_samples.bind("<Return>", self._schedule_persist_prefs)

        lbl_ckpt_secs = tb.Label(perf, text="Checkpoint every N seconds")
        lbl_ckpt_secs.grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_ckpt_secs,
            text="Time-based checkpoint cadence. Useful protection for long samples. 0 disables time-based checkpointing.",
        )
        self.spin_ckpt_secs = tb.Spinbox(
            perf,
            from_=0,
            to=3600,
            increment=1,
            textvariable=self.var_checkpoint_every_seconds,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_ckpt_secs.grid(row=3, column=1, sticky="w", padx=4)
        self.spin_ckpt_secs.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_ckpt_secs.bind("<Return>", self._schedule_persist_prefs)

        lbl_progress_every = tb.Label(perf, text="Progress update every N samples")
        lbl_progress_every.grid(row=4, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_progress_every,
            text="Throttle GUI/log progress updates on large runs. Higher values reduce UI chatter.",
        )
        self.spin_progress_every = tb.Spinbox(
            perf,
            from_=1,
            to=5000,
            textvariable=self.var_progress_every_n_samples,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_progress_every.grid(row=4, column=1, sticky="w", padx=4)
        self.spin_progress_every.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_progress_every.bind("<Return>", self._schedule_persist_prefs)

        lbl_sc_delay = tb.Label(perf, text="SC vote delay (seconds)")
        lbl_sc_delay.grid(row=5, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_sc_delay,
            text="Optional delay between self-consistency votes. Keep at 0 for local speed unless a backend needs pacing.",
        )
        self.spin_sc_delay = tb.Spinbox(
            perf,
            from_=0,
            to=60,
            increment=0.05,
            textvariable=self.var_sc_vote_delay_seconds,
            width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_sc_delay.grid(row=5, column=1, sticky="w", padx=4)
        self.spin_sc_delay.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_sc_delay.bind("<Return>", self._schedule_persist_prefs)

        self.chk_prevent_sleep = tb.Checkbutton(
            perf,
            text="Prevent system sleep during runs",
            variable=self.var_prevent_system_sleep,
            command=self._on_toggle_sleep_controls,
        )
        self.chk_prevent_sleep.grid(row=6, column=0, columnspan=2, sticky="w", padx=4, pady=(6, 2))
        ToolTip(
            self.chk_prevent_sleep,
            text="Keep the machine awake while a run is active. Released on pause, stop, and completion.",
        )

        self.chk_keep_display = tb.Checkbutton(
            perf,
            text="Keep display awake too",
            variable=self.var_keep_display_awake,
            command=self._persist_prefs,
        )
        self.chk_keep_display.grid(row=7, column=0, columnspan=2, sticky="w", padx=24, pady=2)
        ToolTip(
            self.chk_keep_display,
            text="Also prevent the monitor from sleeping while the run is active.",
        )
        lbl_workers = tb.Label(perf, text="Inference workers")
        lbl_workers.grid(row=8, column=0, sticky="w", padx=4, pady=4)
        self.spin_inference_workers = tb.Spinbox(
            perf, from_=1, to=8, textvariable=self.var_inference_workers, width=10,
            command=self._schedule_persist_prefs,
        )
        self.spin_inference_workers.grid(row=8, column=1, sticky="w", padx=4)
        self.spin_inference_workers.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_inference_workers.bind("<Return>", self._schedule_persist_prefs)
        worker_help = (
            "Maximum concurrent inference requests. One worker is the default on every computer. Parallel requests are supported "
            "for Ollama; its server must allow at least this many requests with OLLAMA_NUM_PARALLEL. "
            "Benchmark two workers, then four if GPU memory allows. More workers can be slower or exceed VRAM. "
            "HF and API backends currently require one worker. Seeds and vote counts stay unchanged."
        )
        ToolTip(lbl_workers, text=worker_help)
        ToolTip(self.spin_inference_workers, text=worker_help)
        self.chk_response_cache = tb.Checkbutton(
            perf, text="Reuse responses across runs", variable=self.var_response_cache,
            command=self._schedule_persist_prefs,
        )
        self.chk_response_cache.grid(row=9, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ToolTip(self.chk_response_cache, text=(
            "Reuse successful responses only when the cache identity matches the request, model, runtime, "
            "and generation settings, including the seed. Ollama cross-run reuse also requires an explicit "
            "context window and a cache profile. Within-run parser and vote replay remains enabled regardless of this toggle. "
            "Identical requests can also be reused across experiment types in the same batch. "
            "The local cache defaults to results/cache and may contain "
            "model responses; do not share it automatically between computers. Failed requests are not reused from this cache. "
            "Reports distinguish cache reuse from new generation."
        ))
        self.chk_defer_analysis = tb.Checkbutton(
            perf, text="Defer analysis", variable=self.var_defer_analysis,
            command=self._schedule_persist_prefs,
        )
        self.chk_defer_analysis.grid(row=10, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ToolTip(self.chk_defer_analysis, text=(
            "Save generations and predictions first, then run the statistical and research analyses later without new inference. "
            "Use Resume Saved Run or the analyze command afterward. The basic Standard report is still written after generation. "
            "Bootstrap intervals and repeated prevalence subsets can take substantial CPU time."
        ))
        lbl_cache_profile = tb.Label(perf, text="Cache profile")
        lbl_cache_profile.grid(row=11, column=0, sticky="w", padx=4, pady=4)
        self.entry_cache_profile = tb.Entry(perf, textvariable=self.var_cache_profile)
        self.entry_cache_profile.grid(row=11, column=1, sticky="ew", padx=4)
        self.entry_cache_profile.bind("<FocusOut>", self._schedule_persist_prefs)
        self.entry_cache_profile.bind("<Return>", self._schedule_persist_prefs)
        profile_help = (
            "Optional generic tag for the server setup, such as local-v1. Ollama cross-run caching needs this "
            "tag and an explicit context window. Change the tag after changing server defaults, GPU drivers, "
            "hardware, or other unrecorded server settings so old responses are not reused. Leave it blank "
            "to disable Ollama cross-run caching. Do not put names, passwords, or other personal details here."
        )
        ToolTip(lbl_cache_profile, text=profile_help)
        ToolTip(self.entry_cache_profile, text=profile_help)
        perf.grid_columnconfigure(1, weight=1)

        # RIGHT: Run Monitor ---------------------------------------------------
        middle_col = tb.Labelframe(root, text="Run Monitor", padding=8, bootstyle="info")
        root.add(middle_col, weight=1)

        # Progress bar + runtime display
        top_bar = tb.Frame(middle_col)
        top_bar.pack(fill="x")
        self.progress = tb.Progressbar(
            top_bar,
            mode="determinate",
            length=540,
            maximum=100,
            bootstyle="success-striped",
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_label = tb.Label(top_bar, text="Ready")
        self.progress_label.pack(side="left")
        self.runtime_label = tb.Label(top_bar, text="Runtime: 00:00")
        self.runtime_label.pack(side="right")
        ToolTip(self.progress, text="Estimated completion across all selected experiments. The plan includes requested draws, cached responses, and processing work. It is not an estimate of elapsed time.")

        self.work_label = tb.Label(middle_col, text="Estimated completion: 0%", wraplength=680,
                                   justify="left", bootstyle="secondary")
        self.work_label.pack(fill="x", pady=(6, 0))

        # Sample counter + status line
        under_bar = tb.Frame(middle_col)
        under_bar.pack(fill="x", pady=(6, 2))
        self.sample_counter = tb.Label(under_bar, text="Samples: 0 / 0")
        self.sample_counter.pack(side="left")
        self.status_label = tb.Label(under_bar, text="Ready")
        self.status_label.pack(side="right")

        # Log window (scrollable text area)
        self.log_text = tk.Text(
            middle_col,
            height=22,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
            bg="#f7fbff",
            relief="flat",
            padx=8,
            pady=8,
        )
        self.log_text.pack(fill="both", expand=True)

        # Button to open the latest HTML report in the browser
        self.open_report_btn = tb.Button(
            middle_col, text="Open Report", command=self._open_report, state="disabled", bootstyle="info-outline"
        )
        self.open_report_btn.pack(pady=(8, 0), anchor="e")

    def _build_study_controls(self, parent):
        self.study_box = tb.Labelframe(parent, text="Experiment options", padding=8, bootstyle="info")
        self.study_box.pack(fill="x", pady=(8, 0))
        self.wording_options = tb.Frame(self.study_box)
        wordings = template_manifest()["task_wordings"]
        tb.Label(self.wording_options, text="Task wordings").pack(anchor="w")
        for name, var in self.sel_wordings.items():
            button = tb.Checkbutton(self.wording_options, text=name.replace("_", " ").title(), variable=var,
                                    command=self._schedule_persist_prefs)
            button.pack(anchor="w")
            ToolTip(button, text=wordings[name] + " Only this task sentence changes. Include Reference for paired comparisons.")

        self.component_options = tb.Frame(self.study_box)
        tb.Label(self.component_options, text="Component comparisons").pack(anchor="w")
        component_help = {
            "examples": ("Labeled examples", "Compare the shared baseline with and without the two fixed labeled C demonstrations. The examples and their order stay fixed."),
            "reasoning": ("Step-by-step instruction", "Compare the shared baseline with and without the explicit step-by-step request. The absent condition is a control, not a CoT prompt. It can still reason internally."),
            "adaptive": ("Adaptive instruction", "Compare the shared baseline with and without the instruction to answer directly on straightforward cases and otherwise reason step by step."),
        }
        for name, var in self.sel_components.items():
            label, help_text = component_help[name]
            button = tb.Checkbutton(self.component_options, text=label, variable=var,
                                    command=self._schedule_persist_prefs)
            button.pack(anchor="w")
            ToolTip(button, text=help_text + " Each selection runs both conditions; all pairs share one baseline and add only one block.")
        tb.Label(self.component_options, text="Voting bases (leave both clear for components only)",
                 wraplength=470).pack(anchor="w", pady=(8, 2))
        for name, var in self.sel_voting_bases.items():
            button = tb.Checkbutton(self.component_options, text="CoT" if name == "cot" else "Adaptive CoT",
                                    variable=var, command=self._schedule_persist_prefs)
            button.pack(anchor="w")
            ToolTip(button, text="Generate a separate response pool for this full reference prompt. Its selected voting policies reuse that pool; CoT and Adaptive CoT pools are never mixed.")
        tb.Label(self.component_options, text="Voting policies").pack(anchor="w", pady=(8, 2))
        policy_help = {
            "first": ("First requested draw", "Use the first requested response, including UNKNOWN. It uses one decision call; majority rules use the full pool, so this comparison changes the decision budget. Selecting only this policy generates one draw."),
            "majority_requested": ("Majority of requested draws", "Require more than half of all requested draws to support one label. UNKNOWN stays in the denominator. Five draws require three matching labels."),
            "majority_valid": ("Majority of valid draws", "Require more than half of usable SAFE/VULNERABLE responses, with the selected minimum valid count. UNKNOWN is excluded from the denominator, but its model calls still cost time."),
        }
        for name, var in self.sel_voting_policies.items():
            label, help_text = policy_help[name]
            button = tb.Checkbutton(self.component_options, text=label, variable=var,
                                    command=self._schedule_persist_prefs)
            button.pack(anchor="w")
            ToolTip(button, text=help_text + " Policies use the same saved draws. Ties and insufficient support produce UNKNOWN.")
        valid_row = tb.Frame(self.component_options)
        valid_row.pack(fill="x", pady=(4, 0))
        label = tb.Label(valid_row, text="Minimum valid draws")
        label.pack(side="left")
        spin = tb.Spinbox(valid_row, from_=1, to=100, textvariable=self.var_study_min_valid, width=8,
                          command=self._schedule_persist_prefs)
        spin.pack(side="right")
        ToolTip(label, text="Minimum usable responses for the valid-vote majority. Defaults to three and must not exceed the requested draw count. This prevents decisions from only one or two usable responses in a five-draw pool.")
        spin.bind("<FocusOut>", self._schedule_persist_prefs)

        self.study_common = tb.Frame(self.study_box)
        self.study_common.pack(fill="x", pady=(8, 0))
        common_fields = (
            ("Study run seeds", self.var_study_seeds, "Run seeds for task-wording and component/voting studies, such as 42, 43. Each sample and draw receives a derived seed, matched across compared conditions. Standard prompts use the Seed field under Generation Settings."),
            ("Bootstrap resamples", self.var_study_bootstrap, "Resamples for per-configuration and paired intervals across the selected experiment types. Group snippets by CVE or repository below. Set zero to skip intervals while retaining point estimates and descriptive summaries."),
        )
        self.study_field_entries = []
        for row, (name, var, help_text) in enumerate(common_fields):
            label = tb.Label(self.study_common, text=name)
            label.grid(row=row, column=0, sticky="w", pady=3)
            entry = tb.Entry(self.study_common, textvariable=var, width=18)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
            ToolTip(label, text=help_text)
            ToolTip(entry, text=help_text)
            entry.bind("<FocusOut>", self._schedule_persist_prefs)
            self.study_field_entries.append(entry)
        self.study_common.grid_columnconfigure(1, weight=1)
        pilot = tb.Checkbutton(self.study_common, text="Pilot / smoke test", variable=self.var_study_pilot,
                               command=self._on_experiment_types_change)
        pilot.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 2))
        ToolTip(pilot, text="Mark outputs as a pilot and allow a sample limit. Task-wording and component/voting studies require pilot mode for dummy models. Pilot scores do not represent a full experiment.")
        label = tb.Label(self.study_common, text="Pilot sample limit")
        label.grid(row=3, column=0, sticky="w", pady=3)
        self.entry_study_limit = tb.Entry(self.study_common, textvariable=self.var_study_limit, width=18)
        self.entry_study_limit.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=3)
        self.entry_study_limit.bind("<FocusOut>", self._schedule_persist_prefs)
        ToolTip(label, text="Optional positive sample count per dataset for every selected experiment type. Leave blank to use all samples. Full runs use the complete selected cohort.")

        self.analysis_options = tb.Frame(self.study_box)
        self.analysis_options.pack(fill="x", pady=(8, 0))
        tb.Label(self.analysis_options, text="Saved-result analysis").pack(anchor="w")
        analysis_labels = {"paired_comparisons": "Paired comparisons",
                           "rankings": "Task-wording ranking changes",
                           "prevalence": "Class-imbalance comparisons",
                           "output_audit": "Response summaries and review cases",
                           "dataset_audit": "Dataset overlap and CWE summaries"}
        analysis_help = {**DIAGNOSTIC_HELP,
            "prevalence": "Repeated matched subsets with 20%, 10%, and 5% vulnerable samples. Reports classification results and false positives per 1,000 evaluated snippets. This reuses saved predictions; it does not model the true prevalence in deployed code.",
            "output_audit": "Summarize available response lengths, labels, correctness, and abstentions, and export a limited set of IDs for manual review. Missing response links stay unavailable. Preparing cases does not count as completing a human review.",
            "dataset_audit": "Check exact-code overlap, conflicting labels, shared CVEs and projects in the evaluated cohorts, and report CWE breakdowns where metadata exists. It does not detect all near duplicates or change source labels."}
        self.analysis_buttons = {}
        for name, var in self.sel_analysis.items():
            button = tb.Checkbutton(self.analysis_options, text=analysis_labels[name], variable=var,
                                    command=self._schedule_persist_prefs)
            button.pack(anchor="w")
            ToolTip(button, text=analysis_help[name] + " Disable this calculation to skip it for this run. Classification scores and generation diagnostics are always reported.")
            self.analysis_buttons[name] = button
        fields = tb.Frame(self.analysis_options)
        fields.pack(fill="x", pady=(6, 0))
        fields.grid_columnconfigure(1, weight=1)
        label = tb.Label(fields, text="Uncertainty grouping")
        label.grid(row=0, column=0, sticky="w", pady=3)
        self.combo_analysis_group = tb.Combobox(fields, textvariable=self.var_analysis_group,
            values=("CVE", "Repository"), state="readonly", width=16)
        self.combo_analysis_group.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.combo_analysis_group.bind("<<ComboboxSelected>>", self._schedule_persist_prefs)
        ToolTip(label, text="Resample related snippets together. Repository grouping requires recorded repository identifiers for every sample; missing identifiers produce unavailable intervals rather than a sample-level fallback.")
        for row, (title, var, help_text) in enumerate((
            ("Prevalence subset size", self.var_prevalence_size, "Requested sample count for each prevalence comparison. The analysis uses a common feasible count, rounded down to a multiple of 20 so 20%, 10%, and 5% class ratios are exact. Subsets are sampled without replacement."),
            ("Prevalence repeats", self.var_prevalence_repeats, "Number of reproducible subset draws, shared across matched configurations. Draw variability is reported separately from CVE or repository bootstrap uncertainty."),
            ("Manual review case limit", self.var_review_limit, "Maximum number of compact review cases to export. Cases identify saved responses and leave human judgment fields blank. Zero omits the case list; no raw model text is embedded in reports."),
        ), start=1):
            label = tb.Label(fields, text=title)
            label.grid(row=row, column=0, sticky="w", pady=3)
            entry = tb.Entry(fields, textvariable=var, width=16)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 0))
            entry.bind("<FocusOut>", self._schedule_persist_prefs)
            entry.bind("<Return>", self._schedule_persist_prefs)
            ToolTip(label, text=help_text)
            ToolTip(entry, text=help_text)

    def _refresh_study_controls(self):
        selected = {name for name, var in self.sel_experiment_types.items() if var.get()}
        studies = bool(selected & {"B", "C"})
        self.study_box.pack(fill="x", pady=(8, 0), before=self.generation_box)
        self.wording_options.pack_forget()
        self.component_options.pack_forget()
        if "B" in selected:
            self.wording_options.pack(fill="x", before=self.study_common)
        if "C" in selected:
            self.component_options.pack(fill="x", before=self.study_common)
        for name, button in self.prompt_buttons.items():
            enabled = "standard" in selected or ("B" in selected and name in FAMILIES)
            button.configure(state="normal" if enabled else "disabled")
        self.prompts_box.configure(text="Prompt Strategies")
        if selected & {"standard", "B"}:
            self.prompts_box.pack(fill="x", before=self.ablation_box)
        else:
            self.prompts_box.pack_forget()
        for index, entry in enumerate(self.study_field_entries):
            entry.configure(state="normal" if selected and (studies or index > 0) else "disabled")
        for name, button in self.analysis_buttons.items():
            enabled = bool(selected) and (name != "rankings" or "B" in selected)
            button.configure(state="normal" if enabled else "disabled")
        self.entry_study_limit.configure(state="normal" if self.var_study_pilot.get() else "disabled")

    def _on_experiment_types_change(self):
        self._refresh_study_controls()
        self._refresh_performance_controls()
        self._refresh_resume_checkpoint_ui()
        self._schedule_persist_prefs()

    # -----------------------------------------------------------------
    # Persistence / Presets
    # -----------------------------------------------------------------
    def _list_presets(self):
        """
        Return a list of available preset filenames, with a sentinel first option.
        """
        try:
            return ["(select preset)"] + [p for p in os.listdir(PRESETS_DIR) if p.endswith(".yaml")]
        except Exception:
            return ["(select preset)"]

    def _persist_prefs(self):
        """Save the current controls and refresh their numeric labels."""
        # Cancel any pending debounced write because we're flushing now.
        if self._persist_after_id is not None:
            self.after_cancel(self._persist_after_id)
            self._persist_after_id = None

        prefs = self._build_prefs_snapshot()
        self._write_prefs_snapshot(prefs)
        return prefs

    def _schedule_persist_prefs(self, *_args):
        """Debounce preference writes from high-frequency GUI interactions."""
        if self._persist_after_id is not None:
            self.after_cancel(self._persist_after_id)
        self._persist_after_id = self.after(250, self._persist_if_valid)

    def _persist_if_valid(self):
        try:
            self._persist_prefs()
        except (ValueError, tk.TclError):
            # An entry can be temporarily incomplete while it is being edited.
            self._persist_after_id = None

    def _build_prefs_snapshot(self):
        """Build the current preference snapshot from live widget state."""
        self.lbl_temp_val.configure(text=f"{self.var_temp.get():.2f}")
        self.lbl_topp_val.configure(text=f"{self.var_top_p.get():.2f}")
        self.lbl_freq_val.configure(text=f"{self.var_freq_pen.get():.2f}")
        self.lbl_pres_val.configure(text=f"{self.var_pres_pen.get():.2f}")
        if hasattr(self, "lbl_rep_val"):
            self.lbl_rep_val.configure(text=f"{self.var_rep_pen.get():.2f}")
        self._refresh_performance_controls()

        try:
            self.var_exp_notes.set(self.txt_notes.get("1.0", "end").strip())
        except Exception:
            pass

        return {
            "experiment_name": self.var_exp_name.get().strip(),
            "experiment_notes": self.var_exp_notes.get().strip(),
            "models": [k for k, v in self.sel_models.items() if v.get()],
            "prompts": [k for k, v in self.sel_prompts.items() if v.get()],
            "datasets": [k for k, v in self.sel_datasets.items() if v.get()],
            "output_protocols": [k for k, v in self.sel_output_protocols.items() if v.get()],
            "parser_modes": [k for k, v in self.sel_parser_modes.items() if v.get()],
            "experiment_types": [name for name, var in self.sel_experiment_types.items() if var.get()],
            "study_wordings": [k for k, v in self.sel_wordings.items() if v.get()],
            "study_components": [k for k, v in self.sel_components.items() if v.get()],
            "study_voting_bases": [k for k, v in self.sel_voting_bases.items() if v.get()],
            "study_voting_policies": [k for k, v in self.sel_voting_policies.items() if v.get()],
            "study_seeds": self.var_study_seeds.get().strip(),
            "study_min_valid_votes": int(self.var_study_min_valid.get()),
            "study_bootstrap": int(self.var_study_bootstrap.get()),
            "study_pilot": bool(self.var_study_pilot.get()),
            "study_limit": self.var_study_limit.get().strip(),
            "study_analysis": {**{k: bool(v.get()) for k, v in self.sel_analysis.items()},
                "group_by": {"CVE": "cve_id", "Repository": "repository"}[self.var_analysis_group.get()],
                "prevalence_size": int(self.var_prevalence_size.get()),
                "prevalence_repeats": int(self.var_prevalence_repeats.get()),
                "review_case_limit": int(self.var_review_limit.get())},
            "temperature": float(self.var_temp.get()),
            "top_p": float(self.var_top_p.get()),
            "top_k": int(self.var_top_k.get()) if hasattr(self, "var_top_k") else 40,
            "max_new_tokens": int(self.var_maxnew.get()),
            "repetition_penalty": float(self.var_rep_pen.get()) if hasattr(self, "var_rep_pen") else 1.0,
            "frequency_penalty": float(self.var_freq_pen.get()),
            "presence_penalty": float(self.var_pres_pen.get()),
            "num_beams": int(self.var_num_beams.get()) if hasattr(self, "var_num_beams") else 1,
            "sc_samples": int(self.var_sc_samples.get()),
            "seed": int(self.var_seed.get()) if hasattr(self, "var_seed") else 42,
            "debug_raw_outputs": bool(self.var_debug_raw_outputs.get()),
            "save_debug_log": bool(self.var_save_debug_log.get()),
            "checkpoint_every_n_samples": int(self.var_checkpoint_every_n_samples.get()),
            "checkpoint_every_seconds": float(self.var_checkpoint_every_seconds.get()),
            "progress_every_n_samples": int(self.var_progress_every_n_samples.get()),
            "sc_vote_delay_seconds": float(self.var_sc_vote_delay_seconds.get()),
            "prevent_system_sleep": bool(self.var_prevent_system_sleep.get()),
            "keep_display_awake": bool(self.var_keep_display_awake.get()),
            "ollama_keep_alive": self.cfg.get("performance", {}).get("ollama_keep_alive", "30m"),
            "inference_workers": int(self.var_inference_workers.get()),
            "response_cache": bool(self.var_response_cache.get()),
            "defer_analysis": bool(self.var_defer_analysis.get()),
            "cache_profile": self.var_cache_profile.get().strip(),
            "context_window": self.var_context_window.get().strip(),
            "stop_sequences": [s.strip() for s in self.var_stop.get().split(",") if s.strip()],
        }

    def _write_prefs_snapshot(self, prefs):
        """Write prefs only when they changed to avoid unnecessary disk churn."""
        prefs = safe_settings(prefs)
        if prefs == self._last_prefs_snapshot:
            return
        try:
            save_yaml(PREFS_PATH, prefs)
            self._last_prefs_snapshot = copy.deepcopy(prefs)
        except Exception as e:
            print(f"[WARN] Failed to save user preferences: {e}")

    def _on_save_preset(self):
        """
        Save the current prefs snapshot as a named preset under ui/presets/.
        """
        name = self.var_preset_name.get().strip()
        if not name:
            self._log("Enter a preset name first.")
            return
        try:
            path = preset_path(name)
            data = self._persist_prefs()
            save_yaml(path, data)
        except (OSError, ValueError, tk.TclError) as exc:
            self._log(str(exc))
            return
        self.combo_presets.configure(values=self._list_presets())
        self.var_preset_select.set(f"{name}.yaml")
        self._log(f"Preset saved: {path}")

    def _on_load_preset(self):
        """
        Load settings from a selected preset file and update GUI state.
        """
        fname = self.var_preset_select.get().strip()
        if not fname or fname == "(select preset)":
            self._log("Select a preset to load.")
            return
        try:
            if not fname.endswith(".yaml"):
                raise ValueError("Choose a YAML preset from the list.")
            path = preset_path(fname[:-5])
            data = load_yaml(path)
            selected_models = set(data.get("models", []))

            # --- Restore experiment metadata
            self.var_exp_name.set(data.get("experiment_name", self.var_exp_name.get()))
            self.var_exp_notes.set(data.get("experiment_notes", ""))
            self.txt_notes.delete("1.0", "end")
            self.txt_notes.insert("1.0", self.var_exp_notes.get())

            # --- Restore model / prompt / dataset selections
            for key, cfg in self.model_cfg_by_key.items():
                is_selected = key in selected_models or cfg.get("name") in selected_models
                self.sel_models[key].set(1 if is_selected else 0)
            for p in self.sel_prompts:
                self.sel_prompts[p].set(1 if p in data.get("prompts", []) else 0)
            for d in self.sel_datasets:
                self.sel_datasets[d].set(1 if d in data.get("datasets", []) else 0)
            for name in self.sel_output_protocols:
                self.sel_output_protocols[name].set(1 if name in data.get("output_protocols", []) else 0)
            for name in self.sel_parser_modes:
                self.sel_parser_modes[name].set(1 if name in data.get("parser_modes", []) else 0)
            selected_types = selected_experiment_types(data)
            for name, var in self.sel_experiment_types.items():
                var.set(name in selected_types)
            for key, options in (("study_wordings", self.sel_wordings), ("study_components", self.sel_components),
                                 ("study_voting_bases", self.sel_voting_bases), ("study_voting_policies", self.sel_voting_policies)):
                selected = data.get(key, [name for name, var in options.items() if var.get()])
                for name, var in options.items():
                    var.set(name in selected)
            self.var_study_seeds.set(str(data.get("study_seeds", self.var_study_seeds.get())))
            self.var_study_min_valid.set(int(data.get("study_min_valid_votes", self.var_study_min_valid.get())))
            self.var_study_bootstrap.set(int(data.get("study_bootstrap", self.var_study_bootstrap.get())))
            self.var_study_pilot.set(bool(data.get("study_pilot", False)))
            self.var_study_limit.set(str(data.get("study_limit", "")))
            for name, var in self.sel_analysis.items():
                var.set(bool(data.get("study_analysis", {}).get(name, var.get())))
            loaded_analysis = resolve_analysis_settings({**self.cfg.get("analysis", {}), **data.get("study_analysis", {})})
            self.var_analysis_group.set({"cve_id": "CVE", "repository": "Repository"}[loaded_analysis["group_by"]])
            self.var_prevalence_size.set(loaded_analysis["prevalence_size"])
            self.var_prevalence_repeats.set(loaded_analysis["prevalence_repeats"])
            self.var_review_limit.set(loaded_analysis["review_case_limit"])

            # --- Restore generation parameters
            self.var_temp.set(float(data.get("temperature", self.var_temp.get())))
            self.var_top_p.set(float(data.get("top_p", self.var_top_p.get())))
            if hasattr(self, "var_top_k"):
                self.var_top_k.set(int(data.get("top_k", self.var_top_k.get())))
            self.var_maxnew.set(int(data.get("max_new_tokens", self.var_maxnew.get())))
            if hasattr(self, "var_rep_pen"):
                self.var_rep_pen.set(float(data.get("repetition_penalty", self.var_rep_pen.get())))
            self.var_freq_pen.set(float(data.get("frequency_penalty", self.var_freq_pen.get())))
            self.var_pres_pen.set(float(data.get("presence_penalty", self.var_pres_pen.get())))
            if hasattr(self, "var_num_beams"):
                self.var_num_beams.set(int(data.get("num_beams", self.var_num_beams.get())))
            if hasattr(self, "var_seed"):
                self.var_seed.set(int(data.get("seed", self.var_seed.get())))
            if hasattr(self, "var_debug_raw_outputs"):
                self.var_debug_raw_outputs.set(1 if data.get("debug_raw_outputs", bool(self.var_debug_raw_outputs.get())) else 0)
            if hasattr(self, "var_save_debug_log"):
                self.var_save_debug_log.set(1 if data.get("save_debug_log", bool(self.var_save_debug_log.get())) else 0)
            if hasattr(self, "var_checkpoint_every_n_samples"):
                self.var_checkpoint_every_n_samples.set(
                    int(data.get("checkpoint_every_n_samples", self.var_checkpoint_every_n_samples.get()))
                )
            if hasattr(self, "var_checkpoint_every_seconds"):
                self.var_checkpoint_every_seconds.set(
                    float(data.get("checkpoint_every_seconds", self.var_checkpoint_every_seconds.get()))
                )
            if hasattr(self, "var_progress_every_n_samples"):
                self.var_progress_every_n_samples.set(
                    int(data.get("progress_every_n_samples", self.var_progress_every_n_samples.get()))
                )
            if hasattr(self, "var_sc_vote_delay_seconds"):
                self.var_sc_vote_delay_seconds.set(
                    float(data.get("sc_vote_delay_seconds", self.var_sc_vote_delay_seconds.get()))
                )
            if hasattr(self, "var_prevent_system_sleep"):
                self.var_prevent_system_sleep.set(
                    1 if data.get("prevent_system_sleep", bool(self.var_prevent_system_sleep.get())) else 0
                )
            if hasattr(self, "var_keep_display_awake"):
                self.var_keep_display_awake.set(
                    1 if data.get("keep_display_awake", bool(self.var_keep_display_awake.get())) else 0
                )
            stops = data.get("stop_sequences", self.var_stop.get())
            self.var_stop.set(
                ", ".join(stops) if isinstance(stops, (list, tuple)) else str(stops or "")
            )

            self.var_sc_samples.set(int(data.get("sc_samples", self.var_sc_samples.get())))
            self.var_inference_workers.set(int(data.get("inference_workers", self.var_inference_workers.get())))
            self.var_response_cache.set(bool(data.get("response_cache", self.var_response_cache.get())))
            self.var_defer_analysis.set(bool(data.get("defer_analysis", self.var_defer_analysis.get())))
            self.var_cache_profile.set(str(data.get("cache_profile", self.var_cache_profile.get())))
            context = data.get("context_window", self.var_context_window.get())
            self.var_context_window.set("" if context is None else str(context))
            self._refresh_performance_controls()
            self._refresh_study_controls()
            self._refresh_resume_checkpoint_ui()

            # Persist what we've restored so everything stays in sync on disk
            self._persist_prefs()
            self._log(f"Preset loaded: {path}")
        except Exception as e:
            self._log(f"Failed to load preset: {e}")

    def _refresh_performance_controls(self):
        """Enable or disable dependent performance controls based on related toggles."""
        if hasattr(self, "chk_save_debug_log"):
            debug_state = "normal" if self.var_debug_raw_outputs.get() else "disabled"
            self.chk_save_debug_log.configure(state=debug_state)
        if hasattr(self, "chk_keep_display"):
            state = "normal" if self.var_prevent_system_sleep.get() else "disabled"
            self.chk_keep_display.configure(state=state)
        if hasattr(self, "chk_defer_analysis"):
            selected = any(var.get() for var in self.sel_experiment_types.values())
            self.chk_defer_analysis.configure(state="normal" if selected else "disabled")

    def _on_toggle_debug_controls(self):
        """Refresh dependent debug controls and persist the current choice."""
        self._refresh_performance_controls()
        self._persist_prefs()

    def _on_toggle_sleep_controls(self):
        """Refresh dependent sleep controls and persist the current choice."""
        self._refresh_performance_controls()
        self._persist_prefs()

    def _on_close(self):
        """Flush pending preference changes before closing the dashboard."""
        try:
            self._persist_prefs()
        finally:
            self.destroy()

    # -----------------------------------------------------------------
    # Run + Stop logic
    # -----------------------------------------------------------------
    def _refresh_resume_checkpoint_ui(self):
        """Refresh the saved-checkpoint resume button and label."""
        self.latest_checkpoint_path = self._find_saved_run()
        if not hasattr(self, "resume_saved_btn"):
            return

        active_session = hasattr(self, "run_btn") and str(self.run_btn.cget("state")) == "disabled"
        if self.latest_checkpoint_path:
            label = os.path.basename(os.path.dirname(self.latest_checkpoint_path))
            self.resume_saved_btn.configure(state="disabled" if active_session else "normal")
            self.resume_saved_label.configure(text=label, bootstyle="secondary")
        else:
            self.resume_saved_btn.configure(state="disabled")
            self.resume_saved_label.configure(
                text="No resumable checkpoint found",
                bootstyle="secondary",
            )

    def _find_saved_run(self):
        selected = {name for name, var in self.sel_experiment_types.items() if var.get()}
        candidates = [BatchRunner.find_latest_resumable_checkpoint(self.cfg)]
        if "standard" in selected:
            candidates.append(ExperimentRunner.find_latest_resumable_checkpoint(self.cfg))
        if selected & {"B", "C"}:
            candidates.append(StudyRunner.find_latest_resumable_checkpoint(self.cfg))
        paths = [path for path in candidates if path and Path(path).exists()]
        return max(paths, key=lambda path: Path(path).stat().st_mtime) if paths else None

    def _queue_progress(self, msg, done=None, total=None):
        if done is None or total is None:
            sample = re.search(r"sample\s+(\d+)\s*/\s*(\d+)", msg, flags=re.IGNORECASE)
            if sample:
                done, total = map(int, sample.groups())
        if done is not None and total is not None:
            self.msg_queue.put(("sample_progress", msg, done, total))
        else:
            self.msg_queue.put(("log_only", msg))

    def _on_run(self):
        """Validate the selection and start a batch from a plain settings snapshot."""
        models = [dict(self.model_cfg_by_key[key]) for key, var in self.sel_models.items() if var.get()]
        prompts = [key for key, var in self.sel_prompts.items() if var.get()]
        datasets = [key for key, var in self.sel_datasets.items() if var.get()]
        protocols = [key for key, var in self.sel_output_protocols.items() if var.get()]
        parsers = [key for key, var in self.sel_parser_modes.items() if var.get()]
        try:
            prefs = self._persist_prefs()
            runtime_cfg = build_runtime_config(self.cfg, prefs)
            jobs = build_gui_jobs(runtime_cfg, prefs, models, prompts, datasets, protocols, parsers)
        except (ValueError, tk.TclError) as exc:
            self._log("Check experiment settings: " + str(exc))
            return
        self.runner = None
        self._pending_pause = False
        self._pending_stop = False
        self.run_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.resume_saved_btn.configure(state="disabled")
        self.open_report_btn.configure(text="Open Report", state="disabled")
        self.progress.configure(value=0)
        self.progress_label.configure(text="0% estimated")
        self.work_label.configure(text="Planning the selected experiments...")
        self.status_label.configure(text="Planning...")
        self._start_time = time.time()
        self._update_runtime()
        names = [STUDY_MODES[job["type"]] for job in jobs]
        self._log(f"Starting {', '.join(names)} with models {[model['name'] for model in models]} and datasets {datasets}.")
        threading.Thread(target=self._worker_run,
                         args=(jobs, self._queue_progress, None, runtime_cfg), daemon=True).start()

    def _on_pause(self):
        """Request a cooperative pause and keep the checkpoint resumable."""
        self._pending_pause = True
        if self.runner:
            self.runner.request_pause()
        self.pause_btn.configure(state="disabled")
        self.resume_btn.configure(state="normal")
        self.status_label.configure(text="Pausing...")
        self._log("Pause requested. The run will pause at the next safe boundary.")

    def _on_resume_active(self):
        """Resume an in-memory paused run."""
        self._pending_pause = False
        if self.runner:
            self.runner.request_resume()
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")
        self.status_label.configure(text="Running...")
        self._log("Resume requested for the active run.")

    def _on_resume_saved(self):
        """Resume the most recent checkpointed run from disk."""
        checkpoint_path = self._find_saved_run()
        self.latest_checkpoint_path = checkpoint_path
        if not checkpoint_path:
            self._refresh_resume_checkpoint_ui()
            self._log("No resumable checkpoint was found.")
            return

        try:
            self._persist_prefs()
        except (ValueError, tk.TclError):
            pass
        self.runner = None
        self._pending_pause = False
        self._pending_stop = False
        self.run_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.resume_saved_btn.configure(state="disabled")
        self.open_report_btn.configure(text="Open Report")
        self.open_report_btn.configure(state="disabled")
        self.progress.configure(value=0)
        self.progress_label.configure(text="Resuming from checkpoint...")
        self.work_label.configure(text="Reading the saved work plan...")
        self.status_label.configure(text="Resuming...")
        self.sample_counter.configure(text="Samples: resuming")
        self._start_time = time.time()
        self._update_runtime()
        self._log(f"Resuming saved run from {checkpoint_path}")

        threading.Thread(target=self._worker_run,
                         args=([], self._queue_progress, checkpoint_path, copy.deepcopy(self.cfg)),
                         daemon=True).start()

    def _on_stop(self):
        """Stop after active work has reached a save boundary."""
        self._log("Stop requested by user...")
        self._pending_stop = True
        self.status_label.configure(text="Stopping...")
        self.stop_btn.configure(state="disabled")
        if self.runner:
            self.runner.request_stop()

    def _worker_run(self, jobs, progress_cb, resume_checkpoint, runtime_cfg):
        """Run saved settings without reading Tk objects from the worker thread."""
        try:
            filename = Path(resume_checkpoint).name if resume_checkpoint else None
            if filename == "manifest.json":
                self.runner = StudyRunner(runtime_cfg, progress=progress_cb)
            elif filename == "checkpoint.json":
                self.runner = ExperimentRunner(runtime_cfg, progress=progress_cb)
            else:
                self.runner = BatchRunner(runtime_cfg, progress=progress_cb,
                    overall_progress=lambda payload: self.msg_queue.put(("overall_progress", dict(payload))))
            if self._pending_pause:
                self.runner.request_pause()
            if self._pending_stop:
                self.runner.request_stop()
            if filename == "manifest.json":
                status = self.runner.run_study({}, resume_manifest=resume_checkpoint)
            elif filename == "checkpoint.json":
                status = self.runner.run_all([], [], [], resume_checkpoint=resume_checkpoint)
            else:
                status = self.runner.run_batch(jobs, resume_manifest=resume_checkpoint)
            self.msg_queue.put(("done", status))
        except Exception as exc:
            self.msg_queue.put(("error", safe_text(str(exc))))

    # -----------------------------------------------------------------
    # Runtime / log plumbing
    # -----------------------------------------------------------------
    def _update_runtime(self):
        """
        Periodically update the runtime label while an experiment is running.
        """
        if self._start_time:
            elapsed = int(time.time() - self._start_time)
            m, s = divmod(elapsed, 60)
            self.runtime_label.configure(text=f"Runtime: {m:02d}:{s:02d}")
            self.after(1000, self._update_runtime)

    def _poll_msgs(self):
        """
        Poll the message queue for updates from the worker thread and
        update the GUI accordingly (progress, logs, completion, errors).
        """
        try:
            while True:
                kind, *rest = self.msg_queue.get_nowait()

                if kind == "sample_progress":
                    msg, done, total = rest
                    self.sample_counter.configure(text=f"Samples: {done}/{total}")
                    self._log(msg)

                elif kind == "overall_progress":
                    payload = rest[0]
                    pct = max(0.0, min(100.0, float(payload.get("percent", 0))))
                    self.progress.configure(value=pct)
                    self.progress_label.configure(text=f"{pct:.1f}% estimated")
                    stage = payload.get("stage") or "Running"
                    detail = payload.get("detail") or ""
                    done, total = payload.get("done"), payload.get("total")
                    units = f" ({done:,.0f}/{total:,.0f} work units)" if isinstance(done, (int, float)) and isinstance(total, (int, float)) else ""
                    self.work_label.configure(text=f"{stage}{units}" + (f"\n{detail}" if detail else ""))
                    self.status_label.configure(text=stage)

                elif kind == "log_only":
                    msg = rest[0]
                    self._log(msg)
                    lowered = msg.lower()
                    if "[partial]" in lowered:
                        self.open_report_btn.configure(text="Open Partial Report")
                        self.open_report_btn.configure(
                            state="normal"
                            if self.runner and self.runner.report_html_path and os.path.exists(self.runner.report_html_path)
                            else "disabled"
                        )
                    if "run paused" in lowered:
                        self.status_label.configure(text="Paused")
                        self.pause_btn.configure(state="disabled")
                        self.resume_btn.configure(state="normal")
                        self._refresh_resume_checkpoint_ui()
                        self.open_report_btn.configure(text="Open Partial Report")
                        self.open_report_btn.configure(
                            state="normal"
                            if self.runner and self.runner.report_html_path and os.path.exists(self.runner.report_html_path)
                            else "disabled"
                        )
                    elif "resuming run" in lowered:
                        self.status_label.configure(text="Running...")
                        self.pause_btn.configure(state="normal")
                        self.resume_btn.configure(state="disabled")

                elif kind == "done":
                    status = rest[0] if rest else "completed"
                    self.stop_btn.configure(state="disabled")
                    self.pause_btn.configure(state="disabled")
                    self.resume_btn.configure(state="disabled")
                    self.run_btn.configure(state="normal")
                    self._refresh_resume_checkpoint_ui()
                    self._start_time = None
                    if status == "completed":
                        self.progress.configure(value=100)
                        self.progress_label.configure(text="100% - Completed")
                        self.work_label.configure(text="All selected experiments and reports are complete.")
                        self.status_label.configure(text="Completed Successfully")
                        self.open_report_btn.configure(text="Open Report")
                        self.open_report_btn.configure(
                            state="normal"
                            if self.runner and self.runner.report_html_path and os.path.exists(self.runner.report_html_path)
                            else "disabled"
                        )
                        self._log("Run completed successfully.")
                    elif status == "generated":
                        self.status_label.configure(text="Analysis deferred")
                        self.work_label.configure(text="Generation is complete. Saved-result analysis is pending.")
                        self.open_report_btn.configure(text="Open Run Summary", state="normal"
                            if self.runner and self.runner.report_html_path and os.path.exists(self.runner.report_html_path) else "disabled")
                        self._log("Generations and predictions saved. Resume Saved Run will run analysis without new inference.")
                    else:
                        self.progress_label.configure(text="Run stopped.")
                        self.status_label.configure(text="Stopped by user")
                        self.open_report_btn.configure(text="Open Partial Report")
                        self.open_report_btn.configure(
                            state="normal"
                            if self.runner and self.runner.report_html_path and os.path.exists(self.runner.report_html_path)
                            else "disabled"
                        )
                        self._log("Run stopped. Resume Saved Run continues from the recorded progress.")

                elif kind == "error":
                    msg = rest[0]
                    self.progress_label.configure(text=f"ERROR - {msg}")
                    self.status_label.configure(text="Error Occurred")
                    self.stop_btn.configure(state="disabled")
                    self.pause_btn.configure(state="disabled")
                    self.resume_btn.configure(state="disabled")
                    self.run_btn.configure(state="normal")
                    self._start_time = None
                    self._refresh_resume_checkpoint_ui()
                    self.open_report_btn.configure(text="Open Report")
                    self._log("ERROR: " + msg)

        except queue.Empty:
            pass

        # Continue polling again after a short delay
        self.after(150, self._poll_msgs)

    def _log(self, msg):
        """
        Append a timestamped message to the log text area.
        """
        msg = safe_text(str(msg))
        timestamp = time.strftime("[%H:%M:%S] ")
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, timestamp + msg + "\n")
        try:
            # Trim oldest lines on long runs so the Tk text widget does not
            # become its own performance bottleneck.
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            overflow = line_count - self.max_log_lines
            if overflow > 0:
                self.log_text.delete("1.0", f"{overflow + 1}.0")
        except Exception:
            pass
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_report(self):
        """
        Open the configured HTML report in the user's default web browser.
        """
        path = self.runner.report_html_path if self.runner and self.runner.report_html_path else None
        if not path:
            path = os.path.abspath(self.cfg.get("output", {}).get("report_html", "results/report.html"))
        else:
            path = os.path.abspath(path)
        if os.path.exists(path):
            webbrowser.open_new_tab(Path(path).resolve().as_uri())
        else:
            self._log(f"Report not found at {path}")


# Standalone launch -----------------------------------------------------------
if __name__ == "__main__":
    app = PromptAuditDashboard()
    try:
        # ttkbootstrap provides this helper to center the window on screen
        app.place_window_center()
    except Exception:
        # If centering fails (on some platforms), just ignore and show the window
        pass
    app.mainloop()
