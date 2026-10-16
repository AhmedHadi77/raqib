"""The robot's wiring: every part, every pin and where it must go (same as docs/WIRING.md and config.yaml).

Used by the virtual wiring harness (hal/harness.py), which makes the simulated robot behave like a real
one wired the way you wired it on the Wiring Bench, and served to the bench page by the backend.
Run this file to write wiring_spec.json next to it.
"""
from __future__ import annotations

import json
from pathlib import Path

# physical pin -> (label, class)   classes: p5 p33 gnd sda scl gpio id
HEADER = {
    1: ("3V3", "p33"), 2: ("5V", "p5"), 3: ("GPIO2 SDA", "sda"), 4: ("5V", "p5"), 5: ("GPIO3 SCL", "scl"), 6: ("GND", "gnd"),
    7: ("GPIO4", "gpio"), 8: ("GPIO14 TXD", "gpio"), 9: ("GND", "gnd"), 10: ("GPIO15 RXD", "gpio"), 11: ("GPIO17", "gpio"),
    12: ("GPIO18", "gpio"), 13: ("GPIO27", "gpio"), 14: ("GND", "gnd"), 15: ("GPIO22", "gpio"), 16: ("GPIO23", "gpio"),
    17: ("3V3", "p33"), 18: ("GPIO24", "gpio"), 19: ("GPIO10", "gpio"), 20: ("GND", "gnd"), 21: ("GPIO9", "gpio"),
    22: ("GPIO25", "gpio"), 23: ("GPIO11", "gpio"), 24: ("GPIO8", "gpio"), 25: ("GND", "gnd"), 26: ("GPIO7", "gpio"),
    27: ("ID_SD", "id"), 28: ("ID_SC", "id"), 29: ("GPIO5", "gpio"), 30: ("GND", "gnd"), 31: ("GPIO6", "gpio"),
    32: ("GPIO12", "gpio"), 33: ("GPIO13", "gpio"), 34: ("GND", "gnd"), 35: ("GPIO19", "gpio"), 36: ("GPIO16", "gpio"),
    37: ("GPIO26", "gpio"), 38: ("GPIO20", "gpio"), 39: ("GND", "gnd"), 40: ("GPIO21", "gpio"),
}
BCM_TO_PIN = {int(v[0].split()[0][4:]): k for k, v in HEADER.items() if v[0].startswith("GPIO")}

EXT = [
    {"group": "Motor battery 2x18650 (7.4 V)", "items": [["bat+", "Battery +"], ["bat-", "Battery -"]]},
    {"group": "L298N outputs", "items": [["out12", "OUT1 + OUT2"], ["out34", "OUT3 + OUT4"]]},
    {"group": "Pi ports", "items": [["usbc", "USB-C power input"], ["usb", "USB port"], ["jack", "3.5 mm audio jack"]]},
]

P5, P33, GND = {"cls": "p5"}, {"cls": "p33"}, {"cls": "gnd"}
SDA, SCL = {"pin": 3}, {"pin": 5}


def _us(key: str, name: str, trig_bcm: int, echo_bcm: int, aim: str) -> dict:
    tp, ep = BCM_TO_PIN[trig_bcm], BCM_TO_PIN[echo_bcm]
    return {"id": f"us_{key}", "name": f"HC-SR04 ultrasonic - {name}", "sub": f"Obstacle distance, pointing {aim}",
            "health": "ultrasonic", "webots": f"us_{key} (distance sensor)", "modelled": False,
            "config": f"ultrasonic:\n  {key}: {{trigger: {trig_bcm}, echo: {echo_bcm}}}", "test": "hwtest.test_sensors",
            "app": "Robot health: Distance sensors; the robot stops before obstacles",
            "pins": [
                {"id": "vcc", "label": "VCC", "spec": P5, "why": "The HC-SR04 is a 5 V part."},
                {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
                {"id": "trig", "label": "TRIG", "spec": {"pin": tp},
                 "why": f"BCM GPIO {trig_bcm} (physical pin {tp}). A 3.3 V pulse from the Pi is enough to trigger it."},
                {"id": "echo", "label": "ECHO", "spec": {"pin": ep}, "divider": True,
                 "why": f"BCM GPIO {echo_bcm} (physical pin {ep}) through the divider: ECHO - 1 kOhm - GPIO, with 2 kOhm from "
                        "that point to GND. ECHO is 5 V and would damage the Pi without it."},
            ]}


PARTS = [
    {"id": "pbank", "name": "USB power bank (Pi only)", "sub": "10,000 mAh, 5 V 3 A: powers the Pi, sensors and speaker",
     "health": "power", "webots": "Battery model", "modelled": True, "config": "battery_monitor: none",
     "test": "the Pi boots; no lightning-bolt / undervoltage warning", "app": "The robot turns on with the power bank",
     "pins": [
         {"id": "usb", "label": "USB-C cable", "spec": {"ext": "usbc"},
          "why": "A short USB-C cable from the power bank's output into the Pi. The motors have their own battery, "
                 "so motor starts can never restart the Pi."},
     ]},
    {"id": "l298", "name": "L298N motor driver", "sub": "Turns Pi signals into motor power", "health": "motors",
     "webots": "left wheel motor, right wheel motor", "modelled": False,
     "config": "motor_left: {pwm_pin: 13, in1: 17, in2: 27}\nmotor_right: {pwm_pin: 19, in1: 22, in2: 23}",
     "test": "hwtest.test_motors", "app": "Drive tab arrows move the robot",
     "pins": [
         {"id": "12v", "label": "+12V", "spec": {"ext": "bat+"}, "why": "Motor power comes from the motor battery only, never from the Pi."},
         {"id": "gndbat", "label": "GND (battery)", "spec": {"ext": "bat-"}, "why": "Motor battery ground for the motor current."},
         {"id": "gndpi", "label": "GND (to Pi)", "spec": GND,
          "why": "Common ground, Pi pin 9 (or any GND). ESSENTIAL with two batteries: without it the Pi's IN and EN "
                 "signals have no reference and the motors do nothing."},
         {"id": "ena", "label": "ENA", "spec": {"pin": 33},
          "why": "Left speed: PWM from BCM GPIO 13 (physical pin 33). Remove the ENA jumper first."},
         {"id": "in1", "label": "IN1", "spec": {"pin": 11}, "why": "Left direction, BCM GPIO 17 (physical pin 11)."},
         {"id": "in2", "label": "IN2", "spec": {"pin": 13}, "why": "Left direction, BCM GPIO 27 (physical pin 13)."},
         {"id": "enb", "label": "ENB", "spec": {"pin": 35},
          "why": "Right speed: PWM from BCM GPIO 19 (physical pin 35). Remove the ENB jumper first."},
         {"id": "in3", "label": "IN3", "spec": {"pin": 15}, "why": "Right direction, BCM GPIO 22 (physical pin 15)."},
         {"id": "in4", "label": "IN4", "spec": {"pin": 16}, "why": "Right direction, BCM GPIO 23 (physical pin 16)."},
     ]},
    {"id": "motors", "name": "TT gear motors (4)", "sub": "4WD: front + rear motor of each side joined (red-red, black-black)", "health": "motors",
     "webots": "left wheel motor, right wheel motor", "modelled": False, "config": "invert: true on a side that spins backwards",
     "test": "hwtest.test_motors (wheels in the air)", "app": "Drive tab: forward moves forward",
     "pins": [
         {"id": "left", "label": "Left pair", "spec": {"ext": "out12"},
          "why": "Both left motors (front + rear, joined red to red, black to black) on OUT1/OUT2."},
         {"id": "right", "label": "Right pair", "spec": {"ext": "out34"}, "why": "Both right motors on OUT3/OUT4."},
     ]},
    _us("left", "Left", 12, 16, "45 degrees to the left"),
    _us("center", "Center", 24, 25, "straight ahead"),
    _us("right", "Right", 20, 21, "45 degrees to the right"),
    {"id": "imu", "name": "MPU6050 IMU", "sub": "Heading and turn rate", "health": "imu", "webots": "imu, gyro, accelerometer",
     "modelled": False, "config": "mpu6050_address: 0x68", "test": "hwtest.test_sensors", "app": "\"Turn left 90\" ends at 90 degrees",
     "pins": [
         {"id": "vcc", "label": "VCC", "spec": P33, "why": "3.3 V. Mount it flat near the centre of the chassis."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "Shared I2C data (0x68)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "Shared I2C clock."},
     ]},
    {"id": "aht", "name": "AHT20 + BMP280 climate sensor", "sub": "Temperature, humidity, air pressure", "health": "environment",
     "webots": "Modelled per room", "modelled": True, "config": "env_sensor: auto\naht20_address: 0x38", "test": "hwtest.test_env",
     "app": "Temperature and humidity in inspections",
     "pins": [
         {"id": "vcc", "label": "VIN", "spec": P33, "why": "3.3 V. Keep it away from the Pi CPU and the MQ-135, they are warm."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "Shared I2C data (AHT20 0x38, BMP280 0x77)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "Shared I2C clock."},
     ]},
    {"id": "cam", "name": "USB webcam with microphone", "sub": "Camera and microphone in one; fixed, facing forward",
     "health": "camera", "webots": "camera", "modelled": False, "config": "camera: picamera2 (falls back to the webcam)",
     "test": "hwtest.test_camera_audio", "app": "Live video, \"what do you see?\" and \"who is talking?\"",
     "pins": [{"id": "usb", "label": "USB plug", "spec": {"ext": "usb"},
               "why": "Any USB port (blue USB 3 is best). The robot finds the camera and its microphone by itself."}]},
    {"id": "spk", "name": "Speaker + PAM8403 amp", "sub": "Spoken replies and warnings", "health": "speaker", "webots": "speaker",
     "modelled": False, "config": "speaker_device: auto", "test": "hwtest.test_camera_audio", "app": "The robot speaks",
     "pins": [
         {"id": "vcc", "label": "Amp VCC", "spec": P5, "why": "The PAM8403 runs on 5 V."},
         {"id": "gnd", "label": "Amp GND", "spec": GND, "why": "Ground."},
         {"id": "in", "label": "Audio in (L)", "spec": {"ext": "jack"},
          "why": "From the Pi's own 3.5 mm audio jack: tip to L, sleeve to G."},
     ]},
]

SPEC = {"header": {str(k): list(v) for k, v in HEADER.items()}, "ext": EXT, "parts": PARTS}

if __name__ == "__main__":
    out = Path(__file__).with_name("wiring_spec.json")
    out.write_text(json.dumps(SPEC, indent=1), encoding="utf-8")
    print(f"wrote {out} ({sum(len(p['pins']) for p in PARTS)} wires)")
