@echo off
REM Try ESP32 mode with NO parts: a pretend ESP32 (the simulator behind the real robot's Wi-Fi interface).
cd /d "%~dp0"
start "Pretend ESP32" cmd /k .venv\Scripts\python.exe tools\esp32_emulator.py
timeout /t 4 /nobreak >nul
start "Server" cmd /k start_backend.bat
timeout /t 8 /nobreak >nul
start "Robot brain (ESP32)" cmd /k "cd /d %~dp0edge && ..\.venv\Scripts\python.exe -m robot.main --esp32 127.0.0.1:8780"
timeout /t 6 /nobreak >nul
start "" http://localhost:8000
