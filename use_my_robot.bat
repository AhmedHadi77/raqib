@echo off
REM Put the robot you built in webots\worlds\raqib_build_lab.wbt into the Raqib campus (build guide step 11).
REM Save your build lab world in Webots first (Ctrl+S). To put the original Raqib back: use_my_robot.bat --original
cd /d "%~dp0"
.venv\Scripts\python.exe webots\use_my_robot.py %*
echo.
pause
