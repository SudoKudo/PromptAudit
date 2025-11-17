# core/io.py — Minimal filesystem helpers for Code v2.0
# Author: Steffen Camarato — University of Central Florida
# ---------------------------------------------------------------------
# Purpose:
#   This module provides a tiny utility to make sure one or more directories
#   exist before writing logs, results, or reports.
#
#   Typical usage in Code v2.0:
#       from core.io import ensure_dirs
#       ensure_dirs(["results", "results/logs", "results/plots"])
#
#   If a directory is already present, nothing happens.
#   If it is missing, it is created (including any parent directories).


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
