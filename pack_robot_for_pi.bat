@echo off
REM Makes raqib-robot.zip: everything the Raspberry Pi needs to be a complete robot on its own (robot program +
REM its own server, so the phone app works without this PC). Copy it to the Pi (USB stick or WinSCP), then on the Pi:
REM     unzip raqib-robot.zip -d ~/raqib  &&  cd ~/raqib  &&  bash edge/scripts/install_pi.sh
cd /d "%~dp0"
if exist raqib-robot.zip del raqib-robot.zip
powershell -NoProfile -Command "$tmp=Join-Path $env:TEMP 'raqib-pack'; if (Test-Path $tmp) {Remove-Item $tmp -Recurse -Force}; robocopy edge (Join-Path $tmp 'edge') /E /XD .venv __pycache__ .pytest_cache /XF config.local.yaml *.pyc | Out-Null; robocopy backend (Join-Path $tmp 'backend') /E /XD .venv __pycache__ .pytest_cache data /XF .env *.pyc | Out-Null; Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath 'raqib-robot.zip' -Force; Remove-Item $tmp -Recurse -Force"
if exist raqib-robot.zip (
  echo.
  echo  Created raqib-robot.zip  ^(%CD%\raqib-robot.zip^)
  echo  Copy it to the Raspberry Pi, then on the Pi:
  echo     unzip raqib-robot.zip -d ~/raqib
  echo     cd ~/raqib ^&^& bash edge/scripts/install_pi.sh
  echo  Your AI key is NOT copied. Enter it later in the app: More, AI settings.
) else (
  echo  Could not create the zip - see the message above.
)
echo.
pause
