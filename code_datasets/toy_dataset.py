# code_datasets/toy_dataset.py — Local CSV toy dataset loader for Glacier Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# This module loads a simple "toy" dataset from a local CSV file.
# I use this for:
#   - Quick tests of the full pipeline
#   - Offline demos when large datasets (like CVEfixes/BigVul) are unavailable
#
# Expected CSV columns:
#   - id        (optional; if missing, I auto-generate a sequential ID)
#   - code      (required; the code snippet to classify)
#   - label     (optional; class label, e.g., SAFE or VULNERABLE)
#   - language  (optional; programming language of the snippet)
#
# Output format for each row:
#   {
#       "id": int,
#       "language": str,
#       "code": str,
#       "label": str
#   }

import csv
import os
from typing import Optional  # Needed so Pylance accepts a default of None for a str parameter


def load_toy(path: Optional[str] = None):
    """
    Load the local toy dataset of code samples and labels from a CSV file.

    Args:
        path (str | None):
            - Full path to the CSV file containing the toy dataset.
            - If None or the file does not exist, the function returns an empty list.

    Returns:
        list[dict]:
            A list of rows, each row being a dictionary with keys:
                - "id": int
                - "language": str
                - "code": str
                - "label": str

    Behavior:
        - If the file cannot be found (path is None or invalid), I return an empty list.
        - I normalize labels to uppercase and default missing labels to "UNKNOWN".
        - I normalize language to a lowercase-like "unknown" if missing.
    """
    # If no path is provided or the path does not point to an existing file,
    # return an empty dataset instead of raising an error.
    if not path or not os.path.exists(path):
        return []

    rows = []

    # Open the CSV file using utf-8 encoding and let csv.DictReader map column names to values.
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Enumerate through each row, starting IDs at 1 if an 'id' column is missing.
        for i, row in enumerate(reader, start=1):
            # Extract and clean the "code" field. Default to empty string if missing.
            code = row.get("code", "").strip()

            # Extract and normalize the "label" field.
            # - strip whitespace
            # - convert to uppercase
            # - default to "UNKNOWN" if the value ends up empty
            label = row.get("label", "").strip().upper() or "UNKNOWN"

            # Extract and normalize the "language" field.
            # - strip whitespace
            # - default to "unknown" if missing or empty
            language = row.get("language", "unknown").strip() or "unknown"

            # Build a normalized row dictionary.
            rows.append({
                # Use the 'id' from the CSV if present; otherwise, fall back to the
                # enumeration index 'i' to guarantee a unique, numeric identifier.
                "id": int(row.get("id", i)),

                "language": language,
                "code": code,
                "label": label
            })

    # Return the complete list of normalized rows for downstream processing.
    return rows
