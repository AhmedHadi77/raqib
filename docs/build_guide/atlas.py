"""Builds docs/Raqib_Parts_and_Wiring_Atlas.pdf: a colourful picture book of the budget robot.

    python docs/build_guide/atlas.py

  A. Every part, drawn large in colour with its name, what it looks like, its size and where each pin goes
  B. The boards: Raspberry Pi 4 ports, the full 40-pin map, close-ups of the L298N, HC-SR04, MPU6050, AHT20, hub
  C. The robot's structure: exploded view, side / top / bottom / front views
  D. How everything connects: system map, one diagram per group, the full harness and a wire-by-wire table

The wire table is generated from edge/robot/wiring_spec.py (the same data the robot software and the Wiring Bench use).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import diagrams as D  # noqa: E402
from draw import (BANDS, BLUE, BLUE_D, GOLD, INK, METAL, METAL_D, MUTED, PCB, PCB_D, PI_PINS, S, SILK, W, ads1115,  # noqa: E402
                  aht20, battery_2s, buck_xl4015, cell_18650, encoder_disc, gpio_header, gy521, hcsr04, l298n,
                  mq135, pam8403, pi4, power_bank, resistor, slot_encoder, speaker, tag, tt_motor, webcam, wire)

OUT_HTML = HERE / "atlas.html"
OUT_PDF = HERE.parent / "Raqib_Parts_and_Wiring_Atlas.pdf"

spec_mod = importlib.util.spec_from_file_location("wiring_spec", ROOT / "edge" / "robot" / "wiring_spec.py")
WS = importlib.util.module_from_spec(spec_mod)
spec_mod.loader.exec_module(WS)

GROUPS = {
    "brain": ("The brain", "#1f7a4d", "#e6f4ec"),
    "power": ("Power", "#c0392b", "#fbe9e7"),
    "moving": ("Moving", "#b4621f", "#fbefe3"),
    "sensing": ("Sensing", "#1f5fbf", "#e7effb"),
    "media": ("Camera and sound", "#6b3fa0", "#f0e9f8"),
    "build": ("Wiring and building", "#9a7a12", "#f8f2dc"),
}
# wire colour keys used in the pin tables
WK = {"5v": (W["5v"], "5 V"), "3v3": (W["3v3"], "3.3 V"), "gnd": (W["gnd"], "GND"), "sda": (W["sda"], "SDA"),
      "scl": (W["scl"], "SCL"), "bat": (W["bat"], "battery +"), "mot": (W["mot"], "motor"), "pwm": (W["pwm"], "PWM"),
      "sig": (W["sig1"], "signal"), "usb": ("#555b62", "USB"), "audio": (W["audio"], "audio"), "ana": ("#7a7f87", "analog")}


# ======================================================================= extra drawings
def cut_usb_cable(s, x, y, k=1.0):
    """USB-A to USB-C cable with the A end cut off: red / black wires out, USB-C plug in."""
    s.rect(x, y + 18 * k, 34 * k, 22 * k, METAL, METAL_D, rx=8 * k)                     # USB-C plug
    s.rect(x + 34 * k, y + 14 * k, 30 * k, 30 * k, "#2a2e31", rx=6 * k)
    s.text(x + 17 * k, y + 60 * k, "USB-C", 8 * k, MUTED, "middle", 700)
    s.path(f"M{x + 64 * k} {y + 29 * k} C {x + 120 * k} {y + 29 * k}, {x + 120 * k} {y + 70 * k}, {x + 170 * k} {y + 70 * k}",
           stroke="#2a2e31", sw=9 * k)
    s.path(f"M{x + 170 * k} {y + 66 * k} l 40 -10", stroke="#e23b2e", sw=3.4 * k)
    s.path(f"M{x + 170 * k} {y + 74 * k} l 40 10", stroke="#1b1d20", sw=3.4 * k)
    s.path(f"M{x + 172 * k} {y + 70 * k} l 22 0", stroke="#2e9e4f", sw=1.6 * k)
    s.path(f"M{x + 172 * k} {y + 71 * k} l 18 4", stroke="#f2f2f2", sw=1.6 * k)
    s.text(x + 214 * k, y + 56 * k, "red +5 V", 8 * k, "#c0151b", "start", 700)
    s.text(x + 214 * k, y + 92 * k, "black GND", 8 * k, INK, "start", 700)
    s.text(x + 150 * k, y + 104 * k, "green / white: cut short, tape", 7 * k, MUTED, "middle", 600)


def audio_cable(s, x, y, k=1.0):
    """3.5 mm plug with the other end cut: tip wire and shield."""
    s.rect(x, y + 24 * k, 26 * k, 6 * k, METAL, METAL_D, rx=3 * k)
    s.line(x + 8 * k, y + 24 * k, x + 8 * k, y + 30 * k, "#333", 1.4)
    s.line(x + 16 * k, y + 24 * k, x + 16 * k, y + 30 * k, "#333", 1.4)
    s.rect(x + 26 * k, y + 18 * k, 40 * k, 18 * k, "#2a2e31", rx=5 * k)
    s.path(f"M{x + 66 * k} {y + 27 * k} C {x + 110 * k} {y + 27 * k}, {x + 110 * k} {y + 60 * k}, {x + 150 * k} {y + 60 * k}",
           stroke="#2a2e31", sw=6 * k)
    s.path(f"M{x + 150 * k} {y + 57 * k} l 36 -12", stroke="#e23b2e", sw=2.6 * k)
    s.path(f"M{x + 150 * k} {y + 62 * k} l 36 10", stroke="#b0b5ba", sw=2.6 * k)
    s.text(x + 190 * k, y + 46 * k, "tip → amp L", 8 * k, "#c0151b", "start", 700)
    s.text(x + 190 * k, y + 78 * k, "shield → amp G", 8 * k, INK, "start", 700)
    s.text(x + 13 * k, y + 50 * k, "3.5 mm", 8 * k, MUTED, "middle", 700)


def big_capacitor(s, x, y, k=1.0):
    s.rect(x, y, 46 * k, 74 * k, "#1d3f8f", "#0f2457", rx=8 * k)
    s.rect(x + 32 * k, y, 14 * k, 74 * k, "#c9ced3", rx=4 * k)
    for i in range(3):
        s.text(x + 39 * k, y + (18 + i * 18) * k, "−", 12 * k, "#333", "middle", 800)
    s.rect(x, y, 46 * k, 8 * k, "#c9ced3", rx=4 * k)
    s.text(x + 16 * k, y + 34 * k, "1000µF", 6.5 * k, "#fff", "middle", 700, rot=-90)
    s.text(x + 16 * k, y + 58 * k, "16V", 6.5 * k, "#fff", "middle", 700, rot=-90)
    s.line(x + 12 * k, y + 74 * k, x + 12 * k, y + 110 * k, "#9aa1a7", 2.4)
    s.line(x + 36 * k, y + 74 * k, x + 36 * k, y + 98 * k, "#9aa1a7", 2.4)
    s.text(x + 12 * k, y + 124 * k, "+ long leg", 8 * k, "#c0151b", "middle", 700)
    s.text(x + 52 * k, y + 112 * k, "− short leg", 8 * k, INK, "start", 700)


def pic(key: str) -> str:
    """Large colour drawing of one part (scaled by CSS to the card)."""
    if key in ("pi", "sd", "bat2", "l298n", "hc", "enc", "imu", "mq", "ads", "pam", "spk", "res", "res2", "wires", "hub",
               "standoff", "tools", "aht", "webcam", "buck", "chassis", "pbank"):
        return D.fig_component(key)
    if key == "motor":
        s = S(250, 150)
        tt_motor(s, 60, 90, 1.25)
        return s.svg("comp")
    if key == "cap":
        s = S(150, 140)
        big_capacitor(s, 40, 6, 1.0)
        return s.svg("comp")
    if key == "usbc":
        s = S(300, 120)
        cut_usb_cable(s, 8, 4, 1.0)
        return s.svg("comp")
    if key == "jack":
        s = S(270, 100)
        audio_cable(s, 8, 4, 1.0)
        return s.svg("comp")
    if key == "cells":
        s = S(250, 110)
        cell_18650(s, 10, 14, 200, 36)
        cell_18650(s, 10, 60, 200, 36)
        return s.svg("comp")
    raise KeyError(key)


# ======================================================================= the parts (budget robot)
# (key, group, name, job, looks like, size, [(pin, goes to, wire key)], tip)
PARTS = [
    ("pi", "brain", "Raspberry Pi 4 Model B (2 GB)", "The robot's computer. Runs the robot program, its own server for the phone app, and talks to the AI.",
     "Green board the size of a credit card. Silver USB and Ethernet ports on one short edge, 40 gold pins along one long edge.",
     "85 × 56 mm", [("40-pin header", "all sensors and the L298N (see the pin map)", "sig"), ("USB-C", "5 V from the power bank (its own cable)", "5v"),
                    ("USB 3 (blue)", "USB webcam", "usb"), ("3.5 mm jack", "PAM8403 amplifier", "audio")],
     "The microSD card slot is underneath, on the short edge without ports."),
    ("sd", "brain", "microSD card 16 GB", "Holds Raspberry Pi OS and all the robot software.",
     "Fingernail-size card; buy 'A1' or 'Class 10'.", "15 × 11 mm", [("card", "slot under the Pi", "sig")],
     "Write it with Raspberry Pi Imager on your PC."),
    ("pbank", "power", "USB power bank 10,000 mAh (5 V 3 A)", "Powers the Raspberry Pi, and nothing else: motor starts can never restart it.",
     "Flat black or white box with 4 small LEDs, a button, and USB-A / USB-C ports.", "about 140 × 68 × 16 mm",
     [("USB-C (or USB-A) out", "its own short cable → Pi USB-C power", "usb"), ("LEDs", "how full it is (no wires)", "sig")],
     "It must say 5 V 3 A (15 W) or more. Charge it like a phone."),
    ("cells", "power", "18650 Li-ion cells (×2)", "Store the energy for the motors.",
     "Cylinder like a fat AA battery, usually blue, green or purple wrapping, flat or button top.",
     "18 mm × 65 mm each, 3.7 V", [("+ (button end)", "+ mark in the holder", "bat"), ("− (flat end)", "spring in the holder", "gnd")],
     "Real cells are 2500-3500 mAh. '9900 mAh' cells are fake and unsafe."),
    ("bat2", "power", "2 × 18650 holder with switch", "Joins the two cells into a 7.4 V motor pack; its switch turns the motors on and off.",
     "Black plastic box with two slots, a small slide switch and a red + black lead.", "about 77 × 41 mm",
     [("red lead +", "L298N +12V", "bat"), ("black lead −", "L298N GND (which also goes to Pi pin 9)", "gnd")],
     "Full = 8.4 V, empty ≈ 6.6 V. Never connect its + to the Pi."),
    ("chassis", "moving", "4WD chassis kit", "The robot's body: two acrylic decks, four motors with wheels, brass standoffs.",
     "Two clear or coloured acrylic plates with many holes, 4 yellow TT motors, 4 rubber wheels, brass posts and screws.",
     "about 25 × 15 cm", [("4 motors", "under the bottom deck, 2 per side", "mot"), ("standoffs", "bottom deck → top deck", "mot")],
     "Four driven wheels steer like a tank: left pair and right pair at different speeds."),
    ("motor", "moving", "TT gear motors (×4)", "Each turns one wheel. The robot knows how far it went from motor power × time (calibrated once).",
     "Yellow plastic gearbox with a small metal motor; shaft out of both sides.", "70 × 22 × 18 mm",
     [("left pair red / black", "L298N OUT1 / OUT2 (front + rear joined)", "mot"), ("right pair red / black", "L298N OUT3 / OUT4", "mot")],
     "Join the two motors of a side red-to-red, black-to-black; a side that runs backwards: swap its two wires."),
    ("l298n", "moving", "L298N motor driver", "Switches motor-battery power to the motors forwards or backwards, at the speed the Pi asks.",
     "Red board with a big black finned heatsink, blue screw terminals on three sides, 6 pins on the front.",
     "43 × 43 mm", [("+12V / GND", "motor battery + / −", "bat"), ("GND", "also to Pi pin 9: COMMON GROUND (essential)", "gnd"), ("OUT1/OUT2", "left motor pair", "mot"),
                    ("OUT3/OUT4", "right motor", "mot"), ("ENA / ENB", "Pi pins 33 / 35 (speed)", "pwm"),
                    ("IN1-IN4", "Pi pins 11, 13, 15, 16 (direction)", "sig")],
     "Pull off the ENA and ENB jumpers. Keep the 5V-EN jumper."),
    ("hc", "sensing", "HC-SR04 ultrasonic sensor (×3)", "Measures distance with sound (2 cm-4 m): stops the robot before obstacles.",
     "Blue board with two silver 'eyes' (speaker and microphone), 4 pins at the bottom.", "45 × 20 mm",
     [("VCC", "hub 5V", "5v"), ("Trig", "Pi pin 32 / 18 / 38 (left / centre / right)", "sig"),
      ("Echo", "1k/2k divider → Pi pin 36 / 22 / 40", "sig"), ("Gnd", "hub GND", "gnd")],
     "Echo is 5 V: never connect it to the Pi without the divider. Buy one spare."),
    ("imu", "sensing", "MPU6050 motion sensor (GY-521)", "Gyroscope + accelerometer: knows how far the robot has turned and keeps it straight.",
     "Tiny blue board with a square black chip and 8 pins in a row.", "21 × 16 mm",
     [("VCC", "hub 3V3", "3v3"), ("GND", "hub GND", "gnd"), ("SCL", "hub SCL (Pi pin 5)", "scl"), ("SDA", "hub SDA (Pi pin 3)", "sda")],
     "Mount it flat near the middle; I²C address 0x68."),
    ("aht", "sensing", "AHT20 + BMP280 climate sensor", "Temperature, humidity (AHT20) and air pressure (BMP280) on one board.",
     "Small purple or blue board with a white square chip (AHT20) and a tiny silver one (BMP280).", "about 15 × 12 mm",
     [("VIN", "hub 3V3", "3v3"), ("GND", "hub GND", "gnd"), ("SCL", "hub SCL", "scl"), ("SDA", "hub SDA", "sda")],
     "Two I²C addresses: 0x38 and 0x77 (or 0x76). Keep it away from warm parts."),
    ("webcam", "media", "USB webcam with microphone", "The robot's eyes and ears: photos, live video and sound.",
     "Small black camera on a clip, one USB cable, tiny mic holes on the front.", "about 70-90 mm wide",
     [("USB plug", "Pi USB 3 port (blue)", "usb")],
     "Choose 'UVC / plug and play' with a built-in mic. It is fixed: the robot turns to look."),
    ("pam", "media", "PAM8403 amplifier", "Makes the Pi's audio loud enough for the speaker.",
     "Tiny green board (thumbnail size) with a small chip and pins or pads.", "about 21 × 18 mm",
     [("5V / GND", "hub 5V / GND", "5v"), ("L / G", "3.5 mm cable: tip / shield", "audio"), ("L+ / L−", "speaker", "audio")],
     "Use only the left channel."),
    ("spk", "media", "Speaker 3 W 4 Ω", "The robot's voice.", "Round, about 40 mm, black cone, two solder tabs.", "40 mm",
     [("+ tab", "PAM8403 L+", "audio"), ("− tab", "PAM8403 L−", "audio")], "Face it outwards at the back of the top deck."),
    ("jack", "media", "3.5 mm audio cable (one end cut)", "Takes the sound from the Pi's audio jack to the amplifier.",
     "Ordinary headphone-plug cable.", "20-30 cm",
     [("plug", "Pi 3.5 mm audio jack", "audio"), ("tip wire", "PAM8403 L", "audio"), ("shield", "PAM8403 G", "gnd")],
     "If you are unsure which wire is the tip, test with the multimeter (continuity)."),
    ("res2", "build", "Resistors (1 kΩ ×3, 2 kΩ ×3)", "Three voltage dividers: they protect the Pi from the sonars' 5 V Echo.",
     "Small beige or blue tubes with coloured bands.", "about 6 mm long",
     [("1 kΩ (top)", "sonar Echo → middle point", "sig"), ("2 kΩ (bottom)", "middle point → GND", "gnd")],
     "No 2 kΩ? Two 1 kΩ in series. Read the colour bands (picture)."),
    ("hub", "build", "Hub board (you make it)", "One place where 5 V, 3.3 V, GND, SDA and SCL meet, plus the 3 sonar dividers.",
     "Brown perfboard with five soldered rails and header strips.", "about 7 × 9 cm",
     [("5V / 3V3 / GND", "Pi pins 2 / 1 / 6", "5v"), ("SDA / SCL", "Pi pins 3 / 5", "sda")], "Label each rail with a marker."),
    ("wires", "build", "Jumper wires", "Plug-in connections: no soldering for most parts.",
     "Rainbow ribbon of wires; F = socket end, M = pin end.", "10-20 cm", [("F-F", "pin to pin (Pi to sensor)", "sig"), ("M-F", "pin to socket", "sda")],
     "Use red for 5 V, orange for 3.3 V, black for GND."),
    ("standoff", "build", "Standoffs and screws", "Hold the top deck above the bottom deck, and the boards on the decks.",
     "Brass or nylon hexagon posts with threads.", "M3, 35-40 mm long", [("M3 posts", "between the decks", "mot"), ("M2.5 screws", "Raspberry Pi", "mot")],
     "Nylon washers under boards stop short circuits."),
]


# ======================================================================= board close-ups (callouts)
def callout(s, px, py, tx, ty, text, color, anchor="start"):
    s.line(px, py, tx, ty, color, 1.6)
    s.circle(px, py, 4, color, "#fff", 1.4)
    tag(s, tx + (4 if anchor == "start" else -4), ty + 4, text, color, 9, anchor)


def fig_pi_labelled() -> str:
    s = S(700, 470)
    sc = 1.55
    k = 3.4 * sc
    x0, y0 = 130, 80
    pins = pi4(s, x0, y0, sc)
    cols = {"g": "#1e9e55", "p": "#c0392b", "u": "#2d6be0", "a": "#7a7f87", "c": "#8a55e8"}
    callout(s, pins[1][0], pins[1][1], 60, 40, "pin 1 (square pad)", "#b4530f", "start")
    callout(s, pins[40][0] - 2, pins[40][1] - 4, 440, 30, "40-pin GPIO header: sensors + motor driver", cols["g"], "start")
    callout(s, x0 + 11.5 * k, y0 + 56 * k, 60, 440, "USB-C power: from the power bank", cols["p"], "start")
    callout(s, x0 + 30 * k, y0 + 56 * k, 250, 455, "2 × micro-HDMI (screen, not needed)", "#555b62", "start")
    callout(s, x0 + 54 * k, y0 + 54 * k, 420, 440, "3.5 mm audio jack → PAM8403", cols["a"], "start")
    callout(s, x0 + 45.5 * k, y0 + 45 * k, 440, 410, "CAMERA port (not used: webcam on USB)", "#8a7a52", "start")
    callout(s, x0 + 2.5 * k, y0 + 27 * k, 120, 230, "DISPLAY port", "#555b62", "end")
    callout(s, x0 + 29.5 * k, y0 + 29.5 * k, 120, 300, "CPU (fit the heatsink)", "#555b62", "end")
    callout(s, x0 + 47 * k, y0 + 28 * k, 120, 340, "RAM 2 GB", "#555b62", "end")
    callout(s, x0 + 85 * k, y0 + 10 * k, 590, 110, "Ethernet", "#555b62", "start")
    callout(s, x0 + 85 * k, y0 + 27 * k, 575, 190, "USB 3 (blue): webcam", cols["u"], "start")
    callout(s, x0 + 85 * k, y0 + 44 * k, 590, 270, "USB 2 (spare)", "#555b62", "start")
    s.text(350, 18, "Raspberry Pi 4 Model B, seen from above", 13, INK, "middle", 800)
    return s.svg()


def fig_pinout_full() -> str:
    """Every one of the 40 pins: name, type colour and what the robot uses it for."""
    use = {1: "→ hub 3V3 rail", 2: "→ hub 5V rail", 3: "→ hub SDA rail (I²C)", 5: "→ hub SCL rail (I²C)", 6: "→ hub GND rail",
           9: "→ L298N GND (signal ground)", 11: "→ L298N IN1 (left)", 13: "→ L298N IN2 (left)", 15: "→ L298N IN3 (right)",
           16: "→ L298N IN4 (right)", 18: "← sonar CENTRE Trig", 22: "← sonar CENTRE Echo (divider)", 32: "→ sonar LEFT Trig", 33: "→ L298N ENA (left speed)", 35: "→ L298N ENB (right speed)",
           36: "← sonar LEFT Echo (divider)", 38: "→ sonar RIGHT Trig", 40: "← sonar RIGHT Echo (divider)"}
    tcol = {"p33": W["3v3"], "p5": W["5v"], "gnd": W["gnd"], "sda": W["sda"], "scl": W["scl"], "gpio": "#9aa3ab", "id": "#c7ccd1"}
    used = {}
    for n, (lab, cls) in WS.HEADER.items():
        c = tcol[cls]
        if cls == "gpio" and n in use:
            c = W["pwm"] if n in (33, 35) else W["sig1"]
        used[n] = c
    s = S(700, 700)
    hdr = gpio_header(s, 327, 50, used, pitch=30, labels="none")
    for n, (lab, cls) in WS.HEADER.items():
        px, py, side = hdr[n]
        c = used[n]
        u = use.get(n, "free" if cls == "gpio" else "")
        fg = "#fff" if cls not in ("scl", "id") and c != W["pwm"] else INK
        if side == "L":
            tag(s, 300, py + 4, f"{lab}", c, 8.5, "end", fg=fg)
            s.text(300 - len(lab) * 5.6 - 18, py + 4, u, 8.5, INK if n in use else MUTED, "end", 700 if n in use else 400)
        else:
            tag(s, 400, py + 4, f"{lab}", c, 8.5, "start", fg=fg)
            s.text(400 + len(lab) * 5.6 + 18, py + 4, u, 8.5, INK if n in use else MUTED, "start", 700 if n in use else 400)
    s.text(350, 20, "pin 1 = square pad, at the corner nearest the microSD card · odd pins on the inside row", 9.5, MUTED, "middle", 600)
    lx = 40
    for i, (c, t) in enumerate(((W["5v"], "5 V"), (W["3v3"], "3.3 V"), (W["gnd"], "GND"), (W["sda"], "I²C SDA"), (W["scl"], "I²C SCL"),
                                (W["sig1"], "used signal"), (W["pwm"], "PWM speed"), ("#9aa3ab", "free GPIO"))):
        s.rect(lx + i * 80, 676, 14, 10, c, rx=3)
        s.text(lx + i * 80 + 18, 685, t, 8.5, INK, "start", 600)
    return s.svg()


def fan(s, pts, x_tag, y0, step, side="right"):
    """Labels for a row of pins: each pin drops down, then runs sideways to its label, without crossings.
    pts = [(x, y, text, colour), ...] ordered left to right."""
    n = len(pts)
    order = range(n) if side == "right" else reversed(range(n))
    for rank, i in enumerate(order):
        px, py, text, c = pts[i]
        yy = y0 + (n - 1 - rank) * step
        tx = x_tag
        wire(s, [(px, py), (px, yy), (tx, yy)], c, 2, r=4)
        s.circle(px, py, 3.6, c, "#fff", 1.2)
        tag(s, tx + (4 if side == "right" else -4), yy + 4, text, c, 8.5, "start" if side == "right" else "end",
            fg=INK if c in (W["scl"], W["pwm"], W["3v3"]) else "#fff")


def fig_closeup_l298n() -> str:
    s = S(700, 380)
    s.text(350, 20, "L298N motor driver: every terminal and where it goes", 12, INK, "middle", 800)
    k = 1.2
    l2 = l298n(s, 230, 40, k)
    for o, t in (("OUT1", "OUT1 → left motor (red)"), ("OUT2", "OUT2 → left motor (black)")):
        px, py = l2[o]
        wire(s, [(px, py), (205, py)], W["mot"], 2)
        tag(s, 201, py + 4, t, W["mot"], 8.5, "end")
    for o, t in (("OUT3", "OUT3 → right motor (red)"), ("OUT4", "OUT4 → right motor (black)")):
        px, py = l2[o]
        wire(s, [(px, py), (460, py)], W["mot"], 2)
        tag(s, 464, py + 4, t, W["mot"], 8.5, "start")
    fan(s, [(*l2["+12V"], "+12V ← motor battery + (red)", W["bat"]), (*l2["GND"], "GND ← motor battery − and Pi pin 9", W["gnd"]),
            (*l2["+5V"], "+5V: leave empty", "#9aa3ab")], 205, 270, 22, side="left")
    fan(s, [(*l2["ENA"], "ENA ← Pi pin 33 (left speed)", W["pwm"]), (*l2["IN1"], "IN1 ← Pi pin 11", W["sig1"]),
            (*l2["IN2"], "IN2 ← Pi pin 13", W["sig1"]), (*l2["IN3"], "IN3 ← Pi pin 15", W["sig1"]),
            (*l2["IN4"], "IN4 ← Pi pin 16", W["sig1"]), (*l2["ENB"], "ENB ← Pi pin 35 (right speed)", W["pwm"])], 460, 250, 20)
    callout(s, 230 + 27 * k, 40 + 114 * k, 160, 130, "5V-EN jumper: keep it", "#555b62", "end")
    callout(s, 230 + 92 * k, 40 + 127 * k, 160, 160, "ENA/ENB jumpers: remove", "#555b62", "end")
    return s.svg()


def fig_closeup_small() -> str:
    s = S(700, 505)
    s.text(20, 22, "HC-SR04 ultrasonic sensor", 12, INK, "start", 800)
    h = hcsr04(s, 40, 40, 1.5)
    fan(s, [(*h["VCC"], "VCC ← hub 5V", W["5v"]), (*h["Trig"], "Trig ← Pi pin 32 / 18 / 38", W["sig1"]),
            (*h["Echo"], "Echo → 1k/2k divider → Pi 36 / 22 / 40", W["sig3"]), (*h["Gnd"], "Gnd ← hub GND", W["gnd"])], 270, 150, 20)
    s.text(400, 22, "USB power bank → Raspberry Pi", 12, INK, "start", 800)
    pb = power_bank(s, 420, 50, 1.2)
    ux, uy = pb["usbc"]
    wire(s, [(ux, uy), (ux + 30, uy), (ux + 30, 175)], "#555b62", 4)
    tag(s, ux + 34, 190, "USB-C cable → Pi USB-C power", "#555b62", 8.5, "end")
    s.text(420, 215, "5 V 3 A output · the Pi only · LEDs show the charge", 8.5, MUTED, "start", 600)
    s.text(20, 262, "MPU6050 (GY-521)", 12, INK, "start", 800)
    m = gy521(s, 40, 280, 1.4)
    fan(s, [(*m["VCC"], "VCC ← hub 3V3", W["3v3"]), (*m["GND"], "GND ← hub GND", W["gnd"]),
            (*m["SCL"], "SCL ← hub SCL", W["scl"]), (*m["SDA"], "SDA ← hub SDA", W["sda"])], 240, 420, 14)
    s.text(400, 262, "AHT20 + BMP280", 12, INK, "start", 800)
    e = aht20(s, 430, 280, 1.5)
    fan(s, [(*e["VIN"], "VIN ← hub 3V3", W["3v3"]), (*e["GND"], "GND ← hub GND", W["gnd"]),
            (*e["SCL"], "SCL ← hub SCL", W["scl"]), (*e["SDA"], "SDA ← hub SDA", W["sda"])], 600, 420, 14)
    s.text(20, 498, "MPU6050 = I²C address 0x68 · AHT20 = 0x38, BMP280 = 0x77 (or 0x76). The other GY-521 pins are not used.", 9, MUTED, "start", 600)
    return s.svg()


# ======================================================================= structure
def _iso_deck(s, x, y, w, d, col, edge, label=None):
    """A deck seen from the front-top: a parallelogram with thickness."""
    dx = d * 0.55
    s.path(f"M{x} {y} L{x + w} {y} L{x + w + dx} {y - d * 0.45} L{x + dx} {y - d * 0.45} Z", col, edge, 1.6)
    s.path(f"M{x} {y} L{x + w} {y} L{x + w} {y + 7} L{x} {y + 7} Z", edge, None)
    s.path(f"M{x + w} {y} L{x + w + dx} {y - d * 0.45} L{x + w + dx} {y - d * 0.45 + 7} L{x + w} {y + 7} Z", edge, None)
    if label:
        s.text(24, y + 4, label, 10, INK, "start", 800)


def _block(s, x, y, w, h, col, label, fg="#fff", depth=10):
    s.path(f"M{x} {y} l{depth} {-depth * 0.8} l{w} 0 l{-depth} {depth * 0.8} Z", _shade(col, 1.25), None)
    s.path(f"M{x + w} {y} l{depth} {-depth * 0.8} l0 {h} l{-depth} {depth * 0.8} Z", _shade(col, 0.75), None)
    s.rect(x, y, w, h, col, None, rx=2)
    s.text(x + w / 2, y + h / 2 + 3.5, label, 8, fg, "middle", 800)


def _shade(hexc, f):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(c * f))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def fig_exploded() -> str:
    """Exploded view: the layers of the robot pulled apart, from the battery up to the sensors."""
    s = S(700, 720)
    s.text(350, 22, "EXPLODED VIEW · the robot pulled apart, layer by layer", 12, INK, "middle", 800)
    X, Wd, Dp = 170, 380, 180
    # layer 4: front sensors + webcam
    y4 = 160
    s.text(24, y4 - 12, "4 · front", 10, INK, "start", 800)
    for i, (cx, ang) in enumerate(((X + 70, -1), (X + 190, 0), (X + 310, 1))):
        _block(s, cx - 34, y4 - 30, 68, 28, BLUE, ["sonar L", "sonar C", "sonar R"][i])
    _block(s, X + 140, y4 - 92, 100, 40, "#202326", "USB webcam + mic")
    # layer 3: top deck
    y3 = 340
    _iso_deck(s, X, y3, Wd, Dp, "#d9ecf8", "#7fa8c4", "3 · top deck")
    _block(s, X + 30, y3 - 52, 110, 34, PCB, "Raspberry Pi 4")
    _block(s, X + 250, y3 - 58, 110, 38, "#b07d2c", "hub board")
    _block(s, X + 70, y3 - 14, 56, 18, BLUE, "MPU6050")
    _block(s, X + 140, y3 - 14, 46, 18, "#6b3fa0", "AHT20")
    _block(s, X + 262, y3 - 14, 56, 18, PCB, "PAM8403")
    s.circle(X + 350, y3 - 92, 16, "#2b2f35")
    s.text(X + 350, y3 - 66, "speaker", 8, INK, "middle", 700)
    # standoffs
    y2 = 470
    for sx in (X + 20, X + Wd - 20, X + 100, X + Wd + 60):
        s.rect(sx, y3 + 18, 7, y2 - y3 - 40, "#d4b24c", "#9c7f2a", rx=1)
    s.text(X + Wd + 72, y3 + 70, "4 × standoffs", 9.5, MUTED, "start", 700)
    s.text(X + Wd + 72, y3 + 84, "35-40 mm", 9.5, MUTED, "start", 700)
    # layer 2: bottom deck
    _iso_deck(s, X, y2 + 40, Wd, Dp, "#d9ecf8", "#7fa8c4", "2 · bottom deck")
    # 4 motors + 4 wheels (rear pair drawn behind, up and to the right)
    for wx in (X - 30 + 82, X + Wd + 10 + 82):
        s.add(f'<ellipse cx="{wx}" cy="{y2 + 70 - 66}" rx="20" ry="31" fill="#15181b"/>')
    _block(s, X + 6 + 82, y2 + 54 - 66, 64, 20, "#d9ae22", "rear L", fg="#5c4500")
    _block(s, X + Wd - 76 + 82, y2 + 54 - 66, 64, 20, "#d9ae22", "rear R", fg="#5c4500")
    _block(s, X + 165, y2 - 16, 128, 24, "#2b2f36", "power bank (Pi)")
    _block(s, X + 302, y2 - 20, 74, 32, "#b8322a", "L298N")
    for wx in (X - 30, X + Wd + 10):
        s.add(f'<ellipse cx="{wx}" cy="{y2 + 70}" rx="22" ry="34" fill="#202326"/>')
        s.add(f'<ellipse cx="{wx}" cy="{y2 + 70}" rx="9" ry="14" fill="#f2c230"/>')
    _block(s, X + 6, y2 + 54, 64, 22, "#f2c230", "front L", fg="#5c4500")
    _block(s, X + Wd - 76, y2 + 54, 64, 22, "#f2c230", "front R", fg="#5c4500")
    s.text(X + Wd / 2, y2 + 104, "4 × TT motors + wheels (2 per side)", 9, MUTED, "middle", 700)
    # layer 1: battery
    y1 = 680
    s.text(24, y1 - 14, "1 · underneath", 10, INK, "start", 800)
    _block(s, X + 120, y1 - 32, 150, 30, "#2f7dd1", "2 × 18650 motor battery + switch")
    s.text(40, 712, "Heavy parts low (batteries, L298N, motors); the warm Pi away from the AHT20; sensors at the front.",
           9, MUTED, "start", 600)
    return s.svg()


def fig_layout_bottom() -> str:
    s = S(700, 400)
    x, y, W_, H_ = 80, 50, 540, 300
    s.text(x + W_ / 2, 14, "BOTTOM DECK (seen from above) · front of the robot →", 11, INK, "middle", 800)
    for wx in (x + 360, x + 60):
        for wy in (y - 18, y + H_ - 10):
            s.rect(wx, wy, 110, 28, "#202326", "#111", rx=8)
    s.rect(x, y, W_, H_, "#e6f1f9", "#7fa8c4", rx=40, sw=2)

    def part(px, py, pw, ph, col, label, sub="", fg="#fff"):
        s.rect(x + px, y + py, pw, ph, col, None, rx=6)
        s.text(x + px + pw / 2, y + py + ph / 2 + (0 if sub else 4), label, 9.5, fg, "middle", 800)
        if sub:
            s.text(x + px + pw / 2, y + py + ph / 2 + 13, sub, 7.5, fg, "middle", 500)

    part(360, 18, 110, 34, "#f2c230", "front motor L", "under the deck", fg="#5c4500")
    part(360, H_ - 52, 110, 34, "#f2c230", "front motor R", "under the deck", fg="#5c4500")
    part(60, 18, 110, 34, "#f2c230", "rear motor L", "under the deck", fg="#5c4500")
    part(60, H_ - 52, 110, 34, "#f2c230", "rear motor R", "under the deck", fg="#5c4500")
    part(330, 100, 100, 100, "#b8322a", "L298N", "heatsink up")
    part(90, 66, 200, 64, "#2b2f36", "USB power bank", "on top of the deck: the Pi's battery")
    part(110, 150, 160, 80, "#2f7dd1", "motor battery holder", "underneath; switch reachable")
    for sx, sy in ((x + 26, y + 26), (x + W_ - 26, y + 26), (x + 26, y + H_ - 26), (x + W_ - 26, y + H_ - 26)):
        s.circle(sx, sy, 7, "#d4b24c", "#9c7f2a", 1.5)
    s.text(x + W_ / 2, y + H_ + 34, "Gold dots = standoffs to the top deck. The USB-C cable, motor and battery wires go up through the deck holes.", 9.5, MUTED, "middle", 500)
    return s.svg()


def fig_front() -> str:
    s = S(700, 330)
    gy = 290
    s.line(40, gy + 4, 660, gy + 4, "#c4ccd3", 3)
    s.text(350, 22, "FRONT VIEW · what the robot sees with", 12, INK, "middle", 800)
    for wx in (150, 550):
        s.rect(wx - 22, gy - 70, 44, 74, "#202326", rx=10)
        s.rect(wx - 8, gy - 44, 16, 22, "#f2c230", rx=3)
    s.rect(180, gy - 50, 340, 8, "#cfe6f5", "#7fa8c4", rx=3)
    s.rect(300, gy - 42, 100, 24, "#2f7dd1", rx=4)
    s.text(350, gy - 26, "motor battery", 8, "#fff", "middle", 700)
    for sx in (200, 500):
        s.rect(sx, gy - 140, 8, 90, "#d4b24c", "#9c7f2a", rx=1)
    s.rect(180, gy - 148, 340, 8, "#cfe6f5", "#7fa8c4", rx=3)
    for i, (cx, lab, rot) in enumerate(((235, "LEFT 45°", -22), (350, "CENTRE", 0), (465, "RIGHT 45°", 22))):
        s.add(f'<g transform="rotate({rot} {cx} {gy - 120})"><rect x="{cx - 44}" y="{gy - 140}" width="88" height="40" rx="5" fill="{BLUE}"/>'
              f'<circle cx="{cx - 20}" cy="{gy - 120}" r="14" fill="{METAL}" stroke="{METAL_D}"/><circle cx="{cx + 20}" cy="{gy - 120}" r="14" fill="{METAL}" stroke="{METAL_D}"/>'
              f'<circle cx="{cx - 20}" cy="{gy - 120}" r="7" fill="#4a4f55"/><circle cx="{cx + 20}" cy="{gy - 120}" r="7" fill="#4a4f55"/></g>')
        s.text(cx, gy - 82, lab, 8.5, INK, "middle", 800)
    s.rect(300, gy - 214, 100, 46, "#202326", "#0d0f11", rx=20)
    s.circle(350, gy - 191, 16, "#0f1a2a", "#3a3f44", 3)
    s.circle(345, gy - 196, 5, "#9fc3ff")
    s.rect(343, gy - 168, 14, 20, "#2a2e31", rx=2)
    s.text(420, gy - 196, "USB webcam: fixed, level, looking forward", 9, INK, "start", 700)
    s.text(40, gy - 196, "The robot turns its whole body", 9, MUTED, "start", 600)
    s.text(40, gy - 182, "to look left or right.", 9, MUTED, "start", 600)
    return s.svg()


# ======================================================================= wire table from the wiring spec
CLS_COL = {"p5": (W["5v"], "red"), "p33": (W["3v3"], "orange"), "gnd": (W["gnd"], "black"), "sda": (W["sda"], "blue"),
           "scl": (W["scl"], "yellow"), "gpio": (W["sig1"], "any colour"), "id": ("#999", "-")}


def wire_rows() -> list[tuple]:
    ext = {i: f"{n}" for g in WS.EXT for i, n in g["items"]}
    rows = []
    for p in WS.PARTS:
        for pin in p["pins"]:
            sp = pin["spec"]
            if "ext" in sp:
                to = ext[sp["ext"]]
                col = {"bat+": (W["bat"], "red"), "bat-": (W["gnd"], "black"), "usbc": ("#555b62", "USB cable"),
                       "usb": ("#555b62", "USB cable"), "jack": (W["audio"], "audio cable"), "out12": (W["mot"], "motor wires"),
                       "out34": (W["mot"], "motor wires")}.get(sp["ext"], ("#999", ""))
            elif "cls" in sp:
                pins = [str(n) for n, v in WS.HEADER.items() if v[1] == sp["cls"]]
                to = {"p5": "5 V (hub 5V rail / Pi pin 2 or 4)", "p33": "3.3 V (hub 3V3 rail / Pi pin 1 or 17)",
                      "gnd": "GND (hub GND rail / any Pi GND pin)"}[sp["cls"]]
                col = CLS_COL[sp["cls"]]
            else:
                n = sp["pin"]
                to = f"Pi pin {n} ({WS.HEADER[n][0]})"
                if n == 3:
                    to += " · via hub SDA rail"
                if n == 5:
                    to += " · via hub SCL rail"
                col = CLS_COL[WS.HEADER[n][1]]
                if n in (33, 35):
                    col = (W["pwm"], "any colour")
            if pin.get("divider"):
                to += " · through its divider"
            rows.append((p["name"], pin["label"], to, col))
    return rows


def wire_table() -> str:
    out, last = [], None
    for part, pin, to, (c, cname) in wire_rows():
        first = part != last
        last = part
        out.append(f"<tr{' class=first' if first else ''}><td>{escape(part) if first else ''}</td><td><b>{escape(pin)}</b></td>"
                   f"<td><span class='dot' style='background:{c}'></span>{escape(to)}</td><td>{escape(cname)}</td></tr>")
    return ("<table class='wt'><thead><tr><th>Part</th><th>Pin</th><th>Goes to</th><th>Wire</th></tr></thead><tbody>"
            + "".join(out) + "</tbody></table>")


# ======================================================================= page
CSS_EXTRA = """
.cover2 { background: linear-gradient(160deg, #0f1d33 0%, #183a63 55%, #1f7a4d 100%); color: #fff; height: 258mm; overflow: hidden;
  padding: 16mm 14mm; border-radius: 6px; display: flex; flex-direction: column; }
.cover2 h1 { font-size: 40pt; font-weight: 800; margin: 8px 0 6px; letter-spacing: -0.02em; }
.cover2 .sub { font-size: 12.5pt; color: #d6e2f5; max-width: 150mm; }
.collage { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5mm; margin-top: 10mm; }
.collage div { background: rgba(255,255,255,0.94); border-radius: 10px; padding: 3mm; height: 30mm; display: flex; flex-direction: column;
  align-items: center; justify-content: center; }
.collage svg { max-height: 21mm; width: auto; max-width: 100%; }
.collage span { color: #16202a; font-size: 7.5pt; font-weight: 700; margin-top: 1mm; text-align: center; }
.cover2 .covermeta { margin-top: auto; display: flex; justify-content: space-between; font-size: 9pt; color: #c9d6ea;
  border-top: 1px solid rgba(255,255,255,0.25); padding-top: 5mm; }
.ghead { border-radius: 10px; padding: 5mm 7mm; color: #fff; margin-bottom: 4mm; }
.ghead h2 { font-size: 22pt; font-weight: 800; } .ghead p { margin: 4px 0 0; font-size: 10.5pt; opacity: 0.95; }
.pc { border-radius: 12px; overflow: hidden; break-inside: avoid; margin-bottom: 4mm; border: 2px solid var(--gc); }
.pc .band { background: var(--gc); color: #fff; padding: 2.4mm 4mm; display: flex; align-items: baseline; gap: 3mm; }
.pc .band .n { font-weight: 800; font-size: 10pt; background: rgba(255,255,255,0.25); border-radius: 6px; padding: 0 6px; }
.pc .band h3 { margin: 0; font-size: 13.5pt; }
.pc .body { display: grid; grid-template-columns: 52% 48%; gap: 4mm; padding: 4mm; background: var(--gs); }
.pc .img { background: #fff; border-radius: 10px; display: flex; align-items: center; justify-content: center; padding: 3mm; min-height: 52mm; }
.pc .img svg { max-height: 50mm; width: 100%; height: auto; }
.pc .info p { margin: 0 0 1.6mm; font-size: 8.6pt; line-height: 1.35; }
.pc .info .k { font-weight: 800; color: var(--gc); font-size: 7.5pt; letter-spacing: .06em; text-transform: uppercase; display: block; }
.pins2 { width: 100%; border-collapse: collapse; font-size: 8.4pt; margin-top: 1mm; }
.pins2 td { padding: 0.8mm 1.5mm; border-top: 1px solid rgba(0,0,0,0.08); vertical-align: top; }
.pins2 td:first-child { font-weight: 700; white-space: nowrap; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; vertical-align: -1px; }
.tipb { background: #fff6da; border-radius: 6px; padding: 1.5mm 2.5mm; font-size: 8.4pt; color: #6a4f00; margin-top: 2mm; }
table.wt { width: 100%; border-collapse: collapse; font-size: 8.3pt; }
table.wt th { background: #0f1d33; color: #fff; text-align: left; padding: 4px 6px; }
table.wt td { padding: 3px 6px; border-bottom: 1px solid #e3e7eb; vertical-align: top; }
table.wt tr.first td { border-top: 2px solid #c3ccd5; }
table.wt td:first-child { font-weight: 800; color: #0f1d33; width: 26%; }
table.wt tr { break-inside: avoid; }
.legend2 { display: flex; flex-wrap: wrap; gap: 10px; margin: 4px 0 8px; font-size: 9pt; }
.legend2 span { display: inline-flex; align-items: center; gap: 5px; }
.legend2 i { width: 22px; height: 6px; border-radius: 3px; display: inline-block; }
"""


def part_card(i: int, p: tuple) -> str:
    key, g, name, job, looks, size, pins, tip = p
    _, gc, gs = GROUPS[g]
    rows = "".join(f"<tr><td><span class='dot' style='background:{WK[wk][0]}'></span>{escape(a)}</td><td>{escape(b)}</td></tr>"
                   for a, b, wk in pins)
    return (f"<div class='pc' style='--gc:{gc};--gs:{gs}'><div class='band'><span class='n'>{i}</span><h3>{escape(name)}</h3></div>"
            f"<div class='body'><div class='img'>{pic(key)}</div><div class='info'>"
            f"<p><span class='k'>What it does</span>{escape(job)}</p>"
            f"<p><span class='k'>How to recognise it</span>{escape(looks)}</p>"
            f"<p><span class='k'>Real size</span>{escape(size)}</p>"
            f"<span class='k' style='font-weight:800;color:{gc};font-size:7.5pt;letter-spacing:.06em;text-transform:uppercase'>Connections</span>"
            f"<table class='pins2'>{rows}</table><div class='tipb'>💡 {escape(tip)}</div></div></div></div>")


def figure(svg: str, caption: str = "") -> str:
    return f"<figure>{svg}{f'<figcaption>{caption}</figcaption>' if caption else ''}</figure>"


def build_html() -> str:
    css = (HERE / "style.css").read_text() + CSS_EXTRA
    legend = "".join(f'<span><i style="background:{c}"></i>{t}</span>' for c, t in (
        (W["5v"], "5 V"), (W["3v3"], "3.3 V"), (W["gnd"], "GND"), (W["sda"], "SDA"), (W["scl"], "SCL"),
        (W["bat"], "battery +"), (W["mot"], "motor"), (W["pwm"], "PWM speed"), (W["sig1"], "signal"), (W["audio"], "audio")))
    H = []
    coll = "".join(f"<div>{pic(k)}<span>{escape(n.split(' (')[0])}</span></div>" for k, n in (
        ("pi", "Raspberry Pi 4"), ("hc", "HC-SR04"), ("imu", "MPU6050"), ("aht", "AHT20 + BMP280"), ("pbank", "Power bank"), ("bat2", "Motor battery"),
        ("l298n", "L298N"), ("chassis", "4WD chassis"), ("webcam", "USB webcam"), ("pam", "PAM8403"), ("spk", "Speaker"), ("motor", "TT motor")))
    H.append(f"""<section class="cover2">
<div class="kicker" style="letter-spacing:.18em;font-size:9pt;font-weight:700;color:#9cc7ff">RAQIB · AI INSPECTION ROBOT · RELIABLE BUDGET BUILD</div>
<h1>Parts &amp; Wiring Atlas</h1>
<p class="sub">Every sensor and board in colour with its name and real size, the Raspberry Pi pin by pin, the robot's structure layer by
layer, and how each part is connected.</p>
<div class="collage">{coll}</div>
<div class="covermeta"><div><b>Ahmed Mahram Saeed Saeed Hadi</b><br>Final-year IoT project · UNISIRAJ</div>
<div style="text-align:right">Atlas 1.1 · October 2026<br>Matches the Raqib software 2.5 and the build guide</div></div></section>""")
    H.append("""<section class="page toc"><h2>Inside this atlas</h2><ol class="tocl">
<li><b>Every part</b> - """ + str(len(PARTS)) + """ parts in six colour groups, each with a big picture, its name, how to recognise it and where its pins go</li>
<li><b>The boards</b> - the Raspberry Pi 4 and its ports, all 40 pins, and close-ups of the L298N, HC-SR04, power bank, MPU6050, AHT20 and the hub board</li>
<li><b>The robot's structure</b> - exploded view, side, top, bottom and front views</li>
<li><b>How everything connects</b> - the system map, one wiring diagram per group, the complete harness and a wire-by-wire table</li>
</ol>
<div class="note"><b>About the pictures:</b> they are drawings of the common versions of each board, in their real colours and layout.
Your board may be a slightly different colour or have its pins in another order: <b>always read the labels printed on the board</b>.</div>
<div class="note"><b>Wire colours used in every diagram</b><div class="legend2">""" + legend + """</div>
Use the same colours for your real wires where you can: mistakes become easy to spot.</div>
<div class="note"><b>Colour groups:</b> """ + " · ".join(f"<b style='color:{c}'>{escape(n)}</b>" for n, c, _ in GROUPS.values()) + """</div>
</section>""")
    # A. parts
    n = 0
    for g, (gname, gc, gs) in GROUPS.items():
        items = [p for p in PARTS if p[1] == g]
        cards = []
        for p in items:
            n += 1
            cards.append(part_card(n, p))
        intro = {"brain": "The computer and its memory card.", "power": "Two separate batteries: a USB power bank for the Pi, a 2 × 18650 pack for the motors. One shared ground.",
                 "moving": "Body, wheels and the motor driver.", "sensing": "Distance, turning and climate sensors.",
                 "media": "Seeing, hearing and speaking.", "build": "What holds the robot and its wires together."}[g]
        H.append(f"<section class='page'><div class='ghead' style='background:{gc}'><h2>{escape(gname)}</h2><p>{escape(intro)}</p></div>"
                 + "".join(cards) + "</section>")
    # B. boards
    H.append(f"""<section class="page"><h2 class="sec"><span>B</span>The boards</h2>
<p>The Raspberry Pi 4 is the centre of everything: every other part connects to its pins or ports.</p>
{figure(fig_pi_labelled(), "The Raspberry Pi 4 and what each port is used for in this robot.")}</section>
<section class="page"><h3>All 40 pins of the Raspberry Pi header</h3>
<p>Pin numbers are counted on the board (1-40). Coloured pins are used by the robot; grey ones are free.</p>
{figure(fig_pinout_full(), "The 40-pin header, top view, USB ports pointing down the page.")}</section>
<section class="page"><h3>Board close-ups</h3>{figure(fig_closeup_l298n(), "The L298N: battery and motors on the screw terminals, the Pi on the 6 pins.")}
{figure(fig_closeup_small(), "HC-SR04, power bank, MPU6050 and AHT20: every pin and where it goes.")}</section>
<section class="page"><h3>The hub board (you make it)</h3>{figure(D.fig_hub(), "Five rails on top, the three sonar Echo dividers below.")}
<div class="note">The hub board saves wires: the Pi gives 5 V, 3.3 V, GND, SDA and SCL to the hub once, and every sensor plugs into
the hub. The dividers turn the sonars' 5 V Echo signals into a safe 3.3 V.</div></section>""")
    # C. structure
    H.append(f"""<section class="page"><h2 class="sec"><span>C</span>The robot's structure</h2>
<p>Two acrylic decks on standoffs. The motor battery hangs underneath, the motors, the power bank and the motor driver sit on the bottom deck, the
computer and sensors on the top deck, and the distance sensors and webcam face forward.</p>
{figure(fig_exploded(), "Exploded view: 1 motor battery, 2 bottom deck, 3 top deck, 4 front sensors.")}</section>
<section class="page">{figure(D.fig_layout_side(), "Side view.")}{figure(fig_front(), "Front view: three distance sensors fanned out, the webcam above.")}</section>
<section class="page">{figure(D.fig_layout_top(), "Top deck.")}{figure(fig_layout_bottom(), "Bottom deck.")}</section>""")
    # D. connections
    H.append(f"""<section class="page"><h2 class="sec"><span>D</span>How everything connects</h2>
<p>Start with the big picture, then one diagram per group. The pin numbers are the physical pins of the Raspberry Pi header.</p>
{figure(D.fig_overview(), "The system: five groups of parts around the Raspberry Pi.")}
{figure(D.fig_full_harness(), "The complete harness: every block and the wires between them.")}</section>
<section class="page"><h3>1 · Power</h3>{figure(D.fig_power(), "Power bank → Pi USB-C; 2 × 18650 → L298N; L298N GND → Pi pin 9 (common ground).")}</section>
<section class="page"><h3>2 · I²C sensors</h3>{figure(D.fig_i2c(), "MPU6050 and AHT20 + BMP280 share four wires.")}</section>
<section class="page"><h3>3 · Motors</h3>{figure(D.fig_motors(), "Direction on pins 11/13/15/16, speed on pins 33/35.")}</section>
<section class="page"><h3>4 · Distance sensors</h3>{figure(D.fig_sonar(), "Each Echo goes through a 1 kΩ / 2 kΩ divider.")}</section>
<section class="page"><h3>5 · Camera, microphone and speaker</h3>{figure(D.fig_audio(), "Webcam on USB; Pi audio jack → PAM8403 → speaker.")}</section>
<section class="page"><h3>Every wire, one by one</h3>
<p>The same list the robot software and the app's Wiring Bench use. Tick each wire off as you connect it.</p>{wire_table()}</section>""")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Raqib Parts and Wiring Atlas</title><style>{css}</style></head><body>{''.join(H)}</body></html>"


def main():
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    js = HERE / "_atlas_pdf.js"
    js.write_text(f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://{OUT_HTML}'); await p.waitForTimeout(500);
  await p.pdf({{ path: '{OUT_PDF}', format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-family:Inter,sans-serif;font-size:8px;color:#8a949c;width:100%;padding:0 14mm;display:flex;justify-content:space-between"><span>Raqib · parts and wiring atlas</span><span class="pageNumber"></span></div>',
    margin: {{ top: '12mm', bottom: '14mm', left: '12mm', right: '12mm' }} }});
  await b.close(); }})();""")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js)], check=True, env={**os.environ, "NODE_PATH": npm_root})
    js.unlink()
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    main()
