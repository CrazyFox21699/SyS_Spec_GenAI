@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ==============================================
echo   ALEX - Verify Windows setup
echo ==============================================
echo.

if not exist ".venv\Scripts\activate.bat" (
  echo FAIL: .venv does not exist. Run setup_windows.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo [1/4] Python version
python -c "import sys; print('      ' + sys.version.replace('\n',' ')); raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo FAIL: Python 3.10+ is required.
  pause
  exit /b 1
)

echo [2/4] Required Python imports
python -c "mods=['bcrypt','docx','fastapi','openpyxl','pandas','uvicorn','yaml']; [__import__(m) for m in mods]; print('      OK')"
if errorlevel 1 (
  echo FAIL: Missing Python package. Run setup_windows.bat again.
  pause
  exit /b 1
)

echo [3/4] Runtime files
if exist ".env" (echo       .env OK) else (echo       WARN: .env missing)
if exist "config.local.yaml" (echo       config.local.yaml OK) else (echo       WARN: config.local.yaml missing)
if not exist "web_data\uploads" mkdir "web_data\uploads"
if not exist "web_data\output" mkdir "web_data\output"
echo       web_data OK

echo [4/4] Python syntax check
python -m py_compile run_web.py scripts\start_alex_all.py scripts\reset_team_auth.py
if errorlevel 1 (
  echo FAIL: Python syntax check failed.
  pause
  exit /b 1
)
echo       OK

echo.
echo Verify done. Start server with run_windows.bat
echo.
pause
