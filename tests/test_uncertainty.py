"""Cluster intervals, matched seeds, and bootstrap reuse."""

from array import array
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from evaluation import template_analysis as analysis
from evaluation.metrics import Metrics
from evaluation.template_analysis import analyze_artifacts, cluster_intervals, paired_comparison, resolve_analysis_settings
from tests.test_artifacts import write_study


FAST = {"prevalence": False, "output_audit": False, "dataset_audit": False}


class UncertaintyTests(unittest.TestCase):
    def test_study_seed_summaries_require_matching_inference_namespaces(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("first", "second")]
            write_study(paths[0], seed=42)
            write_study(paths[1], seed=43)
            manifest = json.loads((paths[1] / "manifest.json").read_text())
            manifest["inference_namespaces"]["fixture-id"] = "different-machine-runtime"
            (paths[1] / "manifest.json").write_text(json.dumps(manifest))
            changed = analyze_artifacts(paths, 0, options=FAST)
            self.assertTrue(all(row["mean"] is None and "different model identities or generation settings" in row["unavailable_reason"]
                                for row in changed["seed_summaries"]))
            self.assertTrue(all(row["Accuracy"] == 1 for row in changed["research"]["selective_predictions"]))
            manifest["inference_namespaces"]["fixture-id"] = "fixture-runtime"
            (paths[1] / "manifest.json").write_text(json.dumps(manifest))
            matched = analyze_artifacts(paths, 0, options=FAST)
            self.assertTrue(all(row["unavailable_reason"] is None for row in matched["seed_summaries"]))

    def test_study_without_runtime_identity_keeps_scores_but_not_seed_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("first", "second")]
            for path, seed in zip(paths, (42, 43)):
                write_study(path, seed=seed)
                manifest = json.loads((path / "manifest.json").read_text())
                del manifest["inference_namespaces"]
                (path / "manifest.json").write_text(json.dumps(manifest))
            result = analyze_artifacts(paths, 0, options=FAST)
            self.assertTrue(all(row["mean"] is None and "Complete sample and model identities" in row["unavailable_reason"]
                                for row in result["seed_summaries"]))
            self.assertEqual(len(result["research"]["selective_predictions"]), 2)
            self.assertTrue(all(row["Accuracy"] == 1 for row in result["research"]["selective_predictions"]))

    def test_standard_seed_summaries_require_matching_source_namespaces(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("first", "second")]
            for path, seed, namespace in zip(paths, (42, 43), ("source-v1", "source-v2")):
                path.mkdir()
                (path / "checkpoint.json").write_text(json.dumps({"status": "completed"}))
                record = {"dataset": "fixture", "model": "fixture", "model_id": "fixed-model",
                    "model_info": {"digest": "fixed"}, "inference_namespace": namespace,
                    "prompt": "cot", "params": {"seed": seed}, "predictions": [
                        {"sample_uid": "sample", "code_sha256": "code", "cve_id": "CVE-A",
                         "gold": "safe", "pred": "safe"}]}
                (path / "records.jsonl").write_text(json.dumps(record) + "\n")
            result = analyze_artifacts(paths, 0, options=FAST)
            self.assertTrue(all(row["mean"] is None and "different model identities or generation settings" in row["unavailable_reason"]
                                for row in result["seed_summaries"]))
            second = json.loads((paths[1] / "records.jsonl").read_text())
            second["inference_namespace"] = "source-v1"
            (paths[1] / "records.jsonl").write_text(json.dumps(second) + "\n")
            matched = analyze_artifacts(paths, 0, options=FAST)
            self.assertTrue(all(row["unavailable_reason"] is None for row in matched["seed_summaries"]))
            del second["inference_namespace"]
            (paths[1] / "records.jsonl").write_text(json.dumps(second) + "\n")
            legacy = analyze_artifacts(paths, 0, options=FAST)
            self.assertTrue(all(row["mean"] is None and "Complete sample and model identities" in row["unavailable_reason"]
                                for row in legacy["seed_summaries"]))

    def test_all_metrics_have_cluster_intervals_and_abstention_complements_coverage(self):
        rows = [{"gold": "safe", "pred": "safe", "cve_id": "A"},
                {"gold": "safe", "pred": "unknown", "cve_id": "B"},
                {"gold": "vulnerable", "pred": "vulnerable", "cve_id": "C"}]
        result = cluster_intervals(rows, bootstrap=101)
        self.assertEqual(result["clusters"], 3)
        self.assertEqual(set(result["ci95"]), {"Accuracy", "Precision", "Recall", "F1", "Coverage",
                                               "AbstentionRate", "EffectiveF1", "FalsePositivesPer1000"})
        coverage, abstention = result["ci95"]["Coverage"], result["ci95"]["AbstentionRate"]
        self.assertAlmostEqual(abstention[0], 1 - coverage[1])
        self.assertAlmostEqual(abstention[1], 1 - coverage[0])

    def test_repository_grouping_never_falls_back_to_cves_or_rows(self):
        rows = [{"sample_uid": "a", "gold": "safe", "pred": "safe", "cve_id": "one", "repository": "repo-a"},
                {"sample_uid": "b", "gold": "safe", "pred": "unknown", "cve_id": "one", "repository": "repo-b"}]
        self.assertIsNone(cluster_intervals(rows, 31)["ci95"])
        result = cluster_intervals(rows, 31, group_by="repository")
        self.assertIsNotNone(result["ci95"])
        del rows[1]["repository"]
        missing = cluster_intervals(rows, 31, group_by="repository")
        self.assertIsNone(missing["ci95"])
        self.assertIn("Complete repository", missing["unavailable_reason"])
        paired = paired_comparison(rows, rows, 31, group_by="repository")
        self.assertIsNone(paired["cluster_bootstrap_ci95_by_metric"])

    def test_matching_repeat_runs_get_sample_sd_separate_from_cluster_uncertainty(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("first", "second")]
            write_study(paths[0], seed=42)
            write_study(paths[1], seed=43)
            lines = [json.loads(line) for line in (paths[1] / "predictions.jsonl").read_text().splitlines()]
            lines[0]["pred"] = "unknown"
            (paths[1] / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in lines))
            result = analyze_artifacts(paths, bootstrap=0, options=FAST)
            row = next(row for row in result["seed_summaries"] if row["metric"] == "Accuracy")
            self.assertEqual(row["runs"], 2)
            self.assertEqual(row["mean"], 0.75)
            self.assertAlmostEqual(row["sample_sd"], math.sqrt(0.125))
            self.assertIsNone(row["unavailable_reason"])
            self.assertTrue(all(row["ci95"] is None for row in result["condition_intervals"]))
            self.assertEqual(result["input_artifacts"][1]["kind"], "study")

    def test_repeat_runs_with_changed_settings_are_not_pooled(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("first", "second")]
            write_study(paths[0], seed=42)
            write_study(paths[1], seed=43)
            manifest = json.loads((paths[1] / "manifest.json").read_text())
            manifest["config"]["generation"]["temperature"] = 0.8
            (paths[1] / "manifest.json").write_text(json.dumps(manifest))
            result = analyze_artifacts(paths, bootstrap=0, options=FAST)
            self.assertTrue(all(row["mean"] is None for row in result["seed_summaries"]))
            self.assertTrue(all("different model identities or generation settings" in row["unavailable_reason"]
                                for row in result["seed_summaries"]))

    def test_duplicate_run_seed_is_rejected_instead_of_counted_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / name for name in ("first", "second")]
            for path in paths:
                write_study(path)
            with self.assertRaisesRegex(ValueError, "Duplicate predictions"):
                analyze_artifacts(paths, 0, options=FAST)

    def test_report_failure_preserves_every_previous_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_study(output)
            analyze_artifacts(output, 0, options=FAST)
            files = ("metrics.csv", "analysis.json", "report.html", "prevalence_draws.jsonl", "review_cases.csv",
                     *(path.relative_to(output).as_posix() for path in (output / "paper").iterdir()))
            previous = {name: (output / name).read_bytes() for name in files}
            with patch("evaluation.template_analysis._write_study_report", side_effect=InterruptedError("cancelled")):
                with self.assertRaises(InterruptedError):
                    analyze_artifacts(output, 0, options=FAST)
            self.assertEqual(previous, {name: (output / name).read_bytes() for name in files})
            self.assertFalse(list(output.glob(".analysis-*")))

    def test_shared_analysis_options_reject_invalid_types(self):
        self.assertEqual(resolve_analysis_settings()["group_by"], "cve_id")
        self.assertEqual(resolve_analysis_settings({"diagnostics": False})["output_audit"], True)
        for setting in ({"group_by": "sample"}, {"prevalence_repeats": True}, {"review_case_limit": -1},
                        {"bootstrap_resamples": "100"}, {"prevalence_size": 19}, {"unknown": True}):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                resolve_analysis_settings(setting)


def original_intervals(reference, candidate, bootstrap, seed):
    """The previous paired sampler, independent of the score-vector cache."""
    right = {row["sample_uid"]: row for row in candidate}
    clusters = defaultdict(lambda: [[], []])
    for row in reference:
        clusters[row["cve_id"]][0].append(row)
        clusters[row["cve_id"]][1].append(right[row["sample_uid"]])
    totals = []
    for pair in clusters.values():
        counts = []
        for rows in pair:
            metric = Metrics()
            for row in rows:
                metric.add(row["gold"], row["pred"])
            counts.append(tuple(getattr(metric, field) for field in analysis.COUNT_FIELDS))
        totals.append(counts)
    rng = random.Random(seed)
    differences = {field: [] for field in analysis.INTERVAL_METRICS}
    for _ in range(bootstrap):
        sampled = rng.choices(totals, k=len(totals))
        metrics = []
        for side in (0, 1):
            metric = Metrics(**{field: sum(pair[side][index] for pair in sampled)
                               for index, field in enumerate(analysis.COUNT_FIELDS)})
            metric.compute()
            metrics.append(metric)
        for field in differences:
            differences[field].append(getattr(metrics[1], field) - getattr(metrics[0], field))
    intervals = {field: [sorted(values)[int((bootstrap - 1) * percentile)] for percentile in (0.025, 0.975)]
                 for field, values in differences.items()}
    intervals["AbstentionRate"] = [-intervals["Coverage"][1], -intervals["Coverage"][0]]
    return intervals


def conditions():
    variants = [[], [], []]
    index = 0
    for cluster, size in enumerate((2, 3, 5)):
        for position in range(size):
            gold = "safe" if position % 2 else "vulnerable"
            shared = {"sample_uid": str(index), "cve_id": f"CVE-{cluster}", "gold": gold}
            predictions = ("safe", "vulnerable", gold if position % 3 else "unknown")
            for rows, pred in zip(variants, predictions):
                rows.append({**shared, "pred": pred})
            index += 1
    return variants


class BootstrapPerformanceTests(unittest.TestCase):
    def test_intervals_match_previous_sampler_for_unequal_clusters_and_abstentions(self):
        rng = random.Random(71)
        for clusters in (2, 3, 8):
            reference, candidate = [], []
            for cluster in range(clusters):
                for sample in range(rng.randint(1, 6)):
                    shared = {"sample_uid": f"{cluster}:{sample}", "cve_id": f"CVE-{cluster}",
                              "gold": rng.choice(("safe", "vulnerable"))}
                    reference.append({**shared, "pred": rng.choice(("safe", "vulnerable", "unknown"))})
                    candidate.append({**shared, "pred": rng.choice(("safe", "vulnerable", "unknown"))})
            rng.shuffle(candidate)
            for bootstrap, seed in ((17, 42), (103, -1), (201, 91)):
                with self.subTest(clusters=clusters, bootstrap=bootstrap, seed=seed):
                    expected = original_intervals(reference, candidate, bootstrap, seed)
                    actual = analysis.paired_comparison(reference, candidate, bootstrap, seed)
                    self.assertEqual(actual["cve_bootstrap_ci95_by_metric"], expected)
                    self.assertEqual(actual["cve_bootstrap_ci95"], expected["F1"])

    def test_shared_reference_resampling_is_reused_and_keys_include_seed_and_count(self):
        reference, first, second = conditions()
        cache = analysis._BootstrapCache()
        with patch.object(analysis, "_resample_scores", wraps=analysis._resample_scores) as resample:
            first_result = analysis.paired_comparison(reference, first, 31, 42, _bootstrap_cache=cache)
            analysis.paired_comparison(reference, second, 31, 42, _bootstrap_cache=cache)
            self.assertEqual(resample.call_count, 3)
            repeated = analysis.paired_comparison(reference, first, 31, 42, _bootstrap_cache=cache)
            self.assertEqual(first_result, repeated)
            self.assertEqual(resample.call_count, 3)
            analysis.paired_comparison(reference, first, 31, 43, _bootstrap_cache=cache)
            self.assertEqual(resample.call_count, 5)
            analysis.paired_comparison(reference, first, 32, 43, _bootstrap_cache=cache)
            self.assertEqual(resample.call_count, 7)

    def test_cache_eviction_is_bounded_and_skips_oversized_entries(self):
        scores = {field: array("d", [0.0] * 10) for field in analysis.INTERVAL_METRICS}
        counts = ((1, 1, 0, 0, 0, 0), (1, 0, 0, 1, 0, 0))
        first, second = (10, 42, counts), (10, 43, counts)
        measured = analysis._BootstrapCache()
        measured.put(first, scores)
        cache = analysis._BootstrapCache(max_bytes=measured._bytes)
        cache.put(first, scores)
        cache.put(second, scores)
        self.assertLessEqual(cache._bytes, cache.max_bytes)
        self.assertIsNone(cache.get(first))
        self.assertIs(cache.get(second), scores)
        tiny = analysis._BootstrapCache(max_bytes=1)
        tiny.put(first, scores)
        self.assertEqual(tiny._bytes, 0)
        self.assertIsNone(tiny.get(first))

    def test_cache_hits_still_honor_cooperative_control(self):
        reference, candidate, _other = conditions()
        cache = analysis._BootstrapCache()
        analysis.paired_comparison(reference, candidate, 20, _bootstrap_cache=cache)
        calls = 0

        def control():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise InterruptedError("stop cached analysis")

        with patch.object(analysis, "_resample_scores", side_effect=AssertionError("must reuse cached scores")):
            with self.assertRaisesRegex(InterruptedError, "stop cached analysis"):
                analysis.paired_comparison(reference, candidate, 20, control=control, _bootstrap_cache=cache)
        self.assertEqual(calls, 2)

    def test_analysis_shares_cache_within_run_and_discards_it_afterward(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            (output / "manifest.json").write_text(json.dumps({"pilot": True, "status": "completed"}))
            rows = []
            for sample, gold in enumerate(("safe", "vulnerable")):
                for policy in ("first", "majority_requested", "majority_valid"):
                    rows.append({"dataset": "fixture", "model_id": "model", "model": "fixture",
                                 "run_seed": 42, "protocol": "verdict_last", "parser_mode": "strict",
                                 "condition": f"cot/{policy}/verdict_last", "comparison": "voting",
                                 "family": "cot", "variant": "reference", "sample_uid": str(sample),
                                 "cve_id": f"CVE-{sample}", "gold": gold, "pred": gold,
                                 "aggregation": {"policy": policy}, "generation_ids": [f"{sample}:{i}" for i in range(5)],
                                 "decision_calls": 1 if policy == "first" else 5, "decision_seconds": 0.0})
            (output / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            with patch.object(analysis, "_resample_scores", wraps=analysis._resample_scores) as resample:
                first = analysis.analyze_study(output, 31)
                self.assertEqual(resample.call_count, 1)
                second = analysis.analyze_study(output, 31)
                self.assertEqual(resample.call_count, 2)
            self.assertEqual(first["component_and_voting_contrasts"], second["component_and_voting_contrasts"])


if __name__ == "__main__":
    unittest.main()
