# Raqib robot firmware (XIAO ESP32S3 Sense)

The robot's body. It drives the motors, reads the sensors, streams the camera and microphone, and keeps the robot
safe. The PC (the brain) runs everything else and talks to it over Wi-Fi.

| File | What it is |
|---|---|
| `raqib_esp32_xiao.bin` | Ready-to-flash firmware (bootloader + partitions + app), flash at address `0x0` |
| `raqib_esp32/raqib_esp32.ino` | The source (Arduino, ESP32 core 3.x) |
| `raqib_esp32/wifi_config.h` | Optional built-in Wi-Fi name and password (normally you set them from the robot's own page) |

## Flash it in the browser (easiest, nothing to install)

1. Plug the XIAO into the PC with a **data** USB-C cable (some cables only charge).
2. Open **https://espressif.github.io/esptool-js/** in **Chrome or Edge**.
3. Baud rate 921600 → **Connect** → pick the XIAO's port ("USB JTAG/serial debug unit").
4. Flash Address `0x0`, choose `raqib_esp32_xiao.bin` → **Program**. Wait for "Leaving...".
5. Unplug and replug the USB.

Not connecting? Hold the XIAO's **B** (boot) button while plugging the USB in, then try again.

## Or build it with the Arduino IDE

1. Boards Manager: install **esp32 by Espressif** (3.x).
2. Open `raqib_esp32/raqib_esp32.ino`. Board **XIAO_ESP32S3**, Tools → **PSRAM → OPI PSRAM**.
3. Upload.

## First start: put it on your Wi-Fi

1. The orange LED blinks slowly: the robot made its own Wi-Fi **Raqib-Robot** (password `raqib1234`).
2. Join it with your phone, open **http://192.168.4.1**, type your hotspot's name and password, **Save**.
3. The robot restarts and joins your hotspot (LED blinks fast while joining, then stays on).
4. On the PC (same hotspot): **http://raqib.local** shows the test page with the camera and every sensor.

If it cannot join within 20 s it makes its own Wi-Fi again, so you can always fix the settings.

LED: **steady** = on your Wi-Fi · **slow blink** = its own Wi-Fi · **fast blink** = joining ·
**short flicker off every 1.5 s** = a part is missing (see the test page).

## What it offers (the PC program uses these)

| Address | Does |
|---|---|
| `http://raqib.local/` | Test page: camera, sensors, Wi-Fi settings |
| `/status` | JSON: distance, gyro, temperature, humidity, pressure, motors, Wi-Fi strength, which parts answer |
| `/drive?l=0.5&r=0.5` | Motor power −1…1 (must be repeated: stops by itself after 0.6 s) |
| `/stop` | Stop now |
| `/turn?deg=90&power=0.5` | Turn by the gyro, on the robot itself (accurate even on slow Wi-Fi) |
| `/config?stop_cm=15&max_duty=0.7` | Safety and motor settings (also `ramp`, `deadman_ms`, `inv_l`, `inv_r`, `min_power`) |
| `/capture` | One JPEG photo |
| `:81/stream` | Live MJPEG video |
| `:82/audio?ms=1000` | A WAV recording from the microphone |

It also announces itself as `raqib.local` and with a small Wi-Fi broadcast (UDP 37021), so the PC finds it by
itself. Run `allow_robot_connections.bat` on the PC once so Windows lets that broadcast in.

## Safety built into the robot

- **Dead-man stop:** the motors stop 0.6 s after the last command (Wi-Fi drop, PC crash, app closed).
- **Obstacle stop:** it refuses to drive forward when the distance sensor sees something closer than 15 cm, or
  does not answer. Turning and reversing are still allowed, so it can get itself out.
- **Soft start** and a 70 % power limit (2 × 18650 = 8.4 V, TT motors are 3–6 V motors).

## Pins

| XIAO | Goes to |
|---|---|
| D0, D1 | DRV8833 AIN1, AIN2 (left motor) |
| D2, D3 | DRV8833 BIN1, BIN2 (right motor) |
| D4, D5 | SDA, SCL: MPU6050 (0x68) and AHT20 (0x38) + BMP280 (0x77/0x76) |
| D6, D7 | HC-SR04P TRIG, ECHO |
| 3V3, GND | breadboard + and − rails |
| USB-C | power bank |

Camera and microphone are on the Sense board (no wires).
