@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher 'py' was not found. Install Python 3.11 or 3.12 for Windows first.
  pause
  exit /b 1
)
py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Check Python version and internet access.
  pause
  exit /b 1
)
echo.
echo Installation complete.
echo Next: edit config.json with your token PKCS#11 DLL path, then run token_info.bat.
pause
