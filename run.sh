#!/usr/bin/env bash

cd "$(dirname "$0")" || exit 1

promptaudit_python=""
if [ -d ".venv" ] || [ -d "venv" ]; then
    if [ -d ".venv" ]; then
        promptaudit_python=".venv/bin/python"
    else
        promptaudit_python="venv/bin/python"
    fi
    if ! "$promptaudit_python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
        echo "The local Python environment cannot start or uses Python older than 3.10."
        echo "Recreate it with a working Python installation, then install requirements.txt."
        echo "See the Installation section in README.md."
        exit 1
    fi
else
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
            promptaudit_python="$candidate"
            break
        fi
    done
    if [ -z "$promptaudit_python" ]; then
        echo "Python 3.10 or later was not found."
        echo "Follow the Installation section in README.md to set up Python and dependencies."
        exit 1
    fi
fi

echo "Launching PromptAudit with $promptaudit_python..."
exec "$promptaudit_python" run_PromptAudit.py
