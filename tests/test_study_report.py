"""Study reporting choices must not alter saved scientific scores or vote pools."""

import csv
import json
import tempfile
import unittest
from html import escape
from pathlib import Path
from unittest.mock import patch

from evaluation.metrics import DEFAULT_METRICS, DIAGNOSTIC_HELP, METRIC_HELP
from evaluation.template_analysis import analyze_study, paired_comparison


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


if __name__ == "__main__":
    unittest.main()
