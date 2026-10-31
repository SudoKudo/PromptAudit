"""Check the CVEFixes CSV cohorts against the preserved source samples."""

from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_datasets.dataset_loader import _load_dataset_config, load_dataset
from core.runner import ExperimentRunner


ROOT = Path(__file__).resolve().parents[1]
# These describe the rows loaded before the directory move, not the folder counts.
COHORTS = {50: (44, 100, 200), 100: (95, 616, 1232),
           500: (475, 1260, 2520), 1000: (946, 3037, 6074)}
ROW_HASHES = {
    50: "4d3baa5b09527562364150ff3069f3cfdde3dabf4f14d4719198b835d5401ae9",
    100: "4f65ea39c0297495549afdad9d26ff3b85cd999b857786b4520d80a0f67f0af6",
    500: "cc87131ad80a0e8b636b0314603b29aab33ad29c26054d5c68cacbeb9d1a1ee2",
    1000: "48fe6c061fefecc08e0a270f0e11574f437d3403f8b0612a9de785bd06324baf",
}


def rows_hash(rows):
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CVEFixesDatasetTests(unittest.TestCase):
    def test_registered_csv_cohorts_preserve_rows_order_and_metadata(self):
        entries = _load_dataset_config()
        for size, (cve_count, pair_count, sample_count) in COHORTS.items():
            with self.subTest(size=size):
                name = f"cvefixes_{size}"
                entry = entries[name]
                self.assertEqual(entry["source"], "local")
                self.assertEqual(ROOT / entry["path"], ROOT / "data" / "cvefixes" / f"{name}.csv.gz")
                rows = load_dataset(name)
                self.assertEqual(len(rows), sample_count)
                self.assertEqual([row["id"] for row in rows], list(range(sample_count)))
                self.assertEqual(len({row["cve_id"] for row in rows}), cve_count)
                self.assertEqual(Counter(row["label"] for row in rows),
                                 {"VULNERABLE": pair_count, "SAFE": pair_count})
                self.assertEqual(rows_hash(rows), ROW_HASHES[size])
                pairs = defaultdict(list)
                for row in rows:
                    self.assertTrue(row["code"].strip())
                    self.assertIsInstance(row["file_number"], int)
                    self.assertNotEqual(row["language"], "unknown")
                    self.assertTrue(row["filename"])
                    pairs[(row["cve_id"], row["file_number"])].append(row)
                self.assertEqual(len(pairs), pair_count)
                for pair in pairs.values():
                    self.assertEqual(Counter(row["label"] for row in pair),
                                     {"VULNERABLE": 1, "SAFE": 1})
                    self.assertEqual(pair[0]["filename"], pair[1]["filename"])

    def test_csv_and_preserved_source_folder_return_identical_samples(self):
        folder = ROOT / "data" / "cvefixes" / "cvefixes_50"
        folder_rows = load_dataset({"name": "cvefixes_folder", "source": "local", "path": str(folder)})
        self.assertEqual(folder_rows, load_dataset("cvefixes_50"))

    def test_compressed_csv_preserves_large_code_fields_and_integer_metadata(self):
        code = " \r\n/*" + "x" * 200_000 + "*/\nint sample(void) { return 0; }\n "
        sample = {"id": 7, "language": "C", "code": code, "label": "SAFE",
                  "cve_id": "CVE-fixture", "file_number": 3, "filename": "sample.c"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.csv.gz"
            with gzip.open(path, "wt", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(sample))
                writer.writeheader()
                writer.writerow(sample)
            self.assertEqual(load_dataset({"name": "fixture", "source": "local", "path": str(path)}), [sample])

    def test_standard_run_keeps_cvefixes_metadata_in_prediction_exports(self):
        rows = load_dataset("cvefixes_50")[:2]
        with tempfile.TemporaryDirectory() as folder:
            runner = ExperimentRunner({
                "generation": {"temperature": 0, "max_new_tokens": 8},
                "output": {"run_root": folder},
                "performance": {"prevent_system_sleep": False, "response_cache": False},
            }, progress=lambda _: None)
            with patch("core.runner.load_dataset", return_value=rows):
                status = runner.run_all(
                    selected_datasets=["cvefixes_50"],
                    selected_models=[{"name": "dummy", "backend": "dummy"}],
                    selected_prompts=["zero_shot"], selected_output_protocols=["verdict_last"],
                    selected_parser_modes=["strict"],
                )
            self.assertEqual(status, "completed")
            record = runner.records[0]
            with Path(runner._prediction_csv_path(record)).open(newline="", encoding="utf-8") as stream:
                exported = list(csv.DictReader(stream))
            self.assertEqual(len(exported), len(rows))
            for source, predicted, saved in zip(rows, record["predictions"], exported):
                self.assertEqual(predicted["gold"], source["label"].lower())
                for key in ("cve_id", "file_number", "filename", "language"):
                    self.assertEqual(predicted[key], source[key])
                    self.assertEqual(saved[key], str(source[key]))


if __name__ == "__main__":
    unittest.main()
