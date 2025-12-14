# code_datasets/loader.py — Glacier v2.0 (GUI-compatible dataset loader)
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# This module provides a unified interface for loading datasets in Glacier Code 2.0.
# I designed it so the GUI, experiment runner, and CLI can all load datasets using
# the same function, whether the dataset is local or downloaded from Hugging Face.
#
# The loader accepts either:
#   - A simple dataset name (string), or
#   - A configuration dictionary (source/name/path)
#
# The goal is to allow maximum flexibility while keeping the API extremely simple.

from .toy_dataset import load_toy
from ._local_cve_dataset_loader import load_cvefixes_dataset


def load_dataset(cfg_or_name, progress=lambda m: None):
    """
    Load a dataset using either a dataset name or a configuration dictionary.

    Args:
        cfg_or_name (str | dict):
            If str:
                Treated as a dataset name, e.g., "toy", "cvefixes", etc.
            If dict:
                Should contain optional keys:
                    - "source": dataset source ("local" or "huggingface")
                    - "name": dataset name
                    - "path": explicit file path for local datasets

        progress (callable):
            Callback to display loading progress (used by GUI). Defaults to no-op.

    Returns:
        list[dict]:
            A list of samples in the format:
                {
                    "code": <source code snippet>,
                    "label": <classification label>
                }

    Notes:
        - This function abstracts away handling of Hugging Face downloads vs. local CSV files.
        - The GUI uses this to ensure dataset selection works consistently regardless of source.
    """

    # ------------------------------------------------------------------
    # Normalize input (handle string vs. dict configuration)
    # ------------------------------------------------------------------
    if isinstance(cfg_or_name, dict):
        # Extract source, name, and optional custom path.
        src = cfg_or_name.get("source", "local")
        name = cfg_or_name.get("name", "unknown")
        path = cfg_or_name.get("path")

    else:
        # If the caller passed a simple dataset name, treat it as a string.
        name = str(cfg_or_name)
        path = None

        # Auto-detect whether the dataset should be loaded from Hugging Face.
        # These specific datasets are large research datasets hosted remotely.
        if name.lower() in ["cvefixes", "bigvul", "vul4j"]:
            src = "huggingface"
        else:
            # Everything else defaults to a local dataset in /data/.
            src = "local"

    # ------------------------------------------------------------------
    # Hugging Face datasets (remote)
    # ------------------------------------------------------------------
    if src == "huggingface":
        progress(f"Logging in and downloading {name} from Hugging Face…")

        # Imported here to avoid heavy dependencies when HF datasets aren't used.
        from .hf_loader import load_hf_dataset

        # Download and load the dataset from Hugging Face.
        data = load_hf_dataset(name)

        progress(f"Downloaded {name} samples: {len(data)}")
        return data

    # ------------------------------------------------------------------
    # Local datasets (e.g., toy CSV, or user-provided CSV)
    # ------------------------------------------------------------------
    elif src == "local":
        # cve fixes dataset loader special
        if name.lower() == "cvefixes_local":
            progress(f"Loading local CVEfixes dataset from folder structure...")
            data = load_cvefixes_dataset()
            progress(f"Loaded CVEfixes samples: {len(data)}")
            return data
        
        # If no explicit path is given, assume the CSV lives in /data/.
        dataset_path = path or f"data/{name}.csv"

        progress(f"Loading local dataset: {dataset_path}")

        # The toy loader handles CSV-parsed datasets for Code 2.0.
        return load_toy(dataset_path)

    # ------------------------------------------------------------------
    # Unknown dataset source
    # ------------------------------------------------------------------
    else:
        # If the caller specifies a source we do not support, raise an error.
        raise ValueError(f"Unknown dataset source: {src}")