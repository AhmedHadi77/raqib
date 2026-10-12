@echo off
REM ==========================================================
REM  One-time setup on Windows: backend + simulated robot (core packages, ~30 MB download)
REM  Needs Python 3.11-3.13   (first_run.bat installs it for you)
REM  Usage: setup_windows.bat [--no-pause]
REM  Optional later:  install_extras.bat (real AI + ChromaDB + WebRTC video)
REM                   setup_mobile.bat   (Expo app for your phone)
REM ==========================================================
cd /d "%~dp0"
set PY=
for %%V in (3.12 3.13 3.11) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V" )
)
if not defined PY ( python -c "import sys; assert (3,11)<=sys.version_info[:2]<=(3,13)" >nul 2>nul && set "PY=python" )
if not defined PY (
  echo  *** Python 3.11, 3.12 or 3.13 not found. Run first_run.bat or install from python.org ***
  goto :error
)
echo Using %PY%

echo [1/3] Creating Python virtual environment .venv ...
if not exist .venv\Scripts\python.exe ( %PY% -m venv .venv || goto :error )

echo [2/3] Installing core packages (slow connection? this retries automatically) ...
REM "python -m pip" (not pip.exe): Smart App Control blocks unsigned venv launchers
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --timeout 120 --retries 20 -r backend\requirements.txt -r edge\requirements.txt || goto :error

echo [3/3] Creating backend\.env (if missing) ...
if not exist backend\.env copy backend\.env.example backend\.env

echo.
echo  Setup complete.  Next: double-click start_all.bat
if not "%~1"=="--no-pause" pause
exit /b 0

:error
echo.
echo  *** Setup failed - read the error above. Re-run it: downloads resume from the cache. ***
if not "%~1"=="--no-pause" pause
exit /b 1
