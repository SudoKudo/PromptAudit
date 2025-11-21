# ui/dashboard.py — PromptAudit Code v2.0
# Author: Steffen Camarato — University of Central Florida
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
AUTHOR = "Steffen Camarato — University of Central Florida"

# Where user preferences and presets are stored on disk
PREFS_PATH = "ui/user_prefs.yaml"
PRESETS_DIR = "ui/presets"

# Where logs are written during runs
LOG_DIR = "results/logs"

# Whitelisted Ollama models that the GUI offers as options.
# fuzzy_list_ollama_models() will intersect these with actually installed models.
ALLOWED_MODELS = [
    "mistral:latest",
    "gemma:7b",
    "gemma:7b-instruct",
    "codellama:7b-instruct",
    "deepseek-coder:6.7b-instruct",
    "falcon:7b",
    "falcon:7b-instruct",
]


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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)


# ---------------------------------------------------------------------
# Detect Installed Ollama Models
# ---------------------------------------------------------------------
def fuzzy_list_ollama_models():
    """
    Return installed Ollama models filtered by ALLOWED_MODELS.

    Strategy:
        - Call `ollama list` to get the available models locally.
        - Extract model tags from the CLI output.
        - For each ALLOWED_MODELS entry, check if:
            * Its full tag appears in any line, or
            * The base name (before ':') matches a listed model.
        - Return the subset that appears to be installed, in the same order
          as ALLOWED_MODELS.

    Fallback:
        - If any error occurs (e.g., Ollama CLI not available),
          return ALLOWED_MODELS as a safe default.
    """
    try:
        out = subprocess.check_output(["ollama", "list"], stderr=subprocess.STDOUT, text=True)
        # Skip header line, extract first column = model name/tag
        lines = [ln.split()[0].strip().lower() for ln in out.splitlines()[1:] if ln.strip()]
        found = []
        for allowed in ALLOWED_MODELS:
            tag = allowed.lower()
            # Match either the full tag somewhere in the line or the base model name
            if any(tag in ln or ln.startswith(tag.split(":")[0]) for ln in lines):
                found.append(allowed)
        # Preserve ALLOWED_MODELS order when returning
        return sorted(found, key=lambda x: ALLOWED_MODELS.index(x))
    except Exception:
        # If detection fails, just show the entire allowed list
        return ALLOWED_MODELS


# ---------------------------------------------------------------------
# Dashboard Class
# ---------------------------------------------------------------------
class Code2Dashboard(tb.Window):
    """
    Main GUI window for Code v2.0.

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

        # --- Selections for models / prompts / datasets ----------------------
        detected_models = fuzzy_list_ollama_models()

        # Prompt strategy names from config.yaml (e.g., ["zero_shot", "few_shot", ...])
        self.available_prompts = list(self.cfg.get("prompts", []))

        # Dataset names (only those with a "name" field in config.yaml)
        self.available_datasets = [d.get("name") for d in self.cfg.get("datasets", []) if d.get("name")]

        # Model selection: IntVar(1/0) for each detected model
        self.sel_models = {
            m: IntVar(value=1 if m in self.prefs.get("models", []) else 0)
            for m in detected_models
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

        # --- Metadata (experiment name + notes) ------------------------------
        self.var_exp_name = StringVar(value=self.prefs.get("experiment_name", "Untitled Experiment"))
        self.var_exp_notes = tk.StringVar(value=self.prefs.get("experiment_notes", ""))

        # --- Generation variables (synced with config.yaml + prefs) ----------
        gen_cfg = self.cfg.get("generation", {})

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

        # --- Preset UI state -------------------------------------------------
        self.var_preset_name = StringVar()
        self.var_preset_select = StringVar(value="(select preset)")

        # Build the entire UI layout
        self._build_ui()

        # Start polling for messages from the worker thread
        self.after(150, self._poll_msgs)

    # -----------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------
    def _build_ui(self):
        """
        Construct the three-column layout:
            - Left: Experiment controls and presets
            - Middle: Live run view (progress, logs)
            - Right: Insights & Analysis (placeholder tabs)
        """
        # Root layout: Left (controls), Middle (live), Right (insights)
        root = tb.Panedwindow(self, orient="horizontal")
        root.pack(fill="both", expand=True, padx=8, pady=8)

        # LEFT: Control column -------------------------------------------------
        left_col = tb.Labelframe(root, text="Experiment Control", padding=8)
        left_col.configure(width=420)
        root.add(left_col, weight=0)

        # Scrollable container for all left-side widgets
        left_scroll = ScrolledFrame(left_col, autohide=True, width=400, height=720)
        left_scroll.pack(fill="both", expand=True)
        left_inner = tb.Frame(left_scroll)
        left_inner.pack(fill="both", expand=True)

        # --- Experiment Metadata --------------------------------------------
        meta = tb.Labelframe(left_inner, text="Experiment Metadata", padding=8)
        meta.pack(fill="x")

        lbl_name = tb.Label(meta, text="Name")
        lbl_name.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_name, text="A friendly name for this run. Stored in results and reports.")
        tb.Entry(meta, textvariable=self.var_exp_name).grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        lbl_notes = tb.Label(meta, text="Notes")
        lbl_notes.grid(row=1, column=0, sticky="nw", padx=4, pady=4)
        ToolTip(lbl_notes, text="Any context about goals, changes, or hypotheses for this run.")
        # Multi-line text box for experiment notes
        self.txt_notes = tk.Text(meta, height=3, wrap="word")
        self.txt_notes.insert("1.0", self.var_exp_notes.get())
        self.txt_notes.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        meta.grid_columnconfigure(1, weight=1)

        # --- Models ----------------------------------------------------------
        models_box = tb.Labelframe(left_inner, text="Models (Ollama)", padding=8)
        models_box.pack(fill="x", pady=(8, 0))
        lbl_models = tb.Label(models_box, text="Select Models")
        lbl_models.pack(anchor="w")
        ToolTip(lbl_models, text="Choose one or more installed Ollama models to evaluate.")
        # One checkbox per detected model
        for name, var in self.sel_models.items():
            tb.Checkbutton(models_box, text=name, variable=var, command=self._persist_prefs).pack(anchor="w")

        # --- Prompts ---------------------------------------------------------
        prompts_box = tb.Labelframe(left_inner, text="Prompt Strategies", padding=8)
        prompts_box.pack(fill="x", pady=(8, 0))
        lbl_prompts = tb.Label(prompts_box, text="Select Prompts")
        lbl_prompts.pack(anchor="w")
        ToolTip(
            lbl_prompts,
            text="Different prompting modes (Zero-Shot, Few-Shot, CoT, Self-Consistency, etc.).",
        )
        for name, var in self.sel_prompts.items():
            tb.Checkbutton(prompts_box, text=name, variable=var, command=self._persist_prefs).pack(anchor="w")

        # --- Datasets --------------------------------------------------------
        data_box = tb.Labelframe(left_inner, text="Datasets", padding=8)
        data_box.pack(fill="x", pady=(8, 0))
        lbl_data = tb.Label(data_box, text="Select Datasets")
        lbl_data.pack(anchor="w")
        ToolTip(lbl_data, text="Datasets of code samples (toy, cvefixes, bigvul, etc.).")
        for name, var in self.sel_datasets.items():
            tb.Checkbutton(data_box, text=name, variable=var, command=self._persist_prefs).pack(anchor="w")

       # --- Generation Settings (full parity with config.yaml)
        gen = tb.Labelframe(left_inner, text="Generation Settings", padding=8)
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
            command=lambda e: self._persist_prefs(),
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
            command=lambda e: self._persist_prefs(),
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
            command=self._persist_prefs,
        )
        self.spin_top_k.grid(row=2, column=1, sticky="w", padx=4)

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
            command=self._persist_prefs,
        )
        self.spin_max_tokens.grid(row=3, column=1, sticky="w", padx=4)

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
            command=lambda e: self._persist_prefs(),
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
            command=lambda e: self._persist_prefs(),
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
            command=lambda e: self._persist_prefs(),
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
            command=self._persist_prefs,
        )
        self.spin_num_beams.grid(row=7, column=1, sticky="w", padx=4)

        # Seed ----------------------------------------------------------------
        lbl_seed = tb.Label(gen, text="Seed")
        lbl_seed.grid(row=8, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_seed, text="Random seed for reproducibility. Use the same seed for identical results.")
        self.var_seed = tk.IntVar(
            value=int(self.prefs.get("seed", self.cfg.get("generation", {}).get("seed", 42)))
        )
        tb.Spinbox(
            gen,
            from_=0,
            to=9999,
            textvariable=self.var_seed,
            width=10,
            command=self._persist_prefs,
        ).grid(row=8, column=1, sticky="w", padx=4)

        # Stop Sequences ------------------------------------------------------
        lbl_stop = tb.Label(gen, text="Stop Sequences")
        lbl_stop.grid(row=9, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_stop, text="Comma-separated strings where generation should stop.")
        tb.Entry(gen, textvariable=self.var_stop).grid(row=9, column=1, sticky="ew", padx=4)

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
            command=self._persist_prefs,
        )
        self.spin_sc_samples.grid(row=10, column=1, sticky="w", padx=4)

        # Allow column 1 (the controls) to stretch
        gen.grid_columnconfigure(1, weight=1)

        # --- Presets ---------------------------------------------------------
        presets = tb.Labelframe(left_inner, text="Presets", padding=8)
        presets.pack(fill="x", pady=(8, 0))

        lbl_save = tb.Label(presets, text="Save as")
        lbl_save.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ToolTip(lbl_save, text="Save current selections & generation settings as a preset (.yaml).")
        tb.Entry(presets, textvariable=self.var_preset_name).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        tb.Button(presets, text="💾 Save Preset", command=self._on_save_preset).grid(
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
        tb.Button(presets, text="📂 Load Preset", command=self._on_load_preset).grid(
            row=1, column=2, padx=4, pady=4
        )
        presets.grid_columnconfigure(1, weight=1)

        # --- Run controls ----------------------------------------------------
        run_box = tb.Frame(left_inner, padding=4)
        run_box.pack(fill="x", pady=(10, 6))
        self.run_btn = tb.Button(run_box, text="▶ Run Experiment", command=self._on_run, width=18)
        self.run_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = tb.Button(
            run_box, text="🛑 Stop", command=self._on_stop, width=10, state="disabled"
        )
        self.stop_btn.pack(side="left")

        # MIDDLE: Live Monitor -------------------------------------------------
        middle_col = tb.Labelframe(root, text="Live Run & Metrics", padding=8)
        root.add(middle_col, weight=3)

        # Progress bar + runtime display
        top_bar = tb.Frame(middle_col)
        top_bar.pack(fill="x")
        self.progress = tb.Progressbar(top_bar, mode="determinate", length=540, maximum=100)
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

        # Placeholder chart area (reserved for future live metrics plotting)
        chart_box = tb.Labelframe(middle_col, text="Live Performance (placeholder)", padding=6)
        chart_box.pack(fill="x", pady=(6, 6))
        self.chart_canvas = tk.Canvas(chart_box, height=120, highlightthickness=0, bg="#f8fafc")
        self.chart_canvas.pack(fill="x")
        self.chart_canvas.create_text(
            10,
            60,
            anchor="w",
            text="(Live Accuracy / F1 chart will render here in a future update)",
            fill="#6c757d",
        )

        # Log window (scrollable text area)
        self.log_text = tk.Text(middle_col, height=22, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Button to open the latest HTML report in the browser
        self.open_report_btn = tb.Button(
            middle_col, text="Open Report", command=self._open_report, state="disabled"
        )
        self.open_report_btn.pack(pady=(8, 0), anchor="e")

        # RIGHT: Insights ------------------------------------------------------
        right_col = tb.Labelframe(root, text="Insights & Analysis", padding=8)
        root.add(right_col, weight=2)

        # Tabs for various future analysis/summary views
        tabs = tb.Notebook(right_col, bootstyle="primary")
        tabs.pack(fill="both", expand=True)

        tab_summary = tb.Frame(tabs, padding=8)
        tabs.add(tab_summary, text="Summary")
        tb.Label(
            tab_summary,
            text="(Summary of best models, prompts, and metrics will appear here.)",
            bootstyle="secondary",
        ).pack(anchor="w")

        tab_heatmap = tb.Frame(tabs, padding=8)
        tabs.add(tab_heatmap, text="Model × Prompt")
        tb.Label(
            tab_heatmap,
            text="(Performance heatmap placeholder)",
            bootstyle="secondary",
        ).pack(anchor="w")

        tab_outputs = tb.Frame(tabs, padding=8)
        tabs.add(tab_outputs, text="Raw Outputs")
        tb.Label(
            tab_outputs,
            text="(Misclassifications / raw responses preview placeholder)",
            bootstyle="secondary",
        ).pack(anchor="w")

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
                * stop sequences (normalized to a list of strings)
            - Saves that dictionary to PREFS_PATH as YAML.
        """
        # --- Sync live label values for sliders
        self.lbl_temp_val.configure(text=f"{self.var_temp.get():.2f}")
        self.lbl_topp_val.configure(text=f"{self.var_top_p.get():.2f}")
        self.lbl_freq_val.configure(text=f"{self.var_freq_pen.get():.2f}")
        self.lbl_pres_val.configure(text=f"{self.var_pres_pen.get():.2f}")
        if hasattr(self, "lbl_rep_val"):
            self.lbl_rep_val.configure(text=f"{self.var_rep_pen.get():.2f}")

        # --- Grab notes text
        try:
            self.var_exp_notes.set(self.txt_notes.get("1.0", "end").strip())
        except Exception:
            # If for some reason the text widget is unavailable, keep old notes
            pass

        # --- Build preferences dictionary
        prefs = {
            # Experiment metadata
            "experiment_name": self.var_exp_name.get().strip(),
            "experiment_notes": self.var_exp_notes.get().strip(),

            # Selections
            "models": [k for k, v in self.sel_models.items() if v.get()],
            "prompts": [k for k, v in self.sel_prompts.items() if v.get()],
            "datasets": [k for k, v in self.sel_datasets.items() if v.get()],

            # Generation parameters (1:1 with config.yaml)
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

            # Stop sequences — always stored as a list
            "stop_sequences": [s.strip() for s in self.var_stop.get().split(",") if s.strip()],
        }

        # --- Save preferences to YAML file
        try:
            save_yaml(PREFS_PATH, prefs)
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
        # Load current prefs from disk (ensuring latest _persist_prefs is used)
        data = load_yaml(PREFS_PATH)
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

            # --- Restore experiment metadata
            self.var_exp_name.set(data.get("experiment_name", self.var_exp_name.get()))
            self.var_exp_notes.set(data.get("experiment_notes", ""))
            self.txt_notes.delete("1.0", "end")
            self.txt_notes.insert("1.0", self.var_exp_notes.get())

            # --- Restore model / prompt / dataset selections
            for m in self.sel_models:
                self.sel_models[m].set(1 if m in data.get("models", []) else 0)
            for p in self.sel_prompts:
                self.sel_prompts[p].set(1 if p in data.get("prompts", []) else 0)
            for d in self.sel_datasets:
                self.sel_datasets[d].set(1 if d in data.get("datasets", []) else 0)

            # --- Restore generation parameters
            self.var_temp.set(float(data.get("temperature", self.var_temp.get())))
            self.var_top_p.set(float(data.get("top_p", self.var_top_p.get())))
            self.var_maxnew.set(int(data.get("max_new_tokens", self.var_maxnew.get())))
            self.var_freq_pen.set(float(data.get("frequency_penalty", self.var_freq_pen.get())))
            self.var_pres_pen.set(float(data.get("presence_penalty", self.var_pres_pen.get())))
            stops = data.get("stop_sequences", self.var_stop.get())
            self.var_stop.set(
                ", ".join(stops) if isinstance(stops, (list, tuple)) else str(stops or "")
            )

            self.var_sc_samples.set(int(data.get("sc_samples", self.var_sc_samples.get())))

            # Persist what we've restored so everything stays in sync on disk
            self._persist_prefs()
            self._log(f"Preset loaded: {path}")
        except Exception as e:
            self._log(f"Failed to load preset: {e}")

    # -----------------------------------------------------------------
    # Run + Stop logic
    # -----------------------------------------------------------------
    def _on_run(self):
        """
        Handler for the "Run Experiment" button.

        Validates selections, persists prefs, disables/enables controls,
        and spawns a background worker thread to run the experiment.
        """
        # Build lists of selected models/prompts/datasets
        models = [k for k, v in self.sel_models.items() if v.get()]
        prompts = [k for k, v in self.sel_prompts.items() if v.get()]
        datasets = [k for k, v in self.sel_datasets.items() if v.get()]
        if not (models and prompts and datasets):
            self._log("Please select at least one model, prompt, and dataset.")
            return

        # Save the latest preferences before starting the run
        self._persist_prefs()

        # Update button states and progress UI
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_report_btn.configure(state="disabled")
        self.progress.configure(value=0)
        self.status_label.configure(text="Running…")

        # Start the runtime clock display
        self._start_time = time.time()
        self._update_runtime()

        self._log(f"Starting experiment with datasets: {datasets}")

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
            args=(models, prompts, datasets, progress_cb),
            daemon=True,
        ).start()

    def _on_stop(self):
        """
        Handler for the "Stop" button.

        Signals the ExperimentRunner to stop gracefully by setting flags.
        """
        self._log("🛑 Stop requested by user…")
        self.status_label.configure(text="Stopping…")
        self.stop_btn.configure(state="disabled")
        if self.runner:
            # These flags are interpreted by ExperimentRunner.run_all()
            self.runner.stop_flag = True
            self.runner.stop_requested = True

    def _worker_run(self, models, prompts, datasets, progress_cb):
        """
        Background worker thread that creates an ExperimentRunner and runs it.

        Steps:
            1. Ensure LOG_DIR exists.
            2. Instantiate ExperimentRunner with global cfg + progress callback.
            3. Attach selected models/prompts/datasets for transparency.
            4. Update runner.gen_cfg with GUI-driven generation settings.
            5. Call runner.run_all(...) and surface errors/progress via msg_queue.
        """
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.runner = ExperimentRunner(self.cfg, progress=progress_cb)

            # Pass GUI selections (informational only; runner may also consult cfg)
            self.runner.models_cfg = [{"name": m} for m in models]
            self.runner.prompts_cfg = prompts
            self.runner.selected_datasets = datasets

            # Pass generation config — includes new params.
            # NOTE: The model backends are expected to read these keys:
            #   temperature, top_p, max_new_tokens, frequency_penalty,
            #   presence_penalty, stop_sequences, sc_samples, experiment_name,
            #   experiment_notes. Other keys like top_k, repetition_penalty,
            #   num_beams, seed are stored in prefs and may also be wired in
            #   from the runner depending on how gen_cfg is initialized.
            self.runner.gen_cfg.update({
                "temperature": float(self.var_temp.get()),
                "top_p": float(self.var_top_p.get()),
                "max_new_tokens": int(self.var_maxnew.get()),
                "frequency_penalty": float(self.var_freq_pen.get()),
                "presence_penalty": float(self.var_pres_pen.get()),
                "stop_sequences": [s.strip() for s in self.var_stop.get().split(",") if s.strip()],
                "sc_samples": int(self.var_sc_samples.get()),
                # Optional: useful metadata for reports
                "experiment_name": self.var_exp_name.get().strip(),
                "experiment_notes": self.txt_notes.get("1.0", "end").strip(),
            })

            # Run the full experiment (blocking in this worker thread)
            self.runner.run_all(
                selected_datasets=datasets,
                selected_models=models,
                selected_prompts=prompts,
            )

            # Notify main thread that we're done
            self.msg_queue.put(("done", ""))
        except Exception as e:
            # Surface any errors to the main thread so the GUI can show them
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
                    self.progress_label.configure(text=f"{pct}% — Sample {done}/{total}")
                    self.sample_counter.configure(text=f"Samples: {done}/{total}")
                    self._log(msg)

                elif kind == "log_only":
                    self._log(rest[0])

                elif kind == "done":
                    # Mark progress as complete and unlock controls
                    self.progress.configure(value=100)
                    self.progress_label.configure(text="100% — Completed.")
                    self.status_label.configure(text="✅ Completed Successfully")
                    self.open_report_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                    self.run_btn.configure(state="normal")
                    self._log("Run completed successfully.")
                    self._start_time = None

                    # If the runner recorded a stop request, reflect that in status
                    if self.runner and (self.runner.stop_flag or self.runner.stop_requested):
                        self.status_label.configure(text="🛑 Stopped by user")
                        self._log("🛑 Experiment stopped early.")

                elif kind == "error":
                    msg = rest[0]
                    self.progress_label.configure(text=f"ERROR — {msg}")
                    self.status_label.configure(text="Error Occurred")
                    self.stop_btn.configure(state="disabled")
                    self.run_btn.configure(state="normal")
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
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _open_report(self):
        """
        Open the configured HTML report in the user's default web browser.
        """
        path = os.path.abspath(self.cfg.get("output", {}).get("report_html", "results/report.html"))
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
