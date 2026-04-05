<<<<<<< Updated upstream
# evaluation/report.py — PromptAudit v2.0
# Author: Steffen Camarato — University of Central Florida
#
# 💡 WHAT THIS FILE DOES
# -----------------------------------------------------------------------------
# This file defines a tiny helper class (HtmlReport) that takes my experiment
# results (a list of Python dicts) and turns them into a single, interactive
# HTML dashboard. You open the HTML file in my browser and get:
#   • A styled header with version, author, and a Dark Mode toggle
#   • An accordion with sections: Parameters, Leaderboard, Filters, Chart, Tables
#   • Live filters (dropdowns + sliders) that instantly update everything
#   • A unified bar chart (Accuracy / Precision / Recall / F1)
#   • Two tables:
#       - Results (one row per model+prompt+dataset combo with metrics)
#       - Detailed predictions (one row per sample, with SAFE/VULNERABLE pills)
#   • Export buttons: CSV, JSON, PNG chart capture, full-page PDF, glossary PDF
#
# IMPORTANT NOTES
# -----------------------------------------------------------------------------
# • You DO NOT need to edit any of the HTML/JS below to use this. Just pass my
#   results in and call HtmlReport.write(...). It will generate a .html file.
# • The big HTML string below includes all styles (CSS) and interactive behavior
#   (JavaScript).
# • We never run this HTML inside Python; we only write it out as text.
=======
"""Render the interactive HTML report for a PromptAudit run."""
>>>>>>> Stashed changes

import os
import json
from datetime import datetime


class HtmlReport:
    # The HtmlReport holds onto the results and knows how to write the dashboard.
    def __init__(self, results):
        # `results` is expected to be a list of dicts. Each dict represents one
        # (dataset, model, prompt) combo with aggregated metrics and a `predictions`
        # list of per-sample entries. The JavaScript in the HTML expects those keys.
        self.results = results

    def write(self, output_path, records, metric_keys, version="v2.0",
<<<<<<< Updated upstream
              author="Steffen Camarato — University of Central Florida"):
=======
              author="PromptAudit"):
>>>>>>> Stashed changes
        # Ensure the output folder exists so we can write the HTML file safely.
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # ---- Helpers ---------------------------------------------------------
        def sniff_params(rs):
            """
            Try to find and return a dict of generation/experiment parameters
            from the results list `rs`. Different generators may nest params
            under different keys, so we:
              1) Look for a dict under common keys like 'params', 'gen_cfg', 'generation'
              2) If not found, fall back to pulling a whitelist of known keys
                 directly from rs[0].
            """
            if not rs:
                return {}
            for k in ("params", "gen_cfg", "generation"):
                if isinstance(rs[0].get(k), dict):
                    return rs[0][k]
            # If params weren't nested, grab a set of likely keys at top level.
            keys = [
                "temperature", "top_p", "top_k", "max_new_tokens", "repetition_penalty",
                "frequency_penalty", "presence_penalty", "num_beams", "sc_samples", "seed",
                "stop_sequences", "experiment_name", "experiment_notes"
            ]
            return {k: rs[0][k] for k in rs[0] if k in keys}

        # When the report was generated (displayed in the header).
        params = sniff_params(records)
        gen_when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def build_param_rows(p):
            """
            Convert a dict of parameters into a small HTML table:
              â€¢ Floats get nicely rounded
              â€¢ Lists get joined with commas
              â€¢ If nothing is available, we show a friendly placeholder
            """
            if not p:
                return "<div class='text-muted small'>No parameters recorded.</div>"
            rows = []
            for k, v in p.items():
                if isinstance(v, float):
                    v = f"{v:.3f}"
                elif isinstance(v, list):
                    v = ", ".join(map(str, v))
                rows.append(f"<tr><th class='text-nowrap'>{k}</th><td>{v}</td></tr>")
            return "<table class='table table-sm table-bordered w-auto'><tbody>{}</tbody></table>".format("".join(rows))

        # ---- HTML (escaped safely below) ------------------------------------
        # NOTE: This is a single HTML page containing:
        #   â€¢ Bootstrap (layout + icons)
        #   â€¢ Chart.js (charts)
        #   â€¢ simple-datatables (tables w/ pagination & search)
        #   â€¢ html2canvas + jsPDF (image/PDF export)
        #   â€¢ Lots of semantic <div> sections and CSS variables for theming
        html = """<!DOCTYPE html>
<html lang="en" data-bs-theme="light">
<head>
<meta charset="UTF-8">
<title>PromptAudit - {version}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">

<!-- Bootstrap + Icons -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>

<!-- Charts, Table, Export libs -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
<script src="https://cdn.jsdelivr.net/npm/simple-datatables@9.0.0"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/simple-datatables@9.0.0/dist/style.css">
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>

<style>
/* ------------------------------
   Color system & base theming
   ------------------------------ */
:root {{
  --accent-ice: #e6f2ff;
  --accent-mid: #5aa8ff;
  --accent-navy: #0b2a62;
  --text-light: #e0e0e0;
  --text-dark: #212529;
}}

html, body {{ height: 100%; }}
body {{ background:#f8fafc; color:var(--text-dark); font-family:'Segoe UI',system-ui; }}
[data-bs-theme="dark"] body {{ background:#0d141c; color:var(--text-light); }}

/* Header gradient bar */
.header-gradient {{
  background: linear-gradient(135deg, var(--accent-ice), var(--accent-mid) 40%, var(--accent-navy));
  color: #fff;
}}
[data-bs-theme="dark"] .header-gradient {{
  background: linear-gradient(135deg, #0e1a2b, #123861 40%, #091a3a);
}}

.header-title {{ letter-spacing:.4px; }}
.header-subtitle {{ opacity:.9; font-size:.9rem; }}

/* Subtle "version" badge style */
.badge-version {{
  background: rgba(255,255,255,.2);
  border: 1px solid rgba(255,255,255,.3);
  color: #fff;
}}

/* Card & table treatment for light/dark */
.card {{ border-color:#e8eef6; }}
[data-bs-theme="dark"] .card {{ background:#121a24; border-color:#1e2a38; }}

.table thead th {{ background:#0d6efd; color:#fff; }}
[data-bs-theme="dark"] .table thead th {{ background:#1f3c88; }}

.btn-export {{ min-width:78px; font-weight:600; }}

.header-gradient .btn-export {{
  color:#fff;
  background: rgba(10, 23, 46, 0.18);
  border-color: rgba(255,255,255,.38);
}}
.header-gradient .btn-export:hover,
.header-gradient .btn-export:focus-visible {{
  color:#fff;
  background: rgba(255,255,255,.2);
  border-color: rgba(255,255,255,.62);
}}
.header-gradient .form-check-label,
.header-gradient small {{
  color: rgba(255,255,255,.94);
}}

/* Chart sizing wrapper */
.chart-scroll {{ overflow-x:auto; padding-bottom:0.25rem; }}
.chart-stage {{ position:relative; min-width:1200px; height:460px; }}

/* Result status badges / partial row callouts */
.run-status-badge {{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:88px;
  padding:0.2rem 0.65rem;
  border-radius:999px;
  font-size:0.72rem;
  font-weight:700;
  letter-spacing:.25px;
  text-transform:uppercase;
}}
.status-complete {{
  background:#eaf7ee;
  color:#1f6b3b;
  border:1px solid #b6dfc2;
}}
.status-partial {{
  background:#fff4db;
  color:#9a6700;
  border:1px solid #f2cf7a;
}}
[data-bs-theme="dark"] .status-complete {{
  background:#173223;
  color:#91f2b1;
  border-color:#285539;
}}
[data-bs-theme="dark"] .status-partial {{
  background:#3a2a0f;
  color:#ffd479;
  border-color:#6b4d1a;
}}
.progress-chip {{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:66px;
  padding:0.15rem 0.5rem;
  border-radius:999px;
  font-variant-numeric: tabular-nums;
  background:#eef2f7;
  color:#334155;
}}
[data-bs-theme="dark"] .progress-chip {{
  background:#1a2330;
  color:#d6dee8;
}}
.partial-summary {{
  border-left:4px solid #ffc107;
}}

/* Circular '?' inline info bubbles next to metric labels */
.metric-info {{
  display:inline-flex; align-items:center; justify-content:center;
  width:18px; height:18px; border-radius:50%;
  background:#e3f2fd; color:#0d6efd; font-size:12px; font-weight:700;
  margin-left:6px; cursor:help; border:1px solid #cfe5ff;
}}
[data-bs-theme="dark"] .metric-info {{
  background:#132e57; color:#66b0ff; border-color:#234a82;
}}

/* Bootstrap Popover limits */
.popover {{ max-width:320px; }}
.popover-header {{ background:#0d6efd; color:#fff; font-weight:600; }}
[data-bs-theme="dark"] .popover-header {{ background:#1f3c88; }}

/* Live summary text under filters */
#filterSummary {{ font-size:0.9rem; color:#555; }}
[data-bs-theme="dark"] #filterSummary {{ color:#aab3bf; }}

/* Thin progress bars used in leaderboards */
.progress.skim {{ height:8px; }}
.progress .progress-bar {{ transition: width .4s ease; }}

/* Accordion polish: allow multi-open, remove odd outlines in dark */
.accordion-button:focus {{ box-shadow:none; }}
.accordion-item {{ border-color:#e8eef6; }}
[data-bs-theme="dark"] .accordion-item {{ border-color:#1e2a38; }}
.accordion-body {{ background:transparent; }}

/* Small fade tooltip box (used earlier for clipboard idea) */
[data-bs-theme="dark"] .fade-tip {{ background: rgba(240,248,255,0.12); color:#fff; }}
.fade-tip.show {{ opacity: 1; }}

/* ==============================================
   SAFE / VULNERABLE text bubbles
   These are the green/red rounded "pills"
   ============================================== */
.sv-pill {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:70px;
  height:24px;
  padding:0 .75rem;
  border-radius:999px;
  font-size:12px;
  font-weight:600;
  text-transform:uppercase;
  letter-spacing:.3px;
  user-select:none;
}

.sv-safe {
  background-color:#e6f9e6;
  color:#155724;
  border:1px solid #b2e0b2;
}
.sv-vuln {
  background-color:#fde6e6;
  color:#b30000;
  border:1px solid #f0a1a1;
}

/* Dark-mode variants for the pills */
[data-bs-theme="dark"] .sv-safe {
  background-color:#16381f;
  color:#7aff7a;
  border-color:#265f29;
}
[data-bs-theme="dark"] .sv-vuln {
  background-color:#3b1414;
  color:#ff6c6c;
  border-color:#702d2d;
}

/* ==============================================
    Centered Tables + Bubble Spacing
   ============================================== */

/* Subtle vertical spacing so pills do not touch */
.sv-pill {
  margin: 2px auto;
}

/* Center ALL columns in Detailed Model Predictions table */
#detailsBody td,
#detailsBody th {
  text-align: center;
  vertical-align: middle;
}

</style>
</head>

<body>

<!--
  HEADER BAR
  Shows the product title + version, a timestamp, a Dark toggle, and export buttons.
-->
<div class="header-gradient py-4 px-3 mb-3">
  <div class="container d-flex align-items-center justify-content-between">
    <div>
      <h1 class="h4 header-title mb-1">
        PromptAudit - {version}
      </h1>
      <div class="header-subtitle">LLM-Driven Software Vulnerability Analysis</div>
      <div class="header-subtitle"><strong>{author}</strong></div>
    </div>
    <div class="d-flex align-items-center gap-2">
      <small class="opacity-90">Generated {gen_when}</small>
      <!-- Dark mode switch lives here -->
      <div class="ms-3 form-check form-switch">
        <input class="form-check-input" type="checkbox" id="themeSwitch">
        <label class="form-check-label small" for="themeSwitch">Dark</label>
      </div>
      <!-- Export buttons (CSV/JSON/Charts/PDF/Glossary) -->
      <button id="btn-export-csv" class="btn btn-sm btn-outline-primary btn-export">CSV</button>
      <button id="btn-export-json" class="btn btn-sm btn-outline-secondary btn-export">JSON</button>
      <button id="btn-export-charts" class="btn btn-sm btn-outline-success btn-export">Charts</button>
      <button id="btn-export-pdf" class="btn btn-sm btn-outline-danger btn-export">PDF</button>
      <button id="btn-glossary-pdf" class="btn btn-sm btn-primary btn-export">Glossary</button>
    </div>
  </div>
</div>

<div class="container pb-4">

  <!--
    MAIN ACCORDION
    Multiple sections can be open at once (we do NOT use data-bs-parent).
  -->
  <div class="accordion section-toggle mb-3" id="mainAccordion">

    <!-- Parameters Used -->
    <!-- This section prints the generation/experiment settings table -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingParams">
        <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseParams" aria-expanded="false" aria-controls="collapseParams">
          Parameters Used
        </button>
      </h2>
      <div id="collapseParams" class="accordion-collapse collapse" aria-labelledby="headingParams">
        <div class="accordion-body">
          {param_table}
        </div>
      </div>
    </div>

    <!-- Leaderboard -->
    <!-- For each metric, show the top 3 bars with medals -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingBoard">
        <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseBoard" aria-expanded="true" aria-controls="collapseBoard">
          Best Performers (Top 3 per metric)
        </button>
      </h2>
      <div id="collapseBoard" class="accordion-collapse collapse show" aria-labelledby="headingBoard">
        <div class="accordion-body">
          <div id="leaderboardBody" class="row g-3"></div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <!-- Dropdowns + sliders; they drive the chart + leaderboard + tables -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingFilters">
        <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseFilters" aria-expanded="true" aria-controls="collapseFilters">
          Filters & Thresholds
        </button>
      </h2>
      <div id="collapseFilters" class="accordion-collapse collapse show" aria-labelledby="headingFilters">
        <div class="accordion-body">
          <div class="row g-3 align-items-center">
            <div class="col-auto"><strong>Filters:</strong></div>
            <!-- These selects are populated dynamically from RECORDS -->
            <div class="col"><select id="filterDataset" class="form-select form-select-sm"><option value="">All Datasets</option></select></div>
            <div class="col"><select id="filterModel" class="form-select form-select-sm"><option value="">All Models</option></select></div>
            <div class="col"><select id="filterPrompt" class="form-select form-select-sm"><option value="">All Prompts</option></select></div>
            <div class="col"><select id="filterLanguage" class="form-select form-select-sm"><option value="">All Languages</option></select></div>
            <div class="col-auto"><button id="btn-reset" class="btn btn-sm btn-outline-secondary">Reset</button></div>
          </div>

          <!-- Metric thresholds (live) -->
          <div class="row mt-3 g-3 align-items-center">
            <div class="col">
              <label class="small">Accuracy
                <span class="metric-info" data-bs-toggle="popover" data-bs-trigger="hover focus" title="Accuracy" data-bs-content="Proportion of evaluated vulnerable/safe outcomes that were correct. (TP + TN) / (TP + TN + FP + FN + UnFN)">?</span>
                (<span id="valAcc">0.00</span>)
              </label>
              <input type="range" id="accThreshold" min="0" max="1" step="0.01" value="0" class="form-range">
            </div>
            <div class="col">
              <label class="small">Precision
                <span class="metric-info" data-bs-toggle="popover" data-bs-trigger="hover focus" title="Precision" data-bs-content="Of all predicted vulnerable cases, how many were correct. TP / (TP + FP)">?</span>
                (<span id="valPrec">0.00</span>)
              </label>
              <input type="range" id="precThreshold" min="0" max="1" step="0.01" value="0" class="form-range">
            </div>
            <div class="col">
              <label class="small">Recall
                <span class="metric-info" data-bs-toggle="popover" data-bs-trigger="hover focus" title="Recall" data-bs-content="Of all truly vulnerable cases, how many were correctly identified. TP / (TP + FN + UnFN)">?</span>
                (<span id="valRec">0.00</span>)
              </label>
              <input type="range" id="recThreshold" min="0" max="1" step="0.01" value="0" class="form-range">
            </div>
            <div class="col">
              <label class="small">F1 Score
                <span class="metric-info" data-bs-toggle="popover" data-bs-trigger="hover focus" title="F1 Score" data-bs-content="Harmonic mean of Precision and Recall. 2 * (P * R) / (P + R)">?</span>
                (<span id="valF1">0.00</span>)
              </label>
              <input type="range" id="f1Threshold" min="0" max="1" step="0.01" value="0" class="form-range">
            </div>
          </div>

          <!-- Summary text updates as filters move -->
          <div id="filterSummary" class="mt-2 small text-muted"></div>
        </div>
      </div>
    </div>

    <!-- Chart -->
    <!-- A bar chart that aggregates duplicate (model+prompt) combos -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingChart">
        <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseChart" aria-expanded="true" aria-controls="collapseChart">
          Unified Metrics Chart
        </button>
      </h2>
      <div id="collapseChart" class="accordion-collapse collapse show" aria-labelledby="headingChart">
        <div class="accordion-body">
          <div class="chart-scroll mb-2">
            <div id="chartStage" class="chart-stage"><canvas id="metricChart"></canvas></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Table -->
    <!-- Top table: one row per record (dataset+model+prompt) with metrics -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingTable">
        <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseTable" aria-expanded="true" aria-controls="collapseTable">
          Results Table
        </button>
      </h2>
        <div id="collapseTable" class="accordion-collapse collapse show" aria-labelledby="headingTable">
        <div class="accordion-body">
          <div id="partialSummary" class="alert alert-warning partial-summary py-2 px-3 mb-3 d-none"></div>
          <div class="card">
            <div class="card-header d-flex flex-wrap gap-2 justify-content-between align-items-center">
              <span>Results</span>
              <div class="d-flex align-items-center gap-2">
                <button id="resetResultsFilters" class="btn btn-sm btn-outline-secondary"
                title="Clear all column filters">Reset Filters</button>
                <span id="recordCount" class="text-muted small"></span>
              </div>
            </div>
            <div class="card-body">
              <div class="table-responsive">
                <table id="results-table" class="table table-sm table-hover table-bordered small">
                  <thead>
                    <tr>
                      <th>Dataset</th><th>Model</th><th>Prompt</th><th>Protocol</th><th>Parser</th><th>Status</th><th>Progress</th><th>Lang</th>
                      <th title="Accuracy: (TP+TN)/(TP+TN+FP+FN+UnFN)">Acc</th>
                      <th title="Precision: TP/(TP+FP)">Prec</th>
                      <th title="Recall: TP/(TP+FN+UnFN)">Rec</th>
                      <th title="F1: 2*(P*R)/(P+R)">F1</th>
                      <th title="Coverage: 1 - Abstention Rate">Cov</th>
                      <th title="Abstention Rate: (Incorrect + UnFN) / Total outcomes">Abst</th>
                      <th title="Effective F1: F1 * Coverage">EffF1</th>
                    </tr>
                  </thead>
                  <tbody id="resultsBody"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Detailed Model Predictions -->
    <!-- Bottom table: one row per prediction (per sample) -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingDetailed">
        <button class="accordion-button" type="button"
                data-bs-toggle="collapse" data-bs-target="#collapseDetailed"
                aria-expanded="false" aria-controls="collapseDetailed">
          Detailed Model Predictions
        </button>
      </h2>
      <div id="collapseDetailed" class="accordion-collapse show"
          aria-labelledby="headingDetailed">
        <div class="accordion-body">
          <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
              <span>Per-Sample Results</span>
              <div class="d-flex align-items-center gap-2">
                <button id="resetDetailsFilters" class="btn btn-sm btn-outline-secondary"
                title="Clear all column filters">Reset Filters</button>
                <span id="detailCount" class="text-muted small"></span>
              </div>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table id="details-table" class="table table-sm table-hover table-bordered small align-middle">
                    <thead class="table-light">
                        <tr>
                        <th>ID</th><th>Dataset</th><th>Protocol</th><th>Parser</th><th>Lang</th><th>Model</th><th>Prompt</th>
                        <th>Predicted</th><th>True</th><th>Correct?</th>
                        </tr>
                    </thead>
                    <tbody id="detailsBody"></tbody>
                    </table>
                </div>
                </div>
        </div>
      </div>
    </div>

  </div> <!-- /accordion -->

</div> <!-- /container -->

<script>
/* ----------------------------------------------------------------------------
   DATA INGEST
   RECORDS is the raw JSON version of your Python `records` list dumped below.
---------------------------------------------------------------------------- */
const RECORDS = {json_records};

// --- Global state for robust filtering across ALL pages
let resultsTable = null;  // DataTable instance for the top table
let detailTable  = null;  // DataTable instance for the bottom table

// Caches of every row's textual columns + full HTML, used for fast filtering
let RESULTS_ALL = [];  // [{cols:[...], html:"<tr>...</tr>"}]
let DETAILS_ALL = [];  // same shape
let RESULTS_SOURCE = [];  // current top-level filtered records backing the results table
let DETAILS_SOURCE = [];  // current top-level filtered records backing the details table

// Column filter state maps (per-table)
const resultsActive = {}; // {colIndex: "value"}
const detailsActive = {};

/* Tiny helpers: round numbers, deduplicate arrays */
function roundNum(n){return (typeof n==='number')?n.toFixed(3):'-';}
function asInt(n){{ const parsed = Number(n); return Number.isFinite(parsed) ? Math.max(0, Math.trunc(parsed)) : 0; }}
function unique(v){return Array.from(new Set(v)).sort();}
function normalizeLabel(value){{
  const label = (value || '').toString().trim().toLowerCase();
  return label === 'safe' || label === 'vulnerable' ? label : 'unknown';
}}
function aggregatePredictionMetrics(predictions){{
  const totals = {{
    TP: 0, TN: 0, FP: 0, FN: 0, UnFN: 0, Incorrect: 0,
    Accuracy: 0, Precision: 0, Recall: 0, F1: 0,
    AbstentionRate: 0, Coverage: 0, EffectiveF1: 0, Unknown: 0
  }};
  (predictions || []).forEach(p => {{
    const gold = normalizeLabel(p?.gold);
    const pred = normalizeLabel(p?.pred);
    if (pred === 'vulnerable') {{
      if (gold === 'vulnerable') totals.TP += 1;
      else totals.FP += 1;
    }} else if (pred === 'safe') {{
      if (gold === 'safe') totals.TN += 1;
      else totals.FN += 1;
    }} else {{
      totals.Unknown += 1;
      if (gold === 'vulnerable') totals.UnFN += 1;
      else totals.Incorrect += 1;
    }}
  }});
  const answeredTotal = totals.TP + totals.TN + totals.FP + totals.FN + totals.UnFN;
  const total = answeredTotal + totals.Incorrect;
  totals.Accuracy = answeredTotal ? (totals.TP + totals.TN) / answeredTotal : 0;
  totals.Precision = (totals.TP + totals.FP) ? totals.TP / (totals.TP + totals.FP) : 0;
  const recallDenominator = totals.TP + totals.FN + totals.UnFN;
  totals.Recall = recallDenominator ? totals.TP / recallDenominator : 0;
  totals.F1 = (totals.Precision + totals.Recall)
    ? (2 * totals.Precision * totals.Recall) / (totals.Precision + totals.Recall)
    : 0;
  totals.AbstentionRate = total ? (totals.Incorrect + totals.UnFN) / total : 0;
  totals.Coverage = total ? 1 - totals.AbstentionRate : 0;
  totals.EffectiveF1 = totals.F1 * totals.Coverage;
  return totals;
}}
function recordForSelectedLanguage(record, selectedLanguage){{
  if (!selectedLanguage) return record;
  const target = selectedLanguage.toString().trim().toLowerCase();
  const filteredPredictions = (record?.predictions || []).filter(p => {{
    const language = (p?.language || 'unknown').toString().trim().toLowerCase() || 'unknown';
    return language === target;
  }});
  if (!filteredPredictions.length) return null;
  const displayLanguage = (filteredPredictions[0]?.language || selectedLanguage).toString().trim() || selectedLanguage;
  return {{
    ...record,
    ...aggregatePredictionMetrics(filteredPredictions),
    predictions: filteredPredictions,
    language: displayLanguage,
    languages_present: [displayLanguage],
    language_counts: {{ [displayLanguage]: filteredPredictions.length }},
    filtered_language: displayLanguage,
    language_sample_count: filteredPredictions.length
  }};
}}
function collectLanguageCounts(r){{
  if (r && r.language_counts && typeof r.language_counts === 'object') {{
    return r.language_counts;
  }}
  const counts = {{}};
  (r?.predictions || []).forEach(p => {{
    const lang = (p?.language || 'unknown').toString().trim() || 'unknown';
    counts[lang] = (counts[lang] || 0) + 1;
  }});
  if (!Object.keys(counts).length && r?.language) {{
    counts[r.language] = 1;
  }}
  return counts;
}}
function orderedLanguages(r){{
  return Object.entries(collectLanguageCounts(r))
    .sort((a,b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
    .map(([name]) => name);
}}
function recordLanguageSummary(r){{
  const names = orderedLanguages(r);
  if (!names.length) return '-';
  if (names.length <= 4) return names.join(', ');
  return `${names.slice(0, 4).join(', ')} +${names.length - 4} more`;
}}
function recordLanguageTooltip(r){{
  const entries = Object.entries(collectLanguageCounts(r)).sort((a,b) => (b[1] - a[1]) || a[0].localeCompare(b[0]));
  if (!entries.length) return '-';
  return entries.map(([name,count]) => `${name} (${count})`).join(', ');
}}
function recordStatus(r){{ return r && r.is_partial ? 'Partial' : 'Complete'; }}
function statusBadge(r){{
  return r && r.is_partial
    ? '<span class="run-status-badge status-partial">Partial</span>'
    : '<span class="run-status-badge status-complete">Complete</span>';
}}
function progressLabel(r){{
  const total = asInt(r?.total_samples);
  if(!total) return '-';
  const completed = Math.min(asInt(r?.completed_samples), total);
  return `${completed}/${total}`;
}}
function progressChip(r){{
  return `<span class="progress-chip">${progressLabel(r)}</span>`;
}}
function visibleSampleCount(r){{
  return asInt(r?.language_sample_count || (r?.predictions || []).length);
}}
function updatePartialSummary(rows){{
  const box = document.getElementById('partialSummary');
  if(!box) return;
  const partials = (rows || []).filter(r => r && r.is_partial);
  if(!partials.length){{
    box.classList.add('d-none');
    box.innerHTML = '';
    return;
  }}
  const labels = partials.slice(0, 3).map(r =>
    `<code>${r.model} / ${r.prompt} / ${r.output_protocol || 'verdict_first'} / ${r.parser_mode || 'full'}</code>`
  );
  const extra = partials.length > 3 ? ` and ${partials.length - 3} more` : '';
  box.classList.remove('d-none');
  box.innerHTML = `
    <strong>Partial results visible.</strong>
    ${partials.length} row${partials.length === 1 ? '' : 's'} reflect paused or stopped combinations and use only the samples completed so far.
    ${labels.length ? `Current partial rows: ${labels.join(', ')}${extra}.` : ''}
  `;
}}
function setRecordCount(visible, total, partialVisible = 0){{
  const rc = document.getElementById('recordCount');
  if (!rc) return;
  const suffix = partialVisible ? ` | ${partialVisible} partial` : '';
  rc.textContent = `Showing ${visible} / ${total}${suffix}`;
}}

/* ----------------------------------------------------------------------------
   THEME HANDLING
   We set a data attribute on <html> so Bootstrap and our CSS can react.
---------------------------------------------------------------------------- */
const themeSwitch=document.getElementById('themeSwitch');
themeSwitch?.addEventListener('change',e=>{
  document.documentElement.setAttribute('data-bs-theme', e.target.checked ? 'dark' : 'light');
  if (metricChart) refreshChartTheme();
});

/* Refresh the layout for any sections that were initially hidden */
document.addEventListener('shown.bs.collapse', function(e){
  if(['collapseBoard','collapseChart','collapseTable','collapseParams'].includes(e.target.id)){
    renderAll();
  }
});

/* Activate the small '?' popovers on hover/focus */
document.addEventListener('DOMContentLoaded',()=>{
  [...document.querySelectorAll('[data-bs-toggle="popover"]')].forEach(el=>new bootstrap.Popover(el));
});

/* ----------------------------------------------------------------------------
   FILTER DROPDOWNS
   We populate each dropdown from the unique values in RECORDS.
---------------------------------------------------------------------------- */
function populateFilters(){
  fillSelect('filterDataset', unique(RECORDS.map(r=>r.dataset)));
  fillSelect('filterModel', unique(RECORDS.map(r=>r.model)));
  fillSelect('filterPrompt', unique(RECORDS.map(r=>r.prompt)));
  fillSelect('filterLanguage', unique(RECORDS.flatMap(r=>orderedLanguages(r))));
}
function fillSelect(id, arr){
  const s=document.getElementById(id);
  if (!s) return;
  arr.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; s.appendChild(o); });
}

/* ----------------------------------------------------------------------------
   APPLY FILTERS
   This is the single source of truth for which records are "active".
   It reads the three dropdowns + four slider thresholds and returns
   the filtered list. It also updates the summary text.
---------------------------------------------------------------------------- */
function applyFilters(){
  const d=document.getElementById('filterDataset').value;
  const m=document.getElementById('filterModel').value;
  const p=document.getElementById('filterPrompt').value;
  const lang=document.getElementById('filterLanguage').value;
  const acc=parseFloat(document.getElementById('accThreshold').value);
  const pre=parseFloat(document.getElementById('precThreshold').value);
  const rec=parseFloat(document.getElementById('recThreshold').value);
  const f1=parseFloat(document.getElementById('f1Threshold').value);

  // Keep entries that satisfy ALL chosen filters
  const res=RECORDS
    .filter(r => (!d||r.dataset===d)&&(!m||r.model===m)&&(!p||r.prompt===p))
    .map(r => recordForSelectedLanguage(r, lang))
    .filter(r => r && (r.Accuracy>=acc)&&(r.Precision>=pre)&&(r.Recall>=rec)&&(r.F1>=f1));

  // Readable summary line ("Dataset: X | Acc >= 0.80 | (5/100)")
  const parts=[];
  if(d)parts.push(`Dataset: <b>${d}</b>`);
  if(m)parts.push(`Model: <b>${m}</b>`);
  if(p)parts.push(`Prompt: <b>${p}</b>`);
  if(lang)parts.push(`Language: <b>${lang}</b>`);
  if(acc>0)parts.push(`Acc >= ${acc.toFixed(2)}`);
  if(pre>0)parts.push(`Prec >= ${pre.toFixed(2)}`);
  if(rec>0)parts.push(`Rec >= ${rec.toFixed(2)}`);
  if(f1>0)parts.push(`F1 >= ${f1.toFixed(2)}`);
  parts.push(`<span class='text-secondary ms-2'>(${res.length}/${RECORDS.length} rows)</span>`);
  document.getElementById('filterSummary').innerHTML=parts.join(' | ');

  return res;
}

/* ----------------------------------------------------------------------------
   MASTER RENDER
   This regenerates the chart, leaderboard, and both tables based on filters.
---------------------------------------------------------------------------- */
function renderAll(){
  const data = applyFilters();

  // Chart + leaderboard respond instantly to filters
  renderChart(data);
  renderLeaderboard(data);

  // Tables use a try/catch so minor issues don't block the whole UI
  try {
    if (!resultsTable) {
      renderTable(RECORDS);    // first load uses all records
      initResultsTable();
    } else {
      updateResultsTable(data);
    }
  } catch(e) { console.warn('resultsTable refresh skipped:', e); }

  try {
    if (!detailTable) {
      renderDetails(RECORDS);  // first load uses all predictions
      initDetailTable();
    } else {
      updateDetailTable(data);
    }
  } catch(e) { console.warn('detailTable refresh skipped:', e); }
}

/* ----------------------------------------------------------------------------
   LEADERBOARD
   For each key metric, show the top 3 rows with a small bar.
---------------------------------------------------------------------------- */
function renderLeaderboard(data){
  const body=document.getElementById('leaderboardBody');
  const metrics=[
    {k:'EffectiveF1', label:'Effective F1', c:'#198754'},
    {k:'Coverage', label:'Coverage', c:'#6f42c1'},
    {k:'Accuracy', label:'Accuracy', c:'#0d6efd'},
    {k:'Precision', label:'Precision', c:'#ffc107'},
    {k:'Recall', label:'Recall', c:'#20c997'},
    {k:'F1', label:'F1', c:'#dc3545'},
    {k:'AbstentionRate', label:'Abstention Rate', c:'#fd7e14', lowerIsBetter:true}
  ];
  if(!data.length){ body.innerHTML='<div class="text-muted">No data for leaderboard.</div>'; return; }

  body.innerHTML = metrics.map(({k,label,c,lowerIsBetter})=>{
    const scoreOf = r => lowerIsBetter ? 1 - (r[k] || 0) : (r[k] || 0);
    const sorted=[...data].sort((a,b)=>scoreOf(b)-scoreOf(a)).slice(0,3);
    const maxScore = sorted.length ? scoreOf(sorted[0]) : 1;
    const items = sorted.map((r,i)=>{
      const pct = maxScore>0 ? (scoreOf(r)/maxScore*100) : 0;
      const medal = ['#1','#2','#3'][i] || '';
      return `
        <div class="d-flex align-items-center mb-2">
          <div class="me-2 text-muted small fw-bold" style="width:28px;">${medal}</div>
          <div class="flex-grow-1">
            <div class="d-flex justify-content-between small">
              <div><b>${r.model}</b> <span class="text-muted">(${r.prompt} | ${r.output_protocol} | ${r.parser_mode})</span> <span class="text-muted">[${r.dataset}]</span> <span class="text-muted">[${visibleSampleCount(r)} samples]</span></div>
              <div><b>${roundNum(r[k])}</b></div>
            </div>
            <div class="progress skim">
              <div class="progress-bar" role="progressbar" style="width:${pct.toFixed(1)}%; background:${c};"></div>
            </div>
          </div>
        </div>`;
    }).join('');
    return `
      <div class="col-12 col-lg-6">
        <div class="card h-100">
          <div class="card-header">${label}</div>
          <div class="card-body">${items || '<div class="text-muted small">No entries.</div>'}</div>
        </div>
      </div>`;
  }).join('');
}

/* ----------------------------------------------------------------------------
   RESULTS TABLE (top)
   We first build a cache of all rows, then insert them. DataTables wraps it.
---------------------------------------------------------------------------- */
function buildResultsCache(rows) {{
  return (rows || []).map(r => {{
    const cols = [
      r.dataset,
      r.model,
      r.prompt,
      r.output_protocol || 'verdict_first',
      r.parser_mode || 'full',
      recordStatus(r),
      progressLabel(r),
      recordLanguageSummary(r),
      roundNum(r.Accuracy),
      roundNum(r.Precision),
      roundNum(r.Recall),
      roundNum(r.F1),
      roundNum(r.Coverage),
      roundNum(r.AbstentionRate),
      roundNum(r.EffectiveF1)
    ];
    const cells = [
      cols[0],
      cols[1],
      cols[2],
      cols[3],
      cols[4],
      statusBadge(r),
      progressChip(r),
      cols[7],
      cols[8],
      cols[9],
      cols[10],
      cols[11],
      cols[12],
      cols[13],
      cols[14]
    ];
    // Title attribute provides a quick hover summary
    const html = `
      <tr title="Dataset: ${r.dataset}\nModel: ${r.model}\nPrompt: ${r.prompt}\nProtocol: ${r.output_protocol || 'verdict_first'}\nParser: ${r.parser_mode || 'full'}\nLanguages: ${recordLanguageTooltip(r)}\nSamples: ${visibleSampleCount(r)}\nStatus: ${recordStatus(r)}\nProgress: ${progressLabel(r)}\nAcc: ${roundNum(r.Accuracy)}\nPrec: ${roundNum(r.Precision)}\nRec: ${roundNum(r.Recall)}\nF1: ${roundNum(r.F1)}\nCov: ${roundNum(r.Coverage)}\nAbst: ${roundNum(r.AbstentionRate)}\nEffF1: ${roundNum(r.EffectiveF1)}">
        <td>${cells[0]}</td><td>${cells[1]}</td><td>${cells[2]}</td><td>${cells[3]}</td><td>${cells[4]}</td><td>${cells[5]}</td><td>${cells[6]}</td><td>${cells[7]}</td>
        <td>${cells[8]}</td><td>${cells[9]}</td><td>${cells[10]}</td><td>${cells[11]}</td>
        <td>${cells[12]}</td><td>${cells[13]}</td><td>${cells[14]}</td>
      </tr>`;
    return {
      record: r,
      cols,
      cells,
      html,
      isPartial: !!r.is_partial,
      languages: orderedLanguages(r).map(name => name.toLowerCase()),
      languageLabels: orderedLanguages(r)
    };
  }});
}}

function renderTable(data) {
  const tb = document.getElementById('resultsBody');
  if (!tb) return;
  RESULTS_SOURCE = [...(data || [])];
  RESULTS_ALL = buildResultsCache(RESULTS_SOURCE);
  tb.innerHTML = RESULTS_ALL.map(x => x.html).join('');
}

/* ----------------------------------------------------------------------------
   CHART
   Combine rows that share (model, prompt) by averaging metrics, then
   plot a grouped bar chart with one bar per metric per label.
---------------------------------------------------------------------------- */
let metricChart = null;
function renderChart(data) {
  const ctx = document.getElementById('metricChart');
  if (!ctx) return;

  // If a chart already exists, destroy it so we can rebuild cleanly
  if (metricChart) {
    metricChart.destroy();
  }

  // Group by model+prompt and average metrics
  const groups = {};
  const metricDefs = [
    { key: 'Accuracy', label: 'Accuracy', color: '#0d6efd' },
    { key: 'Precision', label: 'Precision', color: '#ffc107' },
    { key: 'Recall', label: 'Recall', color: '#20c997' },
    { key: 'F1', label: 'F1', color: '#dc3545' },
    { key: 'Coverage', label: 'Coverage', color: '#6f42c1' },
    { key: 'AbstentionRate', label: 'Abstention Rate', color: '#fd7e14' },
    { key: 'EffectiveF1', label: 'Effective F1', color: '#198754' }
  ];

  data.forEach(r => {
    const key = `${r.model}||${r.prompt}||${r.output_protocol || 'verdict_first'}||${r.parser_mode || 'full'}`;
    if (!groups[key]) {
      groups[key] = { ...r, count: 1 };
    } else {
      metricDefs.forEach(({ key: metricKey }) => {
        groups[key][metricKey] = (groups[key][metricKey] || 0) + (r[metricKey] || 0);
      });
      groups[key].count += 1;
    }
  });

  const combined = Object.values(groups).map(g => {
    const row = {
      label: `${g.model} (${g.prompt} | ${g.output_protocol || 'verdict_first'} | ${g.parser_mode || 'full'})`
    };
    metricDefs.forEach(({ key: metricKey }) => {
      row[metricKey] = (g[metricKey] || 0) / g.count;
    });
    return row;
  });

  const stage = document.getElementById('chartStage');
  if (stage) {
    stage.style.width = `${Math.max(1200, combined.length * 150)}px`;
  }

  // If nothing passes the filters, clear the canvas and exit quietly
  if (!combined.length) {
    const g = ctx.getContext('2d');
    g.clearRect(0, 0, ctx.width, ctx.height);
    return;
  }

  // Chart.js expects labels + datasets of numbers
  const labels = combined.map(d => d.label);
  const datasets = metricDefs.map(({ key, label, color }) => ({
    label,
    data: combined.map(d => d[key]),
    backgroundColor: color
  }));

  // Build the bar chart
  metricChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: { top: 8, right: 16, bottom: 8, left: 8 }
      },
      plugins: {
        legend: {
          // Make legend text adapt to Dark vs Light
          labels: { color: getTextColor() },
          // Clicking a legend item toggles that metric on/off
          onClick: (e, legendItem, legend) => {
            const ci = legend.chart;
            const idx = ci.data.datasets.findIndex(ds => ds.label === legendItem.text);
            if (idx >= 0) {
              ci.data.datasets[idx].hidden = !ci.data.datasets[idx].hidden;
              ci.update();
            }
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false
        }
      },
      scales: {
        x: {
          ticks: { color: getTextColor(), maxRotation: 35, minRotation: 20 }
        },
        y: {
          beginAtZero: true,
          max: 1,
          ticks: { color: getTextColor() },
          title: { display: true, text: 'Score', color: getTextColor() }
        }
      }
    }
  });
}

/* Helpers to keep chart colors readable in dark mode */
function getTextColor(){
  return document.documentElement.getAttribute('data-bs-theme')==='dark' ? '#e0e0e0' : '#212529';
}
function refreshChartTheme(){
  if(metricChart){
    metricChart.options.plugins.legend.labels.color = getTextColor();
    metricChart.options.scales.x.ticks.color = getTextColor();
    metricChart.options.scales.y.ticks.color = getTextColor();
    metricChart.options.scales.y.title.color = getTextColor();
    metricChart.update();
  }
}

/* ----------------------------------------------------------------------------
   RESET BUTTON (clears dropdowns and sliders to defaults)
---------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('btn-reset').addEventListener('click', ()=>{
    ['filterDataset','filterModel','filterPrompt','filterLanguage'].forEach(id=>document.getElementById(id).value='');
    [['accThreshold','valAcc'],['precThreshold','valPrec'],['recThreshold','valRec'],['f1Threshold','valF1']]
      .forEach(([sid, lid])=>{
        const s=document.getElementById(sid), l=document.getElementById(lid);
        s.value=0; l.textContent='0.00';
      });
    renderAll();
  });
});

/* ----------------------------------------------------------------------------
   EXPORT BUTTONS
   These let users download CSV, JSON, a PNG snapshot of the chart,
   and a single-page PDF of the entire dashboard. The Glossary PDF
   renders a clean "metrics guide" with formulas and when to use them.
---------------------------------------------------------------------------- */
function exportCSV(){
  const rows=[['Dataset','Model','Prompt','Protocol','Parser','Status','CompletedSamples','TotalSamples','Lang','LangSamples','Acc','Prec','Rec','F1','Coverage','AbstentionRate','EffectiveF1']];
  applyFilters().forEach(r=>rows.push([
    r.dataset,
    r.model,
    r.prompt,
    r.output_protocol || 'verdict_first',
    r.parser_mode || 'full',
    recordStatus(r),
    asInt(r.completed_samples),
    asInt(r.total_samples),
    recordLanguageTooltip(r),
    visibleSampleCount(r),
    r.Accuracy,
    r.Precision,
    r.Recall,
    r.F1,
    r.Coverage,
    r.AbstentionRate,
    r.EffectiveF1
  ]));
  const blob=new Blob([rows.map(x=>x.join(',')).join('\\n')],{type:'text/csv'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='results.csv';a.click();
}
function exportJSON(){
  const blob=new Blob([JSON.stringify(applyFilters(),null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='results.json';a.click();
}
function exportCharts(){
  const canvas=document.getElementById('metricChart');
  html2canvas(canvas).then(c=>{
    const link=document.createElement('a'); link.href=c.toDataURL(); link.download='chart.png'; link.click();
  });
}
function exportPDF(){
  html2canvas(document.body).then(canvas=>{
    const img=canvas.toDataURL('image/png');
    const pdf=new jspdf.jsPDF('p','mm','a4');
    const w=210, h=canvas.height*210/canvas.width;
    pdf.addImage(img,'PNG',0,0,w,h);
    pdf.save('report.pdf');
  });
}

/* Glossary PDF (Color scheme A: PromptAudit blue accents) */
function exportGlossary(){
  const pdf=new jspdf.jsPDF('p','mm','a4');
  // Header bar (blue)
  pdf.setFillColor(13,110,253); // bootstrap primary
  pdf.rect(0,0,210,20,'F');
  pdf.setTextColor(255,255,255);
  pdf.setFontSize(16);
  pdf.text('Metrics Glossary - PromptAudit', 10, 13);
  pdf.setTextColor(0,0,0);
  pdf.setFontSize(12);

  let y=30;
  const section=(title, body)=>{
    pdf.setTextColor(13,110,253); pdf.setFontSize(14); pdf.text(title,10,y); y+=6;
    pdf.setTextColor(0,0,0); pdf.setFontSize(11);
    const split=pdf.splitTextToSize(body, 190);
    pdf.text(split, 10, y);
    y += split.length * 5 + 6;
  };

  // The four core metrics with explanations
  section('Accuracy', 'Proportion of evaluated vulnerable/safe outcomes that were correct. Formula: (TP + TN) / (TP + TN + FP + FN + UnFN).');
  section('Precision', 'Of all samples predicted as vulnerable, how many were correct. Formula: TP / (TP + FP). Use when false positives are costly (e.g., triage load).');
  section('Recall', 'Of all truly vulnerable samples, how many were correctly identified. Formula: TP / (TP + FN + UnFN). Use when missing a vulnerability is costly (safety-critical).');
  section('F1 Score', 'Harmonic mean of Precision and Recall. Formula: 2 * (Precision * Recall) / (Precision + Recall). Use when you need a single score balancing precision and recall.');
  section('Coverage', 'Fraction of samples that received a definitive SAFE or VULNERABLE label. Formula: 1 - Abstention Rate.');
  section('Effective F1', 'Coverage-aware utility score. Formula: F1 * Coverage. High values require both good classification quality and low abstention.');

  pdf.setFontSize(10);
  pdf.setTextColor(110,110,110);
  pdf.text('Generated by PromptAudit', 10, 287);
  pdf.save('metrics_glossary.pdf');
}

// Bind the export buttons to their functions
document.getElementById('btn-export-csv').onclick=exportCSV;
document.getElementById('btn-export-json').onclick=exportJSON;
document.getElementById('btn-export-charts').onclick=exportCharts;
document.getElementById('btn-export-pdf').onclick=exportPDF;
document.getElementById('btn-glossary-pdf').onclick=exportGlossary;

/* ----------------------------------------------------------------------------
   LIVE SLIDERS
   As you drag a slider, the chart + leaderboard update immediately.
   On change, we also call renderAll() as a safety for some browsers.
---------------------------------------------------------------------------- */
['acc','prec','rec','f1'].forEach(x=>{
  const s = document.getElementById(`${x}Threshold`);
  const l = document.getElementById(`val${x.charAt(0).toUpperCase() + x.slice(1)}`);

  // Live update label + chart as you drag
  s.addEventListener('input', () => {
    l.textContent = parseFloat(s.value).toFixed(2);
    renderAll(); // refresh chart & leaderboard as you drag
  });

  // Safety call when you release the slider (some browsers only fire change)
  s.addEventListener('change', renderAll);
});

/* ----------------------------------------------------------------------------
   INITIALIZE
   Populate the dropdowns, wire their 'change' events, then render everything.
---------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', ()=>{
  populateFilters();
  ['filterDataset','filterModel','filterPrompt','filterLanguage'].forEach(id=>{
    document.getElementById(id).addEventListener('change', renderAll);
  });
  // initial render
  renderAll();
});

/* ----------------------------------------------------------------------------
   DETAILED TABLE (per-sample)
   We rebuild a cache (DETAILS_ALL) of all possible rows so column filters
   can enumerate values reliably even when top filters change.
---------------------------------------------------------------------------- */
function buildDetailRows(data) {{
  let total = 0;
  const rows = [];

  (data || []).forEach(rec => {{
    (rec.predictions || []).forEach(p => {
      total++;
      const isCorrect = p.gold === p.pred;
      const predBubble = p.pred === "safe"
        ? `<span class="sv-pill sv-safe">SAFE</span>`
        : p.pred === "vulnerable"
          ? `<span class="sv-pill sv-vuln">VULNERABLE</span>`
          : `<span class="sv-pill text-muted">UNKNOWN</span>`;

      const goldBubble = p.gold === "safe"
        ? `<span class="sv-pill sv-safe">SAFE</span>`
        : p.gold === "vulnerable"
          ? `<span class="sv-pill sv-vuln">VULNERABLE</span>`
          : `<span class="sv-pill text-muted">UNKNOWN</span>`;
      const icon = isCorrect ? "Yes" : "No";
      const lang = p.language || rec.language || "-";

      // The `cols` array holds plain text per column for filtering.
      // The `html` string is the actual row we inject into the table.
      const cols = [
        p.id,
        rec.dataset,
        rec.output_protocol || "verdict_first",
        rec.parser_mode || "full",
        lang,
        rec.model,
        rec.prompt,
        (p.pred || "").toUpperCase(),
        (p.gold || "").toUpperCase(),
        icon
      ];
      const html = `
        <tr>
          <td>${cols[0]}</td>
          <td>${cols[1]}</td>
          <td>${cols[2]}</td>
          <td>${cols[3]}</td>
          <td>${cols[4]}</td>
          <td>${cols[5]}</td>
          <td>${cols[6]}</td>
          <td>${predBubble}</td>
          <td>${goldBubble}</td>
          <td>${cols[9]}</td>
        </tr>`;
      rows.push({
        cols,
        html,
        cells: [
          cols[0],
          cols[1],
          cols[2],
          cols[3],
          cols[4],
          cols[5],
          cols[6],
          predBubble,
          goldBubble,
          cols[9]
        ]
      });
    });
  }});

  return { rows, total };
}}

function renderDetails(data){
  const tbody = document.getElementById('detailsBody');
  if(!tbody) return;

  DETAILS_SOURCE = [...(data || [])];
  const detailState = buildDetailRows(DETAILS_SOURCE);
  DETAILS_ALL = detailState.rows;
  tbody.innerHTML = DETAILS_ALL.map(x => x.html).join("") || "<tr><td colspan='10' class='text-muted'>No predictions available.</td></tr>";
  const dc = document.getElementById('detailCount');
  if(dc) dc.textContent = `Showing ${detailState.total} predictions`;
}

/* ----------------------------------------------------------------------------
   COLUMN FILTER ROWS (per-table)
   We add a second header row of <select> menus that filter by exact match.
   This works WITH pagination safely by using the DataTables API to redraw.
---------------------------------------------------------------------------- */
function addColumnFilters(tableSelector, instance) {
  const tableEl = document.querySelector(tableSelector);
  if (!tableEl) return;
  const thead = tableEl.querySelector("thead");
  if (!thead) return;

  const active = tableSelector === "#results-table" ? resultsActive : detailsActive;
  const bag = tableSelector === "#results-table" ? RESULTS_ALL : DETAILS_ALL;

  // Remove old filter row if present (so we can rebuild cleanly)
  const old = thead.querySelector(".column-filters");
  if (old) old.remove();

  const filterRow = document.createElement("tr");
  filterRow.className = "column-filters";

  const headerCells = thead.querySelectorAll("th");

  headerCells.forEach((th, colIndex) => {
    const cell = document.createElement("th");

    // Skip numeric metric columns in the Results table (keep filters to text cols)
    if (tableSelector === "#results-table" && colIndex >= 8) {
      filterRow.appendChild(cell);
      return;
    }

    const select = document.createElement("select");
    select.className = "form-select form-select-sm";
    select.innerHTML = `<option value="">All</option>`;

    // Populate unique values from the cached rows.
    // The Lang column on the aggregate results table needs per-language options,
    // not the combined summary string shown in the cell.
    const values = new Set();
    if (tableSelector === "#results-table" && colIndex === 7) {
      bag.forEach(r => (r.languageLabels || []).forEach(name => values.add(name)));
    } else {
      bag.forEach(r => values.add((r.cols[colIndex] || "").toString()));
    }
    [...values].sort().forEach(v => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });

    // Restore previously active choice if we had one
    if (active[colIndex]) {
      const targetVal = active[colIndex]; // stored lowercase
      const matchingOption = [...select.options].find(opt => opt.value.trim().toLowerCase() === targetVal);
      if (matchingOption) {
        select.value = matchingOption.value;
      }
    }

    // When a column filter changes, rebuild the table using only matching rows
    select.addEventListener("change", e => {
      // Store the filter value as lowercase for consistent comparison
      active[colIndex] = e.target.value.trim().toLowerCase();

      const filtered = tableSelector === "#results-table"
        ? buildResultsRowsFromActiveFilters()
        : bag.filter(row =>
            Object.entries(active).every(([idx, val]) => {
              if (!val) return true; // empty = "All"
              const text = (row.cols[idx] || "").toString().trim().toLowerCase();
              return text === val;
            })
          );

      // Use DataTables API for pagination-safe updates
      if (instance && typeof instance.rows === "function") {
        instance.rows().remove();

        // Convert each row's HTML to an array of cell innerHTML strings
        const newRows = filtered.map(r => {
          const div = document.createElement("tbody");
          div.innerHTML = r.html.trim();
          const tr = div.firstElementChild;
          return [...tr.children].map(td => td.innerHTML);
        });

        if (newRows.length > 0) {
          instance.rows().add(newRows);
        }

        // Reset paging and force a layout refresh
        if (typeof instance?.setPage === "function") instance.setPage(1);
        else if (typeof instance?.page === "function") instance.page(1);
        instance.pagination?.update?.();
        instance.update?.();
        instance.refresh?.();

      } else {
        // Fallback: rebuild the tbody manually if the API isn't available
        const tbody = tableEl.querySelector("tbody");
        const colCount = headerCells.length;

        tbody.innerHTML = filtered.map(r => r.html).join("") ||
          `<tr><td colspan='${colCount}' class='text-muted'>No data matches filters.</td></tr>`;
      }

      // Update the little "count" text on the right side of each card header
      if (tableSelector === "#results-table") {
        const totalBag = buildResultsCache(
          (resultsActive[7] || '').trim()
            ? RESULTS_SOURCE.map(r => recordForSelectedLanguage(r, resultsActive[7])).filter(Boolean)
            : RESULTS_SOURCE
        );
        setRecordCount(filtered.length, totalBag.length, filtered.filter(r => r.isPartial).length);
      } else {
        const dc = document.getElementById('detailCount');
        if (dc) dc.textContent = `Showing ${filtered.length} predictions`;
      }
    });

    cell.appendChild(select);
    filterRow.appendChild(cell);
  });

  thead.appendChild(filterRow);
}

function buildResultsRowsFromActiveFilters() {
  let source = [...RESULTS_SOURCE];
  const languageFilter = (resultsActive[7] || '').trim().toLowerCase();

  if (languageFilter) {
    source = source.map(r => recordForSelectedLanguage(r, languageFilter)).filter(Boolean);
  }

  const bag = buildResultsCache(source);
  return bag.filter(row =>
    Object.entries(resultsActive).every(([idx, val]) => {
      if (!val) return true;
      if (Number(idx) === 7) return true;
      const text = (row.cols[idx] || "").toString().trim().toLowerCase();
      return text === val;
    })
  );
}

/* ----------------------------------------------------------------------------
   RESET COLUMN FILTERS (per-table)
   Clears the little header selects and redraws all rows on page 1.
---------------------------------------------------------------------------- */
function resetColumnFilters(tableSelector, instance, activeMap) {
  const thead = document.querySelector(`${tableSelector} thead`);
  const selects = thead?.querySelectorAll(".column-filters select") || [];
  selects.forEach(sel => sel.value = "");
  Object.keys(activeMap).forEach(k => delete activeMap[k]);

  const bag = tableSelector === "#results-table" ? RESULTS_ALL : DETAILS_ALL;

  // ******** THIS IS THE FIX ********
  // Use the same refresh logic as addColumnFilters for pagination safety.
  if (instance && typeof instance.rows === "function") {
    instance.rows().remove();

    const allRows = bag.map(r => {
      const div = document.createElement("tbody");
      div.innerHTML = r.html.trim();
      const tr = div.firstElementChild;
      return [...tr.children].map(td => td.innerHTML);
    });

    if (allRows.length > 0) {
      instance.rows().add(allRows);
    }

    if (typeof instance?.setPage === "function") instance.setPage(1);
    else if (typeof instance?.page === "function") instance.page(1);
    instance.pagination?.update?.();
    instance.update?.();
    instance.refresh?.();

  } else {
    // Fallback: plain rebuild
    const tbody = document.querySelector(`${tableSelector} tbody`);
    const colCount = thead.querySelectorAll("th").length;

    tbody.innerHTML = bag.map(x => x.html).join("") ||
      `<tr><td colspan='${colCount}' class='text-muted'>No predictions available.</td></tr>`;
  }

  // Update counters
  if (tableSelector === "#results-table") {
    setRecordCount(bag.length, RESULTS_ALL.length, bag.filter(r => r.isPartial).length);
  } else {
    const dc = document.getElementById('detailCount');
    if (dc) dc.textContent = `Showing ${bag.length} predictions`;
  }
}

/* ----------------------------------------------------------------------------
   DATATABLE INITIALIZATION (top results table)
---------------------------------------------------------------------------- */
function initResultsTable() {
  // If an existing datatable instance exists, clean it up first
  if (resultsTable) {
    try { resultsTable.destroy(); } catch (e) { /* ignore if already destroyed */ }
    resultsTable = null;
  }

  // Create a fresh simple-datatables instance
  resultsTable = new simpleDatatables.DataTable("#results-table", {
    searchable: true,      // search box in the header
    sortable: true,        // allow in-browser sorting after language filtering
    fixedHeight: false,    // allow table to grow naturally
    perPage: 10,           // default rows per page
    perPageSelect: [5,10,25,50,100] // allow user to change page size
  });

  // Rebuild the second header row with column selects
  setTimeout(() => addColumnFilters("#results-table", resultsTable), 50);

  // Initialize the count label immediately
  setRecordCount(RESULTS_ALL.length, RESULTS_ALL.length, RESULTS_ALL.filter(r => r.isPartial).length);
}

/* ----------------------------------------------------------------------------
   DATATABLE INITIALIZATION (bottom detailed table)
---------------------------------------------------------------------------- */
function initDetailTable() {
  if (detailTable) {
    detailTable.destroy();
    detailTable = null;
  }
  detailTable = new simpleDatatables.DataTable("#details-table", {
    searchable: true,
    sortable: true,
    fixedHeight: false,
    perPage: 10,
    perPageSelect: [5,10,25,50,100]
  });

  setTimeout(() => addColumnFilters("#details-table", detailTable), 50);

  // Initialize the detail count immediately
  const dc = document.getElementById('detailCount');
  if (dc) dc.textContent = `Showing ${DETAILS_ALL.length} predictions`;
}

/* ----------------------------------------------------------------------------
   UPDATE RESULTS TABLE (top) AFTER FILTERS CHANGE
---------------------------------------------------------------------------- */
function updateResultsTable(data) {
  if (!resultsTable) return;
  updatePartialSummary(data);
  Object.keys(resultsActive).forEach(k => delete resultsActive[k]);
  RESULTS_SOURCE = [...(data || [])];
  RESULTS_ALL = buildResultsCache(RESULTS_SOURCE);
  const newRows = RESULTS_ALL.map(r => r.cells);

  resultsTable.rows().remove();
  if (newRows.length) resultsTable.rows().add(newRows);
  if (typeof resultsTable?.setPage === "function") resultsTable.setPage(1);
  else if (typeof resultsTable?.page === "function") resultsTable.page(1);
  resultsTable.pagination?.update?.();
  resultsTable.update?.();
  resultsTable.refresh?.();
  setTimeout(() => addColumnFilters("#results-table", resultsTable), 0);

  // Update the "Showing X / Y" label
  setRecordCount(newRows.length, RESULTS_ALL.length, data.filter(r => r.is_partial).length);
}

/* ----------------------------------------------------------------------------
   UPDATE DETAILED TABLE (bottom) AFTER FILTERS CHANGE
---------------------------------------------------------------------------- */
function updateDetailTable(data) {
  if (!detailTable) return;
  Object.keys(detailsActive).forEach(k => delete detailsActive[k]);
  DETAILS_SOURCE = [...(data || [])];
  const detailState = buildDetailRows(DETAILS_SOURCE);
  DETAILS_ALL = detailState.rows;
  const newRows = DETAILS_ALL.map(r => r.cells);

  detailTable.rows().remove();
  if (newRows.length) detailTable.rows().add(newRows);
  if (typeof detailTable?.setPage === "function") detailTable.setPage(1);
  else if (typeof detailTable?.page === "function") detailTable.page(1);
  detailTable.pagination?.update?.();
  detailTable.update?.();
  detailTable.refresh?.();
  setTimeout(() => addColumnFilters("#details-table", detailTable), 0);

  // Update the "Showing N predictions" label
  const dc = document.getElementById('detailCount');
  if (dc) dc.textContent = `Showing ${detailState.total} predictions`;
}

/* ----------------------------------------------------------------------------
   RESET BUTTONS FOR COLUMN FILTERS (top & bottom tables)
---------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  const btnRes = document.getElementById("resetResultsFilters");
  const btnDet = document.getElementById("resetDetailsFilters");

  btnRes?.addEventListener("click", () => {
    if (resultsTable) resetColumnFilters("#results-table", resultsTable, resultsActive);
  });

  btnDet?.addEventListener("click", () => {
    if (detailTable) resetColumnFilters("#details-table", detailTable, detailsActive);
  });

  updatePartialSummary(RECORDS);
});
</script>
</body>
</html>
"""

        # ---- Safe format: escape, then reinsert slots ----
        # The curly braces `{}` have special meaning for Python's .format().
        # Because our HTML/CSS/JS also contains many braces, we first escape
        # ALL of them by doubling ({{ and }}), then "un-escape" only the
        # placeholders we want to fill (version, gen_when, author, etc.).
        safe_html = (
            html.replace("{", "{{").replace("}", "}}")
                .replace("{{version}}", "{version}")
                .replace("{{gen_when}}", "{gen_when}")
                .replace("{{author}}", "{author}")
                .replace("{{param_table}}", "{param_table}")
                .replace("{{json_records}}", "{json_records}")
        ).format(
            version=version,                 # e.g., "v2.0"
            gen_when=gen_when,               # time for header
            author=author,                   # displayed under the title
            param_table=build_param_rows(params),  # small HTML table of params
            json_records=json.dumps(records, ensure_ascii=False)  # embed data as JSON
        )

        # The template still contains some hand-escaped double braces in CSS/HTML.
        # Collapse those leftovers after formatting so the emitted HTML uses
        # normal braces and validates cleanly in browsers/editors.
        safe_html = safe_html.replace("{{", "{").replace("}}", "}")

        # Normalize legacy mojibake that can still leak through old template
        # fragments or browser-cached report snippets.
        replacements = {
            "â€”": "-",
            "â€“": "-",
            "â€¦": "...",
            "â€™": "'",
            "â€œ": '"',
            "â€": '"',
            "Â·": " | ",
            "â‰¥": ">=",
            "Ã¢â‚¬â€": "-",
            "ðŸ”§ ": "",
            "ðŸ† ": "",
            "ðŸ”Ž ": "",
            "ðŸ“ˆ ": "",
            "ðŸ—‚ ": "",
            "ðŸ”¬ ": "",
            "ðŸ¥‡": "#1",
            "ðŸ¥ˆ": "#2",
            "ðŸ¥‰": "#3",
            "âœ…": "Yes",
            "âŒ": "No",
        }
        for old, new in replacements.items():
            safe_html = safe_html.replace(old, new)

        # Finally, write the finished HTML string to disk.
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(safe_html)
        print(f"[HTML Report] Dashboard saved to {output_path} ({version})")
