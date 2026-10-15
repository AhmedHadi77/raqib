# Hardware bring-up: from boxes of parts to a working robot

> The full illustrated build guide (shopping list under RM 500, power and wiring diagrams, assembly) is
> `docs/Raqib_Robot_Build_Guide.pdf`. Budget build: motor speed on GPIO 13/19 (pins 33/35) instead of a PCA9685,
> no servos, AHT20 + BMP280, battery voltage on ADS1115 A1, USB webcam, speaker amp on the Pi audio jack. When the real robot is running, start the PC with
> `start_backend.bat` (not `start_all.bat`, which also starts the simulated robot01), and set a
> vision AI provider in `backend/.env` so photos are analysed.

Do these steps **in order**. Each one checks one subsystem before you depend on it.
Run the commands on the Raspberry Pi, inside `edge/` with the venv active (`source .venv/bin/activate`).

## 0. Prepare the Pi (≈ 30 min, once)

The finished robot needs **no laptop**: the Raspberry Pi runs the robot program *and* its own server, and the phone
app talks straight to the robot.

1. Flash **Raspberry Pi OS (64-bit)** with Raspberry Pi Imager. In the imager's settings set the hostname (`robot01`),
   enable SSH, and add a Wi-Fi: your **phone's hotspot** is the best choice (the robot then has internet for the AI
   wherever you go). Home or campus Wi-Fi works too.
2. On the PC, double-click `pack_robot_for_pi.bat`. It makes `raqib-robot.zip` (robot program + server; your AI key is
   not included). Copy it to the Pi (USB stick, or WinSCP to `robot01.local`).
3. On the Pi: `unzip raqib-robot.zip -d ~/raqib && cd ~/raqib && bash edge/scripts/install_pi.sh`
4. `sudo reboot`

From then on, at every power-on the robot starts its server and program by itself and says its address out loud.
Wi-Fi: it joins a known network; if none is in range for a minute it makes its **own Wi-Fi "Raqib-Robot"**
(password `raqib1234`, robot address 10.42.0.1). Either way, open the app and tap **Find automatically**.
Add another network later: `sudo nmcli dev wifi connect "NAME" password "PASSWORD"`.

> While you run the tests below, stop the background robot program so the two don't fight over the pins:
> `sudo systemctl stop inspection-robot`. Start it again with `sudo systemctl start inspection-robot`.

## 1. I²C devices

```
python -m hwtest.i2c_scan
```

Every expected device should show `[OK ]`: MPU6050 0x68, ADS1115 0x48 and the AHT20 0x38 + BMP280 0x77/0x76.
If one is MISSING, check SDA/SCL, 3.3 V and the address. It also tells you that motor speed comes from GPIO 13/19
(no PCA9685 on the budget robot).

## 2. Motors and encoders. **Wheels in the air!**

```
python -m hwtest.test_motors
```

- Each wheel should spin in the stated direction. If not, set `invert: true` for that side.
- Encoder ticks should increase for each wheel. If they stay at 0, check the encoder OUT pin.
- The budget robot has no servos (fixed camera), so the servo part is skipped. With the PCA9685 upgrade the servos
  sweep left/right/up/down; adjust `min_us`/`max_us` if the range is wrong.

Then put the robot on the floor for **Milestone 2**:

```
python -m hwtest.test_motors --straight 5
```

Measure the sideways drift with a tape measure. The target is < 20 cm.
- Drifts consistently to one side → tune `heading_kp`.
- Distance is wrong → correct `wheel_diameter_m` / `encoder_ticks_per_rev` (odometry KPI ±5 %).
- Robot hesitates or won't turn → raise `min_power` (4WD skid steering usually needs 0.35–0.45; raise `turn_speed` to 0.6 on carpet).

## 3. Ultrasonics + IMU + battery

```
python -m hwtest.test_sensors
```

- Move your hand in front of each sensor. The distance should follow. A constant 400 usually means a wiring fault or a missing echo divider.
- Rotate the robot by hand. Yaw should change by about ±90° for a quarter turn. Keep the robot still for the first 2 s while the gyro calibrates.

## 4. Environment sensor

```
python -m hwtest.test_env                     # live values + verdicts
python -m hwtest.test_env --calibrate-mq135   # outdoors, after 24 h burn-in -> mq135_r0
```

Put the printed values into `config.yaml`. Check temperature and humidity against a reference
thermometer/hygrometer (KPI: classification > 85 %). If the AHT20 reads high, it is picking up heat
from the Pi or the MQ-135. Move it away or add a small duct. (With the BME680 upgrade, also run
`python -m hwtest.test_env --burn-in` for its VOC baseline.)

## 5. Camera, microphone, speaker

```
python -m hwtest.test_camera_audio
```

Open `test_snapshot.jpg` (from the USB webcam), play `test_audio.wav` (the webcam's microphone), and listen for the
spoken test phrase (PAM8403 on the Pi's audio jack; quick check: `speaker-test -D plughw:CARD=Headphones -c1 -t wav -l1`).

## 6. Audio model (Edge Impulse)

Follow [EDGE_IMPULSE.md](EDGE_IMPULSE.md) to record the four classes and deploy `models/campus-audio.eim`.
Until then, the built-in heuristic classifier is used automatically.

## 7. Connect to the app

There is nothing to configure. Switch the robot on, wait about a minute (it says "Raqib is ready" and its address):

1. Put the phone on the same Wi-Fi as the robot: the phone's own hotspot, the same home/campus Wi-Fi, or the
   robot's Wi-Fi "Raqib-Robot".
2. In the app, sign in (it finds the robot by itself, or tap **Find automatically**). Default login: admin / admin123.
3. **More > AI settings**: paste your Gemini key once; it is saved on the robot.
4. **More > Robot health** lists every part. A part you plug in later: tap **Re-check parts**.

Logs on the Pi: `journalctl -u raqib-server -f` (server) and `journalctl -u inspection-robot -f` (robot program).
Prefer the old setup with the server on a PC? Delete `~/raqib/backend` before running the installer: the robot then
looks for `start_backend.bat` on the Wi-Fi instead.

## 8. Map your real rooms

Drive the robot (Dashboard → Manual drive) from the Home spot to each room. Read the pose (x, y) on the
Dashboard and write them into `zones:` in `config.yaml`, using the same names the agent should understand
(e.g. `IoT_Lab`, `LectureHall_B`). Restart the robot service. "Inspect the IoT lab" now drives there.

> Always start the robot at the **Home** position, facing the same direction. Dead reckoning has no global
> position fix, so it drifts over long distances (this is a scope limitation in section 1.6).
> *Settings → Set current position as Home* re-zeros it.

## 9. Safety checklist before any demo

- [ ] The STOP button in the app stops the robot (and **RESET E-STOP** is required to move again)
- [ ] A hand placed 30 cm in front of a driving robot stops it before 15 cm (T-01)
- [ ] Stopping the server (`sudo systemctl stop raqib-server`) stops the robot within ~10 s, and the state becomes SAFE_HOLD (T-09)
- [ ] The battery level is shown, and you have a charged spare set of 18650 cells
- [ ] `JWT_SECRET` and the default passwords in `backend/.env` have been changed
