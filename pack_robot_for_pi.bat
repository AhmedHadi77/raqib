@echo off
REM Makes raqib-robot.zip with everything the Raspberry Pi needs. Copy it to the Pi (USB stick or WinSCP), then on the Pi:
REM     unzip raqib-robot.zip -d ~/edge  &&  cd ~/edge  &&  bash scripts/install_pi.sh
cd /d "%~dp0"
if exist raqib-robot.zip del raqib-robot.zip
powershell -NoProfile -Command "$src='edge'; $tmp=Join-Path $env:TEMP 'raqib-edge'; if (Test-Path $tmp) {Remove-Item $tmp -Recurse -Force}; robocopy $src $tmp /E /XD .venv __pycache__ .pytest_cache /XF config.local.yaml *.pyc | Out-Null; Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath 'raqib-robot.zip' -Force; Remove-Item $tmp -Recurse -Force"
if exist raqib-robot.zip (
  echo.
  echo  Created raqib-robot.zip  ^(%CD%\raqib-robot.zip^)
  echo  On the Raspberry Pi:
  echo     unzip raqib-robot.zip -d ~/edge
  echo     cd ~/edge ^&^& bash scripts/install_pi.sh
) else (
  echo  Could not create the zip - see the message above.
)
echo.
pause
