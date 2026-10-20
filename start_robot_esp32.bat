@echo off
REM The ESP32 robot's brain: drives the real robot over Wi-Fi (switch the robot on first, same Wi-Fi as this PC).
REM Robot not found? Open its test page (http://raqib.local) and put its address in edge\config.yaml -> hardware: esp32_host
cd /d "%~dp0edge"
..\.venv\Scripts\python.exe -m robot.main --esp32 %*
pause
