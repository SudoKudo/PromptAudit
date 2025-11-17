#!/bin/bash
# ==============================
# PromptAudit — Linux/Mac Launcher
# Author: Steffen Camarato
# ==============================

# Move to this script's directory
cd "$(dirname "$0")"

echo "-----------------------------------------"
echo "  Launching PromptAudit GUI..."
echo "-----------------------------------------"

# Activate virtual environment if exists
if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "[Warning] No virtual environment detected."
    echo "Create one with: python3 -m venv venv"
    echo
fi

# Start GUI
python3 run_PromptAudit.py
