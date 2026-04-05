#!/bin/bash
# PromptAudit POSIX launcher

# Move to this script's directory
cd "$(dirname "$0")"

echo "-----------------------------------------"
echo "  Launching PromptAudit GUI..."
echo "-----------------------------------------"

# Activate the local virtual environment when present.
if [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "[Warning] No virtual environment detected."
    echo "Create one with: python3 -m venv .venv"
    echo
fi

# Start GUI
python3 run_PromptAudit.py
