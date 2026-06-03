@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo ==============================================
echo   ALEX - Windows setup
echo   Folder: %CD%
echo ==============================================
echo.

set "PY_CMD="
where py >nul 2>nul
if %ERRORLEVEL%==0 set "PY_CMD=py -3"
if not defined PY_CMD (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo ERROR: Python 3.10+ not found.
  echo Install Python from https://www.python.org/downloads/windows/
  echo Enable "Add python.exe to PATH", reopen this folder, then run setup_windows.bat again.
  pause
  exit /b 1
)

echo [1/5] Check Python...
%PY_CMD% -c "import sys; print('      Python ' + sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo ERROR: ALEX needs Python 3.10+.
  pause
  exit /b 1
)

echo [2/5] Create .venv...
if not exist ".venv" (
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create .venv.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo ERROR: Cannot activate .venv.
  pause
  exit /b 1
)
echo       OK

echo [3/5] Install Python packages...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo ERROR: pip upgrade failed.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: requirements install failed.
  pause
  exit /b 1
)
echo       OK

echo [4/5] Create local runtime files...
if not exist ".env" (
  if exist ".env.example" (
    copy ".env.example" ".env" >nul
    echo       Created .env from .env.example
  ) else (
    echo       WARN: .env.example missing
  )
) else (
  echo       .env already exists
)
if not exist "web_data" mkdir "web_data"
if not exist "web_data\uploads" mkdir "web_data\uploads"
if not exist "web_data\output" mkdir "web_data\output"
if not exist "output" mkdir "output"
if not exist "input" mkdir "input"
if not exist "config" mkdir "config"
echo       OK

echo [5/5] Reset local admin account...
python scripts\reset_team_auth.py --yes --username admin --password "Alex@2025!"
if errorlevel 1 (
  echo ERROR: Failed to reset local admin account.
  pause
  exit /b 1
)
echo       OK

echo.
echo ==============================================
echo   SETUP DONE
echo ==============================================
echo.
echo Run ALEX:
echo   run_windows.bat
echo.
echo Open browser:
echo   http://127.0.0.1:8765/login
echo.
echo Login:
echo   admin / Alex@2025!
echo.
pause
