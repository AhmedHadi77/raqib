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
    {"group": "Battery 3x18650 (11.1 V)", "items": [["bat+", "Battery +"], ["bat-", "Battery -"]]},
    {"group": "UPS hat outputs", "items": [["ups5", "5 V servo output"]]},
    {"group": "PCA9685 outputs", "items": [["pca0", "Channel 0 (PWM)"], ["pca1", "Channel 1 (PWM)"],
                                           ["pca14", "Channel 14 header"], ["pca15", "Channel 15 header"]]},
    {"group": "L298N outputs", "items": [["out12", "OUT1 + OUT2"], ["out34", "OUT3 + OUT4"]]},
    {"group": "ADS1115 inputs", "items": [["adsa0", "A0 (analog in)"]]},
    {"group": "Pi ports", "items": [["csi", "CSI camera port"], ["usb", "USB port"], ["usbaudio", "USB sound card out"]]},
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
    {"id": "ups", "name": "UPS hat", "sub": "Powers the Pi from the battery, measures charge", "health": "battery",
     "webots": "Battery model", "modelled": True, "config": "ups_ina219_address: 0x42", "test": "hwtest.i2c_scan -> 0x42",
     "app": "Battery % on the Home screen",
     "pins": [
         {"id": "in+", "label": "Battery in +", "spec": {"ext": "bat+"},
          "why": "The UPS hat turns the 11.1 V battery into a steady 5 V / 3 A for the Pi. It plugs onto the 40-pin header, "
                 "so its I2C gauge (0x42) is already on the bus."},
         {"id": "in-", "label": "Battery in -", "spec": {"ext": "bat-"}, "why": "Battery ground to the Pi ground: the start of the common ground."},
     ]},
    {"id": "l298", "name": "L298N motor driver", "sub": "Turns Pi signals into motor power", "health": "motors",
     "webots": "left wheel motor, right wheel motor", "modelled": False,
     "config": "motor_left: {pwm_channel: 0, in1: 17, in2: 27}\nmotor_right: {pwm_channel: 1, in1: 22, in2: 23}",
     "test": "hwtest.test_motors", "app": "Drive tab arrows move the robot",
     "pins": [
         {"id": "12v", "label": "+12V", "spec": {"ext": "bat+"}, "why": "Motor power comes straight from the battery, never from the Pi."},
         {"id": "gndbat", "label": "GND (battery)", "spec": {"ext": "bat-"}, "why": "Battery ground for the motor current."},
         {"id": "gndpi", "label": "GND (to Pi)", "spec": GND,
          "why": "Common ground: without it the Pi's IN1-IN4 signals have no reference and the motors do nothing."},
         {"id": "ena", "label": "ENA", "spec": {"ext": "pca0"}, "why": "Left speed: PCA9685 channel 0 (remove the ENA jumper)."},
         {"id": "in1", "label": "IN1", "spec": {"pin": 11}, "why": "Left direction, BCM GPIO 17 (physical pin 11)."},
         {"id": "in2", "label": "IN2", "spec": {"pin": 13}, "why": "Left direction, BCM GPIO 27 (physical pin 13)."},
         {"id": "enb", "label": "ENB", "spec": {"ext": "pca1"}, "why": "Right speed: PCA9685 channel 1 (remove the ENB jumper)."},
         {"id": "in3", "label": "IN3", "spec": {"pin": 15}, "why": "Right direction, BCM GPIO 22 (physical pin 15)."},
         {"id": "in4", "label": "IN4", "spec": {"pin": 16}, "why": "Right direction, BCM GPIO 23 (physical pin 16)."},
     ]},
    {"id": "motors", "name": "Gear motors (4)", "sub": "Front and rear motors of each side in parallel", "health": "motors",
     "webots": "left wheel motor, right wheel motor", "modelled": False, "config": "invert: true on a side that spins backwards",
     "test": "hwtest.test_motors (wheels in the air)", "app": "Drive tab: forward moves forward",
     "pins": [
         {"id": "left", "label": "Left pair", "spec": {"ext": "out12"}, "why": "Both left motors on OUT1/OUT2."},
         {"id": "right", "label": "Right pair", "spec": {"ext": "out34"}, "why": "Both right motors on OUT3/OUT4."},
     ]},
    {"id": "pca", "name": "PCA9685 PWM driver", "sub": "PWM for motor speed and the servos", "health": "motors",
     "webots": "No separate device", "modelled": False, "config": "pca9685_address: 0x40", "test": "hwtest.i2c_scan -> 0x40",
     "app": "Robot health: Drive motors and Camera mount",
     "pins": [
         {"id": "vcc", "label": "VCC (logic)", "spec": P33, "why": "The PCA9685 logic runs on 3.3 V so its I2C lines match the Pi."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "I2C data, shared on pin 3 (this board is 0x40)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "I2C clock, shared on pin 5."},
         {"id": "v+", "label": "V+ (servo power)", "spec": {"ext": "ups5"},
          "why": "Servos get 5 V from the UPS output or a 5 V BEC through V+, never from the Pi's 3.3 V."},
     ]},
    {"id": "servos", "name": "Pan/tilt servos (2x SG90)", "sub": "Turn and tilt the camera", "health": "pan_tilt",
     "webots": "pan motor, tilt motor", "modelled": False, "config": "servo_pan: {channel: 14}\nservo_tilt: {channel: 15}",
     "test": "hwtest.test_motors (servo part)", "app": "Assistant: \"look left\", \"look up\"",
     "pins": [
         {"id": "pan", "label": "Pan servo plug", "spec": {"ext": "pca14"}, "why": "Header column 14 (signal / V+ / GND)."},
         {"id": "tilt", "label": "Tilt servo plug", "spec": {"ext": "pca15"}, "why": "Header column 15."},
     ]},
    _us("left", "Left", 12, 16, "45 degrees to the left"),
    _us("center", "Center", 24, 25, "straight ahead"),
    _us("right", "Right", 20, 21, "45 degrees to the right"),
    {"id": "enc", "name": "Wheel encoders (2)", "sub": "Count wheel slots for distance", "health": "encoders",
     "webots": "left wheel sensor, right wheel sensor", "modelled": False,
     "config": "encoder_left_pin: 5\nencoder_right_pin: 6", "test": "hwtest.test_sensors", "app": "\"Go forward 2 m\" stops at 2 m",
     "pins": [
         {"id": "vcc", "label": "VCC (both)", "spec": P33, "why": "3.3 V keeps their output safe for the Pi."},
         {"id": "gnd", "label": "GND (both)", "spec": GND, "why": "Ground."},
         {"id": "left", "label": "Left OUT", "spec": {"pin": 29}, "why": "BCM GPIO 5 (physical pin 29)."},
         {"id": "right", "label": "Right OUT", "spec": {"pin": 31}, "why": "BCM GPIO 6 (physical pin 31)."},
     ]},
    {"id": "imu", "name": "MPU6050 IMU", "sub": "Heading and turn rate", "health": "imu", "webots": "imu, gyro, accelerometer",
     "modelled": False, "config": "mpu6050_address: 0x68", "test": "hwtest.test_sensors", "app": "\"Turn left 90\" ends at 90 degrees",
     "pins": [
         {"id": "vcc", "label": "VCC", "spec": P33, "why": "3.3 V. Mount it flat near the centre of the chassis."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "Shared I2C data (0x68)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "Shared I2C clock."},
     ]},
    {"id": "bme", "name": "BME680 climate sensor", "sub": "Temperature, humidity, pressure, VOC", "health": "environment",
     "webots": "Modelled per room", "modelled": True, "config": "bme680_address: 0x76", "test": "hwtest.test_env",
     "app": "Temperature and humidity in inspections",
     "pins": [
         {"id": "vcc", "label": "VCC", "spec": P33, "why": "3.3 V. Keep it away from the Pi CPU and the motors."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "Shared I2C data (0x76)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "Shared I2C clock."},
     ]},
    {"id": "ads", "name": "ADS1115 ADC", "sub": "Analog input for the MQ-135 (the Pi has none)", "health": "environment",
     "webots": "Modelled", "modelled": True, "config": "ads1115_address: 0x48", "test": "hwtest.i2c_scan -> 0x48",
     "app": "Air quality value in inspections",
     "pins": [
         {"id": "vdd", "label": "VDD", "spec": P33, "why": "3.3 V keeps its I2C lines safe for the Pi."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "sda", "label": "SDA", "spec": SDA, "why": "Shared I2C data (0x48)."},
         {"id": "scl", "label": "SCL", "spec": SCL, "why": "Shared I2C clock."},
         {"id": "addr", "label": "ADDR", "spec": GND, "why": "ADDR to GND sets the address to 0x48, the value in config.yaml."},
     ]},
    {"id": "mq", "name": "MQ-135 gas sensor", "sub": "Air quality", "health": "environment", "webots": "Modelled per room",
     "modelled": True, "config": "mq135_divider_gain: 1.5", "test": "hwtest.test_env --calibrate-mq135",
     "app": "Gas verdict (Normal / Warning / Hazard)",
     "pins": [
         {"id": "vcc", "label": "VCC (heater)", "spec": P5, "why": "The heater needs 5 V."},
         {"id": "gnd", "label": "GND", "spec": GND, "why": "Ground."},
         {"id": "aout", "label": "AOUT", "spec": {"ext": "adsa0"}, "divider": True,
          "why": "Through a 10 kOhm / 20 kOhm divider into A0: AOUT can reach 5 V and the ADS1115 runs on 3.3 V."},
     ]},
    {"id": "cam", "name": "Pi Camera v2", "sub": "On the pan/tilt head", "health": "camera", "webots": "camera",
     "modelled": False, "config": "camera: picamera2", "test": "hwtest.test_camera_audio", "app": "Live video and \"what do you see?\"",
     "pins": [{"id": "ribbon", "label": "Ribbon cable", "spec": {"ext": "csi"},
               "why": "CSI port, blue side of the ribbon facing the Ethernet port."}]},
    {"id": "mic", "name": "USB microphone", "sub": "Hears talking; faces forward", "health": "microphone",
     "webots": "Modelled", "modelled": True, "config": "microphone_device: null", "test": "hwtest.test_camera_audio",
     "app": "\"Who is talking?\" turns to the voice",
     "pins": [{"id": "usb", "label": "USB plug", "spec": {"ext": "usb"}, "why": "Any USB port."}]},
    {"id": "spk", "name": "Speaker + PAM8403 amp", "sub": "Spoken replies and warnings", "health": "speaker", "webots": "speaker",
     "modelled": False, "config": "speaker_tts: espeak-ng", "test": "hwtest.test_camera_audio", "app": "The robot speaks",
     "pins": [
         {"id": "vcc", "label": "Amp VCC", "spec": P5, "why": "The PAM8403 runs on 5 V."},
         {"id": "gnd", "label": "Amp GND", "spec": GND, "why": "Ground."},
         {"id": "in", "label": "Audio in (L)", "spec": {"ext": "usbaudio"}, "why": "From a USB sound card."},
     ]},
]

SPEC = {"header": {str(k): list(v) for k, v in HEADER.items()}, "ext": EXT, "parts": PARTS}

if __name__ == "__main__":
    out = Path(__file__).with_name("wiring_spec.json")
    out.write_text(json.dumps(SPEC, indent=1), encoding="utf-8")
    print(f"wrote {out} ({sum(len(p['pins']) for p in PARTS)} wires)")
