"""The ESP32 robot's wiring: every part, every pin and where it must go (same as docs/WIRING.md and the firmware).

Used by the virtual wiring harness (hal/harness.py), which makes the simulated robot behave like a real
one wired the way you wired it on the Wiring Bench, and served to the bench page by the backend.
Run this file to write wiring_spec.json next to it.
"""
from __future__ import annotations

import json
from pathlib import Path

# XIAO ESP32S3 pins as the bench draws them: odd numbers = left column (D0..D6), even = right column
# (5V, GND, 3V3, D10..D7), USB-C at the top.   pin -> (label, class)   classes: p5 p33 gnd sda scl gpio
HEADER = {
    1: ("D0 · GPIO1", "gpio"), 2: ("5V", "p5"),
    3: ("D1 · GPIO2", "gpio"), 4: ("GND", "gnd"),
    5: ("D2 · GPIO3", "gpio"), 6: ("3V3", "p33"),
    7: ("D3 · GPIO4", "gpio"), 8: ("D10 · GPIO9", "gpio"),
    9: ("D4 · SDA", "sda"), 10: ("D9 · GPIO8", "gpio"),
    11: ("D5 · SCL", "scl"), 12: ("D8 · GPIO7", "gpio"),
    13: ("D6 · TX", "gpio"), 14: ("D7 · RX", "gpio"),
}
BOARD = {"title": "XIAO ESP32S3 Sense", "note": "seen from above, USB-C at the top", "name": "XIAO"}
D = {f"D{i}": n for n, (lab, _) in HEADER.items() for i in range(11) if lab.startswith(f"D{i} ")}

EXT = [
    {"group": "Motor battery 2x18650 (7.4 V)", "items": [["bat+", "Battery +"], ["bat-", "Battery -"]]},
    {"group": "DRV8833 outputs", "items": [["aout", "AOUT1 + AOUT2"], ["bout", "BOUT1 + BOUT2"]]},
    {"group": "XIAO connectors", "items": [["usbc", "USB-C power input"], ["b2b", "Sense board connector"],
                                           ["camsock", "Camera socket (on the Sense board)"]]},
]

P5, P33, GND = {"cls": "p5"}, {"cls": "p33"}, {"cls": "gnd"}
SDA, SCL = {"pin": D["D4"]}, {"pin": D["D5"]}


PARTS = [
    {"id": "pbank", "name": "USB power bank (ESP32 only)", "sub": "5,000-10,000 mAh: powers the XIAO, its camera and the sensors",
     "health": "power", "webots": "Battery model", "modelled": True, "config": "battery_monitor: none",
     "test": "the orange LED blinks, then stays on when the robot is on Wi-Fi", "app": "The robot appears in the app",
     "pins": [
         {"id": "usb", "label": "USB-C cable", "spec": {"ext": "usbc"},
          "why": "A USB-C cable from the power bank into the XIAO. The motors have their own battery, "
                 "so motor starts can never restart the ESP32."},
     ]},
    {"id": "drv", "name": "DRV8833 motor driver", "sub": "Turns the ESP32's signals into motor power", "health": "motors",
     "webots": "left wheel motor, right wheel motor", "modelled": False,
     "config": "firmware: AIN1/AIN2 = D0/D1 (left), BIN1/BIN2 = D2/D3 (right)",
     "test": "hwtest.test_motors, or the arrows on http://raqib.local", "app": "Drive tab arrows move the robot",
     "pins": [
         {"id": "vm", "label": "VM", "spec": {"ext": "bat+"}, "why": "Motor power comes from the motor battery only, never from the XIAO."},
         {"id": "gndbat", "label": "GND (battery)", "spec": {"ext": "bat-"}, "why": "Motor battery ground for the motor current."},
         {"id": "gndx", "label": "GND (to XIAO)", "spec": GND,
          "why": "Common ground with the XIAO (the breadboard's GND rail). ESSENTIAL with two batteries: without it "
                 "the ESP32's signals have no reference and the motors do nothing."},
         {"id": "ain1", "label": "AIN1", "spec": {"pin": D["D0"]}, "why": "Left motor, forward PWM: D0 (GPIO1)."},
         {"id": "ain2", "label": "AIN2", "spec": {"pin": D["D1"]}, "why": "Left motor, reverse PWM: D1 (GPIO2)."},
         {"id": "bin1", "label": "BIN1", "spec": {"pin": D["D2"]}, "why": "Right motor, forward PWM: D2 (GPIO3)."},
         {"id": "bin2", "label": "BIN2", "spec": {"pin": D["D3"]}, "why": "Right motor, reverse PWM: D3 (GPIO4)."},
         {"id": "eep", "label": "EEP (sleep)", "spec": P33,
          "why": "The DRV8833's wake-up pin (EEP, also printed SLP or STBY) on the 3.3 V rail. Left open, the driver "
                 "stays asleep and the wheels do nothing."},
     ]},
    {"id": "motors", "name": "TT gear motors (2)", "sub": "2WD: one motor per side, a caster wheel at the back", "health": "motors",
     "webots": "left wheel motor, right wheel motor", "modelled": False, "config": "invert: true on a side that spins backwards",
     "test": "hwtest.test_motors (wheels in the air)", "app": "Drive tab: forward moves forward",
     "pins": [
         {"id": "left", "label": "Left motor", "spec": {"ext": "aout"}, "why": "The left motor's two wires on AOUT1 / AOUT2."},
         {"id": "right", "label": "Right motor", "spec": {"ext": "bout"}, "why": "The right motor's two wires on BOUT1 / BOUT2."},
     ]},
    {"id": "us", "name": "HC-SR04P distance sensor (3.3 V version)", "sub": "Obstacle distance, straight ahead", "health": "ultrasonic",
     "webots": "us_center (distance sensor)", "modelled": False, "config": "firmware: TRIG = D6, ECHO = D7",
     "test": "hwtest.test_sensors", "app": "Robot health: Distance sensors; the robot stops before obstacles",
     "pins": [
         {"id": "vcc", "label": "VCC", "spec": P33,
          "why": "3.3 V, so its ECHO answer is 3.3 V too and needs no resistors. On 5 V the ECHO would be 5 V and could damage D7."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "trig", "label": "TRIG", "spec": {"pin": D["D6"]}, "why": "D6 (GPIO43) sends the ping."},
         {"id": "echo", "label": "ECHO", "spec": {"pin": D["D7"]}, "why": "D7 (GPIO44) times the echo."},
     ]},
    {"id": "imu", "name": "MPU6050 IMU", "sub": "Heading and turn rate", "health": "imu", "webots": "imu, gyro, accelerometer",
     "modelled": False, "config": "I2C address 0x68", "test": "hwtest.test_sensors", "app": "\"Turn left 90\" ends at 90 degrees",
     "pins": [
         {"id": "vcc", "label": "VCC", "spec": P33, "why": "3.3 V. Mount it flat near the centre of the chassis."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "Shared I2C data on D4 (0x68)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "Shared I2C clock on D5."},
     ]},
    {"id": "aht", "name": "AHT20 + BMP280 climate sensor", "sub": "Temperature, humidity, air pressure", "health": "environment",
     "webots": "Modelled per room", "modelled": True, "config": "AHT20 0x38, BMP280 0x77", "test": "hwtest.test_env",
     "app": "Temperature and humidity in inspections",
     "pins": [
         {"id": "vcc", "label": "VIN", "spec": P33, "why": "3.3 V. Keep it away from the XIAO, which gets warm."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "Shared I2C data on D4 (AHT20 0x38, BMP280 0x77)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "Shared I2C clock on D5."},
     ]},
    {"id": "sense", "name": "Sense board: camera + microphone", "sub": "Built into the XIAO ESP32S3 Sense, facing forward",
     "health": "camera", "webots": "camera", "modelled": False, "config": "firmware: PSRAM = OPI PSRAM",
     "test": "the picture on http://raqib.local", "app": "Live video, photos and \"is anyone talking?\"",
     "pins": [
         {"id": "b2b", "label": "Sense board", "spec": {"ext": "b2b"},
          "why": "Press the Sense expansion board onto the XIAO's board-to-board connector until it clicks. It carries the "
                 "camera socket and the microphone."},
         {"id": "cam", "label": "Camera ribbon", "spec": {"ext": "camsock"},
          "why": "The camera's ribbon into the socket on the Sense board: lift the latch, push the ribbon in, close the latch."},
     ]},
]

SPEC = {"header": {str(k): list(v) for k, v in HEADER.items()}, "board": BOARD, "ext": EXT, "parts": PARTS}

if __name__ == "__main__":
    out = Path(__file__).with_name("wiring_spec.json")
    out.write_text(json.dumps(SPEC, indent=1), encoding="utf-8")
    print(f"wrote {out} ({sum(len(p['pins']) for p in PARTS)} wires)")
