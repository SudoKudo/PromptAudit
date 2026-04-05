<<<<<<< Updated upstream
@echo off
:: ==============================
:: PromptAudit — Windows Launcher
:: Author: Steffen Camarato
:: ==============================

:: Switch to the directory of this script
cd /d "%~dp0"

echo -----------------------------------------
echo  Launching PromptAudit GUI...
echo -----------------------------------------

:: Automatically activate venv if found
if exist venv\Scripts\activate (
    echo Activating virtual environment...
    call venv\Scripts\activate
) else (
    echo [Warning] No virtual environment found.
    echo Create one with:
    echo     python -m venv venv
    echo.
)

:: Start the GUI
python run_PromptAudit.py

echo.
echo PromptAudit has closed.
pause
=======
@echo off
:: PromptAudit Windows launcher

:: Switch to the directory of this script
cd /d "%~dp0"

echo -----------------------------------------
echo  Launching PromptAudit GUI...
echo -----------------------------------------

:: Activate the local virtual environment when present.
if exist .venv\Scripts\activate (
    echo Activating virtual environment...
    call .venv\Scripts\activate
) else if exist venv\Scripts\activate (
    echo Activating virtual environment...
    call venv\Scripts\activate
) else (
    echo [Warning] No virtual environment found.
    echo Create one with:
    echo     python -m venv .venv
    echo.
)

:: Start the GUI
python run_PromptAudit.py

echo.
echo PromptAudit has closed.
pause
>>>>>>> Stashed changes
