"""All figures of the Raqib build guide (component pictures, wiring diagrams, layouts)."""
from __future__ import annotations

import math

from draw import (aht20, buck_xl4015, caster, power_bank, webcam, BANDS, BLUE, BLUE_D, GOLD, INK, LINE, MUTED, PCB, PCB_D, PI_PINS, S, SILK, W, ads1115, battery_2s,
                  bme680, board, cell_18650, chip, encoder_disc, gpio_header, gy521, hcsr04, header_row, jumper, l298n,
                  mq135, multimeter, pam8403, pca9685, pi4, pi_camera, resistor, rounded_path, sd_card, sg90,
                  slot_encoder, soldering_iron, speaker, tag, tt_motor, ups_3s, usb_mic, usb_soundcard, wire)

FIG_W = 700


def _route_from_pin(hdr, pin, lane, to, color, s, sw=3.0, via_y=None):
    """Wire from a header pin straight out to x=lane, then to the target point (tx, ty).
    via_y: approach the target vertically from this y (target pins that point down)."""
    px, py, side = hdr[pin]
    tx, ty = to
    pts = [(px, py), (lane, py)]
    if via_y is not None:
        pts += [(lane, via_y), (tx, via_y), (tx, ty)]
    else:
        pts += [(lane, ty), (tx, ty)]
    wire(s, pts, color, sw)


def pin_label(s, hdr, pin, color, text=None, dx=10):
    px, py, side = hdr[pin]
    t = text or f"{pin} · {PI_PINS[pin]}"
    if side == "L":
        tag(s, px - 22 - dx, py + 3.5, t, color, 8, "end")
    else:
        tag(s, px + 22 + dx, py + 3.5, t, color, 8, "start")


# ======================================================================= component pictures (one per card)
def fig_component(name: str) -> str:
    sizes = {"pi": (320, 230), "sd": (90, 90), "ups": (290, 190), "bat2": (200, 110), "chassis": (330, 220), "motor": (200, 120),
             "l298n": (200, 190), "pca": (280, 110), "servo": (300, 140), "cam": (130, 170), "hc": (180, 110), "enc": (210, 120),
             "imu": (150, 120), "bme": (120, 110), "mq": (140, 120), "ads": (170, 110), "mic": (130, 60), "usbsnd": (130, 60),
             "pam": (130, 80), "spk": (110, 110), "res": (230, 135),
             "aht": (115, 105), "webcam": (160, 110), "buck": (165, 85), "wires": (190, 110), "tools": (330, 180), "hub": (330, 200),
             "standoff": (220, 110), "pbank": (190, 96), "res2": (230, 70)}
    w, h = sizes[name]
    s = S(w, h)
    if name == "pi":
        pi4(s, 10, 10, 1.0)
    elif name == "sd":
        sd_card(s, 18, 10)
    elif name == "ups":
        ups_3s(s, 8, 8, 1.0)
    elif name == "bat2":
        battery_2s(s, 6, 8, 1.0)
    elif name == "chassis":
        chassis_top(s, 10, 10, 1.0, bare=True)
    elif name == "aht":
        aht20(s, 18, 8, 1.0)
    elif name == "webcam":
        webcam(s, 10, 6, 1.0)
    elif name == "buck":
        buck_xl4015(s, 12, 8, 1.0)
    elif name == "motor":
        tt_motor(s, 40, 70, 1.0)
    elif name == "pbank":
        power_bank(s, 10, 9, 1.0)
    elif name == "res2":
        for i, (k, lab) in enumerate((("1k", "1 kΩ  brown-black-red  (x 3)"), ("2k", "2 kΩ  red-black-red  (x 3)"))):
            resistor(s, 10, 20 + i * 28, 80, 20 + i * 28, BANDS[k])
            s.text(88, 24 + i * 28, lab, 9, INK, "start", 600)
    elif name == "l298n":
        l298n(s, 15, 8, 1.0)
    elif name == "pca":
        pca9685(s, 10, 6, 1.06)
    elif name == "servo":
        sg90(s, 20, 50, 1.0, "pan")
    elif name == "cam":
        pi_camera(s, 22, 6, 1.0)
    elif name == "hc":
        hcsr04(s, 20, 8, 1.0)
    elif name == "enc":
        slot_encoder(s, 20, 30, 1.2)
        encoder_disc(s, 165, 48, 30)
    elif name == "imu":
        gy521(s, 18, 10, 1.0)
    elif name == "bme":
        bme680(s, 18, 10, 1.0)
    elif name == "mq":
        mq135(s, 20, 10, 1.0)
    elif name == "ads":
        ads1115(s, 20, 10, 1.0)
    elif name == "mic":
        usb_mic(s, 20, 14, 1.0)
    elif name == "usbsnd":
        usb_soundcard(s, 20, 14, 1.0)
    elif name == "pam":
        pam8403(s, 20, 12, 1.0)
    elif name == "spk":
        speaker(s, 55, 45, 34)
    elif name == "res":
        for i, (k, lab) in enumerate((("1k", "1 kΩ  brown-black-red"), ("2k", "2 kΩ  red-black-red"),
                                      ("10k", "10 kΩ brown-black-orange"), ("20k", "20 kΩ red-black-orange"),
                                      ("4k7", "4.7 kΩ yellow-violet-red"))):
            resistor(s, 10, 18 + i * 25, 80, 18 + i * 25, BANDS[k])
            s.text(88, 22 + i * 25, lab, 8.5, INK, "start", 600)
    elif name == "wires":
        jumper(s, 20, 20, "F-F", W["5v"])
        jumper(s, 20, 70, "M-F", W["sda"])
    elif name == "tools":
        multimeter(s, 10, 20)
        soldering_iron(s, 120, 40)
        s.text(215, 110, "soldering iron + solder", 9, MUTED, "middle", 600)
        s.text(55, 175, "multimeter", 9, MUTED, "middle", 600)
        # screwdriver
        s.rect(130, 140, 60, 14, "#e23b2e", rx=6)
        s.rect(190, 145, 70, 4, "#aab0b5")
        s.text(220, 170, "small screwdrivers", 9, MUTED, "middle", 600)
    elif name == "hub":
        hub_board(s, 10, 10, 1.0, compact=True)
    elif name == "standoff":
        for i in range(4):
            x = 20 + i * 48
            s.path(f"M{x} 20 l14 0 l4 8 l0 44 l-4 8 l-14 0 l-4 -8 l0 -44 z", "#d4b24c", "#9c7f2a", 1.2)
            s.rect(x + 3, 6, 8, 14, "#b9b9b9", rx=1)
        s.text(110, 105, "M3 standoffs 35-40 mm + screws", 9, MUTED, "middle", 600)
    return s.svg("comp")




# ======================================================================= the perfboard "hub"
def hub_board(s, x, y, sc=1.0, compact=False):
    """Hand-made distribution board: 5 power/bus rails + the voltage dividers. Returns pin points."""
    k = sc
    w, h = 310 * k, 180 * k
    s.rect(x, y, w, h, "#d8b77a", "#9c7f42", rx=6, sw=1.5)
    for gx in range(int(w // (10 * k))):
        for gy in range(int(h // (10 * k))):
            s.circle(x + 6 * k + gx * 10 * k, y + 6 * k + gy * 10 * k, 1.1 * k, "#9c7f42")
    rails = [("5V", W["5v"]), ("3V3", W["3v3"]), ("GND", W["gnd"]), ("SDA", W["sda"]), ("SCL", W["scl"])]
    pts = {}
    for i, (name, col) in enumerate(rails):
        ry = y + (16 + i * 13) * k
        s.line(x + 40 * k, ry, x + w - 10 * k, ry, col, 3.2 * k)
        s.text(x + 34 * k, ry + 3, name, 8 * k, col if name != "GND" else "#2a2e31", "end", 800)
        pts[name] = (x + 46 * k, ry)
        pts[name + "_r"] = (x + w - 14 * k, ry)
    if compact:
        s.text(x + w / 2, y + h - 12 * k, "+ 3 echo dividers (1k / 2k)", 8.5 * k, "#5b4520", "middle", 700)
        return pts
    # three ECHO dividers + MQ divider, drawn vertically under the rails
    names = [("ECHO L", "1k", "2k"), ("ECHO C", "1k", "2k"), ("ECHO R", "1k", "2k")]
    for i, (lab, top, bot) in enumerate(names):
        cx = x + (80 + i * 80) * k
        y_in = y + 96 * k
        y_mid = y + 128 * k
        y_gnd = y + 162 * k
        s.text(cx, y_in - 6 * k, lab, 7.5 * k, INK, "middle", 800)
        resistor(s, cx, y_in, cx, y_mid, BANDS[top])
        resistor(s, cx, y_mid, cx, y_gnd, BANDS[bot])
        s.circle(cx, y_mid, 3 * k, "#2a2e31")
        s.text(cx + 8 * k, y_in + 18 * k, top, 7 * k, INK, "start", 700)
        s.text(cx + 8 * k, y_mid + 18 * k, {"4k7": "4.7k"}.get(bot, bot), 7 * k, INK, "start", 700)
        s.line(cx, y_gnd, cx, y_gnd + 6 * k, "#2a2e31", 2)
        s.text(cx, y_gnd + 14 * k, "GND", 6.5 * k, "#2a2e31", "middle", 700)
        pts[f"in{i}"] = (cx, y_in)
        pts[f"mid{i}"] = (cx, y_mid)
    return pts


# ======================================================================= system overview
def fig_overview() -> str:
    s = S(FIG_W, 430)

    def box(x, y, w, h, title, sub, col, fg="#fff"):
        s.rect(x, y, w, h, col, rx=12)
        s.text(x + w / 2, y + 24, title, 13, fg, "middle", 800)
        for i, line in enumerate(sub):
            s.text(x + w / 2, y + 42 + i * 14, line, 9.5, fg, "middle", 500)

    box(250, 150, 200, 110, "Raspberry Pi 4", ["robot program + its own server", "AI agent · Wi-Fi to the phone", "USB webcam + mic · speaker"], PCB)
    box(20, 20, 200, 90, "Power", ["power bank → Pi (5 V)", "2x18650 pack → motors"], "#c0392b")
    box(480, 20, 200, 90, "Phone app (APK)", ["Wi-Fi: hotspot, home, or", "the robot's own 'Raqib-Robot'"], "#2d6be0")
    box(20, 300, 200, 110, "Moving", ["4WD chassis, 4 TT motors", "L298N: one channel per side", "speed from Pi pins 33 / 35"], "#8d5a3b")
    box(250, 300, 200, 110, "Seeing obstacles", ["3x HC-SR04 sonar", "MPU6050 motion sensor", "distance: motor time"], "#1e9e55")
    box(480, 300, 200, 110, "Measuring the room", ["AHT20 + BMP280 climate", "webcam microphone", "camera + AI"], "#8a55e8")
    box(20, 150, 200, 110, "Sensor hub board", ["your perfboard: 5V, 3V3, GND,", "SDA, SCL rails + dividers"], "#b07d2c")
    for (x1, y1, x2, y2, c, lab) in ((120, 110, 300, 150, W["5v"], "5 V"), (580, 110, 400, 150, W["sda"], "Wi-Fi"),
                                     (220, 205, 250, 205, W["scl"], "I²C + GPIO"), (120, 260, 120, 300, W["gnd"], ""),
                                     (350, 260, 350, 300, W["sig1"], "GPIO"), (440, 260, 560, 300, W["sig2"], "I²C"),
                                     (300, 260, 180, 300, W["mot"], "GPIO")):
        s.line(x1, y1, x2, y2, c, 3)
        if lab:
            tag(s, (x1 + x2) / 2, (y1 + y2) / 2 + 4, lab, c, 8, "middle")
    return s.svg()


# ======================================================================= Pi header map
def fig_pi_header() -> str:
    used = {1: W["3v3"], 2: W["5v"], 3: W["sda"], 5: W["scl"], 6: W["gnd"], 9: W["gnd"], 11: W["sig1"], 13: W["sig1"],
            15: W["sig2"], 16: W["sig2"], 18: W["sig3"], 22: W["sig3"], 32: W["sig5"], 33: W["pwm"], 35: "#c98a00",
            36: W["sig5"], 38: W["sig6"], 40: W["sig6"]}
    what = {1: "3.3 V → hub 3V3 rail", 2: "5 V → hub 5V rail", 3: "SDA → hub SDA rail", 5: "SCL → hub SCL rail",
            6: "GND → hub GND rail", 9: "GND → L298N GND (common ground)", 11: "L298N IN1 (left motors)",
            13: "L298N IN2 (left motors)", 15: "L298N IN3 (right motors)", 16: "L298N IN4 (right motors)",
            18: "sonar CENTRE Trig", 22: "sonar CENTRE Echo (via divider)", 32: "sonar LEFT Trig",
            33: "L298N ENA (left speed, PWM)", 35: "L298N ENB (right speed, PWM)", 36: "sonar LEFT Echo (via divider)",
            38: "sonar RIGHT Trig", 40: "sonar RIGHT Echo (via divider)"}
    s = S(FIG_W, 440)
    hdr = gpio_header(s, 327, 58, used, pitch=17.5, labels="none")
    for n, txt in what.items():
        px, py, side = hdr[n]
        col = used[n]
        if side == "L":
            s.line(px - 8, py, 300, py, col, 1.5)
            s.text(296, py + 3.5, f"{PI_PINS[n]}  ·  {txt}", 9, col if n not in (6, 9, 33) else INK, "end", 700)
        else:
            s.line(px + 8, py, 400, py, col, 1.5)
            s.text(404, py + 3.5, f"{PI_PINS[n]}  ·  {txt}", 9, col if n not in (6, 9, 33) else INK, "start", 700)
    s.text(350, 16, "pin 1 is the square pad, at the corner nearest the microSD card", 9, MUTED, "middle", 600)
    s.text(350, 432, "Odd pins (1, 3, 5 …) are the row on the inside of the board; even pins the row along the edge.", 9, MUTED, "middle", 500)
    return s.svg()


# ======================================================================= power
def fig_power() -> str:
    s = S(FIG_W, 560)
    s.text(20, 26, "Motor battery 2 × 18650 (7.4 V): motors only", 10, INK, "start", 800)
    bat = battery_2s(s, 20, 40, 1.0)
    s.text(300, 26, "L298N motor driver", 10, INK, "start", 800)
    l2 = l298n(s, 300, 36, 0.9)
    (bpx, bpy), (bnx, bny) = bat["+"], bat["-"]
    wire(s, [(bpx, bpy), (240, bpy), (240, 230), (l2["+12V"][0], 230), l2["+12V"]], W["bat"], 3.4, r=6)
    wire(s, [(bnx, bny), (226, bny), (226, 244), (l2["GND"][0], 244), l2["GND"]], W["gnd"], 3.4, r=6)
    tag(s, 120, 162, "+ → +12V · − → GND", W["bat"], 8.5, "middle")
    s.text(20, 318, "USB power bank 10,000 mAh (5 V 3 A): the Pi only", 10, INK, "start", 800)
    pb = power_bank(s, 20, 334, 1.0)
    pk = 0.7
    k = 3.4 * pk
    PX, PY = 420, 300
    pins = pi4(s, PX, PY, pk)
    s.text(PX, PY - 10, "Raspberry Pi 4", 10, INK, "start", 800)
    usbc = (PX + 11.5 * k, PY + 56 * k + 2)
    ux, uy = pb["usbc"]
    wire(s, [(ux, uy), (ux + 30, uy), (ux + 30, 480), (usbc[0], 480), usbc], "#555b62", 7, r=12)
    tag(s, 300, 500, "short USB-C cable: power bank → Pi USB-C", "#555b62", 8.5, "middle")
    # common ground L298N -> Pi pin 9
    p9 = pins[9]
    wire(s, [l2["GND"], (l2["GND"][0], 256), (690, 256), (690, p9[1] - 14), (p9[0], p9[1] - 14), p9], W["gnd"], 2.8, r=8)
    tag(s, 560, 270, "L298N GND → Pi pin 9: COMMON GROUND (essential)", W["gnd"], 8.5, "middle")
    s.text(20, 532, "Two batteries: motor current spikes can never restart the Pi, and there is no voltage to set by hand.", 9, MUTED)
    s.text(20, 548, "The one wire that joins the two systems is the common ground; without it the motors ignore the Pi.", 9, INK, "start", 700)
    return s.svg()


# ======================================================================= hub
def fig_hub() -> str:
    s = S(FIG_W, 300)
    p = hub_board(s, 190, 20, 1.0)
    hdr_pts = {"5V": (60, 36), "3V3": (60, 49), "GND": (60, 62), "SDA": (60, 75), "SCL": (60, 88)}
    lab = {"5V": "Pi pin 2 (5V)", "3V3": "Pi pin 1 (3.3V)", "GND": "Pi pin 6 (GND)", "SDA": "Pi pin 3 (SDA)", "SCL": "Pi pin 5 (SCL)"}
    col = {"5V": W["5v"], "3V3": W["3v3"], "GND": W["gnd"], "SDA": W["sda"], "SCL": W["scl"]}
    for i, r in enumerate(("5V", "3V3", "GND", "SDA", "SCL")):
        tx, ty = p[r]
        wire(s, [(120, ty), (tx, ty)], col[r], 3)
        tag(s, 115, ty + 3.5, lab[r], col[r], 8, "end")
    s.text(20, 150, "Each divider:", 10, INK, "start", 800)
    for i, t in enumerate(["sonar Echo (5 V) enters at the top", "top resistor 1 kΩ", "middle point → Pi pin",
                           "bottom resistor 2 kΩ → GND", "5 V × 2/3 = 3.3 V: safe"]):
        s.text(20, 168 + i * 15, f"• {t}", 9.5, INK)
    s.text(505, 276, "Solder the rails as bare wire along the strips;", 8.5, MUTED, "middle")
    s.text(505, 288, "every module plugs into the rails with jumper wires.", 8.5, MUTED, "middle")
    return s.svg()


# ======================================================================= I2C
def fig_i2c() -> str:
    s = S(FIG_W, 360)
    rails = [("3V3", W["3v3"]), ("GND", W["gnd"]), ("SDA", W["sda"]), ("SCL", W["scl"])]
    for i, (nm, c) in enumerate(rails):
        x = 24 + i * 24
        s.line(x, 30, x, 250, c, 4)
        s.text(x, 262, nm, 8, c if nm != "GND" else INK, "middle", 800)
    s.text(60, 276, "hub rails", 9, MUTED, "middle", 700)
    railx = {nm: 24 + i * 24 for i, (nm, _) in enumerate(rails)}
    col = dict(rails)
    devices = [
        ("MPU6050  (0x68)", lambda x, y: gy521(s, x, y, 1.2), 170, 40, {"VCC": "3V3", "GND": "GND", "SDA": "SDA", "SCL": "SCL"}),
        ("AHT20 + BMP280  (0x38 + 0x77)", lambda x, y: aht20(s, x, y, 1.4), 420, 40, {"VIN": "3V3", "GND": "GND", "SDA": "SDA", "SCL": "SCL"}),
    ]
    lane = 0
    for title, fn, x, y, conn in devices:
        pins = fn(x, y)
        s.text(x, y - 8, title, 10, INK, "start", 800)
        for pin, rail in conn.items():
            px, py = pins[pin]
            yy = 170 + lane * 8
            lane += 1
            wire(s, [(px, py), (px, yy), (railx[rail], yy)], col[rail], 2.4, r=5)
    s.text(150, 296, "• Both boards join the same four rails: 3.3 V, GND, SDA, SCL (Pi pins 1, 6, 3, 5).", 10, INK)
    s.text(150, 312, "• Each answers to its own address: MPU6050 0x68, AHT20 0x38, BMP280 0x77 (or 0x76).", 10, INK)
    s.text(150, 328, "• Test: python -m hwtest.i2c_scan lists every address found.", 10, INK)
    return s.svg()


# ======================================================================= motors
def fig_motors() -> str:
    s = S(FIG_W, 590)
    used = {9: W["gnd"], 11: W["sig1"], 13: W["sig2"], 15: W["sig3"], 16: W["sig4"], 33: W["pwm"], 35: "#c98a00"}
    hdr = gpio_header(s, 40, 30, used, pitch=13, labels="none")
    l2 = l298n(s, 300, 160, 1.0)
    k = 0.8
    for (mx, label) in ((160, "LEFT pair (front + rear)"), (520, "RIGHT pair (front + rear)")):
        s.text(mx, 34, label, 8.5, INK, "start", 800)
        tt_motor(s, mx, 44, k, wheel=False)
        tt_motor(s, mx, 84, k, wheel=False)
    for i, (o, c) in enumerate((("OUT1", "#e23b2e"), ("OUT2", "#2a2e31"))):
        x0, y0 = l2[o]
        tabs = [(160 + 94 * k, my + (7.5 if i == 0 else 14.5) * k) for my in (44, 84)]
        lane = 284 - i * 8
        wire(s, [(x0, y0), (lane, y0), (lane, tabs[0][1]), tabs[0]], c, 2.6, r=4)
        wire(s, [(lane, tabs[0][1]), (lane, tabs[1][1]), tabs[1]], c, 2.6, r=4)
        s.circle(lane, tabs[1][1], 3, c)
    for i, (o, c) in enumerate((("OUT3", "#e23b2e"), ("OUT4", "#2a2e31"))):
        x0, y0 = l2[o]
        tabs = [(520 + 94 * k, my + (7.5 if i == 0 else 14.5) * k) for my in (44, 84)]
        lane = tabs[0][0] + 14 + i * 8
        wire(s, [(x0, y0), (500 + i * 8, y0), (500 + i * 8, 130 + i * 8), (lane, 130 + i * 8), (lane, tabs[0][1]), tabs[0]], c, 2.6, r=4)
        wire(s, [(lane, tabs[1][1]), tabs[1]], c, 2.6, r=4)
        s.circle(lane, tabs[1][1], 3, c)
    tag(s, 245, 150, "OUT1 / OUT2", W["mot"], 7.5, "middle")
    tag(s, 580, 150, "OUT3 / OUT4", W["mot"], 7.5, "middle")
    # GPIO -> IN1..IN4 and ENA/ENB, all routed under the L298N
    routes = [(11, "IN1"), (13, "IN2"), (15, "IN3"), (16, "IN4"), (33, "ENA"), (35, "ENB")]
    lanes_l = {11: 26, 13: 22, 15: 18, 33: 14, 35: 10}
    for i, (pin, inp) in enumerate(routes):
        px, py, side = hdr[pin]
        tx, ty = l2[inp]
        yy = 350 + i * 9
        xo = lanes_l.get(pin, 0) if side == "L" else 128
        wire(s, [(px, py), (xo, py), (xo, yy), (tx, yy), (tx, ty)], used[pin], 2.6, r=5)
    labels = [(11, "IN1"), (13, "IN2"), (15, "IN3"), (16, "IN4"), (33, "ENA  (left speed)"), (35, "ENB  (right speed)")]
    for i, (pin, inp) in enumerate(labels):
        tag(s, 160 + (i % 2) * 250, 432 + (i // 2) * 20, f"pin {pin} · {PI_PINS[pin]} → {inp}", used[pin], 8, "start",
            fg=INK if pin == 33 else "#fff")
    px, py, _ = hdr[9]
    wire(s, [(px, py), (4, py), (4, 500), (l2["GND"][0], 500), l2["GND"]], W["gnd"], 2.6, r=6)
    tag(s, 210, 515, "pin 9 GND → L298N GND (signal ground)", W["gnd"], 8, "middle")
    s.text(20, 540, "• Pull the ENA and ENB jumpers off: the Pi sets the speed on pins 33 and 35. Keep the 5V-EN jumper.", 9.5, INK)
    s.text(20, 556, "• +12V and GND come from the battery (power page). Leave the L298N's +5V terminal unconnected.", 9.5, INK)
    s.text(20, 572, "• Each side's two motors are joined (red to red, black to black) and run together: skid steering.", 9.5, INK)
    return s.svg()


# ======================================================================= servos + camera


# ======================================================================= ultrasonics
def fig_sonar() -> str:
    s = S(FIG_W, 600)
    used = {18: W["sig3"], 22: W["sig3"], 32: W["sig5"], 36: W["sig5"], 38: W["sig6"], 40: W["sig6"]}
    hdr = gpio_header(s, 610, 40, used, pitch=12.5, labels="none")
    sensors = [("LEFT", 20, 20, 32, 36, W["sig5"]), ("CENTRE", 20, 190, 18, 22, W["sig3"]), ("RIGHT", 20, 360, 38, 40, W["sig6"])]
    for i, (name, x, y, trig, echo, c) in enumerate(sensors):
        p = hcsr04(s, x, y, 1.0, f"HC-SR04  {name}")
        # divider next to the sensor
        dx = 230 + i * 0
        top_y, mid_y, bot_y = y + 20, y + 62, y + 104
        resistor(s, dx, top_y, dx, mid_y, BANDS["1k"])
        resistor(s, dx, mid_y, dx, bot_y, BANDS["2k"])
        s.text(dx + 10, top_y + 24, "1 kΩ", 8, INK, "start", 700)
        s.text(dx + 10, mid_y + 26, "2 kΩ", 8, INK, "start", 700)
        s.circle(dx, mid_y, 3.4, INK)
        # VCC/GND tags
        vx, vy = p["VCC"]
        gx, gy = p["Gnd"]
        wire(s, [(vx, vy), (vx, vy + 26)], W["5v"], 2.6)
        tag(s, vx, vy + 40, "5V", W["5v"], 8, "middle")
        wire(s, [(gx, gy), (gx, gy + 26)], W["gnd"], 2.6)
        tag(s, gx, gy + 40, "GND", W["gnd"], 8, "middle")
        wire(s, [(dx, bot_y), (dx, bot_y + 18)], W["gnd"], 2.6)
        tag(s, dx, bot_y + 30, "GND", W["gnd"], 8, "middle")
        # echo -> top of divider
        ex, ey = p["Echo"]
        wire(s, [(ex, ey), (ex, ey + 14), (200, ey + 14), (200, top_y), (dx, top_y)], "#7a7f87", 2.6, r=5)
        # trig -> pi
        tx, ty = p["Trig"]
        hx, hy, side = hdr[trig]
        lane = 330 + i * 18
        wire(s, [(tx, ty), (tx, ty + 18 + 0), (300 + i * 6, ty + 18), (300 + i * 6, y + 6 + 0), (lane, y + 6), (lane, hy), (hx, hy)] if False else
             [(tx, ty), (tx, ty + 20), (lane, ty + 20), (lane, hy), (hx, hy)], c, 2.6, r=6)
        # mid -> echo pin
        mx, my2 = dx, mid_y
        hx2, hy2, side2 = hdr[echo]
        lane2 = 400 + i * 18 if side2 == "L" else 400 + i * 18
        wire(s, [(mx, my2), (lane2, my2), (lane2, hy2), (hx2, hy2)] if side2 == "L" else
             [(mx, my2), (lane2, my2), (lane2, 8 + i * 7), (674 + i * 8, 8 + i * 7), (674 + i * 8, hy2), (hx2, hy2)], c, 2.6, r=6)
        tag(s, 520, 470 + i * 18 + 10 - 470 + 470 + 0, "", c, 1) if False else None
    rows = [("LEFT", "Trig pin 32 (GPIO12)", "Echo pin 36 (GPIO16)", W["sig5"]), ("CENTRE", "Trig pin 18 (GPIO24)", "Echo pin 22 (GPIO25)", W["sig3"]),
            ("RIGHT", "Trig pin 38 (GPIO20)", "Echo pin 40 (GPIO21)", W["sig6"])]
    for i, (n, t, e, c) in enumerate(rows):
        tag(s, 290, 535 + i * 20, f"{n}:  {t}  ·  {e} through the divider", c, 8.5, "start")
    s.text(290, 516, "Echo is 5 V. The 1 kΩ / 2 kΩ divider makes it 3.3 V for the Pi.", 9, INK, "start", 700)
    return s.svg()


# ======================================================================= encoders


# ======================================================================= gas


# ======================================================================= audio + camera
def fig_audio() -> str:
    s = S(FIG_W, 400)
    x0, y0, sc = 20, 70, 0.85
    pi4(s, x0, y0, sc)
    k = 3.4 * sc
    cam = webcam(s, 420, 6, 0.95)
    s.text(420, 120, "USB webcam with built-in mic", 9, INK, "start", 800)
    usb_end = x0 + 85 * k + 4
    y_usb3 = y0 + 25 * k
    ux, uy = cam["usb"]
    wire(s, [(ux, uy), (ux + 18, uy), (ux + 18, y_usb3), (usb_end, y_usb3)], "#555b62", 4.5, r=8)
    tag(s, 330, y_usb3 - 10, "webcam → any USB port", "#555b62", 8, "middle")
    jack = (x0 + 54 * k, y0 + 56 * k)
    pam = pam8403(s, 330, 290, 0.95)
    s.text(330, 282, "PAM8403 amplifier", 9, INK, "start", 800)
    speaker(s, 580, 330, 28)
    wire(s, [jack, (jack[0], 270), (300, 270), (300, pam["L"][1]), pam["L"]], W["audio"], 2.6, r=6)
    wire(s, [(jack[0] + 6, jack[1]), (jack[0] + 6, 262), (310, 262), (310, pam["G"][1]), pam["G"]], W["gnd"], 2.2, r=6)
    tag(s, jack[0] - 10, 300, "Pi audio jack → 3.5 mm cable", W["audio"], 8, "end")
    tag(s, jack[0] - 10, 318, "tip → L, sleeve → G", W["audio"], 8, "end")
    wire(s, [pam["out L+"], (490, pam["out L+"][1]), (490, 318), (552, 318)], "#e23b2e", 2.4, r=4)
    wire(s, [pam["out L-"], (480, pam["out L-"][1]), (480, 342), (552, 342)], "#2a2e31", 2.4, r=4)
    wire(s, [pam["5V"], (300, pam["5V"][1]), (300, 380)], W["5v"], 2.4)
    tag(s, 300, 393, "PAM8403 5V + GND from the hub", W["5v"], 8, "middle")
    s.text(630, 380, "speaker 3 W", 8.5, MUTED, "middle", 600)
    return s.svg()


# ======================================================================= chassis / layout
def chassis_top(s, x, y, sc=1.0, bare=False):
    k = sc
    w, h = 300 * k, 190 * k
    # wheels
    for wx, wy in ((x + 30 * k, y - 2 * k), (x + 210 * k, y - 2 * k), (x + 30 * k, y + h - 24 * k), (x + 210 * k, y + h - 24 * k)):
        s.rect(wx, wy, 60 * k, 26 * k, "#202326", "#111", rx=7)
        for i in range(6):
            s.line(wx + (6 + i * 9) * k, wy, wx + (6 + i * 9) * k, wy + 26 * k, "#3a3f44", 2)
    s.rect(x + 10 * k, y + 22 * k, w - 20 * k, h - 44 * k, "#cfe6f5", "#7fa8c4", rx=14 * k, sw=1.5)
    s.rect(x + 10 * k, y + 22 * k, w - 20 * k, h - 44 * k, "#ffffff", None, rx=14 * k, op=0.35)
    for hx in range(6):
        for hy in range(3):
            s.circle(x + (40 + hx * 45) * k, y + (55 + hy * 40) * k, 3 * k, "#ffffff", "#7fa8c4", 1)
    if bare:
        for mx, my in ((x + 40 * k, y + 26 * k), (x + 196 * k, y + 26 * k), (x + 40 * k, y + h - 48 * k), (x + 196 * k, y + h - 48 * k)):
            s.rect(mx, my, 64 * k, 22 * k, "#f2c230", "#b38a12", rx=3)
        s.text(x + w / 2, y + h / 2 + 4, "acrylic deck · 4 TT motors · 4 wheels", 9 * k, "#33536b", "middle", 700)


def fig_layout_top() -> str:
    s = S(FIG_W, 420)
    x, y = 60, 40
    W_, H_ = 540, 340
    s.rect(x, y, W_, H_, "#e6f1f9", "#7fa8c4", rx=40, sw=2)
    s.text(x + W_ / 2, y - 12, "TOP DECK (seen from above)  ·  front of the robot →", 11, INK, "middle", 800)

    def part(px, py, pw, ph, col, label, sub="", fg="#fff"):
        s.rect(x + px, y + py, pw, ph, col, None, rx=6)
        s.text(x + px + pw / 2, y + py + ph / 2 + (0 if sub else 4), label, 9.5, fg, "middle", 800)
        if sub:
            s.text(x + px + pw / 2, y + py + ph / 2 + 13, sub, 7.5, fg, "middle", 500)

    part(190, 40, 150, 100, PCB, "Raspberry Pi 4", "on standoffs")
    part(30, 70, 140, 140, "#b07d2c", "Sensor hub board", "rails + 3 echo dividers")
    part(190, 160, 90, 60, BLUE, "MPU6050", "flat, centre")
    part(30, 260, 70, 50, "#6b3fa0", "AHT20", "rear edge")
    part(280, 262, 80, 40, PCB, "PAM8403")
    s.circle(x + 405, y + 240, 26, "#2b2f35")
    s.text(x + 405, y + 244, "speaker", 8, "#fff", "middle", 700)
    part(360, 135, 80, 50, "#202326", "webcam", "front, looking out")
    fx = W_ - 20
    for (dy, ang, lab) in ((40, -45, "sonar L"), (160, 0, "sonar C"), (280, 45, "sonar R")):
        cx, cy = x + fx, y + dy + 10
        s.add(f'<g transform="rotate({ang} {cx} {cy})"><rect x="{cx - 14}" y="{cy - 28}" width="22" height="56" rx="4" fill="{BLUE}"/>'
              f'<circle cx="{cx + 4}" cy="{cy - 14}" r="9" fill="#c9ced3"/><circle cx="{cx + 4}" cy="{cy + 14}" r="9" fill="#c9ced3"/></g>')
        s.text(cx - 26, cy + 4, lab, 8.5, INK, "end", 800)
    s.text(x + 20, y + H_ + 22, "Bottom deck: power bank and L298N; the 4 motors and the motor battery underneath. Keep the AHT20 away from the Pi CPU.", 9.5, MUTED, "start", 500)
    return s.svg()


def fig_layout_side() -> str:
    s = S(FIG_W, 300)
    gy = 250
    s.line(20, gy + 30, 680, gy + 30, "#c4ccd3", 3)
    s.circle(480, gy, 32, "#202326", "#111", 2)
    s.circle(480, gy, 13, "#f2c230")
    s.rect(140, gy - 16, 60, 18, "#f2c230", "#b38a12", rx=3)
    s.circle(170, gy, 32, "#202326", "#111", 2)
    s.circle(170, gy, 13, "#f2c230")
    s.rect(100, gy - 24, 450, 8, "#cfe6f5", "#7fa8c4", rx=3)
    s.rect(440, gy - 16, 60, 18, "#f2c230", "#b38a12", rx=3)
    s.rect(200, gy - 18, 150, 20, "#2f7dd1", "#1d4f87", rx=5)
    s.text(275, gy - 4, "motor battery (under deck)", 8, "#fff", "middle", 700)
    s.rect(250, gy - 52, 90, 28, "#b8322a", rx=4)
    s.text(295, gy - 34, "L298N", 9, "#fff", "middle", 800)
    s.rect(370, gy - 42, 120, 18, "#2b2f36", rx=4)
    s.text(430, gy - 29, "power bank", 8, "#fff", "middle", 700)
    for sx in (110, 352, 530):
        s.rect(sx, gy - 104, 8, 80, "#d4b24c", "#9c7f2a", rx=1)
    s.text(122, gy - 64, "35-40 mm standoffs", 8, MUTED, "start", 600)
    s.rect(100, gy - 112, 450, 8, "#cfe6f5", "#7fa8c4", rx=3)
    s.rect(230, gy - 140, 110, 28, PCB, rx=4)
    s.text(285, gy - 122, "Pi 4", 9, "#fff", "middle", 800)
    s.rect(500, gy - 150, 46, 30, "#202326", rx=12)
    s.circle(536, gy - 135, 9, "#0f1a2a", "#3a3f44", 2)
    s.rect(512, gy - 120, 14, 8, "#2a2e31")
    s.text(500, gy - 160, "webcam", 8.5, INK, "start", 700)
    s.rect(552, gy - 108, 22, 40, BLUE, rx=3)
    s.circle(563, gy - 98, 7, "#c9ced3")
    s.circle(563, gy - 78, 7, "#c9ced3")
    s.text(590, gy - 86, "sonar", 8.5, INK, "start", 700)
    s.text(600, gy + 26, "front →", 10, INK, "start", 800)
    s.text(40, 20, "SIDE VIEW", 11, INK, "start", 800)
    return s.svg()


def fig_motor_mount() -> str:
    s = S(FIG_W, 245)
    chassis_top(s, 20, 20, 1.0, bare=True)
    s.text(170, 236, "Screw the 4 motors under the bottom deck with the kit's brackets", 9, INK, "middle", 600)
    tt_motor(s, 420, 110, 1.3, wheel=True)
    s.text(490, 196, "TT motor + wheel (×4)", 9.5, INK, "middle", 700)
    s.text(490, 212, "solder a red + black wire to each motor first", 9, MUTED, "middle", 600)
    return s.svg()




def fig_motor_pairs() -> str:
    s = S(FIG_W, 210)
    for j, (side, y) in enumerate((("LEFT side", 40), ("RIGHT side", 130))):
        tt_motor(s, 60, y, 0.8, wheel=False)
        tt_motor(s, 200, y, 0.8, wheel=False)
        s.text(20, y - 22, side + "  (front motor + rear motor)", 9.5, INK, "start", 800)
        wire(s, [(134, y + 5), (150, y + 5), (150, y - 10), (330, y - 10)], "#e23b2e", 2.4, r=4)
        wire(s, [(274, y + 5), (290, y + 5), (290, y - 10)], "#e23b2e", 2.4, r=4)
        wire(s, [(134, y + 11), (160, y + 11), (160, y + 36), (330, y + 36)], "#2a2e31", 2.4, r=4)
        wire(s, [(274, y + 11), (300, y + 11), (300, y + 36)], "#2a2e31", 2.4, r=4)
        tag(s, 340, y + 16, f"to L298N {'OUT1 / OUT2' if j == 0 else 'OUT3 / OUT4'}", W["mot"], 8.5, "start")
    s.text(500, 70, "Join red to red and black to black:", 9.5, INK, "start", 600)
    s.text(500, 84, "the two motors of a side then work", 9.5, INK, "start", 600)
    s.text(500, 98, "as one. A side that turns the wrong", 9.5, INK, "start", 600)
    s.text(500, 112, "way: swap its two wires at the L298N.", 9.5, INK, "start", 600)
    return s.svg()


def fig_full_harness() -> str:
    s = S(FIG_W, 620)
    blocks = {
        "pi": (260, 250, 180, 150, PCB, "Raspberry Pi 4"),
        "hub": (20, 250, 180, 150, "#b07d2c", "Hub board"),
        "pbank": (260, 20, 180, 80, "#2b2f36", "Power bank (Pi only)"),
        "bat": (20, 20, 180, 80, "#c0392b", "Motor battery 2x18650"),
        "l298": (20, 130, 180, 80, "#b8322a", "L298N"),
        "cam": (500, 20, 180, 80, "#202326", "USB webcam + mic"),
        "son": (500, 250, 180, 80, BLUE, "3x HC-SR04"),
        "i2c": (20, 440, 180, 80, "#6b3fa0", "MPU6050 · AHT20"),
        "aud": (500, 440, 180, 80, "#555b62", "PAM8403 + speaker"),
        "mot": (260, 540, 180, 60, "#8d5a3b", "4x TT motors (2 per side)"),
    }
    for key, (x, y, w, h, c, t) in blocks.items():
        s.rect(x, y, w, h, c, rx=10)
        s.text(x + w / 2, y + 24, t, 11 if len(t) < 24 else 10, "#fff", "middle", 800)

    def link(a, b, col, label, ax=0.5, bx=0.5, ay=None, by=None):
        xa, ya, wa, ha = blocks[a][:4]
        xb, yb, wb, hb = blocks[b][:4]
        p1 = (xa + wa * ax, ya + (ha if ay is None else ay))
        p2 = (xb + wb * bx, yb + (0 if by is None else by))
        s.line(*p1, *p2, col, 3)
        tag(s, (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 4, label, col, 7.5, "middle", fg="#fff" if col not in (W["pwm"], W["scl"]) else INK)

    subs = {"hub": ["rails: 5V · 3V3 · GND · SDA · SCL", "3 echo dividers (1k/2k)"],
            "pi": ["robot program + server", "pins: see the pin map page"], "pbank": ["10,000 mAh · 5 V 3 A"],
            "bat": ["7.4 V · switch in the holder"], "l298": ["motor driver"], "cam": ["photos, video, sound"],
            "son": ["Echo via hub dividers"], "i2c": ["3.3 V · I²C"], "aud": ["from the Pi's 3.5 mm jack"]}
    for key, lines in subs.items():
        x, y, w, h = blocks[key][:4]
        for i, t in enumerate(lines):
            s.text(x + w / 2, y + 44 + i * 14, t, 8.5, "#ffffffd0", "middle", 500)
    link("pbank", "pi", "#555b62", "USB-C 5 V", 0.5, 0.5)
    link("bat", "l298", W["bat"], "+ / −", 0.5, 0.5)
    link("l298", "mot", W["mot"], "OUT1/2 · OUT3/4", 0.5, 0.0, ay=80, by=30)
    link("pi", "l298", W["sig1"], "IN1-4 · ENA 33 · ENB 35 · GND 9", 0.0, 1.0, ay=30, by=50)
    link("pi", "hub", W["3v3"], "pins 1,2,3,5,6", 0.0, 1.0, ay=75, by=75)
    link("pi", "cam", "#555b62", "USB", 0.9, 0.5, ay=0, by=80)
    link("pi", "son", W["sig3"], "Trig 32/18/38 · Echo 36/22/40", 1.0, 0.0, ay=60, by=40)
    link("hub", "i2c", W["sda"], "3V3 · GND · SDA · SCL", 0.5, 0.5)
    link("pi", "aud", W["audio"], "3.5 mm jack", 0.9, 0.3)
    s.text(20, 614, "Two separate batteries; L298N GND → Pi pin 9 joins their grounds. Sonar Echo → hub divider → Pi.", 9, INK, "start", 600)
    return s.svg()


def fig_divider_why() -> str:
    s = S(FIG_W, 150)
    s.rect(20, 40, 140, 50, BLUE, rx=8)
    s.text(90, 70, "Sonar Echo", 11, "#fff", "middle", 800)
    tag(s, 90, 112, "5 V", W["5v"], 9, "middle")
    wire(s, [(160, 65), (260, 65)], W["5v"], 3)
    resistor(s, 260, 65, 330, 65, BANDS["1k"], "1 kΩ")
    wire(s, [(330, 65), (470, 65)], W["sig3"], 3)
    s.circle(400, 65, 4, INK)
    resistor(s, 400, 65, 400, 130, BANDS["2k"])
    s.text(412, 104, "2 kΩ", 9, INK, "start", 700)
    s.text(400, 146, "GND", 8.5, INK, "middle", 700)
    s.rect(470, 40, 150, 50, PCB, rx=8)
    s.text(545, 70, "Pi GPIO pin", 11, "#fff", "middle", 800)
    tag(s, 545, 112, "3.3 V  safe", W["sig1"], 9, "middle")
    return s.svg()


def fig_cover_robot() -> str:
    s = S(560, 400)
    s.add('<defs><linearGradient id="deck" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#e3f1fb"/>'
          '<stop offset="1" stop-color="#a9cde6"/></linearGradient></defs>')
    gy = 330
    s.add(f'<ellipse cx="280" cy="{gy + 32}" rx="230" ry="20" fill="#0b1a2b" opacity="0.18"/>')
    for wx in (128, 432):     # rear wheels, behind
        s.add(f'<ellipse cx="{wx}" cy="{gy - 10}" rx="26" ry="36" fill="#15181b"/>')
    s.add(f'<path d="M100 {gy - 40} L460 {gy - 40} L500 {gy - 10} L60 {gy - 10} Z" fill="url(#deck)" stroke="#6f9cbc" stroke-width="2"/>')
    s.rect(220, gy - 64, 120, 26, "#b8322a", rx=4)
    s.text(280, gy - 46, "L298N", 11, "#fff", "middle", 800)
    for sx in (110, 450):
        s.rect(sx, gy - 140, 8, 100, "#d4b24c", "#9c7f2a", rx=1)
    s.add(f'<path d="M100 {gy - 150} L460 {gy - 150} L500 {gy - 120} L60 {gy - 120} Z" fill="url(#deck)" stroke="#6f9cbc" stroke-width="2"/>')
    s.rect(118, gy - 58, 90, 17, "#2b2f36", rx=4)
    s.rect(335, gy - 188, 120, 40, PCB, PCB_D, rx=5)
    s.text(395, gy - 163, "Raspberry Pi 4", 9.5, "#fff", "middle", 700)
    for wx in (72, 488):
        s.add(f'<ellipse cx="{wx}" cy="{gy}" rx="34" ry="46" fill="#202326" stroke="#0d0f11" stroke-width="2"/>')
        s.add(f'<ellipse cx="{wx}" cy="{gy}" rx="15" ry="21" fill="#f2c230"/>')
    s.rect(160, gy - 118, 240, 14, "#26292c", rx=4)
    for cx in (190, 280, 370):
        s.rect(cx - 36, gy - 112, 72, 34, BLUE, BLUE_D, rx=5)
        s.circle(cx - 16, gy - 95, 12, "#c9ced3", "#8b9399", 1.5)
        s.circle(cx + 16, gy - 95, 12, "#c9ced3", "#8b9399", 1.5)
        s.circle(cx - 16, gy - 95, 6, "#4a4f55")
        s.circle(cx + 16, gy - 95, 6, "#4a4f55")
    # webcam clipped on the front of the top deck
    s.rect(266, gy - 172, 18, 34, "#2a2e31", rx=3)
    s.rect(220, gy - 220, 110, 50, "#202326", "#0d0f11", rx=22)
    s.circle(275, gy - 195, 18, "#0f1a2a", "#3a3f44", 3)
    s.circle(269, gy - 201, 6, "#9fc3ff")
    s.circle(238, gy - 195, 3.5, "#55e07a")
    return s.svg("cover")
