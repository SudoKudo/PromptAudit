"""Render the interactive HTML report for a PromptAudit run."""

import os
import json
from datetime import datetime
from html import escape

from core import __version__
from .metrics import DEFAULT_METRICS, METRIC_HELP, refresh_record_accuracy
from utils.privacy import safe_settings


REPORT_METRICS = {
    "Accuracy": "Acc", "Precision": "Prec", "Recall": "Rec", "F1": "F1",
    "Coverage": "Cov", "AbstentionRate": "Abst", "EffectiveF1": "EffF1",
}


def _without_response_text(value):
    """Reports use compact diagnostics; raw model text stays in run artifacts."""
    private_fields = {"raw_output", "raw_response", "thinking_output", "response_preview",
                      "response_text_preview", "error_message", "prompt_text"}
    if isinstance(value, dict):
        return {key: _without_response_text(item) for key, item in value.items() if key not in private_fields}
    if isinstance(value, list):
        return [_without_response_text(item) for item in value]
    return value


class HtmlReport:
    """Write classification scores, diagnostics, and per-sample results."""

    def __init__(self, results):
        self.results = results

    def write(self, output_path, records, version=f"v{__version__}",
              author="PromptAudit"):
        metric_names = list(DEFAULT_METRICS)
        records = [refresh_record_accuracy(record) for record in safe_settings(_without_response_text(records))]
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        analysis_link = (
            '<p class="mb-3"><a href="analysis_report.html">Open statistical, prevalence, parser, and dataset analyses</a></p>'
            if os.path.exists(os.path.join(output_dir, "analysis_report.html")) else ""
        )
        if os.path.exists(os.path.join(output_dir, "paper", "index.html")):
            analysis_link += ('<p class="mb-3"><a href="paper/index.html">Open paper tables and full-precision exports</a>. '
                              'Use these saved Python calculations for manuscript values. '
                              'Language filters below provide an exploratory view.</p>')
        if any(record.get("pilot") for record in records):
            analysis_link = '<p class="mb-3">Pilot / smoke-test results for checking the workflow.</p>' + analysis_link

        # ---- Helpers ---------------------------------------------------------
        def sniff_params(rs):
            """Read generation settings from current records or older flat records."""
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
        gen_when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def build_param_rows(p):
            """Format recorded settings, or state that none were recorded."""
            if not p:
                return "<div class='text-muted small'>No parameters recorded.</div>"
            rows = []
            for k, v in p.items():
                if isinstance(v, float):
                    v = f"{v:.3f}"
                elif isinstance(v, list):
                    v = ", ".join(map(str, v))
                rows.append(f"<tr><th class='text-nowrap'>{escape(str(k))}</th><td>{escape(str(v))}</td></tr>")
            return "<table class='table table-sm table-bordered w-auto'><tbody>{}</tbody></table>".format("".join(rows))

        def parameter_sections():
            groups = {}
            for record in records:
                params = sniff_params([record])
                key = json.dumps(params, sort_keys=True)
                group = groups.setdefault(key, {"params": params, "models": set(), "combinations": 0})
                group["models"].add(str(record.get("model", "Unknown model")))
                group["combinations"] += 1
            sections = []
            for group in groups.values():
                scope = ", ".join(sorted(group["models"]))
                sections.append(f"<details><summary>{escape(scope)} ({group['combinations']} combinations)</summary>"
                                + build_param_rows(group["params"]) + "</details>")
            return "".join(sections) or build_param_rows({})

        metric_thresholds = "".join(
            f'<div class="col"><label class="small" for="threshold-{key}" title="{escape(METRIC_HELP[key])}">'
            f'{"Maximum" if key == "AbstentionRate" else "Minimum"} {key.replace("AbstentionRate", "Abstention rate").replace("EffectiveF1", "Effective F1")} '
            f'(<span id="threshold-value-{key}">{"1.00" if key == "AbstentionRate" else "0.00"}</span>)</label>'
            f'<input type="range" id="threshold-{key}" min="0" max="1" step="0.01" '
            f'value="{1 if key == "AbstentionRate" else 0}" class="form-range"></div>' for key in metric_names)

        # Keep fallback styles and table controls usable without the CDN libraries.
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
  background: linear-gradient(135deg, #174878, #0b2a62 55%, #2566a5);
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
#details-table .detail-sort { background:transparent; border:0; color:inherit; padding:0; }
#details-table [aria-sort="ascending"] .detail-sort::after { content:" ▲"; }
#details-table [aria-sort="descending"] .detail-sort::after { content:" ▼"; }

/* Keep the numeric report usable when optional CDN assets are unavailable. */
body { margin:0; line-height:1.45; }
.container { width:min(1500px, calc(100% - 32px)); margin:0 auto; }
.row { display:flex; flex-wrap:wrap; gap:1rem; }
.col { flex:1 1 160px; min-width:0; }
.col-auto { flex:0 0 auto; }
.col-12 { width:100%; }
.d-flex { display:flex; flex-wrap:wrap; gap:.5rem; }
.justify-content-between { justify-content:space-between; }
.align-items-center { align-items:center; }
.accordion-item { margin-bottom:1rem; border:1px solid #dce4ee; border-radius:8px; overflow:hidden; }
.accordion-header { margin:0; }
.accordion-button { width:100%; padding:.9rem 1rem; text-align:left; border:0; font:inherit; font-weight:600; cursor:pointer; background:#e8f0fa; color:#16263b; }
[data-bs-theme="dark"] .accordion-button { background:#182b42; color:#e0e0e0; }
.accordion-body, .card-body { padding:1rem; }
.accordion-collapse:not(.show) { display:none; }
.card { border:1px solid #dce4ee; border-radius:6px; }
.card-header { padding:.6rem 1rem; font-weight:600; }
.table-responsive { overflow:auto; max-height:38rem; }
.table { border-collapse:collapse; width:100%; margin:.5rem 0; }
.table th, .table td { padding:.45rem .6rem; border:1px solid #dce4ee; vertical-align:top; }
.table thead th { position:sticky; top:0; z-index:1; }
.table td { overflow-wrap:anywhere; }
.small { font-size:.875rem; }
.text-muted { color:#5c6878; }
.d-none, [hidden] { display:none !important; }
.form-select { width:100%; padding:.35rem; min-width:100px; }
.form-range { width:100%; }
button { font:inherit; padding:.35rem .65rem; }
button:focus-visible, select:focus-visible, input:focus-visible { outline:3px solid #79adff; outline-offset:2px; }
.header-gradient { padding:1.5rem 0; margin-bottom:1rem; }
.header-gradient .container { gap:1rem; }
.header-gradient h1 { margin:0 0 .3rem; }
.header-title, .header-subtitle { text-shadow:0 1px 2px #153255; }
details { margin-bottom:.8rem; }
summary { cursor:pointer; font-weight:600; }
@media(min-width:992px) { .col-lg-6 { width:calc(50% - .5rem); } }
@media(max-width:640px) { .container { width:calc(100% - 16px); } .accordion-body { padding:.6rem; } }
@media print {
  body, [data-bs-theme="dark"] body { background:#fff; color:#000; }
  button, .form-range, .column-filters, .detail-controls, #collapseFilters, .datatable-top, .datatable-bottom { display:none !important; }
  #details-table .detail-sort { display:inline !important; }
  .accordion-collapse { display:block !important; }
  .table-responsive { overflow:visible; max-height:none; }
  .table thead th { position:static; }
  .accordion-item { overflow:visible; break-inside:auto; }
  .container { width:100%; }
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
      <button id="btn-export-charts" title="Export the current chart page as an image" class="btn btn-sm btn-outline-success btn-export">Chart PNG</button>
      <button id="btn-export-pdf" title="Print this report or save a multi-page PDF" class="btn btn-sm btn-outline-danger btn-export">Print / PDF</button>
      <button id="btn-glossary-pdf" class="btn btn-sm btn-primary btn-export">Glossary</button>
    </div>
  </div>
</div>

<div class="container pb-4">

  {analysis_link}

  <!--
    MAIN ACCORDION
    Sections open independently, without data-bs-parent.
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
            <div class="col"><select id="filterDataset" aria-label="Dataset" class="form-select form-select-sm"><option value="">All Datasets</option></select></div>
            <div class="col"><select id="filterModel" aria-label="Model" class="form-select form-select-sm"><option value="">All Models</option></select></div>
            <div class="col"><select id="filterPrompt" aria-label="Prompt approach" class="form-select form-select-sm"><option value="">All Prompts</option></select></div>
            <div class="col"><select id="filterProtocol" aria-label="Verdict protocol" class="form-select form-select-sm"><option value="">All Protocols</option></select></div>
            <div class="col"><select id="filterParser" aria-label="Parser mode" class="form-select form-select-sm"><option value="">All Parsers</option></select></div>
            <div class="col"><select id="filterLanguage" aria-label="Language" class="form-select form-select-sm"><option value="">All Languages</option></select></div>
            <div class="col-auto"><button id="btn-reset" class="btn btn-sm btn-outline-secondary">Reset</button></div>
          </div>

          <div class="row mt-3 g-3 align-items-center" id="metricThresholds">
            {metric_thresholds}
          </div>

          <!-- Summary text updates as filters move -->
          <div id="filterSummary" class="mt-2 small text-muted"></div>
        </div>
      </div>
    </div>

    <!-- Chart -->
    <!-- Page through condition scores without merging different datasets. -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingChart">
        <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseChart" aria-expanded="true" aria-controls="collapseChart">
          Unified Metrics Chart
        </button>
      </h2>
      <div id="collapseChart" class="accordion-collapse collapse show" aria-labelledby="headingChart">
        <div class="accordion-body">
          <p id="chartNotice" class="small text-muted" hidden>Charts are unavailable because the chart library did not load. Numeric results remain available below.</p>
          <div class="d-flex align-items-center justify-content-between mb-2">
            <span id="chartPageStatus" class="small" aria-live="polite"></span>
            <div><button id="chartPrevious" type="button">Previous chart page</button>
            <button id="chartNext" type="button">Next chart page</button></div>
          </div>
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
                      {metric_headers}
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

    <div class="accordion-item">
      <h2 class="accordion-header"><button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseDiagnostics" aria-expanded="true" aria-controls="collapseDiagnostics">Execution and generation diagnostics</button></h2>
      <div id="collapseDiagnostics" class="accordion-collapse collapse show"><div class="accordion-body">
        <p class="small text-muted">Classification counts and parse tiers follow the selected language. Execution counts and elapsed time describe the recorded combination and session. Parser replay and cached responses can avoid fresh generation. Language filters do not prorate these measurements.</p>
        <div class="table-responsive"><table id="execution-table" class="table table-sm table-bordered small"><thead><tr>
          <th>Dataset</th><th>Model</th><th>Prompt</th><th>Protocol</th><th>Parser</th>
          <th title="UNKNOWN predictions, including unresolved or failed responses.">UNKNOWN</th>
          <th title="Vulnerable samples with an unresolved prediction.">Vulnerable abstentions</th>
          <th title="SAFE samples with an unresolved prediction.">SAFE abstentions</th>
          <th title="Maximum client requests running concurrently.">Workers</th>
          <th title="Fresh model executions in this combination and session.">Fresh calls</th>
          <th title="Raw responses replayed from this run's recorded cache.">Within-run reuse</th>
          <th title="Matching responses reused across experiment types in this batch.">Batch reuse</th>
          <th title="Responses reused from the shared cache across runs.">Cross-run hits</th>
          <th title="Elapsed time spent on this combination in the recorded session. It includes cache lookup and parsing.">Elapsed seconds</th>
          <th title="Sum of time spent on fresh model executions. Concurrent calls overlap, so this can exceed elapsed time.">Fresh generation seconds</th>
          <th>Parse tiers</th>
        </tr></thead><tbody id="executionBody"></tbody></table></div>
        <h3 class="h6">Decision cost and completion</h3>
        <p class="small text-muted">Decision cost includes all requested draws used by the voting rule and their original recorded generation cost, including reused responses. It is separate from fresh executions and elapsed time above. These means follow the selected language.</p>
        <div class="table-responsive"><table id="decision-table" class="table table-sm table-bordered small"><thead><tr>
          <th>Dataset</th><th>Model</th><th>Prompt</th><th>Protocol</th><th>Parser</th>
          <th title="Mean requested calls used by each decision, including failed and unresolved draws.">Calls / sample</th>
          <th title="Mean sum of original generation times across the decision calls. Cached times are not the current elapsed time.">Recorded seconds / sample</th>
          <th>Input tokens / sample</th><th>Output tokens / sample</th><th>Distinct responses / pool</th>
          <th title="Fraction of decision calls that reached their output cap. Requires complete backend measurements.">Output-limit hit rate</th>
          <th title="Fraction of sample decisions with complete output-limit measurements.">Limit measurement coverage</th>
          <th>Errors / sample</th>
        </tr></thead><tbody id="decisionBody"></tbody></table></div>
        <p class="small text-muted">Unavailable measurements are shown as unavailable. Anomaly samples alone are not a complete count of failures or capped outputs.</p>
      </div></div>
    </div>

    <!-- Detailed Model Predictions -->
    <!-- Bottom table: one row per prediction (per sample) -->
    <div class="accordion-item">
      <h2 class="accordion-header" id="headingDetailed">
        <button class="accordion-button" type="button"
                data-bs-toggle="collapse" data-bs-target="#collapseDetailed"
                aria-expanded="true" aria-controls="collapseDetailed">
          Detailed Model Predictions
        </button>
      </h2>
      <div id="collapseDetailed" class="accordion-collapse collapse show"
          aria-labelledby="headingDetailed">
        <div class="accordion-body">
          <div class="card">
            <div class="card-header d-flex justify-content-between align-items-center">
              <span>Per-Sample Results</span>
              <div class="d-flex align-items-center gap-2">
                <button id="resetDetailsFilters" class="btn btn-sm btn-outline-secondary"
                title="Clear all column filters">Reset Filters</button>
                <span id="detailCount" class="text-muted small" aria-live="polite"></span>
              </div>
            </div>
            <div class="card-body">
                <div class="detail-controls d-flex align-items-center gap-2">
                  <label for="detailSearch">Search predictions</label>
                  <input id="detailSearch" type="search" aria-controls="details-table">
                  <label for="detailPageSize">Rows per page</label>
                  <select id="detailPageSize" aria-controls="details-table">
                    <option>5</option><option selected>10</option><option>25</option>
                    <option>50</option><option>100</option>
                  </select>
                  <button id="detailPrevious" type="button" aria-controls="details-table">Previous page</button>
                  <button id="detailNext" type="button" aria-controls="details-table">Next page</button>
                </div>
                <div class="table-responsive">
                    <table id="details-table" class="table table-sm table-hover table-bordered small align-middle">
                    <thead class="table-light">
                        <tr>
                        <th scope="col"><button type="button" class="detail-sort">ID</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Dataset</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Protocol</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Parser</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Lang</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Model</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Prompt</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Predicted</button></th>
                        <th scope="col"><button type="button" class="detail-sort">True</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Correct?</button></th>
                        <th scope="col"><button type="button" class="detail-sort">CVE</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Pair</button></th>
                        <th scope="col"><button type="button" class="detail-sort">Parse tier</button></th>
                        </tr>
                    </thead>
                    <tbody id="detailsBody"></tbody>
                    </table>
                </div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div> <!-- /accordion -->

  <details id="metric-definitions"><summary>Metric definitions</summary>
    {metric_glossary}
  </details>

</div> <!-- /container -->

<script>
/* ----------------------------------------------------------------------------
   DATA INGEST
   RECORDS is the raw JSON version of your Python `records` list dumped below.
---------------------------------------------------------------------------- */
const RECORDS = {json_records};
const METRIC_NAMES = {json_metrics};
const METRIC_HELP = {json_metric_help};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

// Filters apply to all table pages.
let resultsTable = null;  // DataTable instance for the top table

let RESULTS_ALL = [];  // [{cols:[...], html:"<tr>...</tr>"}]
let DETAILS_ALL = [];  // plain columns for filtering the full set
let DETAILS_MATCHED = [];
let RESULTS_SOURCE = [];  // current top-level filtered records backing the results table
let detailPage = 0;
let detailPageSize = 10;
let detailSortColumn = null;
let detailSortDirection = 1;
const detailSort = new Intl.Collator(undefined, { numeric:true, sensitivity:'base' });

// Column filter state maps (per-table)
const resultsActive = {}; // {colIndex: "value"}
const detailsActive = {};

/* Tiny helpers: round numbers, deduplicate arrays */
function roundNum(n){return Number.isFinite(n)?n.toFixed(3):'Unavailable';}
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
  const total = totals.TP + totals.TN + totals.FP + totals.FN + totals.UnFN + totals.Incorrect;
  totals.Accuracy = total ? (totals.TP + totals.TN) / total : 0;
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
    const language = (p?.language || record?.language || 'unknown').toString().trim().toLowerCase() || 'unknown';
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
    language_sample_count: filteredPredictions.length,
    parse_tier_counts: filteredPredictions.reduce((counts,prediction)=>{
      const tier=prediction.parse_tier || 'unknown'; counts[tier]=(counts[tier] || 0)+1; return counts;
    },{})
  }};
}}
function collectLanguageCounts(r){{
  if (r && r.language_counts && typeof r.language_counts === 'object') {{
    return r.language_counts;
  }}
  const counts = {{}};
  (r?.predictions || []).forEach(p => {{
    const lang = (p?.language || r?.language || 'unknown').toString().trim() || 'unknown';
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
    `<code>${escapeHtml(r.model)} / ${escapeHtml(r.prompt)} / ${escapeHtml(r.output_protocol || 'verdict_first')} / ${escapeHtml(r.parser_mode || 'full')}</code>`
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

function measuredNumber(value) {
  return typeof value==='number' && Number.isFinite(value) ? value : null;
}
function measuredText(value) {
  const number=measuredNumber(value);
  return number===null ? 'Unavailable' : Number.isInteger(number) ? String(number) : number.toFixed(3);
}
function decisionDiagnostics(record) {
  const rows=record.predictions || [];
  const mean=field=>{
    const values=rows.map(row=>measuredNumber(row[field]));
    return values.length && values.every(value=>value!==null) ? values.reduce((a,b)=>a+b,0)/values.length : null;
  };
  const calls=mean('decision_calls'), hits=mean('decision_output_limit_hits');
  return {
    calls_per_sample:calls, seconds_per_sample:mean('decision_seconds'),
    prompt_tokens_per_sample:mean('decision_prompt_tokens'), output_tokens_per_sample:mean('decision_output_tokens'),
    distinct_responses_per_pool:mean('distinct_responses'),
    output_limit_hit_rate:calls && hits!==null ? hits/calls : null,
    output_limit_measurement_coverage:rows.length ? rows.filter(row=>measuredNumber(row.decision_output_limit_hits)!==null).length/rows.length : null,
    generation_errors_per_sample:mean('decision_generation_errors')
  };
}
function renderDiagnostics(data) {
  const context=record=>[record.dataset,record.model,record.prompt,record.output_protocol || 'verdict_first',record.parser_mode || 'full'];
  const rowHtml=values=>`<tr>${values.map(value=>`<td>${escapeHtml(value)}</td>`).join('')}</tr>`;
  document.getElementById('executionBody').innerHTML=data.map(record=>{
    const performance=record.inference_performance || {};
    const tiers=record.parse_tier_counts || {};
    return rowHtml([...context(record),...['Unknown','UnFN','Incorrect'].map(key=>measuredText(record[key])),
      ...['workers','generated_calls','run_reuses','batch_cache_hits','shared_cache_hits','wall_seconds','generation_seconds'].map(key=>measuredText(performance[key])),
      Object.keys(tiers).length ? Object.entries(tiers).map(([key,value])=>`${key}: ${value}`).join(', ') : 'Unavailable']);
  }).join('') || '<tr><td colspan="16">No combinations match the filters.</td></tr>';
  document.getElementById('decisionBody').innerHTML=data.map(record=>
    rowHtml([...context(record),...Object.values(decisionDiagnostics(record)).map(measuredText)])
  ).join('') || '<tr><td colspan="13">No combinations match the filters.</td></tr>';
}

/* ----------------------------------------------------------------------------
   THEME HANDLING
   Bootstrap and the fallback styles use the theme attribute on <html>.
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
  [...document.querySelectorAll('[data-bs-toggle="popover"]')].forEach(el=>{
    el.title = el.dataset.bsContent || el.title;
    if(window.bootstrap?.Popover) new bootstrap.Popover(el);
  });
  if(!window.bootstrap) document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(button=>{
    button.addEventListener('click',()=>{
      const section=document.querySelector(button.dataset.bsTarget);
      const open=section.classList.toggle('show');
      button.setAttribute('aria-expanded',String(open));
    });
  });
});

/* ----------------------------------------------------------------------------
   FILTER DROPDOWNS
   Populate dropdowns from the recorded values.
---------------------------------------------------------------------------- */
function populateFilters(){
  fillSelect('filterDataset', unique(RECORDS.map(r=>r.dataset)));
  fillSelect('filterModel', unique(RECORDS.map(r=>r.model)));
  fillSelect('filterPrompt', unique(RECORDS.map(r=>r.prompt)));
  fillSelect('filterProtocol', unique(RECORDS.map(r=>r.output_protocol || 'verdict_first')));
  fillSelect('filterParser', unique(RECORDS.map(r=>r.parser_mode || 'full')));
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
function thresholdValue(key) {
  return Number(document.getElementById(`threshold-${key}`).value);
}
function applyFilters(){
  const d=document.getElementById('filterDataset').value;
  const m=document.getElementById('filterModel').value;
  const p=document.getElementById('filterPrompt').value;
  const protocol=document.getElementById('filterProtocol').value;
  const parser=document.getElementById('filterParser').value;
  const lang=document.getElementById('filterLanguage').value;
  const res=RECORDS
    .filter(r => (!d||r.dataset===d)&&(!m||r.model===m)&&(!p||r.prompt===p)
      &&(!protocol||(r.output_protocol||'verdict_first')===protocol)
      &&(!parser||(r.parser_mode||'full')===parser))
    .map(r => recordForSelectedLanguage(r, lang))
    .filter(r => r && METRIC_NAMES.every(key => {
      const limit=thresholdValue(key), value=r[key];
      if (key==='AbstentionRate') return limit===1 || (Number.isFinite(value) && value<=limit);
      return limit===0 || (Number.isFinite(value) && value>=limit);
    }));
  const parts=[];
  [['Dataset',d],['Model',m],['Prompt',p],['Protocol',protocol],['Parser',parser],['Language',lang]]
    .forEach(([label,value])=>{ if(value) parts.push(`${label}: <b>${escapeHtml(value)}</b>`); });
  METRIC_NAMES.forEach(key=>{
    const limit=thresholdValue(key), maximum=key==='AbstentionRate';
    if(maximum ? limit<1 : limit>0) parts.push(`${key} ${maximum ? '<=' : '>='} ${limit.toFixed(2)}`);
  });
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
  renderDiagnostics(data);

  // Tables use a try/catch so minor issues don't block the whole UI
  try {
    if (!resultsTable) {
      Object.keys(resultsActive).forEach(key=>delete resultsActive[key]);
      renderTable(data);
      initResultsTable();
    } else {
      updateResultsTable(data);
    }
  } catch(e) { console.warn('resultsTable refresh skipped:', e); }

  renderDetails(data);
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
  ].filter(metric => METRIC_NAMES.includes(metric.k));
  if(!data.length){ body.innerHTML='<div class="text-muted">No data for leaderboard.</div>'; return; }

  body.innerHTML = metrics.map(({k,label,c,lowerIsBetter})=>{
    const scoreOf = r => lowerIsBetter ? 1 - (r[k] || 0) : (r[k] || 0);
    const sorted=data.filter(row=>Number.isFinite(row[k])).sort((a,b)=>scoreOf(b)-scoreOf(a)).slice(0,3);
    const maxScore = sorted.length ? scoreOf(sorted[0]) : 1;
    const items = sorted.map((r,i)=>{
      const pct = maxScore>0 ? (scoreOf(r)/maxScore*100) : 0;
      const medal = ['#1','#2','#3'][i] || '';
      return `
        <div class="d-flex align-items-center mb-2">
          <div class="me-2 text-muted small fw-bold" style="width:28px;">${medal}</div>
          <div class="flex-grow-1">
            <div class="d-flex justify-content-between small">
              <div><b>${escapeHtml(r.model)}</b> <span class="text-muted">(${escapeHtml(r.prompt)} | ${escapeHtml(r.output_protocol)} | ${escapeHtml(r.parser_mode)})</span> <span class="text-muted">[${escapeHtml(r.dataset)}]</span> <span class="text-muted">[${visibleSampleCount(r)} samples]</span></div>
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
          <div class="card-header" title="${escapeHtml(METRIC_HELP[k])}">${label}</div>
          <div class="card-body">${items || '<div class="text-muted small">No entries.</div>'}</div>
        </div>
      </div>`;
  }).join('');
}

/* ----------------------------------------------------------------------------
   RESULTS TABLE (top)
   Build rows before DataTables adds pagination.
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
      ...METRIC_NAMES.map(key => roundNum(r[key]))
    ];
    const cells = cols.map(escapeHtml);
    cells[5] = statusBadge(r);
    cells[6] = progressChip(r);
    const summary = [
      `Dataset: ${r.dataset}`, `Model: ${r.model}`, `Prompt: ${r.prompt}`,
      `Protocol: ${r.output_protocol || 'verdict_first'}`, `Parser: ${r.parser_mode || 'full'}`,
      `Languages: ${recordLanguageTooltip(r)}`, `Samples: ${visibleSampleCount(r)}`,
      ...METRIC_NAMES.map(key => `${key}: ${roundNum(r[key])}`)
    ].join(' | ');
    // Title attribute provides a quick hover summary
    const html = `
      <tr title="${escapeHtml(summary)}">
        ${cells.map(cell => `<td>${cell}</td>`).join('')}
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
   Plot a bounded page of condition scores. Tables and exports retain all rows.
---------------------------------------------------------------------------- */
let metricChart = null;
let chartPage = 0;
const CHART_PAGE_SIZE = 12;
function renderChart(data, resetPage = true) {
  const ctx = document.getElementById('metricChart');
  if (!ctx) return;
  if(resetPage) chartPage=0;
  const pageCount=Math.ceil(data.length/CHART_PAGE_SIZE);
  chartPage=Math.max(0,Math.min(chartPage,pageCount-1));
  const start=chartPage*CHART_PAGE_SIZE;
  const pageRows=data.slice(start,start+CHART_PAGE_SIZE);
  const available=typeof Chart==='function';
  document.getElementById('chartPageStatus').textContent=`Chart conditions ${data.length ? start+1 : 0}-${start+pageRows.length} of ${data.length}. Tables and exports retain all filtered conditions.`;
  document.getElementById('chartPrevious').disabled=!available || chartPage===0;
  document.getElementById('chartNext').disabled=!available || chartPage+1>=pageCount;
  document.getElementById('chartNotice').hidden=available;
  document.getElementById('chartStage').hidden=!available;
  if(!available) return;

  // Replace the previous chart instance.
  if (metricChart) {
    metricChart.destroy();
  }

  const metricDefs = [
    { key: 'Accuracy', label: 'Accuracy', color: '#0d6efd' },
    { key: 'Precision', label: 'Precision', color: '#ffc107' },
    { key: 'Recall', label: 'Recall', color: '#20c997' },
    { key: 'F1', label: 'F1', color: '#dc3545' },
    { key: 'Coverage', label: 'Coverage', color: '#6f42c1' },
    { key: 'AbstentionRate', label: 'Abstention Rate', color: '#fd7e14' },
    { key: 'EffectiveF1', label: 'Effective F1', color: '#198754' }
  ].filter(metric => METRIC_NAMES.includes(metric.key));

  // Keep each dataset and parser/protocol condition separate in the chart.
  const combined=pageRows.map(record=>({
    ...record,
    label:`${record.dataset} | ${record.model} (${record.prompt} | ${record.output_protocol || 'verdict_first'} | ${record.parser_mode || 'full'})`
  }));

  const stage = document.getElementById('chartStage');
  if (stage) {
    stage.style.width = `${Math.max(1200, combined.length * 150)}px`;
  }

  // Clear the canvas when no rows match.
  if (!combined.length) {
    const g = ctx.getContext('2d');
    g.clearRect(0, 0, ctx.width, ctx.height);
    return;
  }

  // Chart.js expects labels + datasets of numbers
  const labels = combined.map(d => d.label);
  const datasets = metricDefs.map(({ key, label, color }) => ({
    label,
    data: combined.map(d => Number.isFinite(d[key]) ? d[key] : null),
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
  document.getElementById('chartPrevious').addEventListener('click',()=>{
    if(chartPage>0) { chartPage--; renderChart(applyFilters(),false); }
  });
  document.getElementById('chartNext').addEventListener('click',()=>{
    chartPage++; renderChart(applyFilters(),false);
  });
  document.getElementById('btn-reset').addEventListener('click', ()=>{
    ['filterDataset','filterModel','filterPrompt','filterProtocol','filterParser','filterLanguage'].forEach(id=>document.getElementById(id).value='');
    METRIC_NAMES.forEach(key=>{
      const value=key==='AbstentionRate' ? 1 : 0;
      document.getElementById(`threshold-${key}`).value=value;
      document.getElementById(`threshold-value-${key}`).textContent=value.toFixed(2);
    });
    renderAll();
  });
});

/* ----------------------------------------------------------------------------
   EXPORT BUTTONS
   These let users download CSV, JSON, a PNG snapshot of the chart,
   and a multi-page print/PDF view. The Glossary PDF
   includes metric definitions and formulas.
---------------------------------------------------------------------------- */
function exportCSV(){
  const scores=Object.keys(METRIC_HELP);
  const counts=['TP','TN','FP','FN','UnFN','Incorrect','Unknown'];
  const rows=[['Dataset','Model','Prompt','Protocol','Parser','Status','CompletedSamples','TotalSamples','Lang','LangSamples',...counts,...scores]];
  applyFilters().forEach(r=>rows.push([
    r.dataset,r.model,r.prompt,r.output_protocol || 'verdict_first',r.parser_mode || 'full',
    recordStatus(r),asInt(r.completed_samples),asInt(r.total_samples),recordLanguageTooltip(r),visibleSampleCount(r),
    ...counts.map(key=>r[key]),...scores.map(key=>r[key])
  ]));
  const quote=value=>{ const text=String(value ?? ''); return '"'+text.replace(/"/g,'""')+'"'; };
  const blob=new Blob([rows.map(row=>row.map(quote).join(',')).join('\\n')],{type:'text/csv;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='results.csv';a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function exportJSON(){
  const blob=new Blob([JSON.stringify(applyFilters(),null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='results.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}
function exportCharts(){
  const canvas=document.getElementById('metricChart');
  html2canvas(canvas).then(c=>{
    const link=document.createElement('a'); link.href=c.toDataURL(); link.download='chart.png'; link.click();
  });
}
function exportPDF(){
  const data=applyFilters();
  // Pagination must not silently omit rows from a printed report.
  if(resultsTable) { resultsTable.destroy(); resultsTable=null; }
  document.querySelectorAll('.column-filters').forEach(row=>row.remove());
  renderTable(data);
  renderDetails(data, true);
  window.addEventListener('afterprint',renderAll,{once:true});
  window.print();
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

  METRIC_NAMES.forEach(key => section(key, METRIC_HELP[key]));

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
if(!window.html2canvas) { document.getElementById('btn-export-charts').disabled=true; document.getElementById('btn-export-charts').title='Chart export requires the image export library.'; }
if(!window.jspdf?.jsPDF) { document.getElementById('btn-glossary-pdf').disabled=true; document.getElementById('btn-glossary-pdf').title='Glossary PDF requires the PDF library. Metric explanations are available in the report tooltips.'; }

/* ----------------------------------------------------------------------------
   LIVE SLIDERS
   Update during input; keep the change event for browser compatibility.
---------------------------------------------------------------------------- */
METRIC_NAMES.forEach(key=>{
  const slider=document.getElementById(`threshold-${key}`);
  slider.addEventListener('input',()=>{
    document.getElementById(`threshold-value-${key}`).textContent=Number(slider.value).toFixed(2);
    renderAll();
  });
  slider.addEventListener('change',renderAll);
});

/* ----------------------------------------------------------------------------
   INITIALIZE
   Populate the dropdowns, wire their 'change' events, then render everything.
---------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', ()=>{
  populateFilters();
  ['filterDataset','filterModel','filterPrompt','filterProtocol','filterParser','filterLanguage'].forEach(id=>{
    document.getElementById(id).addEventListener('change', renderAll);
  });
  // initial render
  renderAll();
});

// Keep text for filtering, and build HTML only for rows about to be shown.
function buildDetailRows(data) {
  return (data || []).flatMap(rec => (rec.predictions || []).map(p => {
    const isCorrect = ["safe","vulnerable"].includes(p.gold) && p.gold === p.pred;
    return { cols: [
      p.id, rec.dataset, rec.output_protocol || "verdict_first", rec.parser_mode || "full",
      p.language || rec.language || "-", rec.model, rec.prompt,
      (p.pred || "unknown").toUpperCase(), (p.gold || "unknown").toUpperCase(),
      isCorrect ? "Yes" : "No", p.cve_id || "-", p.pair_id ?? "-", p.parse_tier || "unknown"
    ] };
  }));
}

function detailRowHtml(row) {
  const cells = row.cols.map((value, index) => {
    if (index !== 7 && index !== 8) return escapeHtml(value);
    if (value === "SAFE") return '<span class="sv-pill sv-safe">SAFE</span>';
    if (value === "VULNERABLE") return '<span class="sv-pill sv-vuln">VULNERABLE</span>';
    return '<span class="sv-pill text-muted">UNKNOWN</span>';
  });
  return `<tr>${cells.map(cell => `<td>${cell}</td>`).join('')}</tr>`;
}

function renderDetailPage(printAll = false) {
  const total = DETAILS_MATCHED.length;
  const lastPage = Math.max(0, Math.ceil(total / detailPageSize) - 1);
  detailPage = Math.min(Math.max(0, detailPage), lastPage);
  const start = printAll ? 0 : detailPage * detailPageSize;
  const end = printAll ? total : Math.min(start + detailPageSize, total);
  document.getElementById('detailsBody').innerHTML =
    DETAILS_MATCHED.slice(start, end).map(detailRowHtml).join('') ||
    "<tr><td colspan='13' class='text-muted'>No predictions match the filters.</td></tr>";
  document.getElementById('detailCount').textContent = total
    ? `Showing ${start + 1 === end ? end : `${start + 1}-${end}`} of ${total} ${total === 1 ? 'prediction' : 'predictions'}`
    : "No predictions match the filters";
  document.getElementById('detailPrevious').disabled = detailPage === 0;
  document.getElementById('detailNext').disabled = detailPage === lastPage;
}

function refreshDetailFilters(printAll = false) {
  const selected = Object.entries(detailsActive).filter(([, value]) => value);
  const search = document.getElementById('detailSearch').value.trim().toLowerCase();
  const terms = search ? search.split(/\\s+/) : [];
  DETAILS_MATCHED = DETAILS_ALL.filter(row => {
    if (!selected.every(([idx, value]) => String(row.cols[idx] ?? '').trim().toLowerCase() === value)) {
      return false;
    }
    if (!terms.length) return true;
    const text = row.cols.join(' ').toLowerCase();
    return terms.every(term => text.includes(term));
  });
  if (detailSortColumn !== null) {
    DETAILS_MATCHED.sort((a, b) => detailSortDirection * detailSort.compare(
      String(a.cols[detailSortColumn] ?? ''), String(b.cols[detailSortColumn] ?? '')
    ));
  }
  detailPage = 0;
  renderDetailPage(printAll);
}

function renderDetails(data, printAll = false) {
  Object.keys(detailsActive).forEach(key => delete detailsActive[key]);
  document.getElementById('detailSearch').value = '';
  DETAILS_ALL = buildDetailRows(data);
  refreshDetailFilters(printAll);
  if (!printAll) addColumnFilters('#details-table', null);
}

/* ----------------------------------------------------------------------------
   COLUMN FILTER ROWS (per-table)
   Column menus filter rows by exact match.
   This works WITH pagination safely by using the DataTables API to redraw.
---------------------------------------------------------------------------- */
function replaceTableRows(instance, rows) {
  // simple-datatables v9 exposes rows as a property; insert accepts multiple rows.
  const indexes=instance.data.data.map((_row,index)=>index);
  if(indexes.length) instance.rows.remove(indexes);
  if(rows.length) instance.insert({data:rows});
  instance.page(1);
}

function addColumnFilters(tableSelector, instance) {
  const tableEl = document.querySelector(tableSelector);
  if (!tableEl) return;
  const thead = tableEl.querySelector("thead");
  if (!thead) return;

  const isResults = tableSelector === "#results-table";
  const active = isResults ? resultsActive : detailsActive;
  const bag = isResults ? RESULTS_ALL : DETAILS_ALL;

  // Rebuild the column menus after replacing rows.
  const old = thead.querySelector(".column-filters");
  if (old) old.remove();

  const filterRow = document.createElement("tr");
  filterRow.className = "column-filters";

  const headerCells = thead.querySelectorAll("th");

  headerCells.forEach((th, colIndex) => {
    const cell = document.createElement("th");

    // Skip numeric metric columns in the Results table (keep filters to text cols)
    if (isResults && colIndex >= 8) {
      filterRow.appendChild(cell);
      return;
    }

    const select = document.createElement("select");
    select.className = "form-select form-select-sm";
    select.setAttribute("aria-label", `Filter by ${th.textContent.trim()}`);
    select.innerHTML = `<option value="">All</option>`;

    // Populate unique values from the cached rows.
    // The Lang column on the aggregate results table needs per-language options,
    // not the combined summary string shown in the cell.
    const values = new Set();
    if (isResults && colIndex === 7) {
      bag.forEach(r => (r.languageLabels || []).forEach(name => values.add(name)));
    } else {
      bag.forEach(r => values.add((r.cols[colIndex] ?? "").toString()));
    }
    [...values].sort().forEach(v => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });

    // Keep the current column selection.
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

      if (!isResults) {
        refreshDetailFilters();
        return;
      }
      const filtered = buildResultsRowsFromActiveFilters();

      // Use DataTables API for pagination-safe updates
      if (instance && instance.rows && typeof instance.insert === "function") {
        replaceTableRows(instance,filtered.map(row=>row.cells || (()=>{
          const body=document.createElement('tbody'); body.innerHTML=row.html.trim();
          return [...body.firstElementChild.children].map(cell=>cell.innerHTML);
        })()));
        setTimeout(()=>addColumnFilters(tableSelector,instance),0);

      } else {
        // Fallback: rebuild the tbody manually if the API isn't available
        const tbody = tableEl.querySelector("tbody");
        const colCount = headerCells.length;

        tbody.innerHTML = filtered.map(r => r.html).join("") ||
          `<tr><td colspan='${colCount}' class='text-muted'>No data matches filters.</td></tr>`;
      }

      const totalBag = buildResultsCache(
        (resultsActive[7] || '').trim()
          ? RESULTS_SOURCE.map(r => recordForSelectedLanguage(r, resultsActive[7])).filter(Boolean)
          : RESULTS_SOURCE
      );
      setRecordCount(filtered.length, totalBag.length, filtered.filter(r => r.isPartial).length);
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
      const text = (row.cols[idx] ?? "").toString().trim().toLowerCase();
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

  if (tableSelector === "#details-table") {
    refreshDetailFilters();
    return;
  }
  const bag = RESULTS_ALL;

  // Use the same refresh logic as addColumnFilters for pagination safety.
  if (instance && instance.rows && typeof instance.insert === "function") {
    replaceTableRows(instance,bag.map(row=>row.cells || (()=>{
      const body=document.createElement('tbody'); body.innerHTML=row.html.trim();
      return [...body.firstElementChild.children].map(cell=>cell.innerHTML);
    })()));
    setTimeout(()=>addColumnFilters(tableSelector,instance),0);

  } else {
    // Fallback: plain rebuild
    const tbody = document.querySelector(`${tableSelector} tbody`);
    const colCount = thead.querySelectorAll("th").length;

    tbody.innerHTML = bag.map(x => x.html).join("") ||
      `<tr><td colspan='${colCount}' class='text-muted'>No predictions available.</td></tr>`;
  }

  setRecordCount(bag.length, RESULTS_ALL.length, bag.filter(r => r.isPartial).length);
}

/* ----------------------------------------------------------------------------
   DATATABLE INITIALIZATION (top results table)
---------------------------------------------------------------------------- */
function initResultsTable() {
  if (resultsTable) {
    try { resultsTable.destroy(); } catch (e) { /* ignore if already destroyed */ }
    resultsTable = null;
  }

  if(!window.simpleDatatables?.DataTable) { addColumnFilters('#results-table',null); return; }
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
   UPDATE RESULTS TABLE (top) AFTER FILTERS CHANGE
---------------------------------------------------------------------------- */
function updateResultsTable(data) {
  if (!resultsTable) return;
  updatePartialSummary(data);
  Object.keys(resultsActive).forEach(k => delete resultsActive[k]);
  RESULTS_SOURCE = [...(data || [])];
  RESULTS_ALL = buildResultsCache(RESULTS_SOURCE);
  const newRows = RESULTS_ALL.map(r => r.cells);

  replaceTableRows(resultsTable,newRows);
  setTimeout(() => addColumnFilters("#results-table", resultsTable), 0);

  // Update the "Showing X / Y" label
  setRecordCount(newRows.length, RESULTS_ALL.length, data.filter(r => r.is_partial).length);
}

/* ----------------------------------------------------------------------------
   RESET BUTTONS FOR COLUMN FILTERS (top & bottom tables)
---------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  const btnRes = document.getElementById("resetResultsFilters");
  const btnDet = document.getElementById("resetDetailsFilters");

  btnRes?.addEventListener("click", () => {
    resetColumnFilters("#results-table", resultsTable, resultsActive);
  });

  btnDet?.addEventListener("click", () => {
    resetColumnFilters("#details-table", null, detailsActive);
  });

  document.getElementById('detailSearch').addEventListener('input', () => refreshDetailFilters());
  document.getElementById('detailPageSize').addEventListener('change', event => {
    detailPageSize = Number(event.target.value);
    detailPage = 0;
    renderDetailPage();
  });
  document.getElementById('detailPrevious').addEventListener('click', () => {
    detailPage--;
    renderDetailPage();
  });
  document.getElementById('detailNext').addEventListener('click', () => {
    detailPage++;
    renderDetailPage();
  });
  const detailHeaders = document.querySelectorAll('#details-table .detail-sort');
  detailHeaders.forEach((button, index) => {
    button.addEventListener('click', () => {
      detailSortDirection = detailSortColumn === index ? -detailSortDirection : 1;
      detailSortColumn = index;
      detailHeaders.forEach(header => header.parentElement.removeAttribute('aria-sort'));
      button.parentElement.setAttribute('aria-sort', detailSortDirection === 1 ? 'ascending' : 'descending');
      refreshDetailFilters();
    });
  });

  updatePartialSummary(RECORDS);
});
</script>
</body>
</html>
"""

        # Normalize legacy template braces before inserting data; doing this
        # afterward would corrupt nested JSON objects in the saved records.
        html = html.replace("{{", "{").replace("}}", "}")

        # ---- Safe format: escape, then reinsert slots ----
        # Escape CSS/JavaScript braces, then restore the named template slots.
        safe_html = (
            html.replace("{", "{{").replace("}", "}}")
                .replace("{{version}}", "{version}")
                .replace("{{gen_when}}", "{gen_when}")
                .replace("{{author}}", "{author}")
                .replace("{{analysis_link}}", "{analysis_link}")
                .replace("{{param_table}}", "{param_table}")
                .replace("{{metric_thresholds}}", "{metric_thresholds}")
                .replace("{{metric_glossary}}", "{metric_glossary}")
                .replace("{{json_records}}", "{json_records}")
                .replace("{{metric_headers}}", "{metric_headers}")
                .replace("{{json_metrics}}", "{json_metrics}")
                .replace("{{json_metric_help}}", "{json_metric_help}")
        ).format(
            version=escape(str(version)),
            analysis_link=analysis_link,
            gen_when=gen_when,               # time for header
            author=escape(str(author)),
            param_table=parameter_sections(),  # small HTML table of params
            metric_thresholds=metric_thresholds,
            metric_glossary="<dl>" + "".join(f"<dt>{escape(key)}</dt><dd>{escape(METRIC_HELP[key])}</dd>"
                                               for key in metric_names) + "</dl>",
            json_records=json.dumps(records, ensure_ascii=False).replace("<", "\\u003c").replace("&", "\\u0026"),
            metric_headers="".join(f'<th title="{escape(METRIC_HELP[key])}">{REPORT_METRICS[key]}</th>'
                                   for key in metric_names),
            json_metrics=json.dumps(metric_names),
            json_metric_help=json.dumps(METRIC_HELP),
        )

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
