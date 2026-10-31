"""Check report display choices and safe embedding of experiment metadata."""

import csv
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from core.runner import ExperimentRunner
from evaluation.report import HtmlReport
from evaluation.metrics import DEFAULT_METRICS, Metrics


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
const context={document:{getElementById:element,addEventListener(){},querySelectorAll(){return [];},
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


if __name__ == "__main__":
    unittest.main()
