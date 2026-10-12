# Wiring guide

All GPIO numbers are **BCM** numbers, the same as in `edge/config.yaml → hardware:`. If you wire something
differently, change the number in the config. The code does not need to change.

## Power (most important: do this first)

```
3x 18650 (11.1 V) ──┬──► L298N  +12V  (motors)      ← raw battery, motor noise stays here
                    └──► UPS hat ──► 5 V/3 A ──► Raspberry Pi 4 (+ sensors' 5 V/3.3 V from the Pi)
GND of battery, L298N, UPS hat and Pi MUST be connected together (common ground).
```

- Remove the L298N's **5 V regulator jumper** only if your battery is above 12 V.
- Never power the motors from the Pi's 5 V pin.

## I²C bus (Pi pins 3 = SDA, 5 = SCL, 3.3 V)

| Device | Address | Notes |
|---|---|---|
| PCA9685 PWM driver | 0x40 | VCC = 3.3 V logic. **V+ terminal = 5 V** (UPS 5 V rail or a 5 V BEC): it powers the servo headers |
| MPU6050 IMU | 0x68 | mount flat, near the centre of the chassis |
| BME680 | 0x76 (0x77 on some boards) | mount away from the Pi CPU and the motors (heat), with airflow |
| ADS1115 ADC | 0x48 | **new part**: the Pi has no analog inputs, so the MQ-135 needs this |
| UPS hat battery gauge (INA219) | 0x42 | depends on the hat; set `ups_ina219_address: null` if yours has none |

Check everything with `python -m hwtest.i2c_scan`.

## Motors: L298N + PCA9685

| L298N pin | Connect to |
|---|---|
| ENA (remove jumper) | PCA9685 channel **0** PWM |
| IN1 / IN2 | GPIO **17** / **27** (left motors) |
| ENB (remove jumper) | PCA9685 channel **1** PWM |
| IN3 / IN4 | GPIO **22** / **23** (right motors) |
| OUT1/OUT2 | left front + left rear motors in parallel |
| OUT3/OUT4 | right front + right rear motors in parallel |
| GND | battery GND **and** Pi GND |

If a side spins backwards, set `invert: true` for that motor in the config.

## Pan/tilt servos (SG90)

| Servo | PCA9685 channel | Power |
|---|---|---|
| Pan | 14 | from the PCA9685 V+ rail (5 V), **never** the Pi 3.3 V |
| Tilt | 15 | same |

Plug the servo cables straight into PCA9685 header columns 14 and 15 (signal / V+ / GND).

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

- **Pi Camera V2:** CSI ribbon (blue side facing the Ethernet port on a Pi 4).
- **USB microphone:** any USB port. Check it with `arecord -l`.
- **PAM8403 + speaker:** power it from 5 V. Take the input from a USB sound card, or from the Pi 3.5 mm jack if your Pi has one (L/R + GND).

## Pin summary

```
GPIO  5 enc L   | GPIO 12 US-L trig | GPIO 20 US-R trig | GPIO 24 US-C trig
GPIO  6 enc R   | GPIO 16 US-L echo | GPIO 21 US-R echo | GPIO 25 US-C echo
GPIO 17 IN1     | GPIO 27 IN2       | GPIO 22 IN3       | GPIO 23 IN4
GPIO  2/3 I2C SDA/SCL  (PCA9685 0x40, MPU6050 0x68, BME680 0x76, ADS1115 0x48, INA219 0x42)
```

## Updated bill of materials

Add to Table 2:

| Component | Qty | Unit (MYR) | Why |
|---|---|---|---|
| ADS1115 16-bit ADC | 1 | ~12.00 | MQ-135 analog output (the Pi has no ADC) |
| Resistors 1 kΩ / 2 kΩ / 10 kΩ / 20 kΩ | few | ~3.00 | HC-SR04 echo + MQ-135 voltage dividers |
