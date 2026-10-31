"""Load local CVE patch datasets and report source exclusions."""

from collections import Counter
from pathlib import Path
import re


README_LINE_RE = re.compile(r"\s+(\d+)\.\s+(.+)")
BEFORE_FILE_RE = re.compile(r"(\d+)_before_")
AFTER_FILE_RE = re.compile(r"(\d+)_after_")
EXTENSION_LANGUAGES = {
    ".c": "C", ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".h": "C++", ".hpp": "C++",
    ".java": "Java", ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust", ".php": "PHP",
    ".rb": "Ruby", ".cs": "C#", ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala",
    ".sh": "Shell", ".sql": "SQL", ".html": "HTML", ".css": "CSS",
}


def load_cvefixes_dataset(source_path=None, *, return_inventory=False):
    """Read direct before/after files, retaining the established language filter.

    Optional inventory counts distinguish source exclusions from model abstentions.
    Nested CVE folders are counted but remain outside the selected cohort.
    """
    if source_path is None:
        source_path = Path(__file__).resolve().parents[1] / "data" / "cvefixes" / "cvefixes_1000"
    source_dir = Path(source_path)
    if not source_dir.is_dir():
        raise ValueError(f"CVEfixes source path does not exist: {source_path}")
    folders = sorted(path for path in source_dir.iterdir() if path.is_dir())
    inventory = {"source": source_dir.name, "format": "cve_folders", "source_cve_folders": len(folders),
                 "source_before_files": 0, "source_after_files": 0, "nested_cve_folders_ignored": 0,
                 "missing_readmes": 0, "unreadable_readmes": 0, "missing_after_files": 0,
                 "orphan_after_files": 0, "unrecognized_before_files": 0}
    excluded = Counter({"unsupported_language": 0, "empty_code": 0, "unreadable_code": 0})
    samples = []
    for folder in folders:
        inventory["nested_cve_folders_ignored"] += sum(1 for path in folder.rglob("CVE-*") if path.is_dir())
        filenames = {}
        readme = folder / "README.txt"
        if readme.exists():
            try:
                for line in readme.read_text(encoding="utf-8", errors="replace").split("\n"):
                    match = README_LINE_RE.match(line)
                    if match:
                        filenames[int(match.group(1))] = match.group(2).strip()
            except OSError:
                inventory["unreadable_readmes"] += 1
        else:
            inventory["missing_readmes"] += 1
        candidates = sorted(folder.glob("*_before_*.txt"))
        before_files = [path for path in candidates if BEFORE_FILE_RE.match(path.name)]
        inventory["unrecognized_before_files"] += len(candidates) - len(before_files)
        after_names = {path.name for path in folder.iterdir() if path.is_file() and AFTER_FILE_RE.match(path.name)}
        expected_after = {path.name.replace("_before_", "_after_") for path in before_files}
        inventory["source_before_files"] += len(before_files)
        inventory["source_after_files"] += len(after_names)
        inventory["missing_after_files"] += len(expected_after - after_names)
        inventory["orphan_after_files"] += len(after_names - expected_after)
        for before in before_files:
            file_number = int(BEFORE_FILE_RE.match(before.name).group(1))
            after = folder / before.name.replace("_before_", "_after_")
            filename = filenames.get(file_number, "unknown")
            language = EXTENSION_LANGUAGES.get(Path(filename).suffix.lower(), "unknown")
            if language == "unknown":
                excluded["unsupported_language"] += 1 + int(after.exists())
                continue
            for path, label in ((before, "VULNERABLE"), (after, "SAFE")):
                if not path.exists():
                    continue
                try:
                    code = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    excluded["unreadable_code"] += 1
                    continue
                if not code:
                    excluded["empty_code"] += 1
                    continue
                samples.append({"id": len(samples), "cve_id": folder.name, "file_number": file_number,
                                "filename": filename, "language": language, "code": code, "label": label})
    inventory.update(loaded_samples=len(samples), loaded_cves=len({row["cve_id"] for row in samples}),
                     label_counts=dict(Counter(row["label"] for row in samples)),
                     excluded_code_files=dict(excluded))
    return (samples, inventory) if return_inventory else samples
