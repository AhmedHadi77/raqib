@echo off
REM Build an installable Android APK in the cloud with EAS (free Expo account needed: https://expo.dev/signup).
REM The first time it asks you to log in and to create the project - answer Yes.
REM When it finishes it prints a download link / QR code for the .apk - open it on your phone to install.
cd /d "%~dp0mobile"
if not exist node_modules ( call npm install )
call npx eas-cli@latest login
call npx eas-cli@latest build --profile preview --platform android
pause
