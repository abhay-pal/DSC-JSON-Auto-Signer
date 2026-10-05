@echo off
setlocal
cd /d "%~dp0"

echo ==============================================================
echo  DSC JSON Auto Signer - First Time Setup
echo ==============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" was not found.
  echo Install Python 3.11 or 3.12 for Windows, then run this file again.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo Creating Python virtual environment...
  py -m venv .venv
  if errorlevel 1 goto :fail
)

call .venv\Scripts\activate.bat
echo Installing required Python packages...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Starting one-time configuration wizard...
python setup_wizard.py
if errorlevel 1 goto :fail

echo.
echo Setup completed.
echo Now double-click token_info.bat to verify the DSC token.
echo After that, use run_signer.bat for automatic signing.
pause
exit /b 0

:fail
echo.
echo Setup failed. Read the error shown above.
pause
exit /b 1
