@echo off
REM ==========================================================
REM  FIRST RUN: installs Python 3.12 if missing (winget), runs setup_windows.bat, then start_all.bat
REM ==========================================================
cd /d "%~dp0"
title First run - AI Inspection Robot
set NEED_PY=1
for %%V in (3.12 3.13 3.11) do ( py -%%V -c "import sys" >nul 2>nul && set NEED_PY=0 )
if "%NEED_PY%"=="1" ( python -c "import sys; assert (3,11)<=sys.version_info[:2]<=(3,13)" >nul 2>nul && set NEED_PY=0 )
if "%NEED_PY%"=="1" (
  echo [prereq] Installing Python 3.12 ...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%p"
) else ( echo [prereq] Python OK )

echo.
echo ===================== SETUP =====================
call setup_windows.bat --no-pause || goto :error

echo.
echo ===================== START =====================
call start_all.bat
exit /b 0

:error
echo.
echo  *** First run failed - read the messages above. Double-click first_run.bat again to resume. ***
pause
exit /b 1
