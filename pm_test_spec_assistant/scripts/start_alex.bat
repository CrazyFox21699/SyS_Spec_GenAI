@echo off
setlocal EnableDelayedExpansion
REM Double-click to start ALEX (Ollama + web). Folder layout unchanged for development.
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo.
echo  ALEX launcher
echo  Folder: %ROOT%
echo.

REM --- Ollama (skip if already running) ---
curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo Starting Ollama...
  start "Ollama" /min cmd /c "ollama serve"
  timeout /t 4 /nobreak >nul
) else (
  echo Ollama already running.
)

REM --- Python venv (optional) ---
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo Note: no .venv found — using system Python.
)

REM --- Read port from config.yaml (default 8765) ---
set "PORT=8765"
for /f "usebackq tokens=2 delims=: " %%P in (`findstr /r "^  port:" config.yaml 2^>nul`) do set "PORT=%%P"

set "URL=http://127.0.0.1:!PORT!/"
echo Opening !URL!
start "" "!URL!"

echo.
echo Starting ALEX web (Ctrl+C in this window stops the server only)...
echo.
python run_web.py
if errorlevel 1 (
  echo.
  echo Failed. Try: pip install -r requirements.txt
  pause
)
