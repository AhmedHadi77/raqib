@echo off
REM Optional: install the Expo / React Native packages (~300 MB) to run the app on your PHONE with Expo Go.
REM (Not needed for the browser version - the backend already serves it at http://localhost:8000)
cd /d "%~dp0mobile"
call npm install
echo.
echo Done. Then double-click start_mobile.bat and scan the QR code with Expo Go.
pause
