# Wiring guide (reliable budget robot 2.5, ≈ RM 495)

All GPIO numbers are **BCM** numbers, the same as in `edge/config.yaml → hardware:`. If you wire something
differently, change the number in the config. The code does not need to change. The illustrated version with
pictures of every part is `docs/Raqib_Robot_Build_Guide.pdf`.

This build leaves out the parts that most often cause trouble in a first robot: the hand-adjusted 5 V converter,
wheel encoders, the MQ-135 gas sensor and its ADS1115. They can be added later (see *Upgrades* at the end).

## Power (most important: do this first)

Two separate batteries. Motor starts can never make the Pi restart.

```
USB power bank 10,000 mAh, 5 V 3 A ── its own USB-C cable ──► Pi USB-C          (the Pi only)

2x 18650 (7.4 V, holder with switch) ──► L298N +12V / GND                       (the motors only)

L298N GND ──────────────────────────────► Pi pin 9 (GND)                        COMMON GROUND (essential)
```

- **The common ground wire is essential.** Without it the L298N cannot read the Pi's signals: the wheels do nothing or twitch.
- Never connect the motor battery's + to the Pi or the hub board, and never power the motors from the Pi's 5 V pin.
- The power bank must say **5 V 3 A** (15 W or more). Its LEDs show its charge; the app shows "Power bank" instead of a battery %.
- Config: `battery_monitor: none`.

## I²C bus (Pi pins 3 = SDA, 5 = SCL, 3.3 V)

| Device | Address | Notes |
|---|---|---|
| MPU6050 IMU | 0x68 | mount flat, near the centre of the chassis (cheap clones work too) |
| AHT20 + BMP280 combo | 0x38 + 0x77 (or 0x76) | temperature, humidity, pressure; away from the Pi CPU |

Check everything with `python -m hwtest.i2c_scan`.

## Motors: L298N, speed from the Pi

| L298N pin | Connect to |
|---|---|
| ENA (remove jumper) | GPIO **13** (pin 33), PWM |
| IN1 / IN2 | GPIO **17** / **27** (pins 11 / 13), left motor |
| ENB (remove jumper) | GPIO **19** (pin 35), PWM |
| IN3 / IN4 | GPIO **22** / **23** (pins 15 / 16), right motor |
| OUT1/OUT2 | left front + left rear motor, joined (red-red, black-black) |
| OUT3/OUT4 | right front + right rear motor, joined |
| +12V / GND | motor battery + / −; **GND also to Pi pin 9** |

If a side spins backwards, set `invert: true` for that motor in the config. `motor_pwm: auto` uses these GPIO pins
when no PCA9685 is found. The software ramps the power up gently (`motor_ramp_per_s: 4.0`, full power in 0.25 s);
stopping is always immediate.

## Distance without encoders: calibrate once

`encoders: false` and `motion.odometry: auto`: distance = calibrated speed × motor power × time, turns from the MPU6050.

```
python -m hwtest.test_motors --deadband     # wheels in the air -> motor_deadband and min_power
python -m hwtest.test_motors --calibrate    # on the floor, measure with a tape -> max_speed_mps
python -m hwtest.test_motors --straight 2   # check: 1.8-2.2 m
```

Calibrate on the floor the robot will use, with charged motor cells.

## Camera: fixed USB webcam

There are no servos. The webcam is fixed on the front of the top deck; to look left or right the robot turns its
whole body, and turns back before it drives on (`pan_tilt: auto`).

## HC-SR04 ultrasonic sensors (5 V parts!)

The **ECHO pin outputs 5 V**, and the Pi's GPIO pins accept a maximum of 3.3 V. Put a divider on every ECHO line:

```
ECHO ──[ 1 kΩ ]──┬──► GPIO (echo)
                 [ 2 kΩ ]
                 │
                GND
```

| Sensor | TRIG | ECHO (through divider) | Mounting |
|---|---|---|---|
| Left | GPIO 12 | GPIO 16 | front-left, pointing 45° left |
| Center | GPIO 24 | GPIO 25 | front, straight ahead |
| Right | GPIO 20 | GPIO 21 | front-right, pointing 45° right |

VCC goes to 5 V and GND to GND. The sensors are pinged one at a time with a quiet gap
(`ultrasonic_gap_s: 0.012`), so they never hear each other's echoes. Run the pigpio daemon
(`sudo systemctl enable --now pigpiod`) for the most accurate timing. Buy one spare sensor.

## Camera, microphone, speaker

- **USB webcam with microphone:** any USB port. The robot uses it for photos, video and hearing (`arecord -l` lists its mic).
- **PAM8403 + speaker:** power it from 5 V (hub). Input from the Pi's own 3.5 mm audio jack: tip → L, sleeve → G.
  The robot picks the jack by itself (`speaker_device: auto`); test with `speaker-test -D plughw:CARD=Headphones -c1 -t wav -l1`.

## Pin summary

```
pin  9 GND -> L298N GND (common ground)
GPIO 12 US-L trig | GPIO 20 US-R trig | GPIO 24 US-C trig | GPIO 13 ENA (PWM)
GPIO 16 US-L echo | GPIO 21 US-R echo | GPIO 25 US-C echo | GPIO 19 ENB (PWM)
GPIO 17 IN1       | GPIO 27 IN2       | GPIO 22 IN3       | GPIO 23 IN4
GPIO  2/3 I2C SDA/SCL  (MPU6050 0x68, AHT20 0x38, BMP280 0x77)
```

## Upgrades (the software finds them, or one config line)

- **Gas / CO2:** MQ-135 + ADS1115 (0x48, ADDR → GND). MQ-135 AOUT → 10 kΩ / 20 kΩ divider → ADS1115 A0
  (`mq135_divider_gain: 1.5`); set `gas_sensor: mq135`. Burn it in for 24-48 h, then
  `python -m hwtest.test_env --calibrate-mq135` outdoors.
- **Wheel encoders:** LM393 slot sensors on GPIO 5 / 6 (pins 29 / 31), VCC 3.3 V, 20-slot discs on the front motors;
  set `encoders: true` and `encoder_ticks_per_rev`.
- PCA9685 + 2 SG90 servos (ENA/ENB then on PCA9685 ch0/ch1, servos on ch14/ch15), Pi Camera (ribbon), BME680
  (instead of the AHT20), UPS module (INA219 gauge at 0x42, then `battery_monitor: auto`). See the last page of the build guide.
