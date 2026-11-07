"""Standard reports, study reports, and paper exports."""

import csv
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core.runner import ExperimentRunner
from evaluation.metrics import DEFAULT_METRICS, DIAGNOSTIC_HELP, METRIC_HELP, Metrics
from evaluation.paper_exports import PREVIEW_ROWS, write_paper_exports
from evaluation.report import HtmlReport
from evaluation.template_analysis import analyze_study, paired_comparison


def evaluate_report(records, expression):
    """Exercise the generated JavaScript without CDN assets or a browser."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "report.html"
        HtmlReport(records).write(str(path), records)
        source = re.search(r"<script>([\s\S]*?)</script>", path.read_text(encoding="utf-8")).group(1)
    harness = r"""
const vm=require('vm'), fs=require('fs');
const input=JSON.parse(fs.readFileSync(0,'utf8')), elements={};
function element(id) {
  if(!elements[id]) elements[id]={value:id.startsWith('threshold-') ? (id==='threshold-AbstentionRate'?'1':'0'):'',
    style:{},hidden:false,addEventListener(){},getContext(){return {clearRect(){}};},click(){},
    classList:{add(){},remove(){}},querySelectorAll(){return [];}};
  return elements[id];
}
const context={document:{getElementById:element,addEventListener(){},querySelector(){return null;},querySelectorAll(){return [];},
  createElement:()=>element('new-element'),documentElement:{getAttribute(){return 'light';}}},
  window:{},setTimeout(){},console,Blob,charts:[],elements};
context.URL={createObjectURL(blob){context.lastBlob=blob;return 'blob:test';},revokeObjectURL(){}};
context.Chart=class {constructor(_canvas,config){context.charts.push(config);}destroy(){}};
vm.createContext(context); vm.runInContext(input.script,context);
Promise.resolve(vm.runInContext(input.expression,context)).then(value=>process.stdout.write(JSON.stringify(value)));
"""
    result = subprocess.run([shutil.which("node"), "-e", harness],
                            input=json.dumps({"script": source, "expression": expression}),
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


class StandardReportTests(unittest.TestCase):
    def test_pilot_record_marks_the_classification_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.html"
            records = [{"pilot": True}]
            HtmlReport(records).write(str(path), records)
            self.assertIn("Pilot / smoke-test results", path.read_text(encoding="utf-8"))

    def test_saved_result_analysis_report_is_linked_when_available(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            path = output / "report.html"
            HtmlReport([]).write(str(path), [])
            self.assertNotIn('href="analysis_report.html"', path.read_text(encoding="utf-8"))
            (output / "analysis_report.html").write_text("<html></html>", encoding="utf-8")
            HtmlReport([]).write(str(path), [])
            self.assertIn('href="analysis_report.html"', path.read_text(encoding="utf-8"))
            (output / "paper").mkdir()
            (output / "paper" / "index.html").write_text("<html></html>", encoding="utf-8")
            HtmlReport([]).write(str(path), [])
            self.assertIn('href="paper/index.html"', path.read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_browser_metrics_match_python_with_both_types_of_abstention(self):
        predictions = [{"gold": "safe", "pred": "safe"}, {"gold": "safe", "pred": "unknown"},
                       {"gold": "vulnerable", "pred": "unknown"}, {"gold": "vulnerable", "pred": "vulnerable"},
                       {"gold": "vulnerable", "pred": "safe"}]
        expected = Metrics()
        for row in predictions:
            expected.add(row["gold"], row["pred"])
        expected.compute()
        actual = evaluate_report([], f"aggregatePredictionMetrics({json.dumps(predictions)})")
        self.assertEqual(actual["Accuracy"], 0.4)
        self.assertEqual(actual, expected.to_dict())

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_rebuilt_report_and_exports_refresh_saved_accuracy(self):
        record = {"dataset": "fixture", "model": "fixture", "prompt": "zero_shot",
                  "TP": 1, "TN": 1, "FP": 0, "FN": 1, "UnFN": 1, "Incorrect": 1, "Unknown": 2,
                  "Accuracy": 0.5, "Precision": 1.0, "Recall": 1 / 3, "F1": 0.5,
                  "Coverage": 0.6, "AbstentionRate": 0.4, "EffectiveF1": 0.3,
                  "predictions": [{"gold": "safe", "pred": "safe", "language": "C"},
                                  {"gold": "safe", "pred": "unknown", "language": "C"},
                                  {"gold": "vulnerable", "pred": "unknown", "language": "Python"},
                                  {"gold": "vulnerable", "pred": "vulnerable", "language": "Python"},
                                  {"gold": "vulnerable", "pred": "safe", "language": "Python"}]}
        result = evaluate_report([record], """(async () => {
            const overall=RECORDS[0].Accuracy;
            const filtered=recordForSelectedLanguage(RECORDS[0],'C').Accuracy;
            exportCSV(); const csv=await lastBlob.text();
            exportJSON(); const json=JSON.parse(await lastBlob.text());
            return {overall,filtered,csv,json};
        })()""")
        self.assertEqual(result["overall"], 0.4)
        self.assertEqual(result["filtered"], 0.5)
        self.assertEqual(result["json"][0]["Accuracy"], 0.4)
        self.assertEqual(float(next(csv.DictReader(io.StringIO(result["csv"])))["Accuracy"]), 0.4)
        self.assertEqual(record["Accuracy"], 0.5)

    def test_saved_standard_records_and_csv_refresh_accuracy(self):
        record = {"dataset": "fixture", "model": "fixture", "prompt": "zero_shot",
                  "output_protocol": "verdict_first", "parser_mode": "strict",
                  "TP": 0, "TN": 1, "FP": 0, "FN": 0, "UnFN": 0, "Incorrect": 1,
                  "Accuracy": 1.0, "predictions": []}
        with tempfile.TemporaryDirectory() as folder:
            runner = ExperimentRunner({}, progress=lambda _: None)
            runner.records_jsonl_path = str(Path(folder) / "records.jsonl")
            runner.metrics_csv_path = str(Path(folder) / "metrics.csv")
            runner.predictions_dir = str(Path(folder) / "predictions")
            Path(runner.records_jsonl_path).write_text(json.dumps(record) + "\n", encoding="utf-8")
            restored = runner._load_records_jsonl()
            self.assertEqual(restored[0]["Accuracy"], 0.5)
            runner._write_csv([record])
            with Path(runner.metrics_csv_path).open(newline="", encoding="utf-8") as stream:
                self.assertEqual(float(next(csv.DictReader(stream))["Accuracy"]), 0.5)
            self.assertEqual(record["Accuracy"], 1.0)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_new_thresholds_and_protocol_filters_select_the_expected_records(self):
        records = [{"dataset": "a", "F1": 0.9, "Coverage": 0.9, "AbstentionRate": 0.1,
                    "output_protocol": "verdict_first", "parser_mode": "strict"},
                   {"dataset": "b", "F1": 0.9, "Coverage": 0.5, "AbstentionRate": 0.5,
                    "output_protocol": "verdict_last", "parser_mode": "full"},
                   {"dataset": "c", "F1": 0.9, "Coverage": 0.95, "AbstentionRate": 0.05,
                    "output_protocol": "verdict_last", "parser_mode": "strict"}]
        result = evaluate_report(records, """elements['threshold-Coverage'].value='0.8';
            elements['threshold-AbstentionRate'].value='0.15';
            document.getElementById('filterProtocol').value='verdict_last';
            document.getElementById('filterParser').value='strict';
            applyFilters().map(row=>row.dataset)""")
        self.assertEqual(result, ["c"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_chart_keeps_datasets_separate_instead_of_averaging_scores(self):
        records = [{"dataset": "a", "model": "same", "prompt": "cot", "F1": 0.25},
                   {"dataset": "b", "model": "same", "prompt": "cot", "F1": 0.75}]
        chart = evaluate_report(records, "renderChart(RECORDS); charts[0].data")
        self.assertEqual(next(item for item in chart["datasets"] if item["label"] == "F1")["data"], [0.25, 0.75])
        self.assertIn("a | same", chart["labels"][0])
        self.assertIn("b | same", chart["labels"][1])

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_chart_pages_bound_canvas_size_without_dropping_export_rows(self):
        records = [{"dataset": f"dataset-{index}", "model": "fixture", "prompt": "cot", "F1": 0.5}
                   for index in range(35)]
        result = evaluate_report(records, """renderChart(RECORDS);
            const first=charts[0].data.labels;
            chartPage=1; renderChart(RECORDS,false);
            const second=charts[1].data.labels;
            const width=elements.chartStage.style.width;
            const status=elements.chartPageStatus.textContent;
            const exported=applyFilters().length;
            renderChart(RECORDS.slice(0,2));
            ({first,second,width,status,exported,reset:chartPage})""")
        self.assertEqual(len(result["first"]), 12)
        self.assertEqual(len(result["second"]), 12)
        self.assertIn("dataset-12 |", result["second"][0])
        self.assertLessEqual(int(result["width"].removesuffix("px")), 2000)
        self.assertIn("13-24 of 35", result["status"])
        self.assertEqual(result["exported"], 35)
        self.assertEqual(result["reset"], 0)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_prediction_pages_search_the_full_set_and_keep_all_export_rows(self):
        predictions = [
            {"id": index, "gold": "safe", "pred": "safe" if index < 25 else "unknown",
             "cve_id": f"CVE-2026-{index}", "language": "C"}
            for index in range(1, 38)
        ]
        records = [{"dataset": "fixture", "model": "fixture", "prompt": "cot",
                    "predictions": predictions}]
        result = evaluate_report(records, """(async () => {
          const rows = () => (elements.detailsBody.innerHTML.match(/<tr>/g) || []).length;
          renderDetails(RECORDS);
          const initial = {rows:rows(), status:elements.detailCount.textContent};
          detailPage=3; renderDetailPage();
          const last = {rows:rows(), status:elements.detailCount.textContent,
                        nextDisabled:elements.detailNext.disabled};
          detailsActive[7]='unknown'; refreshDetailFilters();
          const column = {rows:rows(), status:elements.detailCount.textContent};
          elements.detailSearch.value='CVE-2026-37';
          refreshDetailFilters();
          const search = {rows:rows(), status:elements.detailCount.textContent,
                          html:elements.detailsBody.innerHTML};
          renderDetails(RECORDS);
          detailSortColumn=0; detailSortDirection=-1; refreshDetailFilters();
          const sorted = elements.detailsBody.innerHTML.startsWith('<tr><td>37</td>');
          exportJSON();
          const exported = JSON.parse(await lastBlob.text())[0].predictions.length;
          renderDetails(RECORDS,true);
          const printed = rows();
          return {initial,last,column,search,sorted,exported,printed};
        })()""")
        self.assertEqual(result["initial"], {"rows": 10, "status": "Showing 1-10 of 37 predictions"})
        self.assertEqual(result["last"], {"rows": 7, "status": "Showing 31-37 of 37 predictions",
                                         "nextDisabled": True})
        self.assertEqual(result["column"], {"rows": 10, "status": "Showing 1-10 of 13 predictions"})
        self.assertEqual(result["search"]["status"], "Showing 1 of 1 prediction")
        self.assertEqual(result["search"]["rows"], 1)
        self.assertIn("CVE-2026-37", result["search"]["html"])
        self.assertTrue(result["sorted"])
        self.assertEqual(result["exported"], 37)
        self.assertEqual(result["printed"], 37)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_decision_cost_preserves_reused_time_and_missing_measurements(self):
        records = [{"predictions": [
            {"decision_calls": 5, "decision_seconds": 10, "decision_prompt_tokens": 200,
             "decision_output_tokens": 40, "distinct_responses": 3,
             "decision_output_limit_hits": 1, "decision_generation_errors": 0},
            {"decision_calls": 5, "decision_seconds": 20, "decision_prompt_tokens": None,
             "decision_output_tokens": 60, "distinct_responses": 2,
             "decision_output_limit_hits": None, "decision_generation_errors": 1}],
            "inference_performance": {"wall_seconds": 0.2, "generated_calls": 0, "shared_cache_hits": 10}}]
        result = evaluate_report(records, "decisionDiagnostics(RECORDS[0])")
        self.assertEqual(result["seconds_per_sample"], 15)
        self.assertEqual(result["calls_per_sample"], 5)
        self.assertIsNone(result["prompt_tokens_per_sample"])
        self.assertIsNone(result["output_limit_hit_rate"])
        self.assertEqual(result["output_limit_measurement_coverage"], 0.5)
        self.assertEqual(result["generation_errors_per_sample"], 0.5)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_csv_includes_all_metrics_and_real_line_breaks(self):
        result = evaluate_report([{"dataset": 'quoted,"value"', "F1": 0.5, "Coverage": 0.75,
                                   "AbstentionRate": 0.25, "EffectiveF1": 0.375}],
                                 "exportCSV(); lastBlob.text()")
        self.assertEqual(len(result.splitlines()), 2)
        self.assertIn('"EffectiveF1"', result.splitlines()[0])
        self.assertIn('"quoted,""value"""', result.splitlines()[1])
        self.assertIn('"0.375"', result.splitlines()[1])

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_table_refresh_uses_the_pinned_library_rows_property(self):
        result = evaluate_report([], """(() => {
          const removed=[], inserted=[], pages=[];
          const table={data:{data:[['old'],['old2']]},rows:{remove(indexes){removed.push(indexes);}},
            insert(data){inserted.push(data.data);},page(number){pages.push(number);}};
          replaceTableRows(table,[['new']]); return {removed,inserted,pages};
        })()""")
        self.assertEqual(result, {"removed": [[0, 1]], "inserted": [[["new"]]], "pages": [1]})

    def test_distinct_model_parameters_and_new_diagnostic_sections_are_present(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.html"
            records = [{"model": "first", "params": {"context_window": 2048}},
                       {"model": "second", "params": {"context_window": 16384}}]
            HtmlReport(records).write(str(path), records)
            text = path.read_text(encoding="utf-8")
            self.assertIn("first (1 combinations)", text)
            self.assertIn("second (1 combinations)", text)
            self.assertIn("16384", text)
            self.assertIn('id="threshold-Coverage"', text)
            self.assertIn('id="threshold-EffectiveF1"', text)
            self.assertIn('id="threshold-Accuracy"', text)
            self.assertIn('id="execution-table"', text)
            self.assertIn('id="decision-table"', text)
            self.assertIn("Batch reuse", text)
            self.assertIn("Fresh calls", text)
            self.assertIn("Recorded seconds / sample", text)

    def test_all_metrics_have_headers_thresholds_and_embedded_names(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.html"
            records = [{"dataset": "fixture", "model": "fixture", "prompt": "zero_shot",
                        "params": {"api_key": "private-test-value", "experiment_notes": "<b>notes</b>"},
                        "Accuracy": 0.5, "F1": 0.5, "Coverage": 1.0, "predictions": []}]
            HtmlReport(records).write(str(path), records)
            text = path.read_text(encoding="utf-8")
            self.assertIn("const METRIC_NAMES = " + json.dumps(list(DEFAULT_METRICS)) + ";", text)
            headers = text.split('id="results-table"', 1)[1].split("</thead>", 1)[0]
            self.assertIn(">F1</th>", headers)
            self.assertIn(">Cov</th>", headers)
            self.assertIn(">Acc</th>", headers)
            for name in DEFAULT_METRICS:
                self.assertIn(f'id="threshold-{name}"', text)
            self.assertNotIn("private-test-value", text)
            self.assertIn("&lt;b&gt;notes&lt;/b&gt;", text)

    def test_metadata_cannot_end_the_embedded_data_script(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.html"
            injected = "</script><script>unexpected()</script>"
            records = [{"dataset": injected, "params": {"experiment_notes": injected}}]
            HtmlReport(records).write(str(path), records, author=injected)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(injected, text)
            embedded = re.search(r"const RECORDS = (.*);", text).group(1)
            self.assertEqual(json.loads(embedded)[0]["dataset"], injected)

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to exercise report JavaScript")
    def test_embedded_data_and_json_export_omit_private_response_text(self):
        record = {"dataset": "fixture", "F1": 0.5,
                  "params": {"experiment_notes": "Keep these benign notes", "context_window": 2048},
                  "generation_anomalies": [{"reason": "generation_exception", "generation_info": {
                      "thinking_output": "private-thought-fixture", "response_preview": "private-preview-fixture",
                      "response_text_preview": "private-http-fixture", "error_message": "private-error-fixture",
                      "status": "error", "error_type": "Timeout", "context_window": 2048}}],
                  "predictions": [{"gold": "safe", "pred": "unknown", "raw_output": "private-raw-fixture",
                                   "prompt_text": "private-prompt-fixture"}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.html"
            HtmlReport([record]).write(str(path), [record])
            text = path.read_text(encoding="utf-8")
            for private in ("private-thought-fixture", "private-preview-fixture", "private-http-fixture",
                            "private-error-fixture", "private-raw-fixture", "private-prompt-fixture"):
                self.assertNotIn(private, text)
        exported = evaluate_report([record], "exportJSON(); lastBlob.text()")
        data = json.loads(exported)[0]
        self.assertEqual(data["params"]["experiment_notes"], "Keep these benign notes")
        info = data["generation_anomalies"][0]["generation_info"]
        self.assertEqual(info, {"status": "error", "error_type": "Timeout", "context_window": 2048})
        self.assertIn("thinking_output", record["generation_anomalies"][0]["generation_info"])

    def test_checkpoint_restores_credentials_without_metric_display_options(self):
        with tempfile.TemporaryDirectory() as folder:
            first = ExperimentRunner({"metrics": {"include": ["F1", "Coverage"]}})
            first.output_dir = folder
            first.checkpoint_path = str(Path(folder) / "checkpoint.json")
            first._save_checkpoint()
            state = json.loads(Path(first.checkpoint_path).read_text())
            state["gen_cfg"]["api_key"] = "legacy-private-test-value"
            Path(first.checkpoint_path).write_text(json.dumps(state))
            resumed = ExperimentRunner({"metrics": {"include": ["Accuracy"]},
                                        "api": {"api_key": "current-private-test-value"}})
            saved = resumed._load_checkpoint_state(first.checkpoint_path)
            resumed.gen_cfg.update(saved.get("gen_cfg", {}))
            self.assertNotIn("report_metrics", saved)
            self.assertEqual(resumed.gen_cfg["api_key"], "current-private-test-value")


def write_fixture(output, *, policies=("first", "majority_requested", "majority_valid"),
                  legacy_metrics=None, analysis=None, dataset="fixture", model="fixture"):
    manifest = {"pilot": True, "status": "completed", "config": {"analysis": analysis or {}}}
    if legacy_metrics is not None:
        manifest["config"]["metrics"] = {"include": legacy_metrics}
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    rows = []
    for sample, gold in enumerate(("safe", "vulnerable")):
        for policy in policies:
            rows.append({"dataset": dataset, "model_id": "fixture-model", "model": model,
                         "run_seed": 42, "protocol": "verdict_last", "parser_mode": "strict",
                         "condition": f"cot/{policy}/verdict_last", "comparison": "voting",
                         "family": "cot", "variant": "reference", "sample_uid": str(sample),
                         "cve_id": f"CVE-{sample}", "gold": gold, "pred": gold,
                         "aggregation": {"policy": policy},
                         "generation_ids": [f"{sample}:{draw}" for draw in range(5)],
                         "decision_calls": 1 if policy == "first" else 5,
                         "decision_seconds": 0.5, "decision_prompt_tokens": 100,
                         "decision_output_tokens": 20, "decision_output_limit_hits": 0,
                         "decision_generation_errors": 0, "distinct_responses": 2})
    (output / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return rows


class StudyReportTests(unittest.TestCase):
    def test_reanalysis_counts_unresolved_safe_samples_in_accuracy(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            rows = write_fixture(output)
            for row in rows:
                if row["gold"] == "safe":
                    row["pred"] = "unknown"
            predictions = "".join(json.dumps(row) + "\n" for row in rows)
            (output / "predictions.jsonl").write_text(predictions, encoding="utf-8")
            manifest = (output / "manifest.json").read_bytes()
            result = analyze_study(output, bootstrap=0)
            self.assertIn("evaluation/metrics.py", result["analysis_provenance"]["source_hashes"])
            with (output / "metrics.csv").open(newline="", encoding="utf-8") as stream:
                scores = list(csv.DictReader(stream))
            self.assertEqual(len(scores), 3)
            self.assertTrue(all(float(row["Accuracy"]) == 0.5 for row in scores))
            self.assertEqual((output / "predictions.jsonl").read_text(encoding="utf-8"), predictions)
            self.assertEqual((output / "manifest.json").read_bytes(), manifest)

    def test_cancelling_before_output_writes_preserves_previous_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_fixture(output)
            baseline = analyze_study(output, bootstrap=0)
            expected_pairs = len(baseline["component_and_voting_contrasts"])
            previous = {name: (output / name).read_bytes()
                        for name in ("metrics.csv", "analysis.json", "report.html")}
            completed = 0

            def compare(*args, **kwargs):
                nonlocal completed
                result = paired_comparison(*args, **kwargs)
                completed += 1
                return result

            def control():
                if completed == expected_pairs:
                    raise InterruptedError("cancelled analysis")

            with patch("evaluation.template_analysis.paired_comparison", side_effect=compare):
                with self.assertRaisesRegex(InterruptedError, "cancelled analysis"):
                    analyze_study(output, bootstrap=0, control=control)
            self.assertEqual(completed, expected_pairs)
            for name, content in previous.items():
                self.assertEqual((output / name).read_bytes(), content)

    def test_bootstrap_checks_cooperative_control_while_resampling(self):
        reference = [{"sample_uid": str(i), "cve_id": f"CVE-{i}", "gold": "safe", "pred": "safe"}
                     for i in range(2)]
        calls = 0

        def control():
            nonlocal calls
            calls += 1
            if calls == 3:
                raise InterruptedError("cancelled bootstrap")

        with self.assertRaisesRegex(InterruptedError, "cancelled bootstrap"):
            paired_comparison(reference, reference, bootstrap=500, control=control)
        self.assertEqual(calls, 3)

    def test_reports_include_all_metrics_even_for_legacy_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_fixture(output, legacy_metrics=["F1"], dataset="<script>alert('fixture')</script>",
                          model="https://fixture-user:fixture-password@example.invalid/model?token=fixture-token")
            result = analyze_study(output, bootstrap=10)
            report = (output / "report.html").read_text(encoding="utf-8")
            self.assertEqual(result["metric_names"], list(DEFAULT_METRICS))
            self.assertNotIn("selected_metrics", result)
            self.assertIn(">F1</th>", report)
            self.assertIn(">Accuracy</th>", report)
            self.assertIn("Difference: Recall", report)
            self.assertIn("Difference: Coverage", report)
            self.assertIn(escape(METRIC_HELP["F1"], quote=True), report)
            self.assertNotIn("<script>alert('fixture')</script>", report)
            self.assertEqual(report.count("<script>"), 1)
            self.assertIn("&lt;script&gt;", report)
            self.assertNotIn("fixture-password", report)
            self.assertNotIn("fixture-token", report)
            with (output / "metrics.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertTrue(all(name in rows[0] for name in DEFAULT_METRICS))
            self.assertIn("Decision cost and generation diagnostics", report)
            self.assertIn("Paired prediction comparisons", report)

    def test_optional_analyses_can_be_disabled_without_recomputing_pairs(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_fixture(output, analysis={"rankings": False, "paired_comparisons": False,
                                            "diagnostics": False})
            with patch("evaluation.template_analysis.paired_comparison", side_effect=AssertionError("disabled")):
                result = analyze_study(output, bootstrap=100)
            self.assertEqual(result["rankings"], [])
            self.assertEqual(result["component_and_voting_contrasts"], [])
            self.assertEqual(result["protocol_contrasts"], [])
            report = (output / "report.html").read_text(encoding="utf-8")
            self.assertIn("<summary>Decision cost", report)
            self.assertNotIn("<summary>Paired prediction", report)
            self.assertIn("Disabled optional sections", report)

    def test_policy_subsets_only_compare_selected_decisions(self):
        cases = [(("first",), []), (("majority_valid",), []),
                 (("first", "majority_requested"), ["majority_requested_minus_first"]),
                 (("first", "majority_valid"), ["majority_valid_minus_first"]),
                 (("majority_requested", "majority_valid"), ["majority_valid_minus_requested"])]
        for policies, expected in cases:
            with self.subTest(policies=policies), tempfile.TemporaryDirectory() as folder:
                output = Path(folder)
                write_fixture(output, policies=policies)
                result = analyze_study(output, bootstrap=0)
                comparisons = result["component_and_voting_contrasts"]
                self.assertEqual([row["comparison"] for row in comparisons], expected)
                for row in comparisons:
                    self.assertEqual(row["same_decision_budget"], "first" not in policies)

    def test_changed_vote_pool_is_rejected_even_when_paired_output_is_disabled(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            rows = write_fixture(output, analysis={"paired_comparisons": False})
            rows[-1]["generation_ids"][-1] = "different-draw"
            (output / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "same generation pool"):
                analyze_study(output, bootstrap=0)
            self.assertFalse((output / "metrics.csv").exists())
            self.assertFalse((output / "report.html").exists())

    def test_tooltips_cover_metrics_and_diagnostics_without_changing_definitions(self):
        self.assertEqual(set(DEFAULT_METRICS), set(METRIC_HELP))
        self.assertIn("all evaluated samples", METRIC_HELP["Accuracy"])
        self.assertIn("UnFN + Incorrect", METRIC_HELP["Accuracy"])
        self.assertIn("vulnerable abstentions", METRIC_HELP["Recall"])
        self.assertIn("same samples", DIAGNOSTIC_HELP["paired_comparisons"])
        self.assertIn("not reasoning quality", DIAGNOSTIC_HELP["output_tokens_per_sample"])

    def test_session_execution_is_separate_from_logical_decision_cost(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_fixture(output)
            manifest = json.loads((output / "manifest.json").read_text())
            manifest.update(total_saved_calls=10, new_calls_this_session=10,
                inference_performance=[{"model_id": "fixture-model", "workers": 2,
                    "generated_calls": 0, "shared_cache_hits": 8, "batch_cache_hits": 2, "run_reuses": 0,
                    "wall_seconds": 0.125, "generation_seconds": 0.0,
                    "persistent_cache_enabled": True}])
            (output / "manifest.json").write_text(json.dumps(manifest))
            result = analyze_study(output, bootstrap=0)
            performance = result["inference_performance"][0]
            self.assertEqual(performance["generated_calls"], 0)
            self.assertEqual(performance["shared_cache_hits"], 8)
            self.assertEqual(performance["batch_cache_hits"], 2)
            self.assertEqual(performance["wall_seconds"], 0.125)
            self.assertEqual(performance["shared_cache_warning"], "None recorded")
            report = (output / "report.html").read_text()
            self.assertIn("Recorded generation execution", report)
            self.assertIn("Fresh executions", report)
            self.assertIn("Batch reuse", report)
            self.assertIn("analysis-only resume keeps the saved counters", report)
            self.assertIn("shared-pool costs must not be summed", report)
            self.assertIn("0.1250", report)
            self.assertIn("0.5000", report)
            with (output / "metrics.csv").open(newline="") as stream:
                scores = list(csv.DictReader(stream))
            self.assertEqual([row["seconds_per_sample"] for row in scores], ["0.5"] * 3)
            self.assertEqual([row["calls_per_sample"] for row in scores], ["1", "5", "5"])

    def test_missing_runtime_and_pool_measurements_stay_unavailable(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_fixture(output)
            result = analyze_study(output, bootstrap=0)
            self.assertEqual(result["inference_performance"], [])
            report = (output / "report.html").read_text()
            self.assertIn("Inference execution counters are unavailable", report)
            self.assertIn("Unavailable", report)
            with (output / "metrics.csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertTrue(all(row["pool_calls_per_sample"] == "" for row in rows))

    def test_unknown_counts_pool_budget_and_setup_are_exposed_without_raw_text(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            rows = write_fixture(output)
            for row in rows:
                row["pool_calls"] = 5
                if row["sample_uid"] == "0":
                    row["pred"] = "unknown"
            (output / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            manifest = json.loads((output / "manifest.json").read_text())
            manifest["config"].update(section="C", votes=5, min_valid_votes=3, seeds=[42])
            manifest["conditions"] = [{"id": "cot/first/verdict_last", "comparison": "voting",
                "family": "cot", "variant": "reference", "protocol": "verdict_last", "draws": 5,
                "policy": "first", "template": "PRIVATE RAW PROMPT"}]
            (output / "manifest.json").write_text(json.dumps(manifest))
            analyze_study(output, bootstrap=0)
            report = (output / "report.html").read_text()
            self.assertIn(">UNKNOWN</th>", report)
            self.assertIn("Pool draws / sample", report)
            self.assertIn("Minimum valid votes", report)
            self.assertIn("Selected experiment conditions", report)
            self.assertNotIn("PRIVATE RAW PROMPT", report)
            with (output / "metrics.csv").open(newline="") as stream:
                scores = list(csv.DictReader(stream))
            self.assertTrue(all(row["Unknown"] == "1" and row["pool_calls_per_sample"] == "5" for row in scores))

    def test_paired_comparisons_expose_measured_budget_equality(self):
        left = [{"sample_uid": "a", "gold": "safe", "pred": "safe", "decision_calls": 1}]
        right = [{**left[0], "decision_calls": 5}]
        self.assertIs(paired_comparison(left, left, bootstrap=0)["same_decision_budget"], True)
        self.assertIs(paired_comparison(left, right, bootstrap=0)["same_decision_budget"], False)
        del right[0]["decision_calls"]
        self.assertIsNone(paired_comparison(left, right, bootstrap=0)["same_decision_budget"])

    def test_protocol_comparison_labels_both_orders_and_collapses_the_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            rows = write_fixture(output)
            rows += [{**row, "protocol": "verdict_first",
                      "condition": row["condition"].replace("verdict_last", "verdict_first")}
                     for row in rows]
            (output / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            manifest = json.loads((output / "manifest.json").read_text())
            manifest["conditions"] = [{"id": "cot/first/verdict_last", "draws": 5}]
            (output / "manifest.json").write_text(json.dumps(manifest))
            result = analyze_study(output, bootstrap=0)
            self.assertTrue(result["protocol_contrasts"])
            self.assertTrue(all("protocol" not in row for row in result["protocol_contrasts"]))
            report = (output / "report.html").read_text()
            self.assertIn("Both (last minus first)", report)
            catalog = '<details data-filterable data-title="Selected experiment conditions">'
            self.assertIn(catalog, report)
            self.assertIn('<details open data-filterable data-title="Classification metrics">', report)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


class PaperExportTests(unittest.TestCase):
    def test_values_context_intervals_and_provenance_are_preserved(self):
        context = {"dataset": "fixture", "model_id": "weights-1", "model": "fixture model",
                   "run_seed": 42, "protocol": "verdict_last", "parser_mode": "strict", "condition": "zero/reference"}
        value = 1 / 3
        metrics = [{**context, "samples": 3, "answered_samples": 2, "TP": 1, "TN": 1, "FP": 0,
                    "FN": 0, "UnFN": 0, "Incorrect": 1, "Accuracy": value, "F1": 0.12345678901234567}]
        analysis = {"pilot": False, "run_status": "completed", "artifact_kind": "standard",
            "condition_intervals": [{**context, "ci95": {"Accuracy": [value, 0.9]}}],
            "seed_summaries": [{**{key: val for key, val in context.items() if key != "run_seed"},
                                "metric": "F1", "run_seeds": [42, 43], "mean": None,
                                "unavailable_reason": "Model identities differ"}],
            "research": {"dataset_overlap": [{"dataset_a": "a", "dataset_b": "b", "shared_projects": None}]},
            "analysis_provenance": {"created_at": "fixture-time", "source_hashes": {"metrics.py": "source-hash"},
                                    "input_hashes": {"records.jsonl": "input-hash"}}}
        with tempfile.TemporaryDirectory() as directory:
            result = write_paper_exports(directory, metrics, analysis)
            target = Path(directory) / "paper"
            scores = read_csv(target / "condition_scores.csv")
            self.assertEqual(len(scores), 1)
            self.assertEqual(float(scores[0]["Accuracy"]), value)
            self.assertEqual(scores[0]["F1"], repr(metrics[0]["F1"]))
            for key, val in context.items():
                self.assertEqual(scores[0][key], str(val))
            bounds = read_csv(target / "condition_intervals.csv")[0]
            self.assertEqual(float(bounds["ci95.Accuracy.lower"]), value)
            self.assertEqual(float(bounds["ci95.Accuracy.upper"]), 0.9)
            seed = read_csv(target / "seed_summaries.csv")[0]
            self.assertEqual(seed["run_seeds.0"], "42")
            self.assertEqual(seed["mean"], "")
            self.assertEqual(seed["unavailable_reason"], "Model identities differ")
            self.assertEqual(read_csv(target / "dataset_overlap.csv")[0]["shared_projects"], "")
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["provenance"]["input_hashes"]["records.jsonl"], "input-hash")
            self.assertEqual(manifest["provenance"]["source_hashes"]["metrics.py"], "source-hash")
            self.assertEqual(manifest["tables"]["condition_scores"]["rows"], 1)
            self.assertIn("mean F1 differs", manifest["aggregation_rules"]["seed_summaries"])
            for name, digest in manifest["file_sha256"].items():
                self.assertEqual(hashlib.sha256((target / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(set(result["files"]), {str(path.relative_to(directory)).replace("\\", "/") for path in target.iterdir()})

    def test_untrusted_text_is_escaped_and_raw_responses_are_excluded(self):
        metrics = [{"dataset": "=HYPERLINK(\"bad\")", "model": "<script>alert(1)</script>_&%",
                    "condition": "a{b}\\c", "run_seed": 42, "F1": 0.5, "delta": -0.5,
                    "raw_output": "PRIVATE RESPONSE", "thinking": "PRIVATE THINKING", "api_key": "PRIVATE KEY"}]
        analysis = {"pilot": True, "research": {"review_cases": [{"case_id": "case1", "review_notes": "PRIVATE REVIEW", "reasons": ["output_limit"]}]}}
        with tempfile.TemporaryDirectory() as directory:
            write_paper_exports(directory, metrics, analysis)
            target = Path(directory) / "paper"
            row = read_csv(target / "condition_scores.csv")[0]
            self.assertEqual(row["dataset"], "'=HYPERLINK(\"bad\")")
            self.assertEqual(row["delta"], "-0.5")
            html = (target / "index.html").read_text(encoding="utf-8")
            tex = (target / "condition_scores.tex").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertIn(r"\_\&\%", tex)
            self.assertIn(r"a\{b\}\textbackslash{}c", tex)
            self.assertIn("Pilot output", html)
            for path in target.iterdir():
                content = path.read_text(encoding="utf-8")
                self.assertNotIn("PRIVATE RESPONSE", content)
                self.assertNotIn("PRIVATE THINKING", content)
                self.assertNotIn("PRIVATE KEY", content)
                self.assertNotIn("PRIVATE REVIEW", content)

    def test_prevalence_detail_is_streamed_and_preview_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "prevalence_draws.jsonl"
            with source.open("w", encoding="utf-8") as stream:
                for draw in range(PREVIEW_ROWS + 9):
                    stream.write(json.dumps({"dataset": "fixture", "condition": "x", "draw": draw,
                        "F1": draw / 100, "cluster_intervals": {"ci95": {"F1": [0.1, 0.9]}}}) + "\n")
            original = Path.read_text

            def forbid_full_read(path, *args, **kwargs):
                if path == source:
                    raise AssertionError("Detail JSONL must be streamed")
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", forbid_full_read):
                write_paper_exports(directory, [], {"research": {"prevalence_draws": [{"draw": "wrong-inline-source"}]}})
            rows = read_csv(Path(directory) / "paper" / "prevalence_draws.csv")
            self.assertEqual(len(rows), PREVIEW_ROWS + 9)
            self.assertEqual(rows[-1]["draw"], str(PREVIEW_ROWS + 8))
            self.assertEqual(rows[0]["cluster_intervals.ci95.F1.lower"], "0.1")
            manifest = json.loads((Path(directory) / "paper" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["tables"]["prevalence_draws"]["rows"], PREVIEW_ROWS + 9)
            html = (Path(directory) / "paper" / "index.html").read_text(encoding="utf-8")
            self.assertIn(f"Preview: first {PREVIEW_ROWS} rows", html)
            self.assertNotIn("wrong-inline-source", html)

    def test_rank_rows_keep_their_variant_family_and_run_axes(self):
        analysis = {"rankings": [{"dataset": "a", "run_seed": 42, "metric": "F1",
            "ranks": {"reference": {"cot": 1, "zero_shot": 1}, "variant2": {"cot": 2, "zero_shot": 1}},
            "changed_from_reference": {"reference": False, "variant2": True}}]}
        with tempfile.TemporaryDirectory() as directory:
            write_paper_exports(directory, [], analysis)
            rows = read_csv(Path(directory) / "paper" / "rankings.csv")
            self.assertEqual(len(rows), 4)
            candidate = next(row for row in rows if row["variant"] == "variant2" and row["family"] == "cot")
            self.assertEqual(candidate["rank"], "2")
            self.assertEqual(candidate["run_seed"], "42")
            self.assertEqual(candidate["ranking_changed_from_reference"], "True")


if __name__ == "__main__":
    unittest.main()
