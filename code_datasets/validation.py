"""Validate evaluation cohorts and keep sample identities consistent across runners."""

import hashlib
import json

from . import sample_metadata


class DatasetValidationError(ValueError):
    """The selected data cannot be scored as a binary classification cohort."""


def validate_samples(rows, dataset_name):
    """Normalize legacy pairs, then reject invalid labels, code, and duplicate IDs."""
    samples, seen = [], set()
    for index, original in enumerate(rows):
        if isinstance(original, dict):
            row = dict(original)
        elif isinstance(original, (list, tuple)) and len(original) >= 2:
            row = {"id": index, "code": original[0], "label": original[1], "language": "unknown"}
        else:
            raise DatasetValidationError(f"Invalid sample in {dataset_name} at row {index + 1}")
        source_id = row.get("id", index)
        if (not isinstance(source_id, (str, int)) or isinstance(source_id, bool)
                or not str(source_id).strip()):
            raise DatasetValidationError(f"Invalid sample ID in {dataset_name} at row {index + 1}")
        key = str(source_id)
        if key in seen:
            raise DatasetValidationError(f"Duplicate sample ID {key} in {dataset_name}")
        label = row.get("label")
        if not isinstance(label, str) or label.strip().lower() not in {"safe", "vulnerable"}:
            raise DatasetValidationError(f"Invalid gold label in {dataset_name}, sample {key}; use SAFE or VULNERABLE")
        code = row.get("code")
        if not isinstance(code, str) or not code.strip():
            raise DatasetValidationError(f"Invalid code in {dataset_name}, sample {key}; expected nonempty text")
        row["id"] = source_id
        row["label"] = label.strip().upper()
        seen.add(key)
        samples.append(row)
    if not samples:
        raise DatasetValidationError(f"Dataset {dataset_name} has no samples")
    return samples


def sample_identity(row, dataset_name, index=0):
    """Match the established study hash without including filesystem paths."""
    metadata = sample_metadata(row)
    if "language" in row:
        metadata["language"] = row["language"]
    sample = {"sample_id": str(row.get("id", index)), "gold": row["label"].strip().lower(),
              "code_sha256": hashlib.sha256(row["code"].encode("utf-8")).hexdigest(), **metadata}
    payload = json.dumps({"dataset": dataset_name, **sample}, sort_keys=True, ensure_ascii=False)
    return {**sample, "sample_uid": hashlib.sha256(payload.encode("utf-8")).hexdigest()}


def cohort_fingerprint(rows):
    """Hash rows in order without building a second copy of all source text."""
    digest = hashlib.sha256()
    for row in rows:
        payload = json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()
