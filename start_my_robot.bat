@echo off
REM ================================================================
REM  Start everything for the REAL ESP32 robot:
REM    1) switch the robot on (its power bank) and wait until its orange LED stays on
REM    2) this PC on the same Wi-Fi (your phone's hotspot is best), then double-click this file
REM ================================================================
cd /d "%~dp0"
start "Server" cmd /k start_backend.bat
timeout /t 8 /nobreak >nul
start "Robot brain (ESP32)" cmd /k start_robot_esp32.bat
timeout /t 8 /nobreak >nul
start "" http://localhost:8000
echo.
echo  Server + robot brain are running in two windows. The app opened in your browser:
echo    http://localhost:8000      (login: operator / operator123)
echo  Phone on the same Wi-Fi: open the Raqib app and tap "Find automatically". This PC's address:
ipconfig | findstr /i "IPv4"
echo.
