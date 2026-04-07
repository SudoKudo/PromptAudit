"""Resolve dataset names and load samples from local or Hugging Face sources."""

import yaml
from pathlib import Path
from functools import lru_cache
from .toy_dataset import load_toy
from ._local_cve_dataset_loader import load_cvefixes_dataset


def _normalize_source(src):
    """Normalize dataset source aliases to the internal names used by the loader."""
    source = str(src or "local").strip().lower()
    aliases = {
        "hf": "huggingface",
        "huggingface": "huggingface",
        "local": "local",
    }
    return aliases.get(source, source)


@lru_cache(maxsize=1)
def _load_dataset_config():
    """Cache config.yaml dataset metadata so repeated dataset loads avoid rereading YAML."""
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return {
        d["name"]: d for d in config.get("datasets", [])
        if isinstance(d, dict) and d.get("name")
    }


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

    # # ------------------------------------------------------------------
    # # Normalize input (handle string vs. dict configuration)
    # # ------------------------------------------------------------------
    # if isinstance(cfg_or_name, dict):
    #     # Extract source, name, and optional custom path.
    #     src = cfg_or_name.get("source", "local")
    #     name = cfg_or_name.get("name", "unknown")
    #     path = cfg_or_name.get("path")

    # else:
    #     # If the caller passed a simple dataset name, treat it as a string.
    #     name = str(cfg_or_name)
    #     path = None

    #     # Auto-detect whether the dataset should be loaded from Hugging Face.
    #     # These specific datasets are large research datasets hosted remotely.
    #     if name.lower() in ["cvefixes", "bigvul", "vul4j"]:
    #         src = "huggingface"
    #     else:
    #         # Everything else defaults to a local dataset in /data/.
    #         src = "local"

    # # ------------------------------------------------------------------
    # # Hugging Face datasets (remote)
    # # ------------------------------------------------------------------
    # if src == "huggingface":
    #     progress(f"Logging in and downloading {name} from Hugging Face…")

    #     # Imported here to avoid heavy dependencies when HF datasets aren't used.
    #     from .hf_loader import load_hf_dataset

    #     # Download and load the dataset from Hugging Face.
    #     data = load_hf_dataset(name)

    #     progress(f"Downloaded {name} samples: {len(data)}")
    #     return data

    # # ------------------------------------------------------------------
    # # Local datasets (e.g., toy CSV, or user-provided CSV)
    # # ------------------------------------------------------------------
    # elif src == "local":
    #     if name.lower().startswith("cvefixes"):
    #         progress(f"Loading CVE-style dataset: {name}")
    #         data = load_cvefixes_dataset(path)  # Pass the path from config
    #         progress(f"Loaded {name} samples: {len(data)}")
    #         return data
        
    #     dataset_path = path or f"data/{name}.csv"

    #     progress(f"Loading local dataset: {dataset_path}")

    #     return load_toy(dataset_path)

    # # ------------------------------------------------------------------
    # # Unknown dataset source
    # # ------------------------------------------------------------------
    # else:
    #     # If the caller specifies a source we do not support, raise an error.
    #     raise ValueError(f"Unknown dataset source: {src}")
    
    datasets_config = _load_dataset_config()

    # ------------------------------------------------------------------
    # Normalize input (handle string vs. dict configuration)
    # ------------------------------------------------------------------
    if isinstance(cfg_or_name, dict):
        # Extract source, name, and optional custom path.
        src = _normalize_source(cfg_or_name.get("source", "local"))
        name = cfg_or_name.get("name", "unknown")
        path = cfg_or_name.get("path")
    else:
        # If the caller passed a simple dataset name, look it up in config
        name = str(cfg_or_name)
        
        # Look up the dataset in config to get its path and source
        if name in datasets_config:
            dataset_info = datasets_config[name]
            src = _normalize_source(dataset_info.get("source", "local"))
            path = dataset_info.get("path")
        else:
            # Fallback for unknown datasets
            path = None
            if name.lower() in ["cvefixes", "bigvul", "vul4j"]:
                src = "huggingface"
            else:
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
        # Check if this is a CVE-style dataset (folder structure with before/after files)
        if name.lower().startswith("cvefixes"):
            progress(f"Loading CVE-style dataset: {name} from {path}")
            data = load_cvefixes_dataset(path)  # Pass the specific path from config
            progress(f"Loaded {name} samples: {len(data)}")
            return data
        
        # If no explicit path is given, assume the CSV lives in /data/.
        dataset_path = path or f"data/{name}.csv"

        progress(f"Loading local dataset: {dataset_path}")

        # The toy loader handles CSV-parsed datasets for PromptAudit.
        return load_toy(dataset_path)

    # ------------------------------------------------------------------
    # Unknown dataset source
    # ------------------------------------------------------------------
    else:
        # If the caller specifies a source we do not support, raise an error.
        raise ValueError(f"Unknown dataset source: {src}")
