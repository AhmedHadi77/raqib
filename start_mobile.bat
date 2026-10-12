@echo off
REM Run the app on your PHONE with Expo Go (install "Expo Go" from Play Store / App Store).
REM Phone and PC must be on the same Wi-Fi. Scan the QR code that appears below with Expo Go (Android)
REM or the Camera app (iPhone). In the app, use Login > "Scan pairing code" or type http://YOUR-PC-IP:8000
cd /d "%~dp0mobile"
if not exist node_modules ( call npm install )
npx expo start --lan --go
pause
