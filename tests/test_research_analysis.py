"""Check offline prevalence, selective prediction, parser, and dataset analyses."""

from collections import OrderedDict
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from evaluation.artifacts import ArtifactReader
from evaluation.research_analysis import (
    audit_dataset_cohorts, compare_parsers, decision_scores, prevalence_plan,
    run_research_analyses,
)


def samples(count=80):
    return [{"sample_uid": f"sample-{index}", "sample_id": str(index),
             "gold": "safe" if index < count // 2 else "vulnerable",
             "pred": "safe", "code_sha256": hashlib.sha256(f"code-{index}".encode()).hexdigest(),
             "cve_id": f"CVE-{index // 2}", "generation_ids": [f"draw-{index}"],
             "decision_generation_ids": [f"draw-{index}"], "decision_calls": 1,
             "protocol": "verdict_last", "parser_mode": "strict", "family": "cot",
             "variant": "reference", "comparison": "templates"}
            for index in range(count)]


class Reader:
    def __init__(self, groups, calls=None):
        self.groups = OrderedDict(groups)
        self.calls = calls or {}
        self.lookups = 0

    def iter_groups(self):
        return self.groups.items()

    def get_generation(self, key):
        self.lookups += 1
        return self.calls.get(key)


GROUP = ("fixture", "fixture-model", "fixture-model", 42, "verdict_last", "strict")


class ResearchAnalysisTests(unittest.TestCase):
    def test_language_scores_use_each_recorded_group_and_keep_abstentions(self):
        rows = samples(4)
        for row, language, pred in zip(rows, ("C", "C", "Python", ""),
                                       ("safe", "unknown", "vulnerable", "safe")):
            row.update(language=language, pred=pred)
        reader = Reader([(GROUP, {"cot/reference/verdict_last": rows})])
        result = run_research_analyses(reader, {"prevalence": False, "output_audit": False,
                                               "dataset_audit": False}, bootstrap=0)
        by_language = {row["language"]: row for row in result["language_breakdowns"]}
        self.assertEqual(set(by_language), {"C", "Python", "Unspecified"})
        self.assertEqual(by_language["C"]["samples"], 2)
        self.assertEqual(by_language["C"]["Accuracy"], 0.5)
        self.assertEqual(by_language["C"]["SelectiveAccuracy"], 1)
        self.assertEqual(by_language["C"]["Incorrect"], 1)
        self.assertEqual(by_language["Unspecified"]["FN"], 1)
        for row in by_language.values():
            self.assertEqual(row["run_seed"], 42)
            self.assertEqual(row["condition"], "cot/reference/verdict_last")
        for key in ("samples", "TP", "TN", "FP", "FN", "UnFN", "Incorrect"):
            self.assertEqual(sum(row[key] for row in by_language.values()),
                             result["selective_predictions"][0][key])

    def test_selective_accuracy_excludes_abstentions_without_changing_accuracy(self):
        rows = [{"gold": "safe", "pred": "safe"}, {"gold": "safe", "pred": "unknown"},
                {"gold": "vulnerable", "pred": "safe"}, {"gold": "safe", "pred": "vulnerable"}]
        result = decision_scores(rows)
        self.assertEqual(result["Accuracy"], 0.25)
        self.assertEqual(result["Coverage"], 0.75)
        self.assertAlmostEqual(result["SelectiveAccuracy"], 1 / 3)
        self.assertAlmostEqual(result["SelectiveRisk"], 2 / 3)
        self.assertEqual(result["FalsePositivesPer1000"], 250)
        abstained = decision_scores([{"gold": "safe", "pred": "unknown"}])
        self.assertIsNone(abstained["SelectiveAccuracy"])
        self.assertIsNone(abstained["SelectiveRisk"])
        self.assertEqual(abstained["Coverage"], 0)
        self.assertIsNone(decision_scores([])["FalsePositivesPer1000"])

    def test_prevalence_subsets_are_exact_matched_and_reproducible(self):
        rows = samples()
        first = prevalence_plan(rows, size=40, repeats=3, dataset="fixture")
        second = prevalence_plan(list(reversed(rows)), size=40, repeats=3, dataset="fixture")
        draws, repeated = list(first["draws"]), list(second["draws"])
        self.assertEqual(draws, repeated)
        self.assertEqual(first["samples"], 40)
        self.assertEqual(len(draws), 9)
        gold = {row["sample_uid"]: row["gold"] for row in rows}
        for draw in draws:
            self.assertEqual(len(draw["sample_ids"]), 40)
            self.assertEqual(len(set(draw["sample_ids"])), 40)
            self.assertEqual(sum(gold[uid] == "vulnerable" for uid in draw["sample_ids"]),
                             {0.2: 8, 0.1: 4, 0.05: 2}[draw["prevalence"]])
        self.assertIsNotNone(prevalence_plan(samples(8), size=1000)["unavailable_reason"])
        with self.assertRaisesRegex(ValueError, "duplicate sample"):
            prevalence_plan(rows + rows[:1])

    def test_legacy_rows_without_code_hashes_do_not_claim_matched_prevalence(self):
        rows = samples()
        for row in rows:
            del row["code_sha256"]
        plan = prevalence_plan(rows, size=40, repeats=2)
        self.assertEqual(plan["samples"], 0)
        self.assertEqual(list(plan["draws"]), [])
        self.assertIn("code hashes", plan["unavailable_reason"])
        self.assertEqual(decision_scores(rows)["samples"], len(rows))

    def test_prevalence_draws_match_methods_and_retain_conditional_intervals(self):
        original = samples()
        candidate = [{**row, "pred": "vulnerable"} for row in original]
        reader = Reader([(GROUP, {"reference": original, "paraphrase": candidate})])
        calls = []

        def intervals(rows, **options):
            calls.append((len(rows), options))
            return {"ci95": {"Recall": [0, 1]}, "clusters": 20,
                    "group_by": options["group_by"], "unavailable_reason": None}

        result = run_research_analyses(reader, {"prevalence_size": 40, "prevalence_repeats": 2,
            "output_audit": False, "dataset_audit": False}, bootstrap=10, interval_fn=intervals)
        by_condition = {}
        for row in result["prevalence_draws"]:
            by_condition.setdefault(row["condition"], {})[(row["prevalence"], row["draw"])] = row["subset_sha256"]
            self.assertEqual(row["cluster_intervals"]["ci95"]["Recall"], [0, 1])
        self.assertEqual(by_condition["reference"], by_condition["paraphrase"])
        self.assertEqual(len(result["prevalence_draws"]), 12)
        self.assertTrue(all(count == 40 and options["bootstrap"] == 10 for count, options in calls))
        self.assertTrue(all("not confidence intervals" in row["uncertainty_note"]
                            for row in result["prevalence_summaries"]))

    def test_prevalence_details_can_be_streamed_without_retaining_global_rows(self):
        rows = samples()
        reader = Reader([(GROUP, {"reference": rows, "candidate": copy.deepcopy(rows)})])
        details = []
        result = run_research_analyses(reader, {"prevalence_size": 40, "prevalence_repeats": 2,
            "output_audit": False, "dataset_audit": False}, bootstrap=0,
            detail_sink=lambda kind, row: details.append((kind, row)))
        self.assertEqual(result["prevalence_draws"], [])
        self.assertEqual(result["prevalence_draw_count"], 12)
        self.assertEqual(result["prevalence_detail_storage"], "external JSONL")
        self.assertEqual(len(details), 12)
        self.assertEqual({kind for kind, _row in details}, {"prevalence_draws"})
        self.assertTrue(all("SelectiveAccuracy" in row for _kind, row in details))

    def test_parser_audit_counts_decision_and_pool_draw_recovery(self):
        reference = [{**samples(2)[0], "pred": "unknown", "generation_ids": ["draw-a", "draw-b"]}]
        candidate = [{**reference[0], "pred": "vulnerable", "parser_mode": "full"}]
        calls = {"draw-a": {"raw_output": "A buffer overflow vulnerability is present in this function."},
                 "draw-b": {"raw_output": "No verdict is available."}}
        result = compare_parsers(reference, candidate, generation_lookup=calls.get)
        self.assertEqual(result["verified_samples"], 1)
        self.assertEqual(result["recovered_verdicts"], 1)
        self.assertEqual(result["matched_pool_draws"], 2)
        self.assertEqual(result["verified_draws"], 2)
        self.assertEqual(result["recovered_draw_verdicts"], 1)
        self.assertEqual(result["candidate_lexical_fallback_draws"], 1)
        self.assertEqual(result["draw_details_coverage"], 1)
        missing = compare_parsers([{**reference[0], "generation_ids": []}], candidate)
        self.assertIsNone(missing["label_disagreement"])
        self.assertEqual(missing["missing_pool_links"], 1)
        with self.assertRaisesRegex(ValueError, "one prediction"):
            compare_parsers(reference * 2, candidate)

    def test_output_summaries_count_missing_measurements_and_export_no_response_text(self):
        rows = samples(4)
        rows[0].update(pred="unknown", decision_calls=2, generation_ids=["draw-0", "missing"],
                       decision_generation_ids=["draw-0", "missing"])
        rows[1].update(generation_ids=[], decision_generation_ids=[], decision_calls=3)
        raw = "private response text\nSAFE"
        reader = Reader([(GROUP, {"reference": rows})], {"draw-0": {
            "raw_output": raw, "generation_info": {"eval_count": 5, "done_reason": "length",
                                                       "thinking_output": "private thinking"}}})
        result = run_research_analyses(reader, {"prevalence": False, "dataset_audit": False,
                                              "review_case_limit": 2}, bootstrap=0)
        unknown = next(row for row in result["output_summaries"] if row["pred"] == "unknown")
        self.assertEqual(unknown["decision_calls"], 2)
        self.assertEqual(unknown["missing_responses"], 1)
        self.assertEqual(unknown["response_measurement_coverage"], 0.5)
        self.assertEqual(unknown["token_measurement_coverage"], 0.5)
        self.assertLessEqual(len(result["review_cases"]), 2)
        self.assertTrue(all(row["rationale_verdict_consistent"] == "" for row in result["review_cases"]))
        serialized = json.dumps(result)
        self.assertNotIn(raw, serialized)
        self.assertNotIn("private thinking", serialized)
        no_cases = run_research_analyses(reader, {"prevalence": False, "dataset_audit": False,
            "review_case_limit": 0}, bootstrap=0)
        self.assertEqual(no_cases["review_cases"], [])
        self.assertGreater(no_cases["review_case_candidates"], 0)

    def test_output_audit_separates_context_errors_and_empty_replies_from_visible_text(self):
        ids = ["context", "network", "blank", "reply", "missing"]
        row = {**samples(2)[0], "pred": "unknown", "decision_calls": len(ids),
               "generation_ids": ids, "decision_generation_ids": ids}
        calls = {
            "context": {"raw_output": "", "generation_info": {"status": "error", "error_type": "ContextWindowExceeded"}},
            "network": {"raw_output": "", "generation_info": {"status": "error", "error_type": "HTTPError"}},
            "blank": {"raw_output": "   ", "generation_info": {"status": "empty_response"}},
            "reply": {"raw_output": "SAFE", "generation_info": {"status": "ok"}},
        }
        result = run_research_analyses(Reader([(GROUP, {"reference": [row]})], calls),
            {"prevalence": False, "dataset_audit": False}, bootstrap=0)
        summary = result["output_summaries"][0]
        self.assertEqual(summary["generation_error_calls"], 2)
        self.assertEqual(summary["context_overflow_calls"], 1)
        self.assertEqual(summary["other_generation_error_calls"], 1)
        self.assertEqual(summary["empty_response_calls"], 1)
        self.assertEqual(summary["visible_response_calls"], 1)
        self.assertEqual(summary["mean_visible_chars_per_visible_response"], 4)
        self.assertEqual(summary["available_responses"], 4)
        self.assertEqual(summary["response_measurement_coverage"], 0.8)
        self.assertEqual(summary["missing_responses"], 1)
        self.assertEqual(set(result["review_cases"][0]["reasons"]),
                         {"unresolved_verdict", "generation_error", "context_overflow", "empty_response"})

    def test_dataset_audit_counts_exact_overlap_and_conflicts_without_mutation(self):
        original = [("a", [{"id": 1, "code": "same code", "label": "SAFE", "cve_id": "CVE-1",
                           "project": "shared", "cwe_id": "CWE-119"},
                          {"id": 2, "code": "same code", "label": "VULNERABLE", "cve_id": "CVE-2"}]),
                    ("b", [{"id": 3, "code": "same code", "label": "VULNERABLE", "cve_id": "CVE-1",
                           "project": "shared"},
                          {"id": 4, "code": "different", "label": "SAFE"}])]
        before = copy.deepcopy(original)
        result = audit_dataset_cohorts(original)
        self.assertEqual(original, before)
        self.assertEqual(len(result["dataset_summaries"]), 2)
        a = result["dataset_summaries"][0]
        self.assertEqual(a["duplicate_code_groups"], 1)
        self.assertEqual(a["conflicting_label_code_groups"], 1)
        pair = result["dataset_overlap"][0]
        self.assertEqual(pair["shared_exact_code_hashes"], 1)
        self.assertEqual(pair["conflicting_label_code_hashes"], 1)
        self.assertEqual(pair["shared_cves"], 1)
        self.assertEqual(pair["shared_projects"], 1)
        with self.assertRaisesRegex(ValueError, "unique nonempty"):
            audit_dataset_cohorts([("a", original[0][1] * 2)])

    def test_legacy_response_audit_keeps_unknown_call_budgets_unavailable(self):
        row = {"sample_uid": "legacy", "gold": "safe", "pred": "unknown"}
        result = run_research_analyses(Reader([(GROUP, {"reference": [row]})]),
            {"prevalence": False, "dataset_audit": False}, bootstrap=0)
        summary = result["output_summaries"][0]
        self.assertIsNone(summary["decision_calls"])
        self.assertIsNone(summary["missing_responses"])
        self.assertIsNone(summary["response_measurement_coverage"])
        self.assertEqual(summary["decision_budget_measurement_coverage"], 0)
        row["decision_calls"] = 5
        result = run_research_analyses(Reader([(GROUP, {"reference": [row]})]),
            {"prevalence": False, "dataset_audit": False}, bootstrap=0)
        summary = result["output_summaries"][0]
        self.assertEqual(summary["decision_calls"], 5)
        self.assertEqual(summary["missing_responses"], 5)
        self.assertEqual(summary["response_measurement_coverage"], 0)

    def test_dataset_rows_are_deduplicated_across_methods_and_cwe_categories_can_overlap(self):
        rows = samples(4)
        for row in rows:
            row["cwe_id"] = "CWE-119; CWE-20"
        result = run_research_analyses(Reader([(GROUP, {"reference": rows, "candidate": copy.deepcopy(rows)})]),
            {"prevalence": False, "output_audit": False}, bootstrap=0)
        self.assertEqual(result["dataset_summaries"][0]["samples"], 4)
        self.assertEqual(len(result["cwe_breakdowns"]), 4)
        self.assertTrue(all(row["samples"] == 4 for row in result["cwe_breakdowns"]))

    def test_missing_dataset_hashes_are_unavailable_rather_than_zero_overlap(self):
        rows = [{"sample_uid": "a", "gold": "safe", "pred": "safe"}]
        other = [{"sample_uid": "b", "gold": "safe", "pred": "safe"}]
        second_group = ("other", *GROUP[1:])
        result = run_research_analyses(Reader([(GROUP, {"reference": rows}),
                                             (second_group, {"reference": other})]),
            {"prevalence": False, "output_audit": False}, bootstrap=0)
        self.assertTrue(all(row["duplicate_code_groups"] is None for row in result["dataset_summaries"]))
        self.assertIsNone(result["dataset_overlap"][0]["shared_exact_code_hashes"])
        self.assertIsNone(result["dataset_overlap"][0]["shared_cves"])
        self.assertTrue(any(row["analysis"] == "CWE_breakdown" for row in result["unavailable"]))

    def test_changed_gold_cohort_and_cancellation_are_rejected(self):
        rows = samples(4)
        different = copy.deepcopy(rows)
        different[0]["gold"] = "vulnerable"
        with self.assertRaisesRegex(ValueError, "same gold-labeled cohort"):
            run_research_analyses(Reader([(GROUP, {"reference": rows, "candidate": different})]),
                {"prevalence": False, "output_audit": False}, bootstrap=0)
        different = copy.deepcopy(rows)
        different[0]["code_sha256"] = hashlib.sha256(b"changed code").hexdigest()
        with self.assertRaisesRegex(ValueError, "same gold-labeled cohort"):
            run_research_analyses(Reader([(GROUP, {"reference": rows, "candidate": different})]),
                {"prevalence": False, "output_audit": False, "dataset_audit": False}, bootstrap=0)

        def stop():
            raise InterruptedError("cancelled")

        with self.assertRaisesRegex(InterruptedError, "cancelled"):
            run_research_analyses(Reader([(GROUP, {"reference": rows})]), control=stop)

    def test_saved_study_reader_supports_all_research_analyses_without_editing_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            manifest = {"status": "completed", "pilot": True, "config": {}}
            (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            predictions, generations = [], []
            for variant in ("reference", "paraphrase"):
                for row in samples():
                    generation_id = variant + ":" + row["generation_ids"][0]
                    generations.append({"generation_id": generation_id,
                        "raw_output": "A buffer overflow vulnerability is present." if row["gold"] == "vulnerable"
                                      else "No known vulnerabilities are present.",
                        "generation_info": {"eval_count": 8}})
                    for mode in ("strict", "full"):
                        predictions.append({**row, **dict(zip(("dataset", "model_id", "model", "run_seed", "protocol"), GROUP[:5])),
                            "condition": f"cot/{variant}/verdict_last", "variant": variant,
                            "parser_mode": mode, "pred": "unknown" if mode == "strict" else row["gold"],
                            "generation_ids": [generation_id], "decision_generation_ids": [generation_id],
                            "cwe_id": "CWE-119"})
            for name, rows in (("predictions.jsonl", predictions), ("generations.jsonl", generations)):
                (output / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            before = {name: (output / name).read_bytes() for name in ("manifest.json", "predictions.jsonl", "generations.jsonl")}
            with ArtifactReader(output) as reader:
                result = run_research_analyses(reader, {"prevalence_size": 40, "prevalence_repeats": 2}, bootstrap=0)
            self.assertEqual(len(result["selective_predictions"]), 4)
            self.assertEqual(result["prevalence_draw_count"], 24)
            self.assertEqual(result["dataset_summaries"][0]["samples"], 80)
            self.assertEqual(len(result["parser_comparisons"]), 2)
            self.assertTrue(all(row["recovered_verdicts"] == 80 for row in result["parser_comparisons"]))
            self.assertTrue(all(row["recovered_draw_verdicts"] == 80 for row in result["parser_comparisons"]))
            for name, content in before.items():
                self.assertEqual((output / name).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
