"""Validate the supplied BigVul cohorts and their normal experiment path."""

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_datasets.dataset_loader import _load_dataset_config, load_dataset
from core.revision_study import run_study
from core.runner import ExperimentRunner
from evaluation.template_analysis import analyze_study


ROOT = Path(__file__).resolve().parents[1]
COHORTS = {50: (132, 264), 100: (280, 560), 500: (1149, 2298), 1000: (2148, 4296)}


def normalize_newlines(code):
    return code.replace("\r\n", "\n").replace("\r", "\n")


class BigVulDatasetTests(unittest.TestCase):
    def test_standard_multi_dataset_run_keeps_bigvul_metadata_in_exports(self):
        selections = {name: load_dataset(name)[:2] for name in ("cvefixes_50", "bigvul_50")}
        with tempfile.TemporaryDirectory() as folder:
            runner = ExperimentRunner({
                "models": [{"name": "dummy", "backend": "dummy"}],
                "generation": {"temperature": 0, "max_new_tokens": 8},
                "output": {"run_root": folder},
                "performance": {"prevent_system_sleep": False},
            }, progress=lambda _: None)
            with patch("core.runner.load_dataset", side_effect=lambda name, **kwargs: selections[name]):
                status = runner.run_all(
                    selected_datasets=list(selections),
                    selected_models=[{"name": "dummy", "backend": "dummy"}],
                    selected_prompts=["zero_shot"], selected_output_protocols=["verdict_last"],
                    selected_parser_modes=["strict"],
                )
            self.assertEqual(status, "completed")
            self.assertEqual({row["dataset"] for row in runner.records}, set(selections))
            record = next(row for row in runner.records if row["dataset"] == "bigvul_50")
            for source, predicted in zip(selections["bigvul_50"], record["predictions"]):
                for field in ("cve_id", "year", "pair_id", "commit_id", "cvss_score"):
                    self.assertEqual(predicted[field], source[field])
            with Path(runner._prediction_csv_path(record)).open(newline="", encoding="utf-8") as stream:
                exported = list(csv.DictReader(stream))
            self.assertEqual([row["year"] for row in exported],
                             [row["year"] for row in selections["bigvul_50"]])

    def test_registered_csv_cohorts_keep_complete_pairs_and_source_metadata(self):
        entries = _load_dataset_config()
        previous_cves = set()
        for size, (pair_count, sample_count) in COHORTS.items():
            with self.subTest(size=size):
                name = f"bigvul_{size}"
                entry = entries[name]
                self.assertEqual(entry["source"], "local")
                source = ROOT / entry["path"]
                self.assertEqual(source, ROOT / "data" / "bigvul" / f"{name}.csv")
                with source.open(newline="", encoding="utf-8-sig") as stream:
                    original = list(csv.DictReader(stream))
                samples = load_dataset(name)
                self.assertEqual(len(samples), sample_count)
                self.assertEqual(len({row["id"] for row in samples}), sample_count)
                self.assertEqual(Counter(row["label"] for row in samples),
                                 {"SAFE": pair_count, "VULNERABLE": pair_count})
                cves = {row["cve_id"] for row in samples}
                self.assertEqual(len(cves), size)
                self.assertTrue(previous_cves.issubset(cves))
                previous_cves = cves
                pairs = defaultdict(list)
                for saved, loaded in zip(original, samples):
                    self.assertEqual(loaded["code"], saved["code"])
                    self.assertTrue(loaded["code"].strip())
                    self.assertIn(loaded["language"], {"C", "C++"})
                    for field in ("cve_id", "year", "project", "pair_id", "commit_id", "cwe_id", "cvss_score"):
                        if saved[field].strip():
                            self.assertEqual(loaded[field], saved[field].strip())
                    pairs[(loaded["cve_id"], loaded["pair_id"])].append(loaded)
                self.assertEqual(len(pairs), pair_count)
                for pair in pairs.values():
                    self.assertEqual(Counter(row["label"] for row in pair), {"SAFE": 1, "VULNERABLE": 1})
                    self.assertNotEqual(pair[0]["code"], pair[1]["code"])

    def test_mirrored_cve_folders_load_without_a_cvefixes_name(self):
        csv_samples = load_dataset("bigvul_50")
        folder_samples = load_dataset({
            "name": "bigvul_folder", "source": "local",
            "path": str(ROOT / "data" / "bigvul" / "bigvul_50"),
        })
        self.assertEqual(len(folder_samples), len(csv_samples))
        self.assertEqual(
            Counter((row["cve_id"], row["label"], normalize_newlines(row["code"])) for row in folder_samples),
            Counter((row["cve_id"], row["label"], normalize_newlines(row["code"])) for row in csv_samples),
        )

    def test_mixed_cvefixes_bigvul_study_keeps_separate_clusters_and_years(self):
        def two_cve_pairs(selection):
            rows = load_dataset(selection)
            cves = list(dict.fromkeys(row["cve_id"] for row in rows))[:2]
            selected = []
            for cve in cves:
                for label in ("VULNERABLE", "SAFE"):
                    selected.append(next(row for row in rows if row["cve_id"] == cve and row["label"] == label))
            return selected

        config = {
            "section": "B", "datasets": ["cvefixes_50", "bigvul_50"],
            "models": [{"name": "dummy", "backend": "dummy"}],
            "families": ["zero_shot"], "variants": ["reference", "paraphrase"],
            "protocols": ["verdict_last"], "parser_modes": ["strict"], "seeds": [42],
            "votes": 1, "generation": {"temperature": 0, "max_new_tokens": 8},
        }
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "study"
            run_study(config, output, pilot=True, dataset_loader=two_cve_pairs, progress=lambda _: None)
            result = analyze_study(output, bootstrap=20)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual({cohort["name"] for cohort in manifest["cohorts"]}, {"cvefixes_50", "bigvul_50"})
            bigvul = next(cohort for cohort in manifest["cohorts"] if cohort["name"] == "bigvul_50")
            self.assertTrue(all(sample.get("year") for sample in bigvul["samples"]))
            rows = [json.loads(line) for line in (output / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(Counter(row["dataset"] for row in rows), {"cvefixes_50": 8, "bigvul_50": 8})
            expected_years = {sample["sample_uid"]: sample["year"] for sample in bigvul["samples"]}
            for row in rows:
                if row["dataset"] == "bigvul_50":
                    self.assertEqual(row["year"], expected_years[row["sample_uid"]])
            comparisons = [row for row in result["template_summaries"] if "metric_differences" in row]
            self.assertEqual({row["dataset"] for row in comparisons}, {"cvefixes_50", "bigvul_50"})
            self.assertTrue(all(row["clusters"] == 2 and row["cve_bootstrap_ci95"] is not None
                                for row in comparisons))


if __name__ == "__main__":
    unittest.main()
