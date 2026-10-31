"""Keep paired intervals identical while reusing condition-level resampling."""

from array import array
from collections import defaultdict
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from evaluation.metrics import Metrics
from evaluation import template_analysis as analysis


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
