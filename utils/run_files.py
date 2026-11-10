"""Keep atomic run-file writes and resume checks safe."""

from time import sleep


# The c4ba49d run files can resume through this exact file-writing patch.
# Any other source change still needs a new run.
_CHECKPOINT_PATCH = {
    "core/runner.py": (
        "4c68de39cb426c55317c43bc94d0dd2f707b96cba0e2c57d81831c8e588c21e0",
        "7bb1b618c92c0a8f4aa1ef600216d4447244440a0022d7dc442229d503038853",
    ),
    "core/batch_runner.py": (
        "cef70f5f983ca49d0322a96ccbd937801b0bfc5dd4cf0a0e33a02409963a0b52",
        "5bddad1ca5c94efee4fe032b63cbb37978a6e7cca8dddadee5c085040ec23b19",
    ),
    "core/revision_study.py": (
        "ba95da2cbe1679741335702f124a08ecb01dcefedae26c962540ee3725826cb3",
        "4b19a555172b4cc8cdd8713b216bca2eb2c502d21aa85fd9ce50647219aa9178",
    ),
}


def replace_with_retry(temporary, destination):
    """Retry a Windows sharing error without removing the previous file."""
    for delay in (0.05, 0.1, 0.2, 0.4, 0.8, 1.6):
        try:
            return temporary.replace(destination)
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33):
                raise
            sleep(delay)
    return temporary.replace(destination)


def resume_sources_match(saved, current):
    """Allow an exact checkpoint-writing update without mixing inference sources."""
    if not isinstance(saved, dict) or saved.keys() != current.keys():
        return False
    return all(
        old == current[name] or (old, current[name]) == _CHECKPOINT_PATCH.get(name.replace("\\", "/"))
        for name, old in saved.items()
    )
