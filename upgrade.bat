@echo off
REM Upgrade to Raqib 2.2: new packages, voice recognition (offline), exam proctoring vision, phone app packages, then restart.
cd /d "%~dp0"
title Upgrade to Raqib 2.2
echo [1/6] Stopping the running backend and robot ...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'uvicorn app\.main|robot\.main' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

echo [2/6] Server and robot packages ...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --timeout 120 --retries 20 -r backend\requirements.txt -r edge\requirements.txt -r backend\requirements-ai.txt -r edge\requirements-video.txt
if errorlevel 1 echo  !! Some extras failed to install - the app still works with the built-in fallbacks.

echo [3/6] Voice recognition (faster-whisper) ...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --timeout 120 --retries 20 -r backend\requirements-voice.txt
if errorlevel 1 echo  !! Voice recognition did not install - run install_voice.bat later. Voice still works in Chrome / Edge on this PC.

echo [4/6] Speech model (one time, about 140 MB) ...
pushd backend
..\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8', download_root='data/models'); print('Speech model ready.')"
popd

echo [5/6] Exam proctoring vision (MediaPipe, offline) ...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --timeout 120 --retries 20 -r backend\requirements-vision.txt
if errorlevel 1 (
  echo  !! MediaPipe did not install for this Python version. Exam monitoring still works with sound,
  echo     and with the camera once you connect a vision AI in the app: More, AI settings.
) else (
  pushd backend
  ..\.venv\Scripts\python.exe -c "from app.proctor import MediaPipeProctor as M; M('data/models').ensure_models(); print('Proctoring models ready.')"
  popd
)

echo [6/6] Phone app packages (npm) ...
pushd mobile
call npm install
popd

echo.
echo Upgrade finished. Starting everything ...
call start_all.bat
