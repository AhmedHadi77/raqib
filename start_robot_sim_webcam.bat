@echo off
REM Simulated robot that uses THIS PC's webcam as its camera.
REM Use it to test exam proctoring for real: sit in front of the webcam, turn your head to the side for
REM 3 seconds, look down at your lap for 8 seconds or hold up your phone. Start "Exam monitor" in the app
REM (Stay in place) and the robot flags it, speaks the warning and sends you the photo.
REM Close start_robot_sim.bat first (only one robot can run).
cd /d "%~dp0edge"
set ROBOT_SIM_CAMERA=webcam
..\.venv\Scripts\python.exe -m robot.main --sim
pause
