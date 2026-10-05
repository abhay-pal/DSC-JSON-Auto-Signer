@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup_once.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -c "from credential_store import delete_saved_pin; delete_saved_pin(); print('Saved DSC PIN removed from Windows Credential Manager.')"
pause
