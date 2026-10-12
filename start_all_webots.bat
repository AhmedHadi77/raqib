@echo off
REM Everything with the 3D Webots robot instead of the built-in 2D simulator.
cd /d "%~dp0"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'robot\.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
REM Is the server already listening on port 8000?
powershell -NoProfile -Command "if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) { exit 1 }"
if errorlevel 1 (
  start "Backend" cmd /k start_backend.bat
  timeout /t 8 /nobreak >nul
)
start "Robot (Webots)" cmd /k start_robot_webots.bat
timeout /t 20 /nobreak >nul
start "" http://localhost:8000
echo.
echo  Backend + Webots robot are running. The app is open at http://localhost:8000
echo  Drive it, talk to it or start the Exam monitor: the robot moves in the Webots window.
echo.
