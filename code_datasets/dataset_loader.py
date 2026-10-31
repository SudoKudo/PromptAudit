"""Load datasets from configuration, local CSV files, or Hugging Face."""

import csv
from collections import Counter
from functools import lru_cache
import gzip
from pathlib import Path

import yaml

from ._local_cve_dataset_loader import load_cvefixes_dataset
from . import sample_metadata


def _normalize_source(source):
    source = str(source or "local").strip().lower()
    return "huggingface" if source == "hf" else source


@lru_cache(maxsize=1)
def _load_dataset_config():
    """Read dataset entries once per process."""
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}
    return {item["name"]: item for item in config.get("datasets", [])
            if isinstance(item, dict) and item.get("name")}


def _load_csv(path):
    """Read code verbatim and retain available matching and cluster identifiers."""
    if not path or not Path(path).exists():
        return []
    # Full source files can exceed the csv module's default 128 KiB field limit.
    csv.field_size_limit(max(csv.field_size_limit(), 2**31 - 1))
    opener = gzip.open if str(path).lower().endswith(".gz") else open
    with opener(path, mode="rt", newline="", encoding="utf-8-sig") as stream:
        samples = []
        for index, row in enumerate(csv.DictReader(stream), start=1):
            metadata = sample_metadata(row)
            # Folder datasets use integer file numbers; keep that type on CSV reload.
            if "file_number" in metadata:
                metadata["file_number"] = int(metadata["file_number"])
            samples.append({
                "id": int(row.get("id", index)),
                "language": (row.get("language") or "").strip() or "unknown",
                "code": row.get("code") or "",
                "label": (row.get("label") or "").strip().upper() or "UNKNOWN",
                **metadata,
            })
        return samples


def load_dataset(cfg_or_name, progress=lambda message: None, *, inventory=None):
    """Accept a configured dataset name or a dictionary with name, source, and path."""
    configured = _load_dataset_config()
    if isinstance(cfg_or_name, dict):
        name = cfg_or_name.get("name", "unknown")
        source = _normalize_source(cfg_or_name.get("source", "local"))
        path = cfg_or_name.get("path")
    else:
        name = str(cfg_or_name)
        if name in configured:
            entry = configured[name]
            source = _normalize_source(entry.get("source", "local"))
            path = entry.get("path")
        else:
            source = "huggingface" if name.lower() in {"cvefixes", "bigvul", "vul4j"} else "local"
            path = None

    if source == "huggingface":
        # Local runs do not need to import the Hub client or trigger authentication.
        from .hf_loader import load_hf_dataset

        progress(f"Logging in and downloading {name} from Hugging Face...")
        samples = load_hf_dataset(name)
        if inventory is not None:
            inventory.update(format="huggingface", loaded_samples=len(samples),
                             label_counts=dict(Counter(row.get("label") for row in samples)))
        progress(f"Downloaded {name} samples: {len(samples)}")
        return samples
    if source != "local":
        raise ValueError(f"Unknown dataset source: {source}")
    is_csv = path and str(path).lower().endswith((".csv", ".csv.gz"))
    if not is_csv and (name.lower().startswith("cvefixes") or (path and Path(path).is_dir())):
        progress(f"Loading CVE-style dataset: {name} from {path}")
        samples, details = load_cvefixes_dataset(path, return_inventory=True)
        if inventory is not None:
            inventory.update(details)
        progress(f"Loaded {name} samples: {len(samples)}")
        if any(details["excluded_code_files"].values()):
            progress(f"Source exclusions for {name}: {details['excluded_code_files']}")
        return samples

    path = path or f"data/{name}.csv"
    progress(f"Loading local dataset: {path}")
    samples = _load_csv(path)
    if inventory is not None:
        inventory.update(format="csv.gz" if str(path).lower().endswith(".gz") else "csv",
                         loaded_samples=len(samples), label_counts=dict(Counter(row["label"] for row in samples)),
                         source_exclusions=None)
    return samples
