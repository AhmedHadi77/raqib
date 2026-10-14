# Wiring guide (budget robot, under RM 500)

All GPIO numbers are **BCM** numbers, the same as in `edge/config.yaml → hardware:`. If you wire something
differently, change the number in the config. The code does not need to change. The illustrated version with
pictures of every part is `docs/Raqib_Robot_Build_Guide.pdf`.

## Power (most important: do this first)

```
2x 18650 (7.4 V, holder with switch) ──┬──► L298N +12V / GND                (motors)
                                       ├──► 1000 µF ─► XL4015 IN+ / IN-  ─► OUT 5.1 V ─► cut USB cable ─► Pi USB-C
                                       └──► 10 kΩ ─┬─ 4.7 kΩ ─ GND         (battery level)
                                                   └──► ADS1115 A1
```

- **Set the XL4015 to 5.1 V with a multimeter before the Pi is plugged in.** Straight from the box it may give 12 V.
- All grounds are joined through the battery − wire; also run L298N GND → Pi pin 9 (signal ground).
- Never power the motors from the Pi's 5 V pin.

## I²C bus (Pi pins 3 = SDA, 5 = SCL, 3.3 V)

| Device | Address | Notes |
|---|---|---|
| MPU6050 IMU | 0x68 | mount flat, near the centre of the chassis |
| AHT20 + BMP280 combo | 0x38 + 0x77 (or 0x76) | temperature, humidity, pressure; away from the Pi CPU and the MQ-135 |
| ADS1115 ADC | 0x48 | A0 = MQ-135, A1 = battery divider; ADDR → GND |

Check everything with `python -m hwtest.i2c_scan`.

## Motors: L298N, speed from the Pi

| L298N pin | Connect to |
|---|---|
| ENA (remove jumper) | GPIO **13** (pin 33), PWM |
| IN1 / IN2 | GPIO **17** / **27** (pins 11 / 13), left motor |
| ENB (remove jumper) | GPIO **19** (pin 35), PWM |
| IN3 / IN4 | GPIO **22** / **23** (pins 15 / 16), right motor |
| OUT1/OUT2 | left TT motor |
| OUT3/OUT4 | right TT motor |
| +12V / GND | battery + / −; GND also to Pi pin 9 |

If a side spins backwards, set `invert: true` for that motor in the config. `motor_pwm: auto` uses these GPIO pins
when no PCA9685 is found.

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

VCC goes to 5 V and GND to GND. Run the pigpio daemon (`sudo systemctl enable --now pigpiod`) for accurate timing.

## Wheel encoders (photoelectric)

| Encoder | OUT pin | Power |
|---|---|---|
| Left | GPIO 5 | 3.3 V (if your module needs 5 V, add a divider on OUT) |
| Right | GPIO 6 | 3.3 V |

Set `motion.encoder_ticks_per_rev` to the number of slots on your encoder disc (usually 20).

## MQ-135 gas sensor → ADS1115

The MQ-135 heater needs **5 V** and its AOUT goes up to 5 V, so use a divider before the ADS1115:

```
MQ-135 AOUT ──[ 10 kΩ ]──┬──► ADS1115 A0
                         [ 20 kΩ ]
                         │
                        GND          (gain 1.5 → config: mq135_divider_gain: 1.5)
ADS1115 VDD = 3.3 V, GND = GND, SDA/SCL = I²C bus, ADDR = GND (0x48)
```

The MQ-135 needs **24–48 h of burn-in** the first time, and ~2 min of warm-up at every power-on.
Calibrate R0 in clean outdoor air with `python -m hwtest.test_env --calibrate-mq135`.

## Camera, microphone, speaker

- **USB webcam with microphone:** any USB port. The robot uses it for photos, video and hearing (`arecord -l` lists its mic).
- **PAM8403 + speaker:** power it from 5 V (hub). Input from the Pi's own 3.5 mm audio jack: tip → L, sleeve → G.
  The robot picks the jack by itself (`speaker_device: auto`); test with `speaker-test -D plughw:CARD=Headphones -c1 -t wav -l1`.

## Pin summary

```
GPIO  5 enc L   | GPIO 12 US-L trig | GPIO 20 US-R trig | GPIO 24 US-C trig | GPIO 13 ENA (PWM)
GPIO  6 enc R   | GPIO 16 US-L echo | GPIO 21 US-R echo | GPIO 25 US-C echo | GPIO 19 ENB (PWM)
GPIO 17 IN1     | GPIO 27 IN2       | GPIO 22 IN3       | GPIO 23 IN4
GPIO  2/3 I2C SDA/SCL  (MPU6050 0x68, AHT20 0x38, BMP280 0x77, ADS1115 0x48)
```

## Upgrades (the software finds them by itself)

PCA9685 + 2 SG90 servos (ENA/ENB then on PCA9685 ch0/ch1, servos on ch14/ch15), Pi Camera (ribbon), BME680
(instead of the AHT20), UPS module (INA219 gauge at 0x42). See the last page of the build guide.
