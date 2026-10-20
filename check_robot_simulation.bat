@echo off
REM Runs the simulated ESP32 robot with the build guide's wiring, drives it, reads every sensor,
REM then tries 13 common wiring mistakes. About 3 minutes; it uses its own ports, so start_all.bat may stay open.
cd /d "%~dp0"
.venv\Scripts\python.exe tools\wiring_sim_check.py
pause
