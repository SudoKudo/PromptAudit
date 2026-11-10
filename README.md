# PromptAudit 3.0

PromptAudit compares prompts and verdict parsing for code vulnerability detection. It saves model replies, classification scores, and reports.

## Installation

Install [Python 3.10 or later](https://www.python.org/downloads/) and Git. Use the clone URL from the repository's **Code** menu.

```bash
git clone <repository-url> PromptAudit
cd PromptAudit
```

Create and activate a virtual environment.

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

```bash
python -m pip install -r requirements.txt
```

The dashboard needs Tkinter and a desktop session. On Debian or Ubuntu, install `python3-venv` and `python3-tk` if needed. If PowerShell blocks activation, use `.venv\Scripts\python.exe` in place of `python`.

## Run the dashboard

Install [Ollama](https://ollama.com/download), start it, and run these commands from the project directory.

```bash
ollama pull mistral:latest
python run_PromptAudit.py
```

For a quick run, choose **Standard prompts**, `mistral:latest`, `toy`, and `zero_shot`. Select `verdict_first` and the `strict` parser, then click **Run Selected Experiments**.

| Experiment type | What it compares |
| --- | --- |
| Standard prompts | Prompting approaches under the selected verdict orders and parsers |
| Task wordings | Different ways to phrase the same classification task |
| Components and voting | Prompt instructions and ways of combining multiple replies |

You can select multiple experiment types and datasets in one batch. Use **Pilot / smoke test** to limit the sample count and turn it off for a full run. To continue an interrupted run, choose **Resume Saved Run**.

On DGX Spark, follow [NVIDIA's Ollama setup](https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/ollama/README.md). If you use Ollama with the included CSVs, the Python packages you need are `ttkbootstrap`, `PyYAML`, and `requests`. Open the dashboard from the Spark desktop or use the command line over SSH.

## Configuration and datasets

[config.yaml](config.yaml) lists the available models, datasets, and run defaults. The numbers below are the counts available for evaluation after filtering.

| Dataset suffix | CVEFixes CVEs | CVEFixes snippets | BigVul CVEs | BigVul snippets |
| ---: | ---: | ---: | ---: | ---: |
| 50 | 44 | 200 | 50 | 264 |
| 100 | 95 | 1,232 | 100 | 560 |
| 500 | 475 | 2,520 | 500 | 2,298 |
| 1,000 | 946 | 6,074 | 1,000 | 4,296 |

[BigVul cohort notes](data/bigvul/README.md) describe how the samples were drawn.

To use your own data, copy a local entry under `datasets` in `config.yaml` and set its name and CSV path. Use a UTF-8 CSV with `id`, `language`, `code`, and `label` columns. Each row needs a unique integer ID, nonempty code, and a `SAFE` or `VULNERABLE` label. Include `cve_id` for confidence intervals grouped by CVE.

## Command line

The command-line runner handles task-wording, component, and voting experiments. The [example configurations](studies/) use the toy dataset and a dummy model, so the following commands work without Ollama.

```bash
python run_revision_study.py run --config studies/section_b.yaml --pilot --limit 3 --output results/experiments/template-demo
python run_revision_study.py analyze results/experiments/template-demo
```

For a full run, copy an example, set your model and dataset, and omit `--pilot` and `--limit`. Run `python run_revision_study.py --help` for the available commands.

## Results

Dashboard runs are saved under `results/runs/`. Open the batch's `report.html` to reach each experiment report. Use **Paper tables** for CSV and LaTeX exports. Keep the run directory together if you plan to resume or analyze it later.

## Project file index

```text
PromptAudit/
|-- config.yaml             # Models, datasets, and defaults
|-- requirements.txt        # Python packages
|-- run_PromptAudit.py       # Desktop dashboard
|-- run_revision_study.py    # Command-line experiments and analysis
|-- run.bat                  # Windows launcher
|-- run.sh                   # macOS and Linux launcher
|-- code_datasets/           # Dataset loading
|-- core/                    # Experiment runners
|-- data/
|   |-- toy.csv              # Small dataset for trying a run
|   |-- bigvul/              # BigVul cohorts and preparation report
|   `-- cvefixes/            # CVEFixes cohorts and source files
|-- evaluation/              # Parsers, scores, and reports
|-- models/                  # Model backends
|-- prompts/                 # Prompt templates
|-- results/                 # Local run outputs
|-- studies/                 # Example experiment configurations
|-- tests/                   # Automated tests
|-- ui/                      # Desktop interface
`-- utils/                   # Shared helpers
```

## Tests

```bash
python -m unittest discover -s tests
```
