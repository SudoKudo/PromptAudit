# PromptAudit 3.0

PromptAudit tests how prompts and verdict parsing affect vulnerability classification. It runs code snippets through a language model and records `SAFE`, `VULNERABLE`, or `UNKNOWN` predictions, along with the responses and scores.

## Installation

Install [Python 3.10 or later](https://www.python.org/downloads/) and Git. Clone the repository using its **Code** menu URL.

```bash
git clone <repository-url> PromptAudit
cd PromptAudit
```

Create and activate an environment from the project directory.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS or Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python packages.

```bash
python -m pip install -r requirements.txt
```

The dashboard needs Tkinter and a desktop session. On Debian or Ubuntu, install `python3-venv` and `python3-tk` if needed. If PowerShell blocks activation, run commands with `.venv\Scripts\python.exe` in place of `python`.

## Run the dashboard

Install [Ollama](https://ollama.com/download) and pull a model listed in [config.yaml](config.yaml).

```bash
ollama pull mistral:latest
python run_PromptAudit.py
```

The dashboard connects to Ollama on the same computer at `127.0.0.1:11434`. If Ollama is closed, start the app or run `ollama serve` in another terminal. Run `ollama list` to check the installed tags. You can also launch the dashboard with `run.bat` on Windows or `bash run.sh` on macOS and Linux.

For a first run, choose **Standard prompts**, then select `mistral:latest`, `toy`, and `zero_shot`. Choose `verdict_first` and the `strict` parser, click **Run Selected Experiments**, then open the report from the run monitor.

| Experiment type | What it compares |
| --- | --- |
| Standard prompts | The selected prompting approaches under each verdict order and parser |
| Task wordings | Four classification task sentences with the role, examples, and other instructions held fixed. Select **Reference** for matched comparisons. |
| Components and voting | Example, step-by-step, and adaptive instruction blocks on a common prompt. Voting policies compare decisions from the same pool of saved draws. |

You can select multiple experiment types and datasets in one batch. **Pilot** can limit the number of samples in each dataset. Turn it off to run the full selection. The monitor estimates the fraction of planned requests and processing finished. Wall time depends on the prompts, responses, and backend.

### DGX Spark setup

Follow NVIDIA's [Ollama setup for DGX Spark](https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/ollama/README.md). For Ollama and local CSVs, you can install just the dashboard, YAML, and HTTP packages in the Spark's Python environment.

```bash
python -m pip install "ttkbootstrap>=1.10.1,<2" "PyYAML>=6.0" "requests>=2.31.0"
```

Run the dashboard from the Spark desktop session. Use the [command-line runner](#batch-experiments) for task-wording and component studies over SSH.

### Inference performance

**Inference workers** defaults to one. More than one worker requires Ollama server slots and memory for the selected context window. Run `ollama ps` during a small model run to see where the model is loaded. Keep worker and server settings fixed across matched runs. See [Ollama's concurrency settings](https://docs.ollama.com/faq#how-does-ollama-handle-concurrent-requests).

Experiments in one batch reuse responses when the model, full prompt, seed, and settings match. Changing parsers does not require more inference. **Reuse responses across runs** also allows local caching of successful calls. For Ollama it requires a known model digest and runtime, an explicit context window, and a cache profile. Change the profile after changing hardware or server settings.

**Defer analysis** saves predictions before running the additional calculations. Use **Resume Saved Run** or `analyze` to finish the analysis from the saved predictions and responses.

## Configuration

[config.yaml](config.yaml) lists the model tags, datasets, and defaults. Saved dashboard preferences take precedence over shared defaults. Model entries can override generation settings such as `context_window` and `max_new_tokens`.

`max_new_tokens` caps the answer. The context window includes the rendered instructions, examples, code, and answer. Ollama needs an explicit window supported by the model. For example, Mistral uses a 32,768-token context and the shared 1,024-token answer cap. Falcon uses a 2,048-token context and a 512-token answer cap. If the complete input fits but leaves less answer space, Ollama can use the smaller budget. An input that exceeds the window is recorded as a context error and scored as `UNKNOWN`. An unusable Ollama setup stops the run before it can be counted as a model response.

The optional `hf` backend uses Transformers and the checkpoint's chat template when available. Set `revision` to pin the checkpoint and `input_format` to `chat` or `raw` if needed. For a completion API, set `PROMPTAUDIT_API_KEY` or `OPENAI_API_KEY` in the environment. Keep credentials and raw responses out of the repository.

### Datasets

The numeric suffix gives the source CVE count. CVEFixes loads fewer CVEs after its language and folder filters. BigVul's four local cohorts are nested. The CVEFixes cohorts also overlap.

| Size | CVEFixes CVEs loaded | CVEFixes snippets | BigVul CVEs loaded | BigVul snippets |
| ---: | ---: | ---: | ---: | ---: |
| 50 | 44 | 200 | 50 | 264 |
| 100 | 95 | 1,232 | 100 | 560 |
| 500 | 475 | 2,520 | 500 | 2,298 |
| 1,000 | 946 | 6,074 | 1,000 | 4,296 |

The configured cohorts use CSV files. The before/after folders are available for source inspection. BigVul's supplied disclosure year and cleaning counts are retained in the dataset and its scrub report. Review the trailing comment in BigVul 1000 pairs 282 and 1693 if using that cohort.

Register another CSV or compressed `.csv.gz` under `datasets`.

```yaml
datasets:
  - name: my_dataset
    source: local
    path: data/my_dataset.csv
```

Use UTF-8 and include `id`, `language`, `code`, and `label`. IDs must be unique integers in the CSV, code must be nonempty, and gold labels must be `SAFE` or `VULNERABLE`. Include `cve_id` for CVE-clustered intervals and `repository` for repository grouping. The loader also retains supplied project, pair, year, and CWE metadata.

### Output protocols and parsers

`verdict_first` requests the label on the first nonempty line. `verdict_last` requests it on the final nonempty line. The **strict** parser checks the requested position after normalizing the token. **Structured** also accepts explicit verdict statements. **Full** adds a lexical fallback. You can inspect parser disagreements in the saved responses.

Overall Accuracy divides correct classifications by all samples, including `UNKNOWN`. Recall includes unresolved vulnerable samples in its denominator. Effective F1 is F1 multiplied by coverage. Selective accuracy uses only answered samples. See [metrics.py](evaluation/metrics.py) for definitions.

## Batch experiments

The command line runs the [task-wording](studies/section_b.yaml) and [component and voting](studies/section_c.yaml) studies. The examples use the dummy backend and toy data.

```bash
python run_revision_study.py run --config studies/section_b.yaml --pilot --limit 3 --output results/experiments/template-demo
```

Copy an example configuration and set the model, dataset, seed, verdict orders, and parser choices for your study. Omit `--pilot` and `--limit` for the full cohort. Use `python run_revision_study.py templates` to inspect the prompts and `python run_revision_study.py --help` for the other commands.

### Prompt design

The same security-auditor role is used across prompts. Few-shot adds two fixed labeled examples. CoT asks for step-by-step reasoning, and Adaptive CoT asks for it on harder cases. The task-wording study changes only the task sentence. The component study uses a shared baseline to compare adding one block at a time.

Self-consistency samples multiple Adaptive CoT responses. The voting study compares CoT and Adaptive CoT pools separately. `first` uses the first draw, `majority_requested` requires a majority of all requested draws, and `majority_valid` requires a majority among parsed labels with a minimum of three valid draws by default. Ties or insufficient votes yield `UNKNOWN`.

### Resume and analyze

Use **Resume Saved Run** in the dashboard or repeat a study command with `--resume`. Keep the whole run directory together. Resume checks the saved cohort, sources, and inference identity. Resume unfinished inference on the original computer.

Use `analyze` to recalculate scores from completed runs and `audit-datasets` to check exact-code overlap.

```bash
python run_revision_study.py analyze results/experiments/template-demo --bootstrap 1000
python run_revision_study.py audit-datasets cvefixes_100 bigvul_100 --output results/dataset_audit.json
```

For a dashboard batch, pass the experiment directory containing its checkpoint or manifest. To combine runs from different machines, copy their closed experiment directories and pass them together by experiment type. Combined analysis writes to the first directory. Keep matched settings across computers and record the hardware used for timing comparisons.

Analysis covers cluster bootstrap intervals, seed and task-wording variation, paired component and voting comparisons, repeated class-prevalence samples, parser disagreements, and dataset overlap. Use **Saved-result analysis** or the command-line options to choose grouping and resample counts. Zero resamples skips intervals.

## Results

Dashboard batches write to `results/runs/`. Open the batch's `report.html` to reach the individual reports. All recorded classification metrics and diagnostics are available in the reports.

| File | What it contains |
| --- | --- |
| `metrics.csv` | Scores by experimental condition |
| `records.jsonl` and `predictions/` | Standard run records and per-sample predictions |
| `generation_cache.sqlite3` | Standard responses linked to their predictions |
| `prompts.jsonl`, `generations.jsonl`, and `predictions.jsonl` | Study prompts, responses, and decisions linked by saved IDs |
| `checkpoint.json` or `manifest.json` | Run settings and resume information |
| `analysis.json` | Statistical and research results |
| `paper/index.html` and `paper/*.csv` | Paper table previews and full-precision exports |
| `review_cases.csv` | Local worksheet for reviewing linked responses and recording author notes |

Keep the full run directory for reproducibility. Use the CSVs in `paper/` for manuscript values. Reanalysis preserves author notes in the local worksheet when the case and response IDs match. Context errors, empty responses, and output-limit hits have separate diagnostics.

## Project file index

Individual CVE snippets are grouped by cohort.

```text
PromptAudit/
|-- .gitattributes                      # Preserve dataset bytes and shell-script line endings
|-- .gitignore                           # Exclude local environments, caches, and generated results
|-- README.md                            # Installation, usage, and project reference
|-- config.yaml                          # Dashboard defaults, model entries, and dataset paths
|-- requirements.txt                     # Python dependencies
|-- run_PromptAudit.py                    # Start the desktop dashboard
|-- run_revision_study.py                 # Run, resume, and analyze batch experiments
|-- run.bat                              # Windows dashboard launcher
|-- run.sh                               # macOS and Linux dashboard launcher
|-- code_datasets/
|   |-- __init__.py                      # Shared dataset metadata fields and extraction helper
|   |-- _local_cve_dataset_loader.py      # Read local CVE before/after code files and metadata
|   |-- dataset_loader.py                # Select a dataset source and read local CSV samples
|   |-- hf_loader.py                     # Download and normalize supported Hugging Face datasets
|   `-- validation.py                    # Validate cohorts and build stable sample identities
|-- core/
|   |-- __init__.py                      # Execution package and product version
|   |-- batch_runner.py                  # Plan and resume multi-experiment batches
|   |-- inference.py                     # Shared request execution, local response cache, and accounting
|   |-- runner.py                        # Run Standard experiments and save checkpoints
|   `-- revision_study.py                # Run task-wording, component, and voting studies
|-- data/
|   |-- toy.csv                          # Small mixed-language dataset for trying a run
|   |-- cvefixes/
|   |   |-- cvefixes_{50,100,500,1000}.csv.gz  # Compressed experiment inputs with preserved cohorts
|   |   `-- cvefixes_{50,100,500,1000}/        # Original CVE before/after files and source readmes
|   `-- bigvul/
|       |-- bigvul_50.csv                # 50-CVE cohort and metadata used by the loader
|       |-- bigvul_100.csv               # 100-CVE cohort and metadata used by the loader
|       |-- bigvul_500.csv               # 500-CVE cohort and metadata used by the loader
|       |-- bigvul_1000.csv              # 1,000-CVE cohort and metadata used by the loader
|       |-- bigvul_{50,100,500,1000}/    # Matching CVE before/after folders and source readmes
|       `-- scrub_report.json           # Supplied cleaning counts and preparation settings
|-- evaluation/
|   |-- __init__.py                      # Evaluation package marker
|   |-- artifacts.py                     # Read saved predictions and linked responses through a disk index
|   |-- label_parser.py                  # Extract SAFE, VULNERABLE, or UNKNOWN from model output
|   |-- metrics.py                       # Compute evaluation metrics and define shared help text
|   |-- output_protocol.py               # Build verdict-first and verdict-last instructions
|   |-- paper_exports.py                 # Export calculated manuscript tables and their definitions
|   |-- report.py                        # Build interactive HTML reports
|   |-- research_analysis.py             # Prevalence, selective prediction, parser/output, and dataset audits
|   |-- template_analysis.py             # Compare templates, ranks, and paired CVE-level results
|   `-- voting.py                        # Apply aggregation policies to a fixed prediction pool
|-- models/
|   |-- __init__.py                      # Model package marker
|   |-- api_model.py                     # HTTP backend for compatible completion APIs
|   |-- base.py                          # Shared model interface and generation metadata
|   |-- context_guard.py                 # Check Ollama context limits and truncation behavior
|   |-- dummy_model.py                   # Offline keyword-based backend for pilots
|   |-- hf_model.py                      # Load and run models with Transformers
|   |-- model_loader.py                  # Select and configure a model backend
|   `-- ollama_model.py                  # Generate responses through the local Ollama API
|-- prompts/
|   |-- __init__.py                      # Prompt package marker
|   |-- adaptive_cot.py                  # Adaptive reasoning prompt
|   |-- base_prompt.py                   # Common prompt interface and formatting helpers
|   |-- cot.py                           # Step-by-step reasoning prompt
|   |-- few_shot.py                      # Few-shot prompt and its fixed labeled examples
|   |-- prompt_loader.py                 # Map strategy names to prompt implementations
|   |-- self_consistency.py              # Collect and aggregate votes in dashboard experiments
|   |-- self_verification.py             # Prompt the model to check its assessment
|   |-- template_variants.py             # Render template variants and matched component controls
|   `-- zero_shot.py                     # Direct classification prompt without examples
|-- results/
|   `-- runs/                            # Dashboard run outputs, reports, and checkpoints
|-- studies/
|   |-- section_b.yaml                   # Example batch configuration for template variation
|   `-- section_c.yaml                   # Example batch configuration for components and voting
|-- tests/
|   |-- test_api_and_privacy.py          # API requests, diagnostics, and credential handling
|   |-- test_artifacts.py                # Saved responses and offline analysis commands
|   |-- test_context_safety.py           # Ollama context limits and retries
|   |-- test_datasets.py                 # BigVul and CVEFixes loading and metadata
|   |-- test_gui_config.py               # Dashboard settings and presets
|   |-- test_inference.py                # Inference requests, caching, and parallel execution
|   |-- test_output_protocol.py          # Verdict placement and parsing
|   |-- test_reports.py                  # Standard reports, study reports, and paper exports
|   |-- test_research_analysis.py        # Prevalence, selective scores, and audits
|   |-- test_revision_study.py           # Prompts, backends, and study runs
|   |-- test_runners.py                  # Batch and study execution, pause, and resume
|   |-- test_uncertainty.py              # Cluster intervals, seed summaries, and bootstrap reuse
|   `-- test_validation_traceability.py  # Input validation, response links, and analysis-only resume
|-- ui/
|   |-- __init__.py                      # Interface package marker
|   `-- dashboard.py                    # Desktop controls, settings, and run monitor
`-- utils/
    |-- __init__.py                      # Utility package marker
    |-- power.py                         # Prevent Windows sleep during long runs
    `-- privacy.py                       # Remove credentials from saved settings and diagnostics
```

## Tests

```bash
python -m unittest discover -s tests
```

The tests use local fixtures and mocked model responses.
