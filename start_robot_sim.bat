@echo off
REM Simulated robot (same code that runs on the Raspberry Pi, with simulation: true)
cd /d "%~dp0edge"
..\.venv\Scripts\python.exe -m robot.main --sim
pause
