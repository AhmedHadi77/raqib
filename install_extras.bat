@echo off
REM Optional extras (~140 MB): GPT-4o / Gemini / Ollama clients, ChromaDB, WebRTC video, OpenCV.
REM Run when you are on a fast connection. Everything works without them (lite fallbacks).
cd /d "%~dp0"
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --timeout 120 --retries 20 -r backend\requirements-ai.txt -r edge\requirements-video.txt
echo.
echo Done. Restart start_all.bat to use the extras.
pause
