@echo off
setlocal

cd /d "%~dp0" || exit /b 1

set "PROMPTAUDIT_PYTHON="
if exist .venv\ (
    set "PROMPTAUDIT_PYTHON=.venv\Scripts\python.exe"
) else if exist venv\ (
    set "PROMPTAUDIT_PYTHON=venv\Scripts\python.exe"
)

if defined PROMPTAUDIT_PYTHON (
    "%PROMPTAUDIT_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo The local Python environment cannot start or uses Python older than 3.10.
        echo Recreate it with a working Python installation, then install requirements.txt.
        echo See the Installation section in README.md.
        pause
        exit /b 1
    )
) else (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PROMPTAUDIT_PYTHON=python"
    ) else (
        python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PROMPTAUDIT_PYTHON=python3"
    )
    if not defined PROMPTAUDIT_PYTHON (
        echo Python 3.10 or later was not found.
        echo Follow the Installation section in README.md to set up Python and dependencies.
        pause
        exit /b 1
    )
)

echo Launching PromptAudit with %PROMPTAUDIT_PYTHON%...
"%PROMPTAUDIT_PYTHON%" run_PromptAudit.py
set "PROMPTAUDIT_EXIT_CODE=%errorlevel%"

echo.
echo PromptAudit has closed.
pause
exit /b %PROMPTAUDIT_EXIT_CODE%
