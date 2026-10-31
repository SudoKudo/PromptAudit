"""Dataset loaders and shared sample metadata for PromptAudit."""


SAMPLE_METADATA_FIELDS = (
    "cve_id", "project", "repository", "commit_id", "filename", "file_number", "pair_id",
    "year", "cwe_id", "cvss_score",
)


def sample_metadata(row):
    """Retain identifiers needed for matching and clustered analysis."""
    result = {}
    for field in SAMPLE_METADATA_FIELDS:
        value = row.get(field)
        if isinstance(value, str):
            value = value.strip()
        if value is not None and value != "":
            result[field] = value
    return result
