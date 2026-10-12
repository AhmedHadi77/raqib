@echo off
REM Voice commands: installs free offline speech recognition (faster-whisper) and downloads
REM the English model once (~140 MB). After this, hold the mic button in the app and speak.
cd /d "%~dp0"
echo Installing speech recognition...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --timeout 120 --retries 20 -r backend\requirements-voice.txt
if errorlevel 1 goto fail
echo Downloading the speech model (one time)...
cd backend
..\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8', download_root='data/models'); print('Speech model ready.')"
if errorlevel 1 goto fail
echo.
echo Done. Restart start_all.bat - the app's microphone button now works on phones too.
pause
exit /b 0
:fail
echo.
echo Something went wrong (check your internet connection) and run install_voice.bat again.
pause
exit /b 1
