"""Load PromptAudit datasets from the Hugging Face Hub and normalize sample rows."""

import os
import subprocess

from datasets import load_dataset

# Prefer HfFolder when it is available so token detection follows the
# current Hugging Face client behavior.
try:
    from huggingface_hub import HfFolder
except ImportError:
    # Fall back to token-file checks when the helper is unavailable.
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
            * Extracting and renaming fields so the rest of PromptAudit
              does not need to care about dataset-specific schemas.
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
        })

    return samples
