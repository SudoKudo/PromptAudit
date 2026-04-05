<<<<<<< Updated upstream
# ui/dashboard.py — PromptAudit Code v2.0
# Author: Steffen Camarato — University of Central Florida
#         Adjusted by Yohan Hmaiti for reasoning models and GPU compatibility
# ---------------------------------------------------------------------
# Purpose:
#   This file implements the main GUI dashboard for Code v2.0 using ttkbootstrap.
#   The dashboard lets me:
#     - Select models, prompt strategies, and datasets
#     - Configure generation settings (temperature, top_p, stop sequences, etc.)
#     - Save/load presets of those settings
#     - Launch the ExperimentRunner and monitor progress in real time
#     - Open the generated HTML report when the run completes
#
#   The dashboard is tightly integrated with:
#     - core.runner.ExperimentRunner  → orchestrates datasets × models × prompts
#     - models backends (Ollama / HF / dummy API) → consume gen_cfg settings
#     - evaluation/report.py          → reads results and builds the HTML report

=======
"""Main ttkbootstrap dashboard for configuring and running PromptAudit experiments."""
>>>>>>> Stashed changes

import copy
import os, sys, time, yaml, queue, threading, subprocess, webbrowser, tkinter as tk, re
import ttkbootstrap as tb
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.tooltip import ToolTip
from tkinter import IntVar, DoubleVar, StringVar

# --- Project path wiring -----------------------------------------------------
# Ensure the project root is on sys.path so imports like core.runner work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.runner import ExperimentRunner

# --- Global constants / metadata ---------------------------------------------
VERSION_TAG = "Prompt Audit 2.0"  # Shown in the window title for quick version ID
<<<<<<< Updated upstream
AUTHOR = "Steffen Camarato — University of Central Florida"
=======
AUTHOR = "PromptAudit"
>>>>>>> Stashed changes

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
        yaml.safe_dump(data, f)


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
        out = subprocess.check_output(["ollama", "list"], stderr=subprocess.STDOUT, text=True)
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
class Code2Dashboard(tb.Window):
    """
    Main GUI window for PromptAudit.

    Responsibilities:
        - Render the control panel for experiment configuration.
        - Persist user preferences across sessions in user_prefs.yaml.
        - Launch the ExperimentRunner in a background thread.
        - Display real-time progress, logs, and basic runtime info.
        - Provide shortcuts to load/save presets and open the HTML report.

    The dashboard does NOT:
        - Perform model inference directly.
        - Compute metrics (delegated to ExperimentRunner and metrics.py).
    """

    def __init__(self):
        # Initialize ttkbootstrap theme + base window
        super().__init__(themename="flatly")
        self.title(f"{VERSION_TAG} | {AUTHOR}")
        self.geometry("1360x820")
        self.minsize(1280, 760)

        # --- Config and user prefs ------------------------------------------
        # Global config.yaml (datasets, prompts, generation defaults, etc.)
        self.cfg = load_yaml("config.yaml")

        # Per-user GUI preferences (models, prompts, last settings, etc.)
        self.prefs = load_yaml(PREFS_PATH)

        # Ensure presets directory exists
        os.makedirs(PRESETS_DIR, exist_ok=True)

        # --- Async / state ---------------------------------------------------
        # Thread-safe queue for messages from the worker thread
        self.msg_queue = queue.Queue()

        # When a run starts, we store the start time to update runtime display
        self._start_time = None

        # ExperimentRunner instance currently in use (or None when idle)
        self.runner = None
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

        # Resume metadata shown in the controls.
        self.latest_checkpoint_path = ExperimentRunner.find_latest_resumable_checkpoint(self.cfg)

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
            value=float(self.prefs.get("top_p", gen_cfg.get("top_p", 1.0)))
        )

        # Max new tokens spinbox (int)
        self.var_maxnew = IntVar(
            value=int(self.prefs.get("max_new_tokens", gen_cfg.get("max_new_tokens", 256)))
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
            # if it's already a string or None, keep it human-friendly
            stops_str = str(stops or "")
        self.var_stop = StringVar(value=stops_str)

        # Self-consistency samples: how many votes for SelfConsistency prompt
        self.var_sc_samples = IntVar(
            value=int(self.prefs.get("sc_samples", gen_cfg.get("sc_samples", 5)))
        )

        # --- Performance / runtime controls ---------------------------------
        self.var_debug_raw_outputs = IntVar(
            value=1 if self.prefs.get("debug_raw_outputs", self.cfg.get("debug_raw_outputs", False)) else 0
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

        # --- Preset UI state -------------------------------------------------
        self.var_preset_name = StringVar()
        self.var_preset_select = StringVar(value="(select preset)")

        # Build the entire UI layout
        self._build_ui()
        self._refresh_performance_controls()
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
            text="Configure one controlled experiment at a time: choose models, prompts, datasets, and runtime behavior, then monitor progress in the run monitor.",
            bootstyle="secondary",
            wraplength=500,
            justify="left",
        ).pack(fill="x", pady=(0, 8))

        # --- Experiment Metadata --------------------------------------------
        meta = tb.Labelframe(left_inner, text="Experiment Metadata", padding=8, bootstyle="primary")
        meta.pack(fill="x")

        lbl_name = tb.Label(meta, text="Name")
        lbl_name.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_name, text="A friendly name for this run. Stored in results and reports.")
        self.entry_exp_name = tb.Entry(meta, textvariable=self.var_exp_name)
        self.entry_exp_name.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.entry_exp_name.bind("<FocusOut>", self._schedule_persist_prefs)
        self.entry_exp_name.bind("<Return>", self._schedule_persist_prefs)

        lbl_notes = tb.Label(meta, text="Notes")
        lbl_notes.grid(row=1, column=0, sticky="nw", padx=4, pady=4)
        ToolTip(lbl_notes, text="Any context about goals, changes, or hypotheses for this run.")
        # Multi-line text box for experiment notes
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
            text="Run Experiment",
            command=self._on_run,
            width=16,
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
        prompts_box.pack(fill="x")
        lbl_prompts = tb.Label(prompts_box, text="Select Prompts")
        lbl_prompts.pack(anchor="w")
        ToolTip(
            lbl_prompts,
            text="Different prompting modes (Zero-Shot, Few-Shot, CoT, Self-Consistency, etc.).",
        )
        for name, var in self.sel_prompts.items():
            tb.Checkbutton(
                prompts_box,
                text=name,
                variable=var,
                command=self._schedule_persist_prefs,
            ).pack(anchor="w")

        # --- Ablations -------------------------------------------------------
        ablation_box = tb.Labelframe(select_right, text="Ablations", padding=8, bootstyle="warning")
        ablation_box.pack(fill="x", pady=(8, 0))

        lbl_protocol = tb.Label(ablation_box, text="Output Protocols")
        lbl_protocol.pack(anchor="w")
        ToolTip(
            lbl_protocol,
            text="Toggle verdict-first vs verdict-last output formatting for protocol ablations.",
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
            text="Toggle strict / structured / full parser variants for parser-sensitivity ablations.",
        )
        for name, var in self.sel_parser_modes.items():
            tb.Checkbutton(
                ablation_box,
                text=name,
                variable=var,
                command=self._schedule_persist_prefs,
            ).pack(anchor="w")

        # --- Generation Settings (full parity with config.yaml)
        gen = tb.Labelframe(left_inner, text="Generation Settings", padding=8, bootstyle="info")
        gen.pack(fill="x", pady=(8, 0))

        # Temperature ---------------------------------------------------------
        lbl_temp = tb.Label(gen, text="Temperature")
        lbl_temp.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ToolTip(
            lbl_temp,
            text="Controls randomness. Lower (<1) = more deterministic; higher (>1) = more random.",
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
        ToolTip(lbl_freq, text="Penalizes frequent token repetition to reduce redundancy.")
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
        ToolTip(lbl_pres, text="Penalizes reusing already-present tokens to encourage new ideas.")
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
        ToolTip(lbl_beams, text="Beam search width for Hugging Face models. 1 = greedy decoding.")
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
        ToolTip(lbl_seed, text="Random seed for reproducibility. Use the same seed for identical results.")
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
            text="Self-consistency: number of independent samples for majority voting.",
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

        # Allow column 1 (the controls) to stretch
        gen.grid_columnconfigure(1, weight=1)

        # --- Run Performance -------------------------------------------------
        perf = tb.Labelframe(left_inner, text="Run Performance", padding=8, bootstyle="success")
        perf.pack(fill="x", pady=(8, 0))

        self.chk_debug = tb.Checkbutton(
            perf,
            text="Verbose debug logging",
            variable=self.var_debug_raw_outputs,
            command=self._persist_prefs,
        )
        self.chk_debug.grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ToolTip(
            self.chk_debug,
            text="Log raw prompts and model outputs. Useful for debugging, but slower and much noisier.",
        )

        lbl_ckpt_samples = tb.Label(perf, text="Checkpoint every N samples")
        lbl_ckpt_samples.grid(row=1, column=0, sticky="w", padx=4, pady=4)
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
        self.spin_ckpt_samples.grid(row=1, column=1, sticky="w", padx=4)
        self.spin_ckpt_samples.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_ckpt_samples.bind("<Return>", self._schedule_persist_prefs)

        lbl_ckpt_secs = tb.Label(perf, text="Checkpoint every N seconds")
        lbl_ckpt_secs.grid(row=2, column=0, sticky="w", padx=4, pady=4)
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
        self.spin_ckpt_secs.grid(row=2, column=1, sticky="w", padx=4)
        self.spin_ckpt_secs.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_ckpt_secs.bind("<Return>", self._schedule_persist_prefs)

        lbl_progress_every = tb.Label(perf, text="Progress update every N samples")
        lbl_progress_every.grid(row=3, column=0, sticky="w", padx=4, pady=4)
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
        self.spin_progress_every.grid(row=3, column=1, sticky="w", padx=4)
        self.spin_progress_every.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_progress_every.bind("<Return>", self._schedule_persist_prefs)

        lbl_sc_delay = tb.Label(perf, text="SC vote delay (seconds)")
        lbl_sc_delay.grid(row=4, column=0, sticky="w", padx=4, pady=4)
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
        self.spin_sc_delay.grid(row=4, column=1, sticky="w", padx=4)
        self.spin_sc_delay.bind("<FocusOut>", self._schedule_persist_prefs)
        self.spin_sc_delay.bind("<Return>", self._schedule_persist_prefs)

        self.chk_prevent_sleep = tb.Checkbutton(
            perf,
            text="Prevent system sleep during runs",
            variable=self.var_prevent_system_sleep,
            command=self._on_toggle_sleep_controls,
        )
        self.chk_prevent_sleep.grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=(6, 2))
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
        self.chk_keep_display.grid(row=6, column=0, columnspan=2, sticky="w", padx=24, pady=2)
        ToolTip(
            self.chk_keep_display,
            text="Also prevent the monitor from sleeping while the run is active.",
        )
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
        """
        Persist user preferences and sync generation settings to user_prefs.yaml.

        This method:
            - Updates slider labels (so the numeric values stay in sync visually).
            - Pulls the latest experiment notes from the text widget.
            - Builds a prefs dict with:
                * experiment metadata
                * selected models/prompts/datasets
                * generation parameters (1:1 with config.yaml keys)
                * runtime/performance controls
                * stop sequences (normalized to a list of strings)
            - Saves that dictionary to PREFS_PATH as YAML.
        """
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
        self._persist_after_id = self.after(250, self._persist_prefs)

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
            "checkpoint_every_n_samples": int(self.var_checkpoint_every_n_samples.get()),
            "checkpoint_every_seconds": float(self.var_checkpoint_every_seconds.get()),
            "progress_every_n_samples": int(self.var_progress_every_n_samples.get()),
            "sc_vote_delay_seconds": float(self.var_sc_vote_delay_seconds.get()),
            "prevent_system_sleep": bool(self.var_prevent_system_sleep.get()),
            "keep_display_awake": bool(self.var_keep_display_awake.get()),
            "ollama_keep_alive": self.cfg.get("performance", {}).get("ollama_keep_alive", "30m"),
            "stop_sequences": [s.strip() for s in self.var_stop.get().split(",") if s.strip()],
        }

    def _write_prefs_snapshot(self, prefs):
        """Write prefs only when they changed to avoid unnecessary disk churn."""
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
        data = self._persist_prefs()
        path = os.path.join(PRESETS_DIR, f"{name}.yaml")
        save_yaml(path, data)
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
        path = os.path.join(PRESETS_DIR, fname)
        try:
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
            self._refresh_performance_controls()

            # Persist what we've restored so everything stays in sync on disk
            self._persist_prefs()
            self._log(f"Preset loaded: {path}")
        except Exception as e:
            self._log(f"Failed to load preset: {e}")

    def _refresh_performance_controls(self):
        """Enable or disable dependent performance controls based on sleep settings."""
        if hasattr(self, "chk_keep_display"):
            state = "normal" if self.var_prevent_system_sleep.get() else "disabled"
            self.chk_keep_display.configure(state=state)

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
        self.latest_checkpoint_path = ExperimentRunner.find_latest_resumable_checkpoint(self.cfg)
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

    def _on_run(self):
        """
        Handler for the "Run Experiment" button.

        Validates selections, persists prefs, disables/enables controls,
        and spawns a background worker thread to run the experiment.
        """
        # Build lists of selected models/prompts/datasets
        selected_model_keys = [k for k, v in self.sel_models.items() if v.get()]
        models = [dict(self.model_cfg_by_key[k]) for k in selected_model_keys]
        prompts = [k for k, v in self.sel_prompts.items() if v.get()]
        datasets = [k for k, v in self.sel_datasets.items() if v.get()]
        output_protocols = [k for k, v in self.sel_output_protocols.items() if v.get()]
        parser_modes = [k for k, v in self.sel_parser_modes.items() if v.get()]
        if not (models and prompts and datasets and output_protocols and parser_modes):
            self._log("Please select at least one model, prompt, dataset, output protocol, and parser mode.")
            return

        # Save the latest preferences before starting the run
        self._persist_prefs()

        # Update button states and progress UI
        self.run_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.resume_saved_btn.configure(state="disabled")
        self.open_report_btn.configure(text="Open Report")
        self.open_report_btn.configure(state="disabled")
        self.progress.configure(value=0)
        self.status_label.configure(text="Running...")

        # Start the runtime clock display
        self._start_time = time.time()
        self._update_runtime()

        self._log(
            "Starting experiment with models: "
            f"{[m.get('name', str(m)) for m in models]} and datasets: {datasets} "
            f"using protocols={output_protocols} parsers={parser_modes}"
        )

        # Callback used by ExperimentRunner to report progress/messages
        def progress_cb(msg, done=None, total=None):
            try:
                if done is not None and total is not None:
                    # Directly supplied sample counters
                    pct = int((done / max(total, 1)) * 100)
                    self.msg_queue.put(("sample_progress", pct, msg, done, total))
                else:
                    # Fallback: parse "sample X / Y" pattern from the message
                    m = re.search(r"sample\s+(\d+)\s*/\s*(\d+)", msg)
                    if m:
                        done, total = int(m.group(1)), int(m.group(2))
                        pct = int((done / max(total, 1)) * 100)
                        self.msg_queue.put(("sample_progress", pct, msg, done, total))
                    else:
                        # If no sample info is found, treat as a plain log message
                        self.msg_queue.put(("log_only", msg))
            except Exception as e:
                self.msg_queue.put(("log_only", f"[WARN] progress_cb error: {e}"))

        # Launch experiment in a background thread so the GUI stays responsive
        threading.Thread(
            target=self._worker_run,
            args=(models, prompts, datasets, output_protocols, parser_modes, progress_cb, None),
            daemon=True,
        ).start()

    def _on_pause(self):
        """Request a cooperative pause and keep the checkpoint resumable."""
        if not self.runner:
            return
        self.runner.request_pause()
        self.pause_btn.configure(state="disabled")
        self.resume_btn.configure(state="normal")
        self.status_label.configure(text="Pausing...")
        self._log("Pause requested. The current sample will finish before the run pauses.")

    def _on_resume_active(self):
        """Resume an in-memory paused run."""
        if not self.runner:
            return
        self.runner.request_resume()
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")
        self.status_label.configure(text="Running...")
        self._log("Resume requested for the active run.")

    def _on_resume_saved(self):
        """Resume the most recent checkpointed run from disk."""
        checkpoint_path = ExperimentRunner.find_latest_resumable_checkpoint(self.cfg)
        self.latest_checkpoint_path = checkpoint_path
        if not checkpoint_path:
            self._refresh_resume_checkpoint_ui()
            self._log("No resumable checkpoint was found.")
            return

        self._persist_prefs()
        self.run_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal")
        self.resume_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.resume_saved_btn.configure(state="disabled")
        self.open_report_btn.configure(text="Open Report")
        self.open_report_btn.configure(state="disabled")
        self.progress.configure(value=0)
        self.progress_label.configure(text="Resuming from checkpoint...")
        self.status_label.configure(text="Resuming...")
        self.sample_counter.configure(text="Samples: resuming")
        self._start_time = time.time()
        self._update_runtime()
        self._log(f"Resuming saved run from {checkpoint_path}")

        def progress_cb(msg, done=None, total=None):
            try:
                if done is not None and total is not None:
                    pct = int((done / max(total, 1)) * 100)
                    self.msg_queue.put(("sample_progress", pct, msg, done, total))
                else:
                    m = re.search(r"sample\s+(\d+)\s*/\s*(\d+)", msg)
                    if m:
                        done, total = int(m.group(1)), int(m.group(2))
                        pct = int((done / max(total, 1)) * 100)
                        self.msg_queue.put(("sample_progress", pct, msg, done, total))
                    else:
                        self.msg_queue.put(("log_only", msg))
            except Exception as e:
                self.msg_queue.put(("log_only", f"[WARN] progress_cb error: {e}"))

        threading.Thread(
            target=self._worker_run,
            args=([], [], [], None, None, progress_cb, checkpoint_path),
            daemon=True,
        ).start()

    def _on_stop(self):
        """
        Handler for the "Stop" button.

        Signals the ExperimentRunner to stop gracefully by setting flags.
        """
        self._log("Stop requested by user...")
        self.status_label.configure(text="Stopping...")
        self.stop_btn.configure(state="disabled")
        if self.runner:
            self.runner.request_stop()

    def _worker_run(self, models, prompts, datasets, output_protocols, parser_modes, progress_cb, resume_checkpoint):
        """
        Background worker thread that creates an ExperimentRunner and runs it.

        Steps:
            1. Instantiate ExperimentRunner with global cfg + progress callback.
            2. Attach selected models/prompts/datasets for transparency.
            3. Update runner.gen_cfg with GUI-driven generation settings.
            4. Call runner.run_all(...) and surface errors/progress via msg_queue.
        """
        try:
            # Copy the base config so per-run GUI overrides do not mutate the
            # long-lived dashboard config object or future preset defaults.
            runner_cfg = copy.deepcopy(self.cfg)
            runner_cfg["debug_raw_outputs"] = bool(self.var_debug_raw_outputs.get())
            runner_cfg.setdefault("performance", {})
            runner_cfg["performance"].update({
                "checkpoint_every_n_samples": int(self.var_checkpoint_every_n_samples.get()),
                "checkpoint_every_seconds": float(self.var_checkpoint_every_seconds.get()),
                "progress_every_n_samples": int(self.var_progress_every_n_samples.get()),
                "sc_vote_delay_seconds": float(self.var_sc_vote_delay_seconds.get()),
                "prevent_system_sleep": bool(self.var_prevent_system_sleep.get()),
                "keep_display_awake": bool(self.var_keep_display_awake.get()),
            })
            self.runner = ExperimentRunner(runner_cfg, progress=progress_cb)

            # Pass GUI selections (informational only; runner may also consult cfg)
            self.runner.models_cfg = models
            self.runner.prompts_cfg = prompts
            self.runner.selected_datasets = datasets

            self.runner.gen_cfg.update({
                "temperature": float(self.var_temp.get()),
                "top_p": float(self.var_top_p.get()),
                "top_k": int(self.var_top_k.get()) if hasattr(self, "var_top_k") else 40,
                "max_new_tokens": int(self.var_maxnew.get()),
                "repetition_penalty": float(self.var_rep_pen.get()) if hasattr(self, "var_rep_pen") else 1.0,
                "frequency_penalty": float(self.var_freq_pen.get()),
                "presence_penalty": float(self.var_pres_pen.get()),
                "num_beams": int(self.var_num_beams.get()) if hasattr(self, "var_num_beams") else 1,
                "seed": int(self.var_seed.get()) if hasattr(self, "var_seed") else 42,
                "stop_sequences": [s.strip() for s in self.var_stop.get().split(",") if s.strip()],
                "sc_samples": int(self.var_sc_samples.get()),
                # Optional: useful metadata for reports
                "experiment_name": self.var_exp_name.get().strip(),
                "experiment_notes": self.txt_notes.get("1.0", "end").strip(),
            })

            status = self.runner.run_all(
                selected_datasets=datasets,
                selected_models=models,
                selected_prompts=prompts,
                selected_output_protocols=output_protocols,
                selected_parser_modes=parser_modes,
                resume_checkpoint=resume_checkpoint,
            )

            self.msg_queue.put(("done", status))
        except Exception as e:
            self.msg_queue.put(("error", str(e)))

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
            # Schedule the next update after 1 second
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
                    pct, msg, done, total = rest
                    self.progress.configure(value=pct)
                    self.progress_label.configure(text=f"{pct}% - Sample {done}/{total}")
                    self.sample_counter.configure(text=f"Samples: {done}/{total}")
                    self._log(msg)

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
                        self.progress_label.configure(text="100% - Completed.")
                        self.status_label.configure(text="Completed Successfully")
                        self.open_report_btn.configure(text="Open Report")
                        self.open_report_btn.configure(
                            state="normal"
                            if self.runner and self.runner.report_html_path and os.path.exists(self.runner.report_html_path)
                            else "disabled"
                        )
                        self._log("Run completed successfully.")
                    else:
                        self.progress_label.configure(text="Run stopped.")
                        self.status_label.configure(text="Stopped by user")
                        self.open_report_btn.configure(text="Open Partial Report")
                        self.open_report_btn.configure(
                            state="normal"
                            if self.runner and self.runner.report_html_path and os.path.exists(self.runner.report_html_path)
                            else "disabled"
                        )
                        self._log("Experiment stopped early. Partial results were compiled and resume is available from the saved checkpoint.")

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
            # No messages at this moment; just reschedule
            pass

        # Continue polling again after a short delay
        self.after(150, self._poll_msgs)

    def _log(self, msg):
        """
        Append a timestamped message to the log text area.
        """
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
            webbrowser.open_new_tab(f"file:///{path}")
        else:
            self._log(f"Report not found at {path}")


# Launcher convenience ---------------------------------------------------------
if __name__ == "__main__":
    app = Code2Dashboard()
    try:
        # ttkbootstrap provides this helper to center the window on screen
        app.place_window_center()
    except Exception:
        # If centering fails (on some platforms), just ignore and show the window
        pass
    app.mainloop()
