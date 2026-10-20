@echo off
REM Simulated ESP32 robot (the same brain program that drives the real robot, with simulation: true)
cd /d "%~dp0edge"
..\.venv\Scripts\python.exe -m robot.main --sim
pause
