#!/usr/bin/env bash
# One-time setup of the Raspberry Pi 4 (Raspberry Pi OS 64-bit, Bookworm or Trixie).
# Run from the edge/ folder:   bash scripts/install_pi.sh
#
# After this the robot starts by itself at every power-on, finds the PC running start_backend.bat on the
# same Wi-Fi (no IP address to type), and shows up in the app. Safe to run again.
set -uo pipefail
cd "$(dirname "$0")/.."
EDGE_DIR="$(pwd)"
WARN=()

step() { echo; echo "==> $*"; }
apt_try() { for p in "$@"; do sudo apt-get install -y "$p" >/dev/null 2>&1 && echo "   ok  $p" || { echo "   --  $p (not available, skipped)"; WARN+=("apt package $p"); }; done; }

step "System packages (a few minutes)"
sudo apt-get update -y >/dev/null || WARN+=("apt update")
# required
for p in python3-venv python3-pip python3-dev i2c-tools espeak-ng libportaudio2 git; do
  sudo apt-get install -y "$p" >/dev/null 2>&1 || { echo "   !! could not install $p"; WARN+=("apt package $p"); }
done
# best effort (names differ between Raspberry Pi OS versions)
apt_try python3-picamera2 python3-libcamera python3-lgpio python3-smbus2 pigpio python3-pigpio \
        libopus-dev libvpx-dev libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev

step "Enable I2C and the camera"
sudo raspi-config nonint do_i2c 0 2>/dev/null || WARN+=("enable I2C in raspi-config")
sudo raspi-config nonint do_camera 0 2>/dev/null || true
if systemctl list-unit-files 2>/dev/null | grep -q '^pigpiod'; then sudo systemctl enable --now pigpiod >/dev/null 2>&1 || true; fi
sudo usermod -aG i2c,gpio,video,audio "$USER" 2>/dev/null || true

step "Python environment (.venv, can take 10+ minutes the first time)"
[ -d .venv ] || python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt || WARN+=("core Python packages")
# Pi and video extras one by one, so one failing wheel does not stop the rest
for req in requirements-pi.txt requirements-video.txt; do
  grep -vE '^\s*(#|$)' "$req" | while read -r line; do
    .venv/bin/python -m pip install "$line" >/dev/null 2>&1 && echo "   ok  $line" || echo "   --  $line (skipped)"
  done
done

step "Robot settings (config.local.yaml)"
if [ ! -f config.local.yaml ]; then
cat > config.local.yaml <<'YAML'
# Settings for THIS Raspberry Pi (they override config.yaml)
simulation: false          # real hardware
mqtt:
  host: auto               # find the PC running start_backend.bat on the same Wi-Fi automatically
  port: 1883               # (or write the PC's IP address here instead of auto)
YAML
  echo "   created config.local.yaml (real hardware, server found automatically)"
else
  echo "   kept your existing config.local.yaml"
fi

step "Start the robot at every power-on"
sed "s#__EDGE_DIR__#${EDGE_DIR}#g; s#__USER__#${USER}#g" systemd/robot.service | sudo tee /etc/systemd/system/inspection-robot.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable inspection-robot >/dev/null 2>&1
sudo systemctl restart inspection-robot

step "Quick hardware check"
.venv/bin/python -m hwtest.i2c_scan 2>/dev/null || echo "   (I2C check needs a reboot the first time)"

echo
echo "================================================================"
echo " Done. The robot program is running and starts at every boot."
echo " 1. On the PC: double-click start_backend.bat (same Wi-Fi)."
echo " 2. In the app: Robot health shows each part. Missing one? Plug it"
echo "    in, then tap 'Re-check parts'."
echo " Live log:  journalctl -u inspection-robot -f"
if [ ${#WARN[@]} -gt 0 ]; then
  echo
  echo " Things that need a look (the robot still runs without them):"
  for w in "${WARN[@]}"; do echo "   - $w"; done
fi
echo " Reboot once now so I2C and group changes apply:  sudo reboot"
echo "================================================================"
