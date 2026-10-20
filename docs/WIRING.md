# Wiring guide (Raqib 3.0, the ESP32 robot, ≈ RM 232)

Every wire of the robot. The illustrated version (a picture of every part and a check after every step) is
`docs/Raqib_Robot_Build_Guide.pdf`; the one-page poster is `docs/Raqib_Full_Wiring_Diagram.pdf`. Pin names are the
XIAO's printed labels (D0…D10). They are fixed in the firmware (`esp32/raqib_esp32/raqib_esp32.ino`), in the
Wiring Bench and in `edge/robot/wiring_spec.py`.

**Try it first on the PC:** `start_robot_sim.bat`, then `http://localhost:8000/bench`. Place these wires on the
virtual XIAO and the simulated robot behaves exactly as that wiring would.

## The golden rule: the XIAO is a 3.3 V board

Never connect the motor battery, or any 5 V signal, to a XIAO pin. Use the **HC-SR04P** (3.3 V version), not the
plain HC-SR04 (5 V). Everything on the breadboard runs from the XIAO's 3V3 pin.

## Power: two batteries, one shared ground

```
USB power bank ─── USB-C cable ───► XIAO USB-C                         (the XIAO + sensors only)

2 × 18650 (7.4 V, holder with switch) ──► DRV8833 VM (+) and GND (−)    (the motors only)

DRV8833 GND ──────────────────────────► breadboard − rail (= XIAO GND)  SHARED GROUND (essential)
```

- Without the shared ground the DRV8833 cannot read the XIAO's signals: the wheels do nothing or twitch.
- The DRV8833 allows up to 10.8 V: 2 cells (8.4 V full) is right, never 3.
- The firmware limits motor power to 70 % (`esp32_max_duty`) because TT motors are 3–6 V motors.
- No battery % in the app: the power bank shows its charge with its own LEDs.

## Rails

| From | To |
|---|---|
| XIAO 3V3 | breadboard + rail (top) |
| XIAO GND | breadboard − rail (top) |
| top + rail | bottom + rail (short wire) |
| top − rail | bottom − rail (short wire) |

## Motors: DRV8833

| XIAO | DRV8833 | Also |
|---|---|---|
| D0 | AIN1 | left motor |
| D1 | AIN2 | left motor |
| D2 | BIN1 | right motor |
| D3 | BIN2 | right motor |
| — | EEP (or SLP / STBY, if your board has it) | to the + rail (3V3), or the driver stays asleep |
| — | AOUT1, AOUT2 | left TT motor (two wires) |
| — | BOUT1, BOUT2 | right TT motor (two wires) |

A wheel turns the wrong way? Swap that motor's two wires, or set `invert: true` for it in
`edge/config.yaml → hardware: motor_left / motor_right` (the PC sends it to the robot). Left and right swapped? Swap the D0/D1 pair with the D2/D3 pair.

## Sensors (I²C bus on D4 = SDA, D5 = SCL)

| Part | VCC | GND | SDA | SCL | Address |
|---|---|---|---|---|---|
| MPU6050 (GY-521) | + rail | − rail | D4 | D5 | 0x68 |
| AHT20 + BMP280 | + rail | − rail | D4 | D5 | 0x38 and 0x77 (or 0x76) |

Both share the same two wires: put SDA and SCL on two breadboard columns and plug both boards' SDA / SCL into them.
Keep the AHT20 away from the XIAO and the power bank (they are warm). The MPU6050 should lie flat near the centre;
keep the robot still for 2 s after switching on (it learns its gyro offset).

## Distance sensor: HC-SR04P (3.3 V)

| HC-SR04P | Goes to |
|---|---|
| VCC | + rail (3V3) |
| Trig | D6 |
| Echo | D7 |
| Gnd | − rail |

Mount it at the front edge, looking straight ahead, below the camera. No voltage divider is needed with the P version.

## Camera and microphone

Both are on the XIAO's Sense board: no wires. Press the Sense board on and click the camera ribbon in **before**
plugging the USB in. Stand the XIAO upright on a small bracket at the front, USB-C up, camera looking forward.

## Wire count

About 22 short jumper wires: XIAO → breadboard 10 (D0–D7, 3V3, GND), rail joiners 2, DRV8833 GND → − rail 1,
EEP 1, sensor power 6, the second sensor's SDA / SCL 2. Plus the battery's two leads, the motors' four wires and
the USB-C cable. (The Wiring Bench counts 25 connections because it also counts the USB cable, the motors and the
camera ribbon.)

## Upgrades later

| Want | Add | Notes |
|---|---|---|
| Longer patrols | bigger power bank (10,000 mAh → 20,000 mAh) | the motor pack lasts longer than the bank |
| Better grip on carpet | 4WD chassis (two motors per DRV8833 channel) | same wiring, motors in parallel |
| Spoken warnings from the robot | a Raspberry Pi build (`hardware.board: pi`) | the phone speaks for the ESP32 robot |
