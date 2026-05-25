@echo off
setlocal EnableDelayedExpansion
REM One terminal: Ollama + worker (production) + web UI
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo.
echo  ALEX team launcher (single terminal)
echo.

if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

set "PORT=8765"
for /f "usebackq tokens=2 delims=: " %%P in (`findstr /r "^  port:" config.yaml 2^>nul`) do set "PORT=%%P"
start "" "http://127.0.0.1:!PORT!/login" 2>nul

python scripts\start_alex_all.py
if errorlevel 1 pause
