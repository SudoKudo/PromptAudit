# code_datasets/hf_loader.py — Hugging Face dataset loader for Glacier Code v2.0

# ---------------------------------------------------------------------
# This module handles loading large research datasets from the Hugging Face Hub
# (e.g., CVEfixes, BigVul, Vul4J) and converting them into the unified format
# used throughout Code v2.0:
#
#     {
#         "id": int,
#         "language": str,
#         "code": str,
#         "label": str
#     }
#
# I also included logic to gently ensure the user is logged into Hugging Face,
# without forcing a login every time the code runs.

import os, subprocess
from datasets import load_dataset

import os, subprocess  # (Duplicate import is harmless; left as-is to avoid changing code.)

# ✅ Try to import HfFolder from huggingface_hub (newer API)
# I use HfFolder (when available) to check whether a token already exists.
try:
    from huggingface_hub import HfFolder
except ImportError:
    # If huggingface_hub is not installed or HfFolder is missing,
    # I fall back to manually checking token files on disk.
    HfFolder = None


def ensure_hf_login():
    """
    Ensure the user is logged into Hugging Face before attempting to download datasets.

    The logic:
      1. Try to detect a token using the modern huggingface_hub API (HfFolder).
      2. If that fails, look for token files in the legacy and cache directories.
      3. If no token is found, prompt the user to log in using the CLI.

    This is designed to be:
      - Safe: only triggers login when really needed.
      - Backward compatible: supports older token locations.
      - Non-intrusive: if login is already set up, it quietly returns.
    """
    # ✅ 1. Try new Hugging Face Hub token cache
    if HfFolder is not None:
        try:
            token = HfFolder.get_token()
            if token:
                # A token is already configured; no login needed.
                return
        except Exception:
            # If anything goes wrong here, fall back to manual path checks.
            pass

    # ✅ 2. Check old and new token locations
    # Legacy path: older versions of the Hugging Face CLI stored the token here.
    legacy_path = os.path.expanduser("~/.huggingface/token")
    # Newer cache path: some setups use this cache-based location instead.
    cache_path = os.path.expanduser("~/.cache/huggingface/token")

    # If we find a token file in either location, we assume the user is logged in.
    if os.path.exists(legacy_path) or os.path.exists(cache_path):
        return  # Token file found; no need to prompt again.

    # ✅ 3. If not logged in, prompt once via CLI
    # At this point, no token was found through any method, so I request login.
    print("🔑 Hugging Face login required (first time only)…")
    try:
        # This calls the Hugging Face CLI to handle the login flow in the terminal.
        subprocess.run(["huggingface-cli", "login"], check=True)
    except Exception as e:
        # If the CLI login fails, raise a clear error message with guidance.
        raise RuntimeError(
            "⚠️ Failed to log into Hugging Face. Run `huggingface-cli login` manually once."
        ) from e
    

def load_hf_dataset(name: str):
    """
    Load a supported dataset from the Hugging Face Hub and normalize its structure.

    Args:
        name (str):
            A shorthand dataset identifier, expected to be one of:
              - "cvefixes"
              - "bigvul"
              - "vul4j"

    Returns:
        list[dict]:
            A list of samples with a consistent structure across datasets:
                {
                    "id": int,             # Sequential index of the sample
                    "language": str,       # Programming language (if available)
                    "code": str,           # Code snippet (usually the vulnerable or pre-fix code)
                    "label": str           # Classification label like "SAFE" or "VULNERABLE"
                }

    Notes:
        - The function handles:
            * Ensuring Hugging Face login is set up.
            * Mapping simple dataset nicknames to full HF repo names.
            * Extracting and renaming fields so the rest of Code 2.0
              does not need to care about dataset-specific schemas.
    """
    # Ensure the user is authenticated with Hugging Face before downloading.
    ensure_hf_login()

    # Standardize the name to lowercase so the mapping is case-insensitive.
    name = name.lower()

    # Map short names used in my code to the actual Hugging Face repository IDs.
    mapping = {
        "cvefixes": "DetectVul/CVEfixes",
        "bigvul": "ZeoBig/BigVul",
        "vul4j": "secureai/Vul4J"
    }

    # Look up the corresponding repository ID.
    repo = mapping.get(name)
    if not repo:
        # If the shorthand is not recognized, fail early with a clear message.
        raise ValueError(f"Unsupported dataset {name}")

    # Use the `datasets` library to download/load the "train" split from HF.
    ds = load_dataset(repo, split="train")

    # Convert the Hugging Face dataset rows into the unified structure expected by Code 2.0.
    samples = []
    for i, row in enumerate(ds):
        samples.append({
            # Sequential numeric ID to uniquely identify each sample.
            "id": i,

            # Some datasets provide "language"; if missing, I default to "unknown".
            "language": row.get("language", "unknown"),

            # Different datasets store the code under different column names.
            # Priority:
            #   1. func_before (vulnerable function before the fix)
            #   2. code (generic code field)
            "code": row.get("func_before", row.get("code", "")),

            # Normalize the label to uppercase string.
            # If "target" is missing, I default to "SAFE" to keep the label consistent.
            "label": str(row.get("target", "SAFE")).upper()
        })

    # Return the fully normalized list of samples.
    return samples
