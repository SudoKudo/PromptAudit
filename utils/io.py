"""Small filesystem helpers shared across PromptAudit modules."""

import os


def ensure_dirs(paths):
    """
    Ensure that each directory in `paths` exists.

    Args:
        paths (Iterable[str]):
            A list (or any iterable) of directory paths.

    Behavior:
        - For every path in `paths`, call os.makedirs(path, exist_ok=True).
        - If the directory already exists, it is left as-is.
        - If it does not exist, it is created along with any missing parents.
        - This is safe to call multiple times, and safe in parallel runners.

    I typically use this before writing files (logs, HTML reports, CSVs)
    so the rest of the code can assume the directories are ready.
    """
    for p in paths:
        os.makedirs(p, exist_ok=True)
