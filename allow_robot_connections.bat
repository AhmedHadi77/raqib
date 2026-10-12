@echo off
REM ================================================================
REM  Run ONCE on the PC that runs the server. Windows asks "Allow this app to make changes?" - click Yes.
REM  It lets the phone app (port 8000) and the real robot (port 1883) reach this PC through Windows Firewall,
REM  on home, campus and public Wi-Fi. Nothing else is opened.
REM ================================================================
net session >nul 2>&1
if errorlevel 1 (
  echo Asking Windows for permission...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
netsh advfirewall firewall delete rule name="Raqib server (app)" >nul 2>&1
netsh advfirewall firewall add rule name="Raqib server (app)" dir=in action=allow protocol=TCP localport=8000 profile=any >nul
netsh advfirewall firewall delete rule name="Raqib robot link (MQTT)" >nul 2>&1
netsh advfirewall firewall add rule name="Raqib robot link (MQTT)" dir=in action=allow protocol=TCP localport=1883 profile=any >nul
echo.
echo  Done. The phone app and the robot can now reach this PC.
echo  (To undo: Windows Security ^> Firewall ^> Advanced settings ^> delete the two "Raqib" rules.)
echo.
pause
