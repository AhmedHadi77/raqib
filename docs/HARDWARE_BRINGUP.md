# Hardware bring-up: from boxes of parts to a working robot

> The full illustrated build guide (shopping list, power and wiring sketches, assembly) is the
> "Raqib robot build guide" document. When the real robot is running, start the PC with
> `start_backend.bat` (not `start_all.bat`, which also starts the simulated robot01), and set a
> vision AI provider in `backend/.env` so photos are analysed.

Do these steps **in order**. Each one checks one subsystem before you depend on it.
Run the commands on the Raspberry Pi, inside `edge/` with the venv active (`source .venv/bin/activate`).

## 0. Prepare the Pi (≈ 30 min, once)

1. Flash **Raspberry Pi OS (64-bit)** with Raspberry Pi Imager. In the imager's settings, set the hostname (`robot01`), enable SSH, and enter **the same Wi-Fi your PC uses**.
2. On the PC, double-click `pack_robot_for_pi.bat`. It makes `raqib-robot.zip`. Copy it to the Pi (USB stick, or WinSCP to `robot01.local`).
3. On the Pi: `unzip raqib-robot.zip -d ~/edge && cd ~/edge && bash scripts/install_pi.sh`
4. `sudo reboot`

That is all the setup. The installer sets the robot to **real hardware**, makes it **start at every power-on**, and sets
`mqtt: host: auto`: the robot listens for the PC's announcement on the Wi-Fi and connects by itself, so you never type an
IP address. On the PC run `allow_robot_connections.bat` once (Windows Firewall) and start `start_backend.bat`.

> While you run the tests below, stop the background robot program so the two don't fight over the pins:
> `sudo systemctl stop inspection-robot`. Start it again with `sudo systemctl start inspection-robot`.

## 1. I²C devices

```
python -m hwtest.i2c_scan
```

Every expected device should show `[OK ]`. If one is MISSING, check SDA/SCL, 3.3 V and the address
(BME680 boards can be at 0x77, so change `bme680_address`).

## 2. Motors, encoders, servos. **Wheels in the air!**

```
python -m hwtest.test_motors
```

- Each wheel should spin in the stated direction. If not, set `invert: true` for that side.
- Encoder ticks should increase for each wheel. If they stay at 0, check the encoder OUT pin.
- Servos sweep left/right/up/down. Adjust `min_us`/`max_us` if the range is wrong.

Then put the robot on the floor for **Milestone 2**:

```
python -m hwtest.test_motors --straight 5
```

Measure the sideways drift with a tape measure. The target is < 20 cm.
- Drifts consistently to one side → tune `heading_kp`.
- Distance is wrong → correct `wheel_diameter_m` / `encoder_ticks_per_rev` (odometry KPI ±5 %).
- Robot hesitates or won't turn → raise `min_power` (4WD skid-steer usually needs 0.35–0.45).

## 3. Ultrasonics + IMU + battery

```
python -m hwtest.test_sensors
```

- Move your hand in front of each sensor. The distance should follow. A constant 400 usually means a wiring fault or a missing echo divider.
- Rotate the robot by hand. Yaw should change by about ±90° for a quarter turn. Keep the robot still for the first 2 s while the gyro calibrates.

## 4. Environment sensor

```
python -m hwtest.test_env                     # live values + verdicts
python -m hwtest.test_env --burn-in           # 5 min in clean air -> gas_baseline_ohm
python -m hwtest.test_env --calibrate-mq135   # outdoors, after 24 h burn-in -> mq135_r0
```

Put the printed values into `config.yaml`. Check temperature and humidity against a reference
thermometer/hygrometer (KPI: classification > 85 %). If the BME680 reads high, it is picking up heat
from the Pi. Move it away or add a small duct.

## 5. Camera, microphone, speaker

```
python -m hwtest.test_camera_audio
```

Open `test_snapshot.jpg`, play `test_audio.wav`, and listen for the spoken test phrase.

## 6. Audio model (Edge Impulse)

Follow [EDGE_IMPULSE.md](EDGE_IMPULSE.md) to record the four classes and deploy `models/campus-audio.eim`.
Until then, the built-in heuristic classifier is used automatically.

## 7. Connect to the app

There is nothing to configure. With `start_backend.bat` running on the PC and the robot switched on (same Wi-Fi):

1. The robot finds the PC within a few seconds (`journalctl -u inspection-robot -f` shows "Found the Raqib server").
2. In the app, the sign-in screen finds the PC by itself (or tap **Find automatically**).
3. **More > Robot health** lists every part. A part you plug in later: tap **Re-check parts**.

If your network blocks broadcasts (some campus Wi-Fi), write the PC's address in `edge/config.local.yaml` on the Pi
instead of `auto` (`mqtt: host: 192.168.1.100`), then `sudo systemctl restart inspection-robot`.

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
- [ ] Turning off the PC's Wi-Fi stops the robot within ~10 s, and the state becomes SAFE_HOLD (T-09)
- [ ] The battery level is shown, and you have a charged spare set of 18650 cells
- [ ] `JWT_SECRET` and the default passwords in `backend/.env` have been changed
