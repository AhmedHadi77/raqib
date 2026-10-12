@echo off
REM Raqib in Webots: opens the 3D campus world in Webots, then runs the Raqib robot software on the 3D robot.
REM The backend must be running (start_backend.bat). Close start_robot_sim.bat first: only one robot can run.
cd /d "%~dp0"
if not defined WEBOTS_HOME set "WEBOTS_HOME=C:\Program Files\Webots"
if not exist "%WEBOTS_HOME%\msys64\mingw64\bin\webotsw.exe" (
  echo Webots was not found in "%WEBOTS_HOME%".
  echo Install Webots R2025a from https://cyberbotics.com, or set WEBOTS_HOME to its folder.
  pause
  exit /b 1
)
tasklist /FI "IMAGENAME eq webots-bin.exe" 2>nul | find /I "webots-bin.exe" >nul
if errorlevel 1 (
  echo Opening the Raqib campus in Webots ...
  start "" "%WEBOTS_HOME%\msys64\mingw64\bin\webotsw.exe" "%~dp0webots\worlds\raqib_campus.wbt"
) else (
  echo Webots is already open. Make sure it shows the Raqib campus:
  echo   File, Open World, then pick webots\worlds\raqib_campus.wbt in this folder.
)
echo Connecting the Raqib software to the robot in Webots (this window must stay open) ...
cd edge
..\.venv\Scripts\python.exe -m robot.main --webots
echo.
echo The robot program stopped. If you closed or reset the Webots world, run this file again.
pause
