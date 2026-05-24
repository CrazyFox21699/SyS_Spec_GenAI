@echo off
setlocal EnableDelayedExpansion
REM Team server: Ollama + web + analyze worker (deployment.mode: production)
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo.
echo  ALEX team launcher (web + worker + Ollama)
echo.

curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo Starting Ollama...
  start "Ollama" /min cmd /c "ollama serve"
  timeout /t 4 /nobreak >nul
)

if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

set "PORT=8765"
for /f "usebackq tokens=2 delims=: " %%P in (`findstr /r "^  port:" config.yaml 2^>nul`) do set "PORT=%%P"

start "ALEX worker" /min cmd /c "cd /d \"%ROOT%\" && if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat && python -m web.worker"
timeout /t 2 /nobreak >nul

start "" "http://127.0.0.1:!PORT!/login"
echo Open http://127.0.0.1:!PORT!/login for team login.
python run_web.py
