# PromptAudit 3.0

PromptAudit measures how prompt wording, reasoning instructions, output format, and parsing affect LLM-based vulnerability classification. It runs code samples through selected models and records `SAFE`, `VULNERABLE`, or `UNKNOWN` predictions.

You can run experiments through a desktop dashboard or a command-line interface. Reports include classification scores, coverage, and abstention rates.

## Features

- Zero-shot, few-shot, chain-of-thought, adaptive reasoning, self-consistency, and self-verification prompts in the dashboard.
- Matched task-wording, component, and voting experiments through the dashboard or command line.
- Local models served by Ollama or loaded with Hugging Face Transformers.
- Local CSV and CVE-based datasets, with loaders for supported Hugging Face datasets.
- CSV results, an interactive HTML dashboard report, and resumable experiments.
- Offline analysis with full-precision paper tables, confidence intervals, and downloadable CSVs.
- Multiple experiment types in one resumable batch, with shared response reuse and overall progress.

## Requirements

- [Python](https://www.python.org/downloads/) 3.10 or later and Git. Local checks have been run with Python 3.12.
- [Ollama](https://ollama.com/download) for the default local-model workflow. The command-line smoke test below uses a dummy model and needs no model download.
- A desktop session and Tkinter for the GUI. Standard Python installations on Windows and macOS usually include Tkinter. On Debian or Ubuntu, install it with `sudo apt install python3-tk` if needed.
- Enough RAM or GPU memory for your chosen model and context length.

For GPU inference with Transformers, install the PyTorch build for your system using the [official installation guide](https://pytorch.org/get-started/locally/).

## Installation

Copy the repository's clone URL from its hosting page, replace `<repository-url>` below, and open the project directory:

```bash
git clone <repository-url> PromptAudit
cd PromptAudit
```

Create and activate a [virtual environment](https://docs.python.org/3/library/venv.html).

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the remaining commands from the project directory with the environment active. If PowerShell blocks activation, use `.venv\Scripts\python.exe` in place of `python`.

## DGX Spark setup

For local Ollama and CSV datasets on the Spark, copy a clean project snapshot to the machine and create its Python environment there. In a terminal inside the Spark desktop session, from the project folder:

```bash
sudo apt install python3-venv python3-tk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ttkbootstrap>=1.10.1,<2" "PyYAML>=6.0" "requests>=2.31.0"
ollama pull falcon:7b-instruct
python run_PromptAudit.py
```

These three Python packages cover the local Ollama/CSV workflow. The complete `requirements.txt` also installs the optional Hugging Face model/dataset dependencies. Ollama must be installed and running separately; use the [NVIDIA Spark Ollama guide](https://github.com/NVIDIA/dgx-spark-playbooks/blob/main/nvidia/ollama/README.md). Verify GPU execution with `ollama ps` during a pilot. Select only the assigned model and match the experiment settings used on the other computer.

The desktop GUI needs a Spark desktop session, accessed locally or through remote desktop. For terminal-only access, `run_revision_study.py` supports wording/component runs, saved-result analysis, and dataset audits without a display. Selecting an Ollama model in the Windows GUI currently uses the Windows machine's local server.

When transferring an unpushed snapshot, exclude `.git`, virtual environments, credentials, local GUI preferences/presets, generated results, and the internal revision log. Transfer the exact code/data snapshot to both computers and keep it fixed during experiments. After pushing, the normal Git clone workflow can be used instead.

## Quick start without a model download

Run a small template-variation experiment using the included toy data and dummy backend:

```bash
python run_revision_study.py run --config studies/section_b.yaml --pilot --limit 3 --output results/experiments/template-demo
```

This checks loading, prompt construction, output storage, and analysis without starting an LLM server. Dummy-model scores are only useful for checking the workflow.

Open `results/experiments/template-demo/metrics.csv` for per-condition scores and `analysis.json` for comparisons. The directory also contains the prompts, responses, predictions, and run manifest.

Output directories must be new for each run. To continue the same run, use the resume command below.

## Run the desktop dashboard

### Set up Ollama

Install and start Ollama using its [setup instructions](https://docs.ollama.com/quickstart). Download a model listed in `config.yaml`, for example:

```bash
ollama pull mistral:latest
ollama list
```

If the Ollama service is not already running, start `ollama serve` in another terminal. PromptAudit connects to `http://127.0.0.1:11434`.

### Start an experiment

```bash
python run_PromptAudit.py
```

You can also use `run.bat` on Windows or `bash run.sh` on macOS and Linux after installing the dependencies. These launchers use `.venv` or `venv` directly when present and check that its interpreter starts with Python 3.10 or later. A broken environment produces setup guidance rather than silently switching interpreters.

For a first run:

1. Select the downloaded model, such as `mistral:latest`.
2. Select the `toy` dataset and `zero_shot` prompt.
3. Select `verdict_first` and the `strict` parser.
4. Click **Run Selected Experiments**.
5. Click **Open Report** when the run finishes.

The dashboard supports pause, resume, stopping at a sample boundary, and resuming a saved checkpoint. It also supports saving and loading selection presets.

Select one or more **Experiment types** to run these workflows in one batch:

| Mode | Controls |
| --- | --- |
| Standard prompts | Run the selected complete prompting approaches with the chosen verdict protocols and parsers |
| Task wordings | Select approaches and task sentences; include Reference for matched comparisons |
| Components and voting | Select paired example, step-by-step, or adaptive-instruction comparisons, and choose voting bases and policies |

Component comparisons share one baseline and add one block at a time. They do not combine arbitrary blocks or modify every complete prompt. Voting policies reuse the same saved pool for each selected CoT or Adaptive CoT base. Selecting only First requires one draw; selecting a majority policy uses the requested pool.

Hover over options and metric names for explanations. Reports always include all seven classification scores and recorded diagnostics. Use the HTML filters to narrow the results. Saved-result analysis controls compute paired comparisons, wording ranks, class-imbalance comparisons, output audits, and dataset summaries. Choose CVE or repository grouping for uncertainty and use zero bootstrap resamples to omit intervals. Study run seeds apply to task-wording and component/voting studies; Standard uses the Generation Settings seed. In a dashboard batch, pilot mode applies the optional sample limit to every selected experiment type. The `dummy` backend is for pilots.

The run monitor shows estimated completion across the selected batch. It counts planned request resolutions and processing work using the dataset sample counts, model selections, prompting approaches, study conditions, run seeds, parsers, and requested draws. Reused responses complete work without a fresh model call. The estimate does not predict remaining clock time, and it reaches 100% only after the batch outputs are saved.

The estimate assigns one work unit to each distinct request within an experiment type and 0.05 units to each parsed prediction. Report processing reserves another 5% of that work, with at least one unit per report. These are planning weights, not measured time ratios. Shared requests still count toward each experiment's completed work, even when they require no new inference.

Pause and stop requests take effect between model requests or analysis batches. Resume Saved Run reuses recorded calls; if all generation finished but analysis remains, a batch can resume analysis from saved predictions without the original datasets or models. Missing response stores make response-level audits unavailable. Model revisions, source files, execution environment, and cohort checks still apply when resuming generation.

### Inference performance

**Inference workers** sets the maximum number of concurrent requests. It defaults to one on every computer. Ollama supports multiple workers when its server is configured to allow them; Hugging Face and API backends currently require one worker. Parallel requests keep their own seeds and settings. They do not change the requested vote count or prompting technique.

Standard mode keeps a bounded queue of up to four samples per worker for single-response strategies. Two workers can therefore queue eight samples while running at most two requests at once. This lets a free worker take the next request while another finishes a slower answer. Pause and stop prevent new submissions; returned responses remain saved for replay. Scheduling is recorded as `standard_prefetch_samples`. One worker uses a one-sample queue.

Standard runs finish the selected datasets for one model before switching to the next model. This reduces backend reloads and gives Ollama more opportunity to reuse loaded weights. Datasets are loaded one at a time; the runner does not retain every cohort in memory. Study modes use the same model-first order and reuse one resolved model-metadata snapshot for provenance and cache matching.

Experiment types selected together share a batch-local response cache. Reuse requires the same model identity, full prompt, generation settings, and seed. Parsers and voting policies can therefore read a saved response rather than request it again. Reference CoT and Adaptive CoT draws can also overlap between wording and voting studies. Standard mode uses its fixed base-seed stream, while studies derive seeds for each sample and draw; a matching prompt with a different seed remains a separate request. The batch cache is separate from optional cross-run caching and stays with the batch outputs for resume.

For Ollama, benchmark two workers, then four if memory allows, and configure the server's `OLLAMA_NUM_PARALLEL` to allow at least that many requests. Disable cross-run response reuse during throughput benchmarks so cache hits do not look like faster generation. More workers do not guarantee higher throughput: context caches also use GPU memory, and memory pressure can make inference slower. A 24 GB GPU is not a guarantee that two models or several long requests fit together. Check `ollama ps` during a pilot to confirm GPU use, and compare elapsed time and completed outputs before choosing settings. PromptAudit does not change server variables or GPU drivers.

The run log prints the planned generation-request count before cross-job or cross-run reuse. Dataset size, models, task wordings, verdict orders, seeds, and repeated draws multiply that count. Parser choices reuse responses. A large full-factorial experiment can still take days or weeks; a deeper queue does not reduce the number of distinct requests. Use one model for a workflow check, then freeze the required experiment matrix and consider splitting model selections across machines. **Defer analysis** lets generation continue across jobs before the saved-result calculations; it does not reduce model computation.

Ollama can reserve context memory for its configured server slots even when fewer clients are active. Lowering only the dashboard worker count may therefore leave GPU memory use unchanged. Check the loaded context with `ollama ps`; a blank dashboard context field does not imply a fixed 4K window. When increasing context length, recheck both `OLLAMA_NUM_PARALLEL` and dashboard workers. Restart the Ollama application after changing its server environment variables. Keeping `OLLAMA_MAX_LOADED_MODELS=1` limits competition between loaded models during a single-model throughput test. See the [Ollama concurrency guidance](https://docs.ollama.com/faq#how-does-ollama-handle-concurrent-requests).

**Reuse responses across runs** uses a local cache under `results/cache` by default. Reuse requires a matching request, seed, model identity, runtime, and generation settings. Within-run parser and vote replay remains enabled regardless of this toggle. The cross-run cache omits failed requests; resuming a run still retains its recorded failures as outcomes. The cache can contain model responses and should stay local to each computer. Its default location is excluded from Git; ignore any custom cache directory too. Performance summaries distinguish fresh generation from cache reuse. A cached response's original generation time describes its decision cost, while the current run's elapsed time describes the time actually spent now.

In a study manifest, `new_calls_this_session` counts newly saved call records, including responses copied from the shared cache. The `inference_performance` summaries report actual model executions as `generated_calls`, alongside cache hits and elapsed time. These execution summaries describe the current session, including after resume; they are not cumulative across sessions.

Ollama cross-run reuse requires an explicit context window, set through **Context window (tokens)** or a model entry, and a nonempty **Cache profile**, plus a known model digest and runtime version. A blank GUI context field leaves model-specific settings or the server default in place. Without an explicit effective window, or with a blank profile, Ollama cross-run reuse is disabled; within-run replay still works. Choose the context during a pilot, with room for the input and output, and keep it fixed across matched conditions. PromptAudit does not shorten the supplied code when this setting changes.

Cache entries do not expire automatically. Use a generic profile tag such as `local-v1`, and change it after server defaults, GPU drivers, hardware, or other server settings change. Those details cannot all be detected from model metadata. To force fresh generation across runs, disable response reuse or choose a new profile/cache directory. You can remove the shared cache while no experiment is using it. Keep each standard run's `generation_cache.sqlite3` with its outputs; deleting an active run's cache can remove responses needed for parser replay and saved resume.

**Defer analysis** saves generations and predictions before running statistical and research analyses. The run monitor shows that analysis is pending. Use **Resume Saved Run** or the `analyze` command below to finish without new inference. Standard still writes its basic classification report after generation; its additional analysis report is written afterward. Intervals for repeated prevalence subsets can take substantial CPU time. Reduce the bootstrap count, use zero to skip intervals, or defer analysis when collecting generations.

Study generation logs flush each response. The standard-run response cache commits before checkpoint updates and when the run closes. Commits to the rebuildable study lookup index are batched to reduce disk overhead. Prompts, vote rules, model choices, and metric formulas are unchanged by these performance controls. Parallel execution can still produce different outputs across runtimes or hardware, so keep its settings fixed across matched experimental conditions.

## Configuration

The dashboard reads [config.yaml](config.yaml). It defines available models and datasets, prompt strategies, decoding defaults, output paths, and checkpoint settings. Batch runs use the configuration passed with `--config`; dataset names are resolved through `config.yaml`.

Generation defaults are temperature `0.2`, top-p `0.9`, top-k `40`, up to `1024` output tokens, repetition penalty `1.0`, one beam, seed `42`, five self-consistency draws, and no project stop strings. The output budget is a maximum, not a target length. Saved GUI preferences override these defaults; check the displayed values before starting. Inspect completed verdicts and output-cap hits during a real-model pilot before freezing the budget.

An Ollama model entry looks like this:

```yaml
models:
  - name: mistral:latest
    backend: ollama
```

For the optional API backend, supply credentials through `PROMPTAUDIT_API_KEY` or `OPENAI_API_KEY` rather than putting them in configuration files. Saved settings omit recognized credential fields and redact credential-bearing URLs. Local preferences, presets, environment files, and generated results are excluded from Git. Inputs, raw responses, free-form notes, and older Git commits are not automatically anonymized; review those separately before sharing.

The API backend records returned token counts, completion reasons, output-limit flags, and runtime fingerprints when available. A configured seed is sent to the completion endpoint; server support and repeatability depend on the provider. Missing diagnostics remain unavailable. Failed requests record error types and HTTP status codes without response bodies.

Use `backend: hf` with a Hugging Face model ID to load a model through Transformers. Run `hf auth login` before using the Hugging Face dataset loader or an access-controlled model; see the [Hugging Face CLI guide](https://huggingface.co/docs/huggingface_hub/en/guides/cli).

HF models use their tokenizer's native chat template when available and preserve the checkpoint's weight dtype by default (`torch_dtype: auto`). Set `input_format: chat` to require a chat template, or `input_format: raw` for a base completion model. A model entry can also set `revision` to a commit hash and pass model-specific options through `chat_template_kwargs`. See the [Transformers chat-template guide](https://huggingface.co/docs/transformers/en/chat_templating). Ollama applies the template installed with the model.

Set `context_window` in generation settings or a model entry to choose an explicit token window; Ollama's `num_ctx` name is also accepted. HF rejects inputs whose prompt plus output budget exceeds the known window. Ollama input handling depends on the server, so inspect its logs and evaluated token counts during the pilot for truncation. Keep model-specific thinking modes fixed: use `think` for supported Ollama models or the checkpoint's documented `chat_template_kwargs` for HF. Returned Ollama thinking text is saved separately and is not passed to the verdict parser.

Check each model's supported context before choosing a shared window. For example, [Falcon-7B-Instruct was trained with a 2,048-token sequence length](https://huggingface.co/tiiuae/falcon-7b-instruct). That space must accommodate the complete prompt, code, and generated answer. Increasing the server window does not establish that the model handles longer inputs reliably. During a pilot, check protocol compliance, unresolved predictions, and output-limit hits as well as classification scores. Changing a parser or trimming an answer to hide poor format compliance would change the comparison.

Model settings override shared generation settings, including when the two use different context-window aliases. If both aliases appear in the same settings block, their values must agree. Invalid token budgets, sampling values, stop lists, or reserved chat-template arguments are rejected before a batch run starts. HF applies configured stop strings during generation; an empty list disables checkpoint-provided stop strings. A forced end token at the output cap is recorded as a limit hit.

### Datasets

The included `toy` dataset is intended for smoke tests. Local CVE datasets are selected by the names and paths registered in `config.yaml`.

To use a CSV dataset, add an entry to the `datasets` list:

```yaml
datasets:
  - name: my_dataset
    source: local
    path: data/my_dataset.csv
```

The CSV should contain `id`, `language`, `code`, and `label` columns. Use unique integer IDs, nonempty code, and `SAFE` or `VULNERABLE` gold labels. Quote multiline code and fields containing commas using standard CSV quoting.

All experiment modes validate every selected cohort before the first model request. Invalid or missing gold labels, empty code, and duplicate sample IDs stop the run with an error. UNKNOWN is a possible model prediction, not a valid gold label. Directory loading also records exclusion counts for unsupported languages, missing pairs, unreadable files, and nested CVE directories. CSV imports cannot reconstruct exclusions made before export and report that limitation.

CSV files may use UTF-8 with or without a byte-order mark. Compressed `.csv.gz` files are also supported through Python's standard library. Code is preserved as supplied, including surrounding whitespace and fields larger than 128 KiB. Optional `cve_id`, `project`, `repository`, `commit_id`, `filename`, `file_number`, `pair_id`, `year`, `cwe_id`, and `cvss_score` columns are retained for matching and analysis. `id` and any supplied `file_number` must be integers. The Hugging Face loader also retains available metadata. Include `cve_id` to enable CVE-clustered intervals.

#### CVEFixes

The local cohorts use compressed CSVs under `data/cvefixes/`, with the original before/after folders beside them for inspection. Select `cvefixes_50`, `cvefixes_100`, `cvefixes_500`, or `cvefixes_1000` in the GUI. These names count top-level source CVE folders; the existing language filter makes the evaluated CVE counts smaller:

| Dataset selection | Source CVE folders | Loaded CVEs | Loaded pairs | Code samples |
| --- | ---: | ---: | ---: | ---: |
| `cvefixes_50` | 50 | 44 | 100 | 200 |
| `cvefixes_100` | 100 | 95 | 616 | 1,232 |
| `cvefixes_500` | 500 | 475 | 1,260 | 2,520 |
| `cvefixes_1000` | 1,000 | 946 | 3,037 | 6,074 |

The CSVs preserve the folder loader's row order, IDs, integer file numbers, filenames, languages, labels, and code exactly as loaded. The raw files remain unchanged. Compression keeps the largest export, about 185 MB uncompressed, manageable without an extra dependency. The four cohorts overlap but are not nested; they should not be treated as independent samples.

The folder loader reads files directly under each top-level CVE and excludes unsupported or unknown filename extensions. Each cohort also contains three nested CVE directories that the existing loader ignores. Those files are retained but are not included in the CSVs. No missing direct before/after pairs, unreadable source files, or empty source files were found in the layout audit. These checks do not establish label correctness or exploitability. Disclosure years, CWE categories, and project metadata have not been inferred from filenames or CVE numbers.

`data/cvefixes/cvefixes_<size>/` remains usable as a directory dataset path. When updating a custom configuration, use that path or the corresponding `.csv.gz` file; the bundled configuration uses compressed CSVs. Folder-to-CSV checks preserve the existing evaluated cohorts, including their exclusions.

#### BigVul

The local BigVul subsets are registered separately from the Hugging Face dataset named `bigvul`:

| Dataset selection | CVEs | Before/after pairs | Code samples |
| --- | ---: | ---: | ---: |
| `bigvul_50` | 50 | 132 | 264 |
| `bigvul_100` | 100 | 280 | 560 |
| `bigvul_500` | 500 | 1,149 | 2,298 |
| `bigvul_1000` | 1,000 | 2,148 | 4,296 |

Each pair contains one VULNERABLE sample and its SAFE counterpart. The four supplied numeric cohort names count CVEs, not rows. Those four cohorts are nested, so they overlap and should not be treated as independent datasets. Their CVE counts by supplied year follow proportional allocation with largest-remainder rounding. Keep the supplied `year` field: it can differ from the year in the CVE identifier. The provided `scrub_report.json` records the preparation settings and counts; reproducing the full cleaning process requires the original inputs and preparation code.

The supplied code and metadata are preserved. In the 1,000-CVE subset, pairs `282` (CVE-2016-3132) and `1693` (CVE-2016-5770) include an unclosed trailing comment after the function body and need source review before a final experiment. Some commit identifiers include URL suffixes or reference names rather than a full commit hash. Loading checks do not establish vulnerability ground truth or standalone compilability.

The configured BigVul entries use CSV files to preserve their labels, languages, and metadata. Matching CVE-style folders for the supplied numeric cohorts are kept for inspection. In the GUI, select any of these local entries together with one or more CVEFixes datasets under **Datasets**. All three experiment modes accept multiple selections and report each dataset separately. A batch configuration can likewise use `datasets: [cvefixes_50, bigvul_50]`.

The CSV metadata is also retained in standard-run predictions and per-sample exports. BigVul loading needs no extra packages or newer Python. The GUI dependency stays on `ttkbootstrap` 1.x because the current imports use compatibility modules removed in version 2.

Dataset-loading behavior is implemented in [code_datasets/](code_datasets/). Paths for local data are relative to the project directory.

### Output protocols and parsers

The shared response contract requests plain text, one bare verdict line, and an explicit first-line or final-line layout. Direct zero-shot and few-shot request only the verdict; CoT, adaptive reasoning, and self-verification retain their own reasoning instructions. Layout placeholders illustrate output order without adding labeled code demonstrations. A one-word answer satisfies both boundary positions. Models can still ignore the format, especially verdict-last, so strict-parser abstentions remain visible. PromptAudit does not move a verdict, rewrite a response, or make an extra repair call. Template hashes/version distinguish these instructions from earlier outputs; start a new matched run after a template change.

| Setting | Behavior |
| --- | --- |
| `verdict_first` | Request the label on the first nonempty line |
| `verdict_last` | Request the label on the final nonempty line |
| `strict` | Accept a label only at the requested position |
| `structured` | Also accept explicit verdict statements |
| `full` | Also apply lexical fallback rules |

An unresolved output becomes `UNKNOWN` and contributes to abstention. Metric definitions are in [evaluation/metrics.py](evaluation/metrics.py).

The reported `Accuracy` uses `(TP + TN) / (TP + TN + FP + FN + UnFN + Incorrect)`: correct predictions divided by all evaluated samples. `UnFN` counts unresolved VULNERABLE samples and `Incorrect` counts unresolved SAFE samples, so both reduce Accuracy. `Recall` includes vulnerable abstentions, and `EffectiveF1` is `F1 * Coverage`.

Rebuilt standard reports and CSV summaries recalculate Accuracy from saved confusion counts or sample predictions when available. Summary-only records without those details retain their recorded score. Existing HTML and CSV files stay unchanged until regenerated. Completed studies can be reanalyzed from saved predictions without new model calls using the `analyze` command below. Source checks still apply when resuming unfinished generation.

Use `strict` as the primary extraction policy and compare the other parsers separately. It checks the requested verdict position after normalizing nonalphabetic characters within the token. A lexical fallback can recover labels from explanations, so its score also reflects the extraction policy. `verdict_last` permits a generated explanation to precede and influence the verdict. Under `verdict_first`, the later explanation follows a decision already emitted; the two orders are separate experimental conditions.

Parser normalization is permissive: for example, `SAFE123` becomes `SAFE`. The `full` parser can also misread explanations that mix negated and affirmative vulnerability statements. Inspect saved outputs when auditing these cases; parser agreement does not validate the reasoning.

## Batch experiments

The command-line runner supports two experiment types:

| Configuration | Experiment |
| --- | --- |
| [Template variation](studies/section_b.yaml) | Compare four task wordings for each prompting approach under both verdict orders |
| [Components and voting](studies/section_c.yaml) | Compare component on/off pairs, voting policies, and verdict placement |

Both examples start with the dummy backend and toy data. To try the component and voting experiment:

```bash
python run_revision_study.py run --config studies/section_c.yaml --pilot --limit 3 --output results/experiments/component-demo
```

Each configuration selects models, datasets, protocols, parsers, run seeds, generation settings, and vote counts. Component pairs change one instruction or example block on a common scaffold. An off control removes that block; it does not prevent internal reasoning. The analysis also compares adaptive and unconditional reasoning directly on that scaffold. For each CoT or adaptive CoT base, voting policies and parsers reuse the same saved responses; the two bases have separate pools. Set `voting_policies` to select policies; its default includes all three. Either `components` or `voting_bases` can be empty when the other selects an experiment.

The component experiment uses its own common scaffold. It does not remove blocks from every full template in the wording experiment or test every component interaction. Its contrasts measure the selected block on that scaffold, so they do not explain the entire difference between two prompting approaches.

### Prompt design

A template is fixed instruction text with a slot for the target code. Filling that slot produces a prompt; the backend then applies any model-specific chat wrapper. The prompting approach specifies how the model is asked to assess the code. Self-consistency adds a sampling and aggregation algorithm to a base prompt.

Every approach and matched component control starts with the same role, `You are a code security auditor.`, followed by the classification task. This holds role assignment fixed; it does not establish that the role improves accuracy.

| Prompting approach | Requested behavior |
| --- | --- |
| Direct zero-shot | Classify directly, without demonstrations or a step-by-step explanation |
| Few-shot | Classify using two fixed labeled examples, without a step-by-step explanation |
| CoT (zero-shot) | Explain the security assessment step by step; no worked reasoning demonstrations are supplied |
| Adaptive CoT | Answer directly on straightforward, clear cases; otherwise explain step by step |
| Self-consistency | Sample several adaptive CoT responses and aggregate their parsed labels |
| Self-verification (dashboard) | Ask the model to check its assessment within one response; no external verifier is used |

The four supported variants, `reference`, `paraphrase`, `reworded`, and `task_first`, use the same four classification-task wordings across approaches. Only that task line changes: the role stays on the first line, and each approach's instructions, examples, code, and output suffix stay fixed. `task_first` puts the classification objective before the assessment action within the task line; it does not move the role. `reference` means the current default template. Analysis reports score variation and ranking changes across the selected wordings. These are a small, predefined set of templates, not an exhaustive search.

The examples are a synthetic C buffer-copy pair in a fixed VULNERABLE-then-SAFE order. They explicitly assume that `buf` points to `len` readable bytes and assess the shown buffer accesses under that contract. This assumption applies only to the demonstrations. Holding them fixed controls wording comparisons; it does not establish robustness to example choice, order, language, or vulnerability type. Task-wording variants leave the target code and examples intact. A shared instruction and `<target_code>` markers separate the target input from the task; these markers are not a security boundary.

Adaptive CoT asks the model to choose its response style within one call. It has no separate routing call, learned complexity estimator, or adaptive compute budget. Response length alone does not show that it followed the instruction. Explicit CoT is an experimental condition, not a claim that it improves every model; native reasoning models may need different guidance, as discussed in [OpenAI's reasoning guide](https://developers.openai.com/api/docs/guides/reasoning-best-practices).

Voting uses distinct reproducible draw seeds and requires sampling (`temperature > 0`, `num_beams: 1`). Distinct seeds do not guarantee diverse answers. The default pool has five draws. `first` uses the first requested draw, `majority_requested` requires more than half of all requested votes, and `majority_valid` requires more than half of valid votes with at least three valid draws by default. Ties and insufficient majorities become `UNKNOWN`. A failed draw also counts as `UNKNOWN`; remaining draws continue, while cancellation still stops execution. These abstention rules are explicit choices for this project; [self-consistency](https://arxiv.org/abs/2203.11171) is the broader sampling-and-aggregation method. Comparing the two majority policies keeps the call budget fixed. With the default five draws, comparing either with `first` compares five decision calls with one. Analysis checks budget equality from the saved call counts, including single-draw configurations.

### Configure a full experiment

Copy one of the example configurations and set its models, datasets, seeds, and generation settings. Run a representative local-model pilot before a full experiment. The example decoding settings and 1,024-token output cap are starting values, not tuned recommendations. Check input fit, completed verdicts, output-limit hits, and response diversity, then freeze settings across matched conditions. Model cards take precedence for supported modes and settings; report any model-specific differences. Use multiple run seeds to measure run variability separately from CVE sampling uncertainty.

Choose a common cohort that fits every selected model and template with room for the output budget. Apply and report any exclusions consistently across matched conditions.

Choose and review templates before examining evaluation scores. Any prompt optimization or example selection based on scores needs separate development data and an untouched evaluation set.

Inspect the template definitions without creating extra files:

```bash
python run_revision_study.py templates
```

Use `--output path/to/templates.json` if you want to save a copy. Each run also records its template definitions and hashes in `manifest.json`.

Pilot mode marks smoke-test outputs and allows a sample limit. After configuring a local model, omit `--pilot` and `--limit` for a full run.

### Resume and analyze

Resume the template smoke test using its original configuration and output directory:

```bash
python run_revision_study.py run --config studies/section_b.yaml --pilot --limit 3 --output results/experiments/template-demo --resume
```

Resume checks the configuration, source files, package versions, dataset fingerprint, and recorded model metadata before reusing saved calls. Pin model revisions where possible and investigate missing metadata. Use one running process per output directory. Saved failed requests remain evaluation outcomes and are not automatically retried.

If resuming a completed run fails before any new model call, its completed manifest and predictions are preserved. An interrupted run must finish before analysis will accept it.

Recompute summaries without making model calls:

```bash
python run_revision_study.py analyze results/experiments/template-demo --bootstrap 1000
```

The same command accepts Standard output directories. To summarize repeated Standard runs together, pass their run directories in one call:

```bash
python run_revision_study.py analyze results/runs/seed-42 results/runs/seed-43 --bootstrap 1000
```

Use the actual experiment directories listed in a dashboard batch, rather than its top-level report-index directory. Combined analysis writes to the first supplied directory. Pilot and full runs cannot be combined. Seed summaries require matching samples, labels, source hashes, model identities, and settings apart from the seed. Legacy outputs with insufficient identity or cohort evidence stay unavailable for those summaries.

#### Run models on separate computers

Use the same code and dataset snapshot on both computers, with a fresh local Python environment and the required model installed on each. In each GUI, select a different model and keep dataset names, prompt selections, protocols, parsers, decoding settings, vote counts, and study seeds aligned. Choose explicit model-specific context windows during input-fit pilots; blank settings can use different server defaults. Keep all conditions and seeds for a given model on one computer. Record its hardware and worker settings; timings from different hardware are not directly comparable as model-only costs.

Keep active outputs and SQLite caches local to each computer. After generation finishes and the run files are closed, copy each complete experiment-type child directory, including its raw-response files, onto the analysis computer. Copy dataset files without newline conversion so code hashes stay identical. Recreate virtual environments locally rather than copying `.venv`; keep credentials, GUI preferences, and caches local.

For example, after copying two completed Standard child directories:

```bash
python run_revision_study.py analyze "results/collected/pc-standard" "results/collected/lab-standard" --bootstrap 1000
```

Repeat separately for the task-wording and component/voting child directories. Do not pass the batch-index directory or concatenate CSV rows. The combined outputs retain separate models and configurations and are written to the first directory. Analysis supports relocated completed folders; interrupted inference should resume on its original computer, where its saved paths and execution identity match. Across-seed summaries require the same recorded inference namespace, so runs of one model on different machines are not silently pooled.

Analysis includes template score ranges, standard deviations, paired label disagreement, ranking changes, and component or protocol comparisons. It also reports decision-call costs, available token counts, output-limit hits, and generation errors. Token counts are backend-reported and tokenizer-dependent. Missing measurements stay unavailable rather than becoming zero. Results stay separate by model, dataset, protocol, parser, and run seed.

#### Statistical and research analyses

| Analysis | Definition and limits |
| --- | --- |
| Uncertainty | Percentile bootstrap intervals resample complete CVEs or repositories. Missing identifiers, fewer than two clusters, or zero resamples produce unavailable intervals. Per-configuration intervals and paired-difference intervals describe sampling uncertainty conditional on the observed run. Small cluster counts still limit their usefulness. Intervals are pointwise, without multiple-comparison correction. |
| Run variation | Matched run seeds have a mean, sample standard deviation, and range. One seed does not establish run-to-run variance. These summaries are distinct from cluster-bootstrap uncertainty. |
| Class imbalance | Draw matched subsets without replacement at 20%, 10%, and 5% VULNERABLE prevalence. The requested size defaults to 1,000; all rates use the same feasible size rounded down to a multiple of 20. Twenty repeated draws are the default. These numbers are project choices, not estimated deployment prevalence. Subsets are shared across compared configurations and can overlap between draws. |
| Prevalence uncertainty | Mean, standard deviation, and draw quantiles describe subset variation. Each realized subset has a separate cluster interval when enabled. Draw quantiles are not confidence intervals, and the two summaries are not a joint interval over both sources of variation. |
| False positives per 1,000 | `1000 * FP / N`, where `N` includes all evaluated samples. This differs from the false-positive rate among SAFE samples. |
| Selective prediction | `SelectiveAccuracy = (TP + TN) / (TP + TN + FP + FN)`; `SelectiveRisk = 1 - SelectiveAccuracy`. No answered samples means unavailable accuracy and risk. These scores accompany coverage and the paper's overall Accuracy. Each configuration gives an observed risk-coverage point; no confidence-threshold curve is invented. |
| Parser audit | Compare labels, recovered verdicts, new abstentions, and parser tiers only when sample identities and saved response pools match. Missing links limit the comparison. Linked legacy responses can be parsed again offline. |
| Response audit | Summarize visible response length, available backend token counts, verdicts, correctness, and abstention. Export compact response IDs for manual review with judgment fields left blank. Length and rationale-verdict agreement do not establish correctness, reasoning quality, or causality. |
| Dataset audit | Check exact-code duplicates, conflicting labels, shared CVEs/projects/repositories, and CWE breakdowns where metadata exists. This covers the evaluated cohorts, not every upstream record. It does not detect all near duplicates or change labels. CWE categories may overlap. |

Tune analysis work in `config.yaml` under `analysis` or in the GUI's **Saved-result analysis** controls. The CLI supports `--group-by repository`, `--prevalence-size`, `--prevalence-repeats`, `--review-case-limit`, `--skip-prevalence`, `--skip-output-audit`, and `--skip-dataset-audit`. These options control computation, not which classification metrics are displayed.

Check dataset overlap before running a model:

```bash
python run_revision_study.py audit-datasets cvefixes_1000 bigvul_1000 --output results/dataset_audit.json
```

Saved predictions are indexed in temporary SQLite storage and processed by condition. Raw responses stay in their original stores and are read through saved IDs. Detailed prevalence draws stream to JSONL instead of being embedded in a large HTML table. Summary output still grows with the number of selected configurations. The temporary analysis index is removed after the analysis finishes.

Before writing summaries, analysis checks the completed condition matrix, cohort, labels, model identities, and recorded decision budgets against the manifest. `analysis.json` records the analysis time, Python version, bootstrap seed, current analysis source hashes, and input-file hashes. Standard response-cache provenance hashes the queried response IDs and verified payload hashes, including missing responses; unused cache entries are excluded. Analysis reads a stable cache snapshot and stops publication if saved inputs change. Reanalysis keeps the generation manifest unchanged.

#### Paper tables

After analysis, open **Paper tables** from the batch or experiment report, or open `paper/index.html` in the run directory. The page previews each table and links its complete CSV. Search covers the first 50 rows per table; use the CSV for the full selection. The same exports are rebuilt by the `analyze` command without new inference.

`paper/condition_scores.csv` contains every configuration's confusion counts, sample and answered denominators, classification scores, selective scores, costs, and matched cluster intervals. Separate CSVs contain seed summaries, wording spreads and comparisons, component/voting/protocol comparisons, prevalence draws and summaries, parser/output audits, dataset overlap, and CWE/language breakdowns. Missing language labels have an `Unspecified` group. Tables with no applicable results are empty; missing measurements remain blank, with reason fields where available.

Use the full-precision CSVs for calculations or copy the displayed values into the manuscript. `paper/condition_scores.tex` provides a LaTeX table to select from. HTML and LaTeX round to four decimal places; CSV and JSON retain the calculated precision. `paper/manifest.json` records the export schema version, definitions, denominators, grouping rules, analysis settings, input/source hashes, and export-file hashes.

Keep dataset, model identity, condition, seed, verdict order, and parser separate when selecting paper values. The exporter copies the Python results and does not pool counts or average across these axes. Across-seed means, variation across selected task wordings, cluster intervals, and prevalence-draw variation describe different quantities. A mean F1 is not an F1 calculated from pooled counts. Use offline language tables for manuscript values; the interactive report's language filters are for exploration.

For all command-line options:

```bash
python run_revision_study.py --help
python run_revision_study.py run --help
```

## Results

Dashboard batches write to `results/runs/batch_<timestamp>_<id>/` by default. Each selected experiment type has a child directory, such as `job_1_standard`, and the top-level `report.html` links their reports. Command-line studies write to the directory passed with `--output`, or print their automatically created directory when that option is omitted.

| Output | Contents | Workflow |
| --- | --- | --- |
| `batch_manifest.json` | Selected jobs, dataset fingerprints, source hashes, work estimates, and batch status | Dashboard batch |
| `responses.sqlite3` | Responses shared across experiment types in this batch | Dashboard batch |
| `progress.sqlite3` | Completed work used to restore the overall percentage | Dashboard batch |
| `metrics.csv` | Per-configuration metrics | Standard and study |
| `report.html` | Batch index, standard-run charts, or study tables with tooltips and comparisons | All |
| `records.jsonl`, `predictions/*.csv` | Configuration records, per-sample labels, and available decision-cost diagnostics | Standard |
| `checkpoint.json` | Resumable standard-run progress | Standard |
| `generation_cache.sqlite3` | Recorded raw responses for parser replay and saved resume | Standard |
| `manifest.json` | Configuration, templates, source hashes, package versions, model identities, samples, and run status | Study |
| `prompts.jsonl`, `generations.jsonl` | Full prompts, responses, seeds, settings, available token counts, limit flags, errors, and timing | Study |
| `predictions.jsonl` | Parsed decisions linked to their source generations | Study |
| `analysis.json` | Comparisons, uncertainty, seed summaries, research analyses, and provenance | Standard and study |
| `analysis_metrics.csv`, `analysis_report.html` | Additional Standard analysis scores and HTML tables; the original classification files remain available | Standard |
| `paper/index.html`, `paper/*.csv`, `paper/condition_scores.tex` | Viewable paper tables, full-precision exports, and a LaTeX configuration table | Standard and study |
| `paper/manifest.json` | Versioned table definitions, grouping rules, settings, source/input hashes, and export hashes | Standard and study |
| `prevalence_draws.jsonl` | Per-draw metrics, subset hashes, and conditional cluster intervals | Standard and study |
| `review_cases.csv` | Compact response links, case reasons, and blank fields for human review | Standard and study |
| `call_index.sqlite3` | Rebuildable index of saved calls | Study |

Generated results are excluded from Git. Keep the output directory together when archiving or sharing a run.

Future batch errors also save `last_failure` in the batch/job metadata: time, exception type, stage, and project-relative code location. Exception messages, raw responses, full tracebacks, and absolute source paths are excluded. This records the most recent failure even after a successful resume; the batch status still describes the current outcome. Earlier runs without this field may not retain enough information to diagnose their failure.

All reports include every classification score and recorded diagnostic. Standard reports link their additional analysis report after automatic analysis finishes. Reanalysis through the CLI writes `analysis_report.html` directly. Study `metrics.csv` keeps the scores and `analysis.json` records comparisons and provenance. New predictions retain source sample IDs, code hashes, response keys, draw pools, and parser details; older outputs may lack some of these links.

Standard reports provide dataset, model, prompt, verdict-protocol, parser, and language filters. Charts keep these conditions separate and use pages for large selections. Decision diagnostics show call counts, recorded generation time, token use, output-limit hits, response diversity, and generation errors when available. The execution table separately shows fresh calls, cache reuse, workers, and measured elapsed time; its combination-level measurements are not prorated by a language filter. CSV and JSON exports include all filtered combinations across table pages. Print / PDF uses the browser's print dialog.

Study reports include the condition catalog, UNKNOWN counts, decision and pool budgets, task-wording variation and ranks, paired comparisons, and recorded generation-session counters. Analysis-only resume retains those saved counters and makes no new model calls. Search filters table rows locally. Missing measurements display as unavailable, and tooltips explain the scores and diagnostics. Standard charts and enhanced table controls use external libraries; basic tables and filters remain usable when those libraries cannot load. Study tables work offline.

## Project file index

The index lists the project files and their roles. Individual CVE snippets and generated run files are grouped under their folders. Local environments, Python caches, and Git internals are omitted. `.gitattributes` preserves supplied data bytes and uses Linux line endings for shell launchers.

```text
PromptAudit/
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
|   |-- batch_runner.py                  # Plan, run, and resume selected experiment types together
|   |-- inference.py                     # Shared request execution, local response cache, and accounting
|   |-- runner.py                        # Execute dashboard runs and save checkpoints and reports
|   `-- revision_study.py                # Execute matched batch runs and reuse saved model calls
|-- data/
|   |-- toy.csv                          # Small mixed-language dataset for smoke tests
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
|   |-- dummy_model.py                   # Offline keyword-based backend for smoke tests
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
|   |-- generate_fake_report.py          # Generate synthetic results to check report rendering
|   |-- test_analysis_cli.py             # Check offline analysis and dataset-audit commands
|   |-- test_api_model.py                # Check API metadata, missing measurements, and failure privacy
|   |-- test_artifacts.py                # Check lazy saved-artifact loading and response integrity
|   |-- test_bigvul_dataset.py           # Check bundled cohorts, metadata, and mixed-dataset studies
|   |-- test_cvefixes_dataset.py         # Check compressed cohorts, source parity, and metadata exports
|   |-- test_batch_runner.py             # Check batch planning, response reuse, progress, and resume
|   |-- test_bootstrap_performance.py    # Check interval equivalence and bounded resampling reuse
|   |-- test_gui_config.py               # Check dashboard selections, presets, and worker dispatch
|   |-- test_inference.py                # Check request isolation, cache matching, and parallel execution
|   |-- test_output_protocol.py          # Check shared formatting, verdict order, and unchanged parsing rules
|   |-- test_paper_exports.py            # Check table precision, provenance, escaping, and bounded previews
|   |-- test_privacy.py                  # Check credential redaction and API key handling
|   |-- test_research_analysis.py        # Check matched prevalence subsets, selective scores, and audits
|   |-- test_revision_study.py           # Check prompts, backends, matched studies, analysis, and resume
|   |-- test_standard_report.py          # Check complete metrics, filters, exports, and safe embedded data
|   |-- test_study_report.py             # Check complete metrics, safe HTML, and comparison reports
|   |-- test_study_runner.py             # Check study selection, pause, stop, and saved resume
|   |-- test_uncertainty.py              # Check grouped intervals and matched run-seed summaries
|   `-- test_validation_traceability.py  # Check shared validation, response links, and analysis-only resume
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
python -m unittest discover -s tests -v
```

The tests cover dataset loading, prompt preservation, matched comparisons, voting rules, parser reuse, clustered analysis, dashboard settings, reports, credential handling, and resume behavior. They do not require a model server or GPU.

To check the HTML report with synthetic data, run `python tests/generate_fake_report.py` and open `results/fake_report.html`.

## Troubleshooting

- **No Ollama model appears:** check `ollama list`, confirm the exact tag is in `config.yaml`, and restart the dashboard after pulling it.
- **Cannot connect to Ollama:** confirm the service is running at `http://127.0.0.1:11434`.
- **Tkinter is missing or the GUI cannot open:** install Tkinter and use a desktop session. The batch runner works without a display.
- **A local dataset cannot be found:** check its configured path and run dashboard commands from the project directory.
- **A copied virtual environment points to a missing Python:** create a fresh environment on the current machine and reinstall `requirements.txt`.
