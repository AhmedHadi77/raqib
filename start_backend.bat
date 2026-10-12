@echo off
REM Cloud backend (FastAPI + LangGraph agent + embedded MQTT broker + web app) on port 8000
cd /d "%~dp0backend"
echo App + API:  http://localhost:8000      API docs: http://localhost:8000/docs
echo Real robot: just switch it on (same Wi-Fi). It finds this PC by itself.
echo Phone app:  tap "Find automatically" on the sign-in screen. First time? run allow_robot_connections.bat once.
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
