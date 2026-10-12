"""All figures of the Raqib build guide (component pictures, wiring diagrams, layouts)."""
from __future__ import annotations

import math

from draw import (BANDS, BLUE, BLUE_D, GOLD, INK, LINE, MUTED, PCB, PCB_D, PI_PINS, S, SILK, W, ads1115, battery_2s,
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
             "pam": (130, 80), "spk": (110, 110), "res": (220, 110), "wires": (190, 110), "tools": (330, 180), "hub": (330, 200),
             "standoff": (220, 110)}
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
    elif name == "motor":
        tt_motor(s, 40, 70, 1.0)
        encoder_disc(s, 160, 40, 24)
    elif name == "l298n":
        l298n(s, 15, 8, 1.0)
    elif name == "pca":
        pca9685(s, 10, 6, 1.06)
    elif name == "servo":
        sg90(s, 20, 50, 1.0, "pan")
        pan_tilt_bracket(s, 190, 20)
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
                                      ("10k", "10 kΩ brown-black-orange"), ("20k", "20 kΩ red-black-orange"))):
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
        s.text(110, 105, "M3 brass standoffs 35-40 mm + screws", 9, MUTED, "middle", 600)
    return s.svg("comp")


def pan_tilt_bracket(s, x, y):
    s.rect(x, y + 70, 80, 14, "#26292c", rx=3)          # base (pan servo inside)
    s.rect(x + 30, y + 30, 20, 40, "#26292c", rx=3)     # upright
    s.rect(x + 12, y + 14, 56, 18, "#26292c", rx=3)     # tilt arm
    s.rect(x + 26, y - 2, 28, 18, PCB, PCB_D, rx=3)     # camera
    s.circle(x + 40, y + 7, 5, "#2b3d55", "#111", 1.5)
    s.text(x + 40, y + 104, "pan/tilt bracket", 8, MUTED, "middle", 600)


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
        s.text(x + w / 2, y + h - 12 * k, "+ 3 echo dividers (1k/2k) + MQ-135 divider (10k/20k)", 8.5 * k, "#5b4520", "middle", 700)
        return pts
    # three ECHO dividers + MQ divider, drawn vertically under the rails
    names = [("ECHO L", "1k", "2k"), ("ECHO C", "1k", "2k"), ("ECHO R", "1k", "2k"), ("MQ AO", "10k", "20k")]
    for i, (lab, top, bot) in enumerate(names):
        cx = x + (70 + i * 62) * k
        y_in = y + 96 * k
        y_mid = y + 128 * k
        y_gnd = y + 162 * k
        s.text(cx, y_in - 6 * k, lab, 7.5 * k, INK, "middle", 800)
        resistor(s, cx, y_in, cx, y_mid, BANDS[top])
        resistor(s, cx, y_mid, cx, y_gnd, BANDS[bot])
        s.circle(cx, y_mid, 3 * k, "#2a2e31")
        s.text(cx + 8 * k, y_in + 18 * k, "1k" if top == "1k" else "10k", 7 * k, INK, "start", 700)
        s.text(cx + 8 * k, y_mid + 18 * k, "2k" if bot == "2k" else "20k", 7 * k, INK, "start", 700)
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

    box(250, 150, 200, 110, "Raspberry Pi 4", ["robot program + its own server", "AI agent · Wi-Fi to the phone", "camera · mic · speaker"], PCB)
    box(20, 20, 200, 90, "Power", ["3x18650 UPS module → Pi (5 V)", "2x18650 pack → motors"], "#c0392b")
    box(480, 20, 200, 90, "Phone app (APK)", ["Wi-Fi: hotspot, home, or", "the robot's own 'Raqib-Robot'"], "#2d6be0")
    box(20, 300, 200, 110, "Moving", ["L298N + 4 TT motors", "PCA9685 (speed + servos)", "pan/tilt camera mount"], "#8d5a3b")
    box(250, 300, 200, 110, "Seeing obstacles", ["3x HC-SR04 sonar", "2 wheel encoders", "MPU6050 motion sensor"], "#1e9e55")
    box(480, 300, 200, 110, "Measuring the room", ["BME680 temp / humidity / VOC", "MQ-135 gas → ADS1115", "USB microphone"], "#8a55e8")
    box(20, 150, 200, 110, "Sensor hub board", ["your perfboard: 5V, 3V3, GND,", "SDA, SCL rails + dividers"], "#b07d2c")
    for (x1, y1, x2, y2, c, lab) in ((120, 110, 300, 150, W["5v"], "5 V"), (580, 110, 400, 150, W["sda"], "Wi-Fi"),
                                     (220, 205, 250, 205, W["scl"], "I²C + GPIO"), (120, 260, 120, 300, W["gnd"], ""),
                                     (350, 260, 350, 300, W["sig1"], "GPIO"), (440, 260, 560, 300, W["sig2"], "I²C"),
                                     (300, 260, 180, 300, W["mot"], "GPIO + PWM")):
        s.line(x1, y1, x2, y2, c, 3)
        if lab:
            tag(s, (x1 + x2) / 2, (y1 + y2) / 2 + 4, lab, c, 8, "middle")
    return s.svg()


# ======================================================================= Pi header map
def fig_pi_header() -> str:
    used = {1: W["3v3"], 2: W["5v"], 3: W["sda"], 5: W["scl"], 6: W["gnd"], 9: W["gnd"], 11: W["sig1"], 13: W["sig1"],
            15: W["sig2"], 16: W["sig2"], 18: W["sig3"], 22: W["sig3"], 29: W["sig4"], 31: W["sig4"], 32: W["sig5"],
            36: W["sig5"], 38: W["sig6"], 40: W["sig6"]}
    what = {1: "3.3 V → hub 3V3 rail", 2: "5 V → hub 5V rail", 3: "SDA → hub SDA rail", 5: "SCL → hub SCL rail",
            6: "GND → hub GND rail", 9: "GND → L298N GND (common ground)", 11: "L298N IN1 (left motors)",
            13: "L298N IN2 (left motors)", 15: "L298N IN3 (right motors)", 16: "L298N IN4 (right motors)",
            18: "sonar CENTRE Trig", 22: "sonar CENTRE Echo (via divider)", 29: "left wheel encoder D0",
            31: "right wheel encoder D0", 32: "sonar LEFT Trig", 36: "sonar LEFT Echo (via divider)",
            38: "sonar RIGHT Trig", 40: "sonar RIGHT Echo (via divider)"}
    s = S(FIG_W, 440)
    hdr = gpio_header(s, 327, 58, used, pitch=17.5, labels="none")
    for n, txt in what.items():
        px, py, side = hdr[n]
        col = used[n]
        if side == "L":
            s.line(px - 8, py, 300, py, col, 1.5)
            s.text(296, py + 3.5, f"{PI_PINS[n]}  ·  {txt}", 9, col if n not in (6, 9) else INK, "end", 700)
        else:
            s.line(px + 8, py, 400, py, col, 1.5)
            s.text(404, py + 3.5, f"{PI_PINS[n]}  ·  {txt}", 9, col if n not in (6, 9) else INK, "start", 700)
    s.text(350, 16, "pin 1 is the square pad, at the corner nearest the microSD card", 9, MUTED, "middle", 600)
    s.text(350, 432, "Odd pins (1, 3, 5 …) are the row on the inside of the board; even pins the row along the edge.", 9, MUTED, "middle", 500)
    return s.svg()


# ======================================================================= power
def fig_power() -> str:
    s = S(FIG_W, 590)
    ups = ups_3s(s, 20, 30, 0.86)
    pins = pi4(s, 400, 30, 0.8)
    k = 3.4 * 0.8
    usbc_pi = (400 + 11.5 * k, 30 + 56 * k + 2)
    # USB-C cable UPS -> Pi
    ups_usbc = (20 + 250 * 0.86 + 4, 30 + 111 * 0.86)
    wire(s, [ups_usbc, (300, ups_usbc[1]), (300, 230), (usbc_pi[0], 230), usbc_pi], "#555b62", 6, r=12)
    tag(s, 300, 248, "USB-C cable: 5 V 5 A to the Pi", "#555b62", 8.5, "middle")
    # gauge wires UPS SDA/SCL/GND -> hub (drawn as tags)
    for i, (p, c, lab) in enumerate((("SDA", W["sda"], "to hub SDA"), ("SCL", W["scl"], "to hub SCL"), ("GND", W["gnd"], "to hub GND"))):
        px, py = ups[p]
        wire(s, [(px, py), (px, 222 + i * 0)], c, 2.6)
    tag(s, 110, 250, "SDA, SCL, GND → hub rails (battery %)", W["sda"], 8, "middle")
    # 5V out -> PCA9685 V+
    px, py = ups["5V"]
    pca = pca9685(s, 400, 300, 1.0)
    wire(s, [(px, py), (px, 270), (380, 270), (380, pca["term V+"][1] - 20), (pca["term V+"][0], pca["term V+"][1] - 20), pca["term V+"]], W["5v"], 3)
    tag(s, 300, 284, "UPS 5 V → PCA9685 V+ (servo power)", W["5v"], 8, "middle")
    gx, gy = ups["GND"]
    # motor battery -> L298N
    bat = battery_2s(s, 20, 330, 0.9)
    l2 = l298n(s, 210, 300, 0.9)
    wire(s, [bat["+"], (200, bat["+"][1]), (200, 470), (l2["+12V"][0], 470), l2["+12V"]], W["bat"], 3.6)
    wire(s, [bat["-"], (192, bat["-"][1]), (192, 480), (l2["GND"][0], 480), l2["GND"]], W["gnd"], 3.6)
    tag(s, 110, 448, "motor pack 7.4 V (8.4 V full)", W["bat"], 8, "middle")
    # common ground L298N GND -> Pi pin 9
    p9 = pins[9]
    wire(s, [l2["GND"], (l2["GND"][0], 500), (720 - 26, 500), (720 - 26, 20), (p9[0], 20), p9], W["gnd"], 2.6, r=10)
    tag(s, 560, 514, "L298N GND → Pi pin 9: the COMMON GROUND", W["gnd"], 8.5, "middle")
    s.text(20, 562, "Two batteries: the UPS module (3 x 18650) feeds the Pi, sensors and servos; a separate 2 x 18650 pack feeds the motors,"
           , 9, MUTED)
    s.text(20, 576, "so motor current spikes never reset the Pi. All grounds are joined.", 9, MUTED)
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
    for i, t in enumerate(["5 V signal enters at the top", "top resistor (1 kΩ / 10 kΩ)", "middle point → Pi pin / ADS1115 A0",
                           "bottom resistor (2 kΩ / 20 kΩ) → GND", "5 V × 2/3 = 3.3 V: safe"]):
        s.text(20, 168 + i * 15, f"• {t}", 9.5, INK)
    s.text(505, 276, "Solder the rails as bare wire along the strips;", 8.5, MUTED, "middle")
    s.text(505, 288, "every module plugs into the rails with jumper wires.", 8.5, MUTED, "middle")
    return s.svg()


# ======================================================================= I2C
def fig_i2c() -> str:
    s = S(FIG_W, 505)
    hubp = {"5V": None}
    # hub rails as a long vertical bus on the left
    rails = [("3V3", W["3v3"]), ("GND", W["gnd"]), ("SDA", W["sda"]), ("SCL", W["scl"])]
    for i, (nm, c) in enumerate(rails):
        x = 24 + i * 24
        s.line(x, 30, x, 470, c, 4)
        s.text(x, 482, nm, 8, c if nm != "GND" else INK, "middle", 800)
    s.text(60, 496, "hub rails", 9, MUTED, "middle", 700)
    railx = {nm: 24 + i * 24 for i, (nm, _) in enumerate(rails)}
    col = dict(rails)
    devices = [
        ("PCA9685  (0x40)", lambda x, y: pca9685(s, x, y, 0.9), 150, 20, {"VCC": "3V3", "GND": "GND", "SDA": "SDA", "SCL": "SCL"}, "left"),
        ("MPU6050  (0x68)", lambda x, y: gy521(s, x, y, 1.0), 150, 150, {"VCC": "3V3", "GND": "GND", "SDA": "SDA", "SCL": "SCL"}, "below"),
        ("BME680  (0x76)", lambda x, y: bme680(s, x, y, 1.0), 330, 150, {"VCC": "3V3", "GND": "GND", "SDA": "SDA", "SCL": "SCL"}, "below"),
        ("ADS1115  (0x48)", lambda x, y: ads1115(s, x, y, 1.0), 470, 150, {"VDD": "3V3", "GND": "GND", "SDA": "SDA", "SCL": "SCL", "ADDR": "GND"}, "below"),
    ]
    lane = 0
    for title, fn, x, y, conn, kind in devices:
        pins = fn(x, y)
        s.text(x, y - 6, title, 10, INK, "start", 800)
        for pin, rail in conn.items():
            px, py = pins[pin]
            rx = railx[rail]
            if kind == "left":
                wire(s, [(px, py), (rx, py)], col[rail], 2.4)
            else:
                yy = 300 + lane * 7
                lane += 1
                wire(s, [(px, py), (px, yy), (rx, yy)], col[rail], 2.4, r=5)
    s.text(150, 410, "• Every I²C board joins the same four rails: 3.3 V, GND, SDA, SCL.", 10, INK)
    s.text(150, 426, "• Each answers to its own address, so they share two wires without clashing.", 10, INK)
    s.text(150, 442, "• ADS1115 ADDR → GND sets 0x48. BME680 SDO open = 0x76 (some boards: 0x77).", 10, INK)
    s.text(150, 458, "• The UPS module's battery gauge joins the same SDA/SCL/GND (see the power page).", 10, INK)
    s.text(150, 474, "• Test: python -m hwtest.i2c_scan lists every address found.", 10, INK)
    return s.svg()


# ======================================================================= motors
def fig_motors() -> str:
    s = S(FIG_W, 560)
    used = {9: W["gnd"], 11: W["sig1"], 13: W["sig2"], 15: W["sig3"], 16: W["sig4"]}
    hdr = gpio_header(s, 40, 40, used, pitch=13, labels="none")
    l2 = l298n(s, 300, 170, 1.0)
    pca = pca9685(s, 400, 20, 0.85)
    # left motor pair above-left of the L298N, right pair to the right
    tt_motor(s, 150, 118, 0.6, wheel=False)
    tt_motor(s, 150, 146, 0.6, wheel=False)
    s.text(150, 110, "LEFT motors (front + rear)", 8, INK, "start", 700)
    tt_motor(s, 575, 230, 0.6, wheel=False)
    tt_motor(s, 575, 258, 0.6, wheel=False)
    s.text(575, 222, "RIGHT motors", 8, INK, "start", 700)
    # OUT1/OUT2 -> left pair (red / black)
    for i, (o, c) in enumerate((("OUT1", "#e23b2e"), ("OUT2", "#2a2e31"))):
        x0, y0 = l2[o]
        xm = 150 + 56
        wire(s, [(x0, y0), (285 - i * 7, y0), (285 - i * 7, 129 + 28 * 0 + i * 28 - 6 + 3), (xm, 129 + i * 28 - 3)], c, 2.6, r=5)
    for i, (o, c) in enumerate((("OUT3", "#e23b2e"), ("OUT4", "#2a2e31"))):
        x0, y0 = l2[o]
        wire(s, [(x0, y0), (490 + 12 + i * 7, y0), (490 + 12 + i * 7, 236 + i * 28), (575, 236 + i * 28)], c, 2.6, r=5)
    tag(s, 245, 172, "OUT1 / OUT2", W["mot"], 7.5, "middle")
    tag(s, 640, 312, "OUT3 / OUT4", W["mot"], 7.5, "middle")
    # GPIO -> IN1..IN4, routed under the board
    for i, (pin, inp) in enumerate(((11, "IN1"), (13, "IN2"), (15, "IN3"), (16, "IN4"))):
        px, py, side = hdr[pin]
        c = used[pin]
        tx, ty = l2[inp]
        yy = 360 + i * 9
        xo = 22 - i * 4 if side == "L" else 118 + i * 0
        wire(s, [(px, py), (xo, py), (xo, yy), (tx, yy), (tx, ty)], c, 2.6, r=5)
    for i, (pin, inp) in enumerate(((11, "IN1"), (13, "IN2"), (15, "IN3"), (16, "IN4"))):
        tag(s, 150 + (i % 2) * 190, 420 + (i // 2) * 20, f"pin {pin} · {PI_PINS[pin]} → {inp}", used[pin], 8, "start")
    # PCA ch0 -> ENA, ch1 -> ENB, routed round the right side
    for j, (ch, en, c) in enumerate((("ch0", "ENA", W["pwm"]), ("ch1", "ENB", "#c98a00"))):
        px, py = pca[ch]
        tx, ty = l2[en]
        lane = 520 + j * 9
        yy = 400 + j * 9
        wire(s, [(px, py), (px, 120 + j * 8), (lane, 120 + j * 8), (lane, yy), (tx, yy), (tx, ty)], c, 2.6, r=5)
    tag(s, 590, 140, "PCA9685 ch0 → ENA", W["pwm"], 8, "middle", fg=INK)
    tag(s, 590, 160, "PCA9685 ch1 → ENB", "#c98a00", 8, "middle")
    # pin 9 GND -> L298N GND
    px, py, _ = hdr[9]
    wire(s, [(px, py), (8, py), (8, 480), (l2["GND"][0], 480), l2["GND"]], W["gnd"], 2.6, r=6)
    tag(s, 200, 476, "pin 9 GND → L298N GND (common ground)", W["gnd"], 8, "middle")
    s.text(20, 510, "• Remove the ENA and ENB jumpers (the PCA9685 sets the speed). Keep the 5V-EN jumper: the motor pack is under 12 V.", 9.5, INK)
    s.text(20, 526, "• +12V and GND terminals come from the motor pack (power page). Leave the +5V terminal unconnected.", 9.5, INK)
    s.text(20, 542, "• IN pins set the direction, ENA/ENB the speed. A side that runs backwards: swap its two motor wires.", 9.5, INK)
    return s.svg()


# ======================================================================= servos + camera
def fig_servos() -> str:
    s = S(FIG_W, 360)
    pca = pca9685(s, 20, 30, 1.15)
    sg90(s, 430, 40, 0.9, "pan")
    sg90(s, 430, 150, 0.9, "tilt")
    bottom = 30 + 70 * 1.15
    for j, (ch, sy) in enumerate((("ch14", 40), ("ch15", 150))):
        px, py = pca[ch]
        plug = (430 + 132 * 0.9, sy + 55 * 0.9)
        yy = 150 + j * 12
        wire(s, [plug, (plug[0] + 14 + j * 8, plug[1]), (plug[0] + 14 + j * 8, 262 + j * 10), (px, 262 + j * 10), (px, bottom)], "#555b62", 3, r=8)
    tag(s, 300, 290, "pan servo plug → column 14 · tilt servo plug → column 15", "#555b62", 8.5, "start")
    s.text(20, 160, "Plug each servo onto its 3-pin column:", 10, INK, "start", 700)
    s.text(20, 176, "brown → GND row · red → V+ row · orange → signal row", 9.5, INK)
    s.text(20, 196, "Servo power comes from the PCA9685 V+ terminal (UPS 5 V),", 9.5, INK)
    s.text(20, 210, "never from the Pi.", 9.5, INK)
    s.text(20, 230, "Centre first: run python -m hwtest.test_motors, then fit", 9.5, INK)
    s.text(20, 244, "the horns so the camera looks straight ahead and level.", 9.5, INK)
    s.text(20, 318, "Camera ribbon → CAMERA connector, blue tab facing the USB/Ethernet ports. Use a 30-50 cm", 9.5, INK)
    s.text(20, 332, "ribbon and leave a loose loop so the pan/tilt can move.", 9.5, INK)
    pan_tilt_bracket(s, 600, 220)
    return s.svg()


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
def fig_encoders() -> str:
    s = S(FIG_W, 300)
    used = {29: W["sig4"], 31: W["sig4"]}
    hdr = gpio_header(s, 600, 30, used, pitch=12, labels="none")
    for i, (name, pin) in enumerate((("LEFT", 29), ("RIGHT", 31))):
        x, y = 30 + i * 260, 70
        p = slot_encoder(s, x, y, 1.3)
        encoder_disc(s, x + 75, y - 10, 30)
        s.text(x, y - 40, f"{name} wheel encoder", 10, INK, "start", 800)
        vx, vy = p["VCC"]
        gx, gy = p["GND"]
        wire(s, [(vx, vy), (vx, vy + 40)], W["3v3"], 2.6)
        tag(s, vx, vy + 54, "3V3", W["3v3"], 8, "middle")
        wire(s, [(gx, gy), (gx, gy + 60)], W["gnd"], 2.6)
        tag(s, gx, gy + 74, "GND", W["gnd"], 8, "middle")
        dx, dy = p["D0"]
        hx, hy, side = hdr[pin]
        lane = 560 + i * 12
        wire(s, [(dx, dy), (dx, 230 + i * 12), (lane, 230 + i * 12), (lane, hy), (hx, hy)], W["sig4"], 2.6, r=6)
        tag(s, dx + 120, 226 + i * 12 + 30, "", W["sig4"], 1) if False else None
    tag(s, 330, 278, "left D0 → pin 29 (GPIO5)   ·   right D0 → pin 31 (GPIO6)   ·   A0 not used", W["sig4"], 8.5, "middle")
    s.text(20, 296, "Power the encoders from 3.3 V so their output is safe for the Pi. The disc must spin freely in the slot.", 9, MUTED)
    return s.svg()


# ======================================================================= gas
def fig_gas() -> str:
    s = S(FIG_W, 300)
    p = mq135(s, 30, 40, 1.4)
    a = ads1115(s, 420, 60, 1.3)
    s.text(30, 30, "MQ-135 gas sensor", 10, INK, "start", 800)
    s.text(420, 50, "ADS1115", 10, INK, "start", 800)
    vx, vy = p["VCC"]
    gx, gy = p["GND"]
    wire(s, [(vx, vy), (vx, vy + 50)], W["5v"], 2.8)
    tag(s, vx, vy + 64, "5V", W["5v"], 8, "middle")
    wire(s, [(gx, gy), (gx, gy + 70)], W["gnd"], 2.8)
    tag(s, gx, gy + 84, "GND", W["gnd"], 8, "middle")
    ax, ay = p["AO"]
    dx = 280
    resistor(s, dx, 120, dx, 170, BANDS["10k"])
    resistor(s, dx, 170, dx, 220, BANDS["20k"])
    s.text(dx + 12, 148, "10 kΩ", 8.5, INK, "start", 700)
    s.text(dx + 12, 198, "20 kΩ", 8.5, INK, "start", 700)
    s.circle(dx, 170, 3.5, INK)
    wire(s, [(ax, ay), (ax, ay + 18), (250, ay + 18), (250, 120), (dx, 120)], "#7a7f87", 2.8, r=6)
    wire(s, [(dx, 220), (dx, 240)], W["gnd"], 2.8)
    tag(s, dx, 254, "GND", W["gnd"], 8, "middle")
    a0x, a0y = a["A0"]
    wire(s, [(dx, 170), (380, 170), (380, a0y + 40), (a0x, a0y + 40), (a0x, a0y)], "#7a7f87", 2.8, r=6)
    s.text(420, 200, "ADS1115: VDD 3V3 · GND · SDA · SCL to the hub rails,", 9.5, INK)
    s.text(420, 214, "ADDR → GND (address 0x48).", 9.5, INK)
    s.text(420, 236, "The MQ-135 heater needs 5 V and gets warm:", 9.5, INK)
    s.text(420, 250, "mount it at the back, away from plastic.", 9.5, INK)
    s.text(420, 272, "First use: 24-48 h burn-in, then calibrate", 9.5, INK)
    s.text(420, 286, "(python -m hwtest.test_env --calibrate-mq135).", 9.5, INK)
    return s.svg()


# ======================================================================= audio + camera
def fig_audio() -> str:
    s = S(FIG_W, 380)
    x0, y0, sc = 20, 70, 0.85
    pi4(s, x0, y0, sc)
    k = 3.4 * sc
    cam = pi_camera(s, 330, 6, 0.6)
    csi = (x0 + 45.5 * k, y0 + 45 * k)
    wire(s, [cam["ribbon"], (cam["ribbon"][0], 60), (csi[0], 60), csi], "#d9cfb6", 7, r=10)
    tag(s, 420, 60, "camera ribbon → CAMERA port", "#8a7a52", 8, "start")
    usb_end = x0 + 85 * k + 4
    y_usb3, y_usb2 = y0 + 25 * k, y0 + 44 * k
    usb_mic(s, 470, y_usb3 - 8, 0.9)
    snd = usb_soundcard(s, 470, y_usb2 - 8, 0.9)
    wire(s, [(usb_end, y_usb3), (470, y_usb3)], "#555b62", 4)
    wire(s, [(usb_end, y_usb2), (470, y_usb2)], "#555b62", 4)
    pam = pam8403(s, 330, 270, 0.95)
    speaker(s, 560, 310, 26)
    ox, oy = snd["out"]
    wire(s, [(ox, oy), (ox + 40, oy), (ox + 40, 250), (300, 250), (300, pam["L"][1]), pam["L"]], W["audio"], 2.6, r=6)
    wire(s, [(ox, oy + 2), (ox + 48, oy + 2), (ox + 48, 258), (308, 258), (308, pam["G"][1]), pam["G"]], W["gnd"], 2.2, r=6)
    tag(s, 450, 268, "3.5 mm plug: tip → L, sleeve → G", W["audio"], 8, "middle")
    wire(s, [pam["out L+"], (470, pam["out L+"][1]), (470, 300), (534, 300)], "#e23b2e", 2.4, r=4)
    wire(s, [pam["out L-"], (462, pam["out L-"][1]), (462, 322), (534, 322)], "#2a2e31", 2.4, r=4)
    wire(s, [pam["5V"], (280, pam["5V"][1]), (280, 352)], W["5v"], 2.4)
    tag(s, 230, 365, "PAM8403 5V + GND from the hub", W["5v"], 8, "middle")
    s.text(600, 360, "", 8)
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
    x, y, sc = 60, 40, 1.9
    k = sc
    # deck outline (top deck)
    s.rect(x, y, 300 * k / 1.0 * 0.95, 190 * k * 0.95 - 20, "#e6f1f9", "#7fa8c4", rx=22, sw=2)
    W_, H_ = 300 * k * 0.95, 190 * k * 0.95 - 20
    s.text(x + W_ / 2, y - 12, "TOP DECK (seen from above)  ·  front of the robot →", 11, INK, "middle", 800)

    def part(px, py, pw, ph, col, label, sub="", fg="#fff"):
        s.rect(x + px, y + py, pw, ph, col, None, rx=6)
        s.text(x + px + pw / 2, y + py + ph / 2 + (0 if sub else 4), label, 9.5, fg, "middle", 800)
        if sub:
            s.text(x + px + pw / 2, y + py + ph / 2 + 13, sub, 7.5, fg, "middle", 500)

    part(20, 30, 150, 110, "#1d3d8f", "UPS module 3S", "3 x 18650 · switch")
    part(185, 40, 140, 95, PCB, "Raspberry Pi 4", "on standoffs")
    part(185, 150, 140, 60, BLUE, "PCA9685", "servo + speed PWM")
    part(20, 155, 150, 90, "#b07d2c", "Sensor hub board", "rails + dividers + ADS1115")
    part(345, 120, 70, 50, BLUE, "MPU6050", "flat, centre")
    part(20, 260, 60, 50, "#6b3fa0", "BME680", "rear edge")
    part(95, 260, 70, 50, BLUE, "MQ-135", "rear edge, hot")
    part(185, 225, 80, 40, PCB, "PAM8403")
    s.circle(x + 300, y + 285, 26, "#2b2f35")
    s.text(x + 300, y + 289, "speaker", 8, "#fff", "middle", 700)
    part(450, 135, 70, 70, "#26292c", "pan/tilt", "camera mast")
    # sonars on the front edge
    fx = W_ - 20
    for (dy, ang, lab) in ((30, -45, "sonar L"), (150, 0, "sonar C"), (270, 45, "sonar R")):
        cx, cy = x + fx, y + dy + 10
        s.add(f'<g transform="rotate({ang} {cx} {cy})"><rect x="{cx - 14}" y="{cy - 28}" width="22" height="56" rx="4" fill="{BLUE}"/>'
              f'<circle cx="{cx + 4}" cy="{cy - 14}" r="9" fill="#c9ced3"/><circle cx="{cx + 4}" cy="{cy + 14}" r="9" fill="#c9ced3"/></g>')
        s.text(cx - 26, cy + 4, lab, 8.5, INK, "end", 800)
    s.circle(x + 450, y + 230, 9, "#333")
    s.text(x + 465, y + 234, "USB mic, facing forward", 8.5, INK, "start", 700)
    s.text(x + 60, y + H_ + 22, "Heat: keep BME680 and MQ-135 away from the Pi CPU. Weight: batteries low and central.", 9.5, MUTED, "start", 500)
    return s.svg()


def fig_layout_side() -> str:
    s = S(FIG_W, 300)
    gy = 250
    s.line(20, gy + 30, 680, gy + 30, "#c4ccd3", 3)
    # wheels
    for wx in (150, 480):
        s.circle(wx, gy, 32, "#202326", "#111", 2)
        s.circle(wx, gy, 13, "#f2c230")
    # bottom deck + motors + battery
    s.rect(100, gy - 24, 450, 8, "#cfe6f5", "#7fa8c4", rx=3)
    s.rect(130, gy - 16, 60, 18, "#f2c230", "#b38a12", rx=3)
    s.rect(460, gy - 16, 60, 18, "#f2c230", "#b38a12", rx=3)
    s.rect(240, gy - 18, 150, 20, "#2f7dd1", "#1d4f87", rx=5)
    s.text(315, gy - 4, "motor pack (under deck)", 8, "#fff", "middle", 700)
    s.rect(250, gy - 52, 90, 28, "#b8322a", rx=4)
    s.text(295, gy - 34, "L298N", 9, "#fff", "middle", 800)
    s.rect(420, gy - 40, 40, 16, BLUE, rx=3)
    s.text(440, gy - 29, "enc", 7, "#fff", "middle", 700)
    # standoffs
    for sx in (110, 375, 530):
        s.rect(sx, gy - 104, 8, 80, "#d4b24c", "#9c7f2a", rx=1)
    s.text(122, gy - 64, "35-40 mm standoffs", 8, MUTED, "start", 600)
    # top deck
    s.rect(100, gy - 112, 450, 8, "#cfe6f5", "#7fa8c4", rx=3)
    s.rect(120, gy - 150, 120, 38, "#1d3d8f", rx=4)
    s.text(180, gy - 127, "UPS 3S", 9, "#fff", "middle", 800)
    s.rect(255, gy - 140, 110, 28, PCB, rx=4)
    s.text(310, gy - 122, "Pi 4", 9, "#fff", "middle", 800)
    s.rect(380, gy - 130, 70, 18, BLUE, rx=3)
    s.text(415, gy - 118, "PCA9685", 7.5, "#fff", "middle", 700)
    # sonar front
    s.rect(552, gy - 128, 22, 40, BLUE, rx=3)
    s.circle(563, gy - 118, 7, "#c9ced3")
    s.circle(563, gy - 98, 7, "#c9ced3")
    s.text(590, gy - 104, "sonar", 8.5, INK, "start", 700)
    # mast + pan tilt + camera
    s.rect(480, gy - 200, 14, 88, "#26292c", rx=2)
    s.rect(466, gy - 216, 42, 18, "#26292c", rx=3)
    s.rect(492, gy - 236, 28, 22, PCB, PCB_D, rx=3)
    s.circle(522, gy - 225, 6, "#2b3d55", "#111", 1.5)
    s.text(530, gy - 240, "camera on pan/tilt", 8.5, INK, "start", 700)
    s.text(600, gy + 26, "front →", 10, INK, "start", 800)
    s.text(40, 20, "SIDE VIEW", 11, INK, "start", 800)
    return s.svg()


def fig_motor_mount() -> str:
    s = S(FIG_W, 245)
    # bottom plate seen from below with motors
    chassis_top(s, 20, 20, 1.0, bare=True)
    s.text(170, 236, "1. Screw the 4 motors under the bottom deck with the kit's brackets", 9, INK, "middle", 600)
    # encoder detail
    x, y = 380, 40
    tt_motor(s, x + 20, y + 90, 1.1, wheel=False)
    encoder_disc(s, x + 112, y + 72, 30)
    slot_encoder(s, x + 160, y + 110, 1.1)
    s.line(x + 112, y + 72, x + 112, y + 110, "#999", 2, dash="4 3")
    s.text(x + 150, y + 182, "2. Disc on the motor's inner shaft, spinning", 9, INK, "middle", 600)
    s.text(x + 150, y + 196, "inside the slot of the encoder module", 9, INK, "middle", 600)
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
    """One-page block map of every connection (what goes where, wire colour)."""
    s = S(FIG_W, 640)
    blocks = {
        "pi": (260, 250, 180, 150, PCB, "Raspberry Pi 4"),
        "hub": (20, 250, 180, 150, "#b07d2c", "Hub board"),
        "ups": (260, 20, 180, 80, "#1d3d8f", "UPS 3S (3x18650)"),
        "bat": (20, 20, 180, 80, "#c0392b", "Motor pack 2x18650"),
        "l298": (20, 130, 180, 80, "#b8322a", "L298N"),
        "pca": (500, 20, 180, 80, BLUE, "PCA9685"),
        "srv": (500, 130, 180, 80, "#26292c", "Pan/tilt servos + camera"),
        "son": (500, 250, 180, 70, BLUE, "3x HC-SR04"),
        "enc": (500, 335, 180, 65, BLUE, "2x encoders"),
        "i2c": (20, 440, 180, 90, "#6b3fa0", "MPU6050 · BME680 · ADS1115"),
        "mq": (260, 440, 180, 90, BLUE, "MQ-135"),
        "aud": (500, 440, 180, 90, "#555b62", "USB mic · sound card · PAM8403 · speaker"),
        "mot": (20, 560, 180, 60, "#8d5a3b", "4x TT motors"),
    }
    for key, (x, y, w, h, c, t) in blocks.items():
        s.rect(x, y, w, h, c, rx=10)
        if len(t) > 26:
            parts = t.split(" · ")
            s.text(x + w / 2, y + 22, " · ".join(parts[:2]), 10, "#fff", "middle", 800)
            s.text(x + w / 2, y + 38, " · ".join(parts[2:]), 10, "#fff", "middle", 800)
        else:
            s.text(x + w / 2, y + 24, t, 11, "#fff", "middle", 800)

    def link(a, b, col, label, ax=0.5, bx=0.5, ay=None, by=None):
        xa, ya, wa, ha = blocks[a][:4]
        xb, yb, wb, hb = blocks[b][:4]
        p1 = (xa + wa * ax, ya + (ha if ay is None else ay))
        p2 = (xb + wb * bx, yb + (0 if by is None else by))
        s.line(*p1, *p2, col, 3)
        tag(s, (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 + 4, label, col, 7.5, "middle", fg="#fff" if col not in (W["pwm"], W["scl"]) else INK)

    link("ups", "pi", "#555b62", "USB-C 5V", 0.5, 0.5)
    link("ups", "pca", W["5v"], "5V → V+", 1.0, 0.0, ay=40, by=40)
    link("bat", "l298", W["bat"], "+ / − (switch)", 0.5, 0.5)
    link("l298", "mot", W["mot"], "OUT1-4 → motors", 0.3, 0.3, ay=80, by=0) if False else None
    wire(s, [(20, 190), (10, 190), (10, 590), (20, 590)], W["mot"], 3, r=6)
    tag(s, 110, 546, "OUT1/2 · OUT3/4 → motors", W["mot"], 7.5, "middle")
    subs = {"hub": ["rails: 5V · 3V3 · GND · SDA · SCL", "3 echo dividers (1k/2k)", "MQ-135 divider (10k/20k)"],
            "pi": ["robot program + server", "pins: see the pin map page"], "ups": ["5 V 5 A · battery gauge"],
            "bat": ["7.4 V · own switch"], "l298": ["motor driver"], "pca": ["PWM: speed + servos"],
            "son": ["Echo via hub dividers"], "enc": ["3.3 V · D0 out"], "mq": ["5 V heater · AO → divider → A0"]}
    for key, lines in subs.items():
        x, y, w, h = blocks[key][:4]
        for i, t in enumerate(lines):
            s.text(x + w / 2, y + 44 + i * 14, t, 8.5, "#ffffffd0", "middle", 500)
    link("pi", "l298", W["sig1"], "IN1-4 pins 11/13/15/16", 0.0, 1.0, ay=30, by=40)
    link("pca", "l298", W["pwm"], "ch0/ch1 → ENA/ENB", 0.0, 1.0, ay=70, by=20)
    link("pca", "srv", "#555b62", "ch14 / ch15", 0.5, 0.5)
    link("pi", "hub", W["3v3"], "pins 1,2,3,5,6", 0.0, 1.0, ay=75, by=75)
    link("pi", "son", W["sig3"], "Trig 32/18/38", 1.0, 0.0, ay=40, by=25)
    link("hub", "son", "#7a7f87", "", 1.0, 0.0, ay=20, by=50) if False else None
    link("pi", "enc", W["sig4"], "pins 29 / 31", 1.0, 0.0, ay=120, by=30)
    link("hub", "i2c", W["sda"], "3V3 · GND · SDA · SCL", 0.5, 0.5)
    link("hub", "mq", W["5v"], "5V · GND · divider", 0.9, 0.5)
    link("pi", "aud", "#555b62", "USB ports", 0.9, 0.3)
    link("pi", "srv", "#d9cfb6", "camera ribbon", 1.0, 0.0, ay=10, by=70)
    s.text(20, 636, "Echo lines: sonar Echo → hub divider → Pi pins 36 / 22 / 40.  Common ground: L298N GND → Pi pin 9.", 9, INK, "start", 600)
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
    """Front three-quarter style illustration of the finished robot."""
    s = S(560, 400)
    s.add('<defs><linearGradient id="deck" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#e3f1fb"/>'
          '<stop offset="1" stop-color="#a9cde6"/></linearGradient></defs>')
    gy = 330
    s.add(f'<ellipse cx="280" cy="{gy + 32}" rx="230" ry="20" fill="#0b1a2b" opacity="0.18"/>')
    # rear wheels (smaller, behind)
    for wx in (128, 432):
        s.add(f'<ellipse cx="{wx}" cy="{gy - 10}" rx="26" ry="36" fill="#15181b"/>')
    # bottom deck
    s.add(f'<path d="M100 {gy - 40} L460 {gy - 40} L500 {gy - 10} L60 {gy - 10} Z" fill="url(#deck)" stroke="#6f9cbc" stroke-width="2"/>')
    s.rect(220, gy - 64, 120, 26, "#b8322a", rx=4)
    s.text(280, gy - 46, "L298N", 11, "#fff", "middle", 800)
    # standoffs
    for sx in (110, 450):
        s.rect(sx, gy - 140, 8, 100, "#d4b24c", "#9c7f2a", rx=1)
    # top deck
    s.add(f'<path d="M100 {gy - 150} L460 {gy - 150} L500 {gy - 120} L60 {gy - 120} Z" fill="url(#deck)" stroke="#6f9cbc" stroke-width="2"/>')
    s.rect(120, gy - 196, 120, 50, "#1d3d8f", rx=6)
    for i in range(3):
        s.rect(128, gy - 190 + i * 14, 104, 10, "#2f7dd1", rx=4)
    s.rect(250, gy - 186, 110, 40, PCB, PCB_D, rx=5)
    s.text(305, gy - 162, "Raspberry Pi 4", 9.5, "#fff", "middle", 700)
    s.rect(370, gy - 172, 70, 24, BLUE, rx=4)
    # front wheels (big, in front)
    for wx in (72, 488):
        s.add(f'<ellipse cx="{wx}" cy="{gy}" rx="34" ry="46" fill="#202326" stroke="#0d0f11" stroke-width="2"/>')
        s.add(f'<ellipse cx="{wx}" cy="{gy}" rx="15" ry="21" fill="#f2c230"/>')
    # front sonar bar
    s.rect(160, gy - 118, 240, 14, "#26292c", rx=4)
    for i, cx in enumerate((190, 280, 370)):
        s.rect(cx - 36, gy - 112, 72, 34, BLUE, BLUE_D, rx=5)
        s.circle(cx - 16, gy - 95, 12, "#c9ced3", "#8b9399", 1.5)
        s.circle(cx + 16, gy - 95, 12, "#c9ced3", "#8b9399", 1.5)
        s.circle(cx - 16, gy - 95, 6, "#4a4f55")
        s.circle(cx + 16, gy - 95, 6, "#4a4f55")
    # mast + pan/tilt + camera
    s.rect(272, gy - 270, 16, 84, "#26292c", rx=3)
    s.rect(248, gy - 286, 64, 22, "#26292c", rx=4)
    s.rect(256, gy - 324, 48, 42, PCB, PCB_D, rx=5)
    s.circle(280, gy - 303, 13, "#1c2b40", "#0a0f16", 3)
    s.circle(276, gy - 307, 4, "#9fc3ff")
    # status LED glow
    s.circle(445, gy - 160, 5, "#55e07a")
    return s.svg("cover")
