@echo off
REM Raqib parts check: tests the robot you are building in Webots (like hwtest on the real robot).
REM 1) Webots open with your world (webots\worlds\raqib_build_lab.wbt), robot name "raqib", controller "<extern>".
REM 2) Press Play in Webots, then double-click this file. Run it after every build step.
cd /d "%~dp0"
if not defined WEBOTS_HOME set "WEBOTS_HOME=C:\Program Files\Webots"
echo Checking your robot in Webots. If nothing happens for a minute, make sure the world is running
echo and has a Robot named "raqib" whose controller is ^<extern^>.
.venv\Scripts\python.exe webots\check_my_robot.py
echo.
pause
