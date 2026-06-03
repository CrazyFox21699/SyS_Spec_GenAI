@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Missing .venv. Run setup_windows.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
set "ALEX_CONFIG=config.local.yaml"

echo.
echo ==============================================
echo   ALEX - Windows local run
echo   URL: http://127.0.0.1:8765/login
echo ==============================================
echo.
echo Keep this window open. Press Ctrl+C to stop.
echo.

python scripts\start_alex_all.py
pause
