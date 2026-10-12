@echo off
cd /d "%~dp0"
start "Backend" cmd /k start_backend.bat
timeout /t 8 /nobreak >nul
start "Robot (simulation)" cmd /k start_robot_sim.bat
timeout /t 5 /nobreak >nul
start "" http://localhost:8000
echo.
echo  Backend + simulated robot are running in two windows.
echo  The app opened in your browser:  http://localhost:8000   (login: operator / operator123)
echo  From your phone (same Wi-Fi) open  http://YOUR-PC-IP:8000  - your IP:
ipconfig | findstr /i "IPv4"
echo.
