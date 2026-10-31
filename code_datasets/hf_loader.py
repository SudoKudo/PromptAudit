"""Load PromptAudit datasets from the Hugging Face Hub and normalize sample rows."""

import os
import subprocess

from datasets import load_dataset
from . import sample_metadata

# Prefer HfFolder when it is available so token detection follows the
# current Hugging Face client behavior.
try:
    from huggingface_hub import HfFolder
except ImportError:
    # Fall back to token-file checks when the helper is unavailable.
    HfFolder = None


def ensure_hf_login():
    """Use an existing Hub token or open the command-line login prompt."""
    # 1. Try the current Hugging Face Hub token helper.
    if HfFolder is not None:
        try:
            token = HfFolder.get_token()
            if token:
                return
        except Exception:
            # If anything goes wrong here, fall back to manual path checks.
            pass

    # 2. Check legacy and cache token locations.
    legacy_path = os.path.expanduser("~/.huggingface/token")
    cache_path = os.path.expanduser("~/.cache/huggingface/token")
    if os.path.exists(legacy_path) or os.path.exists(cache_path):
        return

    # 3. If not logged in, prompt once via CLI.
    print("[HF] Hugging Face login required (first time only).")
    try:
        try:
            subprocess.run(["hf", "auth", "login"], check=True)
        except FileNotFoundError:
            subprocess.run(["huggingface-cli", "login"], check=True)
    except Exception as e:
        raise RuntimeError(
            "Failed to log into Hugging Face. Run `hf auth login` manually once."
        ) from e


def load_hf_dataset(name: str):
    """Load a supported Hub dataset and return normalized code samples.

    Rows contain an ID, code, language, SAFE/VULNERABLE label, and available
    CVE metadata. Dataset-specific field mappings are handled here.
    """
    ensure_hf_login()
    name = name.lower()

    # Map short names used in PromptAudit to the actual Hugging Face repository IDs.
    mapping = {
        "cvefixes": "DetectVul/CVEfixes",
        "bigvul": "ZeoBig/BigVul",
        "vul4j": "secureai/Vul4J",
    }

    repo = mapping.get(name)
    if not repo:
        raise ValueError(f"Unsupported dataset {name}")

    ds = load_dataset(repo, split="train")

    def normalize_label(value) -> str:
        """Map common HF label encodings into the project-wide SAFE/VULNERABLE scheme."""
        cleaned = value.strip().lower() if isinstance(value, str) else str(value).strip().lower()

        if cleaned in {"1", "true", "vulnerable", "vuln", "unsafe"}:
            return "VULNERABLE"
        if cleaned in {"0", "false", "safe", "benign", "clean"}:
            return "SAFE"
        return cleaned.upper() or "UNKNOWN"

    # Convert the Hugging Face dataset rows into the unified structure expected by PromptAudit.
    samples = []
    for i, row in enumerate(ds):
        samples.append({
            "id": i,
            "language": row.get("language", "unknown"),
            "code": row.get("func_before", row.get("code", row.get("func", ""))),
            # Missing gold labels should stay explicit rather than being coerced to SAFE.
            "label": normalize_label(row.get("target", "UNKNOWN")),
            **sample_metadata(row),
        })

    return samples
