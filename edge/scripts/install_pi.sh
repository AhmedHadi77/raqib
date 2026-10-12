#!/usr/bin/env bash
# One-time setup of the Raspberry Pi 4 (Raspberry Pi OS 64-bit, Bookworm or Trixie).
# Run from the edge/ folder:   bash scripts/install_pi.sh
#
# After this the robot is a complete product on its own: at every power-on it starts its own server (the app
# talks straight to the robot - no laptop), joins a known Wi-Fi or makes its own Wi-Fi "Raqib-Robot", and the
# phone app finds it automatically. Safe to run again.
set -uo pipefail
cd "$(dirname "$0")/.."
EDGE_DIR="$(pwd)"
BACKEND_DIR="$(cd .. && pwd)/backend"
ONBOARD=0; [ -f "$BACKEND_DIR/app/main.py" ] && ONBOARD=1
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

if [ "$ONBOARD" = 1 ]; then
  step "Robot server (the app talks straight to the robot)"
  .venv/bin/python -m pip install -r "$BACKEND_DIR/requirements.txt" || WARN+=("server Python packages")
  for extra in "langchain-google-genai>=2.0" "langchain-openai>=0.3"; do
    .venv/bin/python -m pip install "$extra" >/dev/null 2>&1 && echo "   ok  $extra (AI)" || echo "   --  $extra (skipped)"
  done
  .venv/bin/python -m pip install "faster-whisper>=1.0" >/dev/null 2>&1 && echo "   ok  voice recognition" || echo "   --  voice recognition (skipped)"
  if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    SECRET=$(head -c 24 /dev/urandom | base64 | tr -d '/+=')
    sed -i "s/^JWT_SECRET=.*/JWT_SECRET=${SECRET}/; s/^EMBEDDED_BROKER=.*/EMBEDDED_BROKER=true/; s/^MQTT_HOST=.*/MQTT_HOST=localhost/; s/^WHISPER_MODEL=.*/WHISPER_MODEL=tiny.en/; s/^EMBEDDING_BACKEND=.*/EMBEDDING_BACKEND=hash/" "$BACKEND_DIR/.env"
    grep -q '^SITE_NAME=' "$BACKEND_DIR/.env" && sed -i "s/^SITE_NAME=.*/SITE_NAME=Raqib robot/" "$BACKEND_DIR/.env"
    echo "   created backend/.env (set the AI key later in the app: More > AI settings)"
  else
    echo "   kept your existing backend/.env"
  fi
  sed "s#__EDGE_DIR__#${EDGE_DIR}#g; s#__BACKEND_DIR__#${BACKEND_DIR}#g; s#__USER__#${USER}#g" systemd/raqib-server.service | sudo tee /etc/systemd/system/raqib-server.service >/dev/null
fi

step "Robot settings (config.local.yaml)"
if [ ! -f config.local.yaml ]; then
if [ "$ONBOARD" = 1 ]; then HOSTLINE="  host: localhost          # the server runs on this robot"; else
  HOSTLINE="  host: auto               # find the PC running start_backend.bat on the same Wi-Fi automatically"; fi
cat > config.local.yaml <<YAML
# Settings for THIS Raspberry Pi (they override config.yaml)
simulation: false          # real hardware
mqtt:
${HOSTLINE}
  port: 1883
YAML
  echo "   created config.local.yaml (real hardware)"
else
  echo "   kept your existing config.local.yaml"
fi

step "Start the robot at every power-on"
sed "s#__EDGE_DIR__#${EDGE_DIR}#g; s#__USER__#${USER}#g" systemd/robot.service | sudo tee /etc/systemd/system/inspection-robot.service >/dev/null
sed "s#__EDGE_DIR__#${EDGE_DIR}#g" systemd/raqib-wifi.service | sudo tee /etc/systemd/system/raqib-wifi.service >/dev/null
sudo systemctl daemon-reload
if [ "$ONBOARD" = 1 ]; then sudo systemctl enable raqib-server >/dev/null 2>&1; sudo systemctl restart raqib-server; fi
sudo systemctl enable inspection-robot raqib-wifi >/dev/null 2>&1
sudo systemctl restart inspection-robot raqib-wifi

step "Quick hardware check"
.venv/bin/python -m hwtest.i2c_scan 2>/dev/null || echo "   (I2C check needs a reboot the first time)"

echo
echo "================================================================"
echo " Done. The robot starts by itself at every power-on."
if [ "$ONBOARD" = 1 ]; then
echo " No laptop needed: open the app and tap 'Find automatically'."
echo "  - Phone and robot on the same Wi-Fi (or the phone's hotspot), or"
echo "  - away from known Wi-Fi the robot makes its own Wi-Fi: Raqib-Robot"
echo "    (password raqib1234). Join it with the phone, then open the app."
echo " Add your phone's hotspot so the robot has internet for the AI:"
echo "    sudo nmcli dev wifi connect \"HOTSPOT-NAME\" password \"HOTSPOT-PASSWORD\""
else
echo " On the PC: double-click start_backend.bat (same Wi-Fi)."
fi
echo " In the app, Robot health shows each part. Plugged one in later? Tap 'Re-check parts'."
echo " Logs:  journalctl -u inspection-robot -f      journalctl -u raqib-server -f"
if [ ${#WARN[@]} -gt 0 ]; then
  echo
  echo " Things that need a look (the robot still runs without them):"
  for w in "${WARN[@]}"; do echo "   - $w"; done
fi
echo " Reboot once now so I2C and group changes apply:  sudo reboot"
echo "================================================================"
