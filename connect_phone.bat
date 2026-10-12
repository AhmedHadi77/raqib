@echo off
REM Connect the phone app to this PC: checks the 3 things that usually go wrong and fixes them.
cd /d "%~dp0"
title Connect the Raqib phone app
echo.
echo  [1/3] Is the Raqib server running?
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo        No - starting it now in a new window ...
  start "Backend" cmd /k start_backend.bat
  powershell -NoProfile -Command "for ($i=0; $i -lt 60; $i++) { if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 }; Start-Sleep 1 }; exit 1"
  if errorlevel 1 ( echo        !! The server did not start. Read the error in the Backend window. & goto :end )
)
echo        Yes.
echo.
echo  [2/3] Does Windows Firewall let the phone in?
netsh advfirewall firewall show rule name="Raqib server (app)" >nul 2>&1
if errorlevel 1 (
  echo        Not yet - Windows will ask "Allow this app to make changes?": click YES.
  call allow_robot_connections.bat
) else (
  echo        Yes.
)
echo.
echo  [3/3] This PC's address on your Wi-Fi (type it in the app if "Find automatically" fails):
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceAlias -notmatch 'vEthernet|VirtualBox|VMware|Loopback|WSL' } | ForEach-Object { '        http://' + $_.IPAddress + ':8000      (' + $_.InterfaceAlias + ')' }"
powershell -NoProfile -Command "Get-NetConnectionProfile | ForEach-Object { if ($_.NetworkCategory -eq 'Public') { '        Note: Windows calls the network ''' + $_.Name + ''' Public. The firewall rule above still allows the app.' } }"
echo.
echo  On the phone: same Wi-Fi as this PC (not mobile data, not a guest network), then tap "Find automatically".
echo  A QR code to scan is opening in your browser.
start "" http://localhost:8000/connect
:end
echo.
pause
