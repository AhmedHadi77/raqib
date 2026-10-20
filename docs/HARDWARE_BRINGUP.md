# Hardware bring-up: from a bag of parts to a working robot (ESP32 robot 3.0)

> The illustrated build guide (shopping list ≈ RM 232, a picture of every part, 11 steps each ending with a check)
> is `docs/Raqib_Robot_Build_Guide.pdf`; every wire is in [WIRING.md](WIRING.md). The robot is a XIAO ESP32S3
> Sense body; **your laptop is the brain** (server + AI + robot program). The phone app speaks and shows alerts.

Do these steps **in order**. Each one checks one part before you depend on it. The tests run **on the PC**, in a
command window inside the project's `edge` folder:

```
cd "C:\final year app\edge"
..\.venv\Scripts\python -m hwtest.i2c_scan
```

Close `start_my_robot.bat` (or `start_robot_esp32.bat`) while you run a test, so the two don't both drive the robot.

## 0. Flash the firmware and join Wi-Fi (≈ 15 min, once)

1. Flash `esp32/raqib_esp32_xiao.bin` from Chrome or Edge: https://espressif.github.io/esptool-js/ → Connect →
   address `0x0` → Program ([esp32/README.md](../esp32/README.md) has the details and the Arduino IDE way).
2. The LED blinks slowly: join the robot's Wi-Fi **Raqib-Robot** (password `raqib1234`), open http://192.168.4.1,
   save your phone hotspot's name and password. The robot restarts and joins it (LED steady).
3. Put the PC on the same hotspot. Run `allow_robot_connections.bat` once (lets Windows accept the robot's broadcast).
4. Open **http://raqib.local** (or the address the robot's page showed). The test page shows the camera and every
   sensor live. Nothing wired yet? `imu`, `sonar`, `aht` show as missing: correct for now.

Robot not found by name? Use its IP address, and put it in `edge/config.yaml → hardware: esp32_host`.

## 1. I²C devices and the robot link

```
..\.venv\Scripts\python -m hwtest.i2c_scan
```

It finds the robot, then shows each part as `[OK ]` or `MISSING`: MPU6050 (0x68), AHT20 (0x38) and BMP280
(0x77/0x76), plus the distance sensor, camera and microphone. A missing I²C part: check SDA on D4, SCL on D5, VCC on
the + rail and GND on the − rail.

## 2. Motors. **Wheels in the air!**

```
..\.venv\Scripts\python -m hwtest.test_motors
```

- Each wheel should spin in the stated direction. A wheel backwards → swap that motor's two wires (or set
  `invert: true` for it under `hardware: motor_left / motor_right` in `edge/config.yaml`). Left and right swapped → swap the D0/D1 pair with D2/D3.
- Wheels do nothing or twitch → the shared ground (DRV8833 GND → breadboard − rail) is missing, the motor battery is
  off, or EEP is not on the + rail.
- Forward refused but backwards works → that is the safety stop: the distance sensor is not answering or sees
  something closer than 15 cm.

Then **calibrate the driving** (no encoders: distance comes from motor time; turns use the gyro on the robot):

```
..\.venv\Scripts\python -m hwtest.test_motors --deadband     # wheels in the air: answer y when both wheels turn
..\.venv\Scripts\python -m hwtest.test_motors --calibrate    # on the floor: drives 3 s, type the distance in cm
```

Write the printed `motor_deadband`, `min_power` and `max_speed_mps` into `edge/config.yaml`. Then, on the floor:

```
..\.venv\Scripts\python -m hwtest.test_motors --straight 2   # target 1.8-2.2 m, drift < 20 cm
```

- Drifts to one side → tune `heading_kp`. Distance wrong → charge the 18650s and run `--calibrate` again on this floor.
- Hesitates or won't turn → raise `min_power` (0.30–0.40 is usual for 2WD; more on carpet).

## 3. Distance sensor + gyro

```
..\.venv\Scripts\python -m hwtest.test_sensors
```

- Move your hand in front of the HC-SR04P. The distance should follow it (2–400 cm). Always 0 / missing → check
  TRIG on D6, ECHO on D7, VCC on 3V3, and that it is the **P** (3.3 V) version.
- Rotate the robot by hand: yaw changes about 90° for a quarter turn. Keep it still for 2 s after power-on (gyro offset).

## 4. Climate sensor

```
..\.venv\Scripts\python -m hwtest.test_env
```

Compare temperature and humidity with a reference thermometer. Reads high → the AHT20 is too close to the XIAO or
the power bank; move it to the far end of the breadboard. Gas reads "not measured": correct, there is no gas sensor.

## 5. Camera and microphone

```
..\.venv\Scripts\python -m hwtest.test_camera_audio
```

Open `test_snapshot.jpg` and play `test_audio.wav`. No camera → press the Sense board on firmly and re-seat the camera
ribbon (with the USB unplugged). The robot has no speaker: the test says so and skips it.

## 6. Connect to the app

1. Double-click **`start_my_robot.bat`**: it starts the server and the robot program, which finds the ESP32.
2. Phone on the same hotspot. In the app, sign in and tap **Find automatically** (default login admin / admin123).
3. **More > AI settings**: paste your Gemini key once (it is saved on the PC).
4. **More > Robot health** lists every part. *Speaker: the phone speaks*, *Battery level: not measured* and
   *Gas: not fitted* are correct for this robot. A part you plug in later: tap **Re-check parts**.

## 7. Map your real rooms

Drive the robot (Drive tab) from the Home spot to each room. Read the pose (x, y) on Home and write them into
`zones:` in `edge/config.yaml`, using the names the agent should understand (e.g. `IoT_Lab`, `Exam_Hall`).
Restart `start_my_robot.bat`. "Inspect the IoT lab" now drives there.

> Always start the robot at the **Home** position, facing the same direction. Dead reckoning has no global
> position fix, so it drifts over long distances (a scope limitation in section 1.6).
> *Settings → Set current position as Home* re-zeros it.

## 8. Audio model (optional, Edge Impulse)

Follow [EDGE_IMPULSE.md](EDGE_IMPULSE.md) to record the classes and deploy `models/campus-audio.eim`. Until then the
built-in classifier is used automatically.

## 9. Safety checklist before any demo

- [ ] The STOP button in the app stops the robot (and **RESET E-STOP** is needed to move again)
- [ ] A hand placed 30 cm in front of a driving robot stops it before 15 cm (T-01)
- [ ] Closing the robot program's window stops the wheels within 0.6 s (the ESP32's dead-man stop)
- [ ] The power bank is full (all LEDs), the 18650s are charged, and you have a charged spare pair
- [ ] Driving calibrated on this floor: `--straight 2` ends within 1.8–2.2 m
- [ ] `JWT_SECRET` and the default passwords in `backend/.env` have been changed

The older Raspberry Pi build (robot program on the Pi) still works with `hardware.board: pi`; its instructions are in
the git history of this file (version 2.5).
