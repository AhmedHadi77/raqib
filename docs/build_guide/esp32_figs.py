"""Figures for the ESP32 robot 3.0 build guide and poster (SVG strings)."""
from __future__ import annotations

from draw import BLUE, INK, MUTED, PURPLE, S, W, aht20, battery_2s, caster, gy521, power_bank, tag, tt_motor, wire
from esp32_draw import XIAO_SUB, chassis_2wd, drv8833, half_breadboard, hcsr04p, xiao_sense

C33, CGND, CSDA, CSCL = W["3v3"], W["gnd"], W["sda"], W["scl"]
CBAT, CMOT, CUSB = W["bat"], W["mot"], "#555b62"
CM = {"D0": "#1e9e55", "D1": "#1e9e55", "D2": "#8a55e8", "D3": "#8a55e8", "D6": "#e0458b", "D7": "#0ea5c6"}


def dot(s, x, y, c):
    s.circle(x, y, 4.6, c, "#fff", 1.4)


# ================================================================== the big wiring drawing (every step is a part of it)
def wiring(groups=("power", "motors", "sensors"), title: str | None = None, big=False) -> str:
    """The whole robot's wiring; `groups` picks which wires are drawn (the parts are always shown)."""
    g = set(groups)
    s = S(1120, 730, "#ffffff")
    if title:
        s.text(30, 34, title, 20 if big else 15, INK, "start", 800)
    # ---------------- breadboard rails: top pair and bottom pair (joined at the right end)
    R3T, RGT, R3B, RGB = 112, 134, 664, 686
    x0r, x1r = 300, 1080
    for y, c, lab in ((R3T, C33, "3V3 rail (breadboard +)"), (RGT, CGND, "GND rail (breadboard −)"),
                      (R3B, C33, "3V3 rail (breadboard +)"), (RGB, CGND, "GND rail (breadboard −)")):
        s.line(x0r, y, x1r, y, c, 5)
        s.text(x0r + 4, y - 6, lab, 9, c if c != CGND else INK, "start", 800)
    if g & {"sensors"}:
        wire(s, [(x1r, R3T), (x1r + 18, R3T), (x1r + 18, R3B), (x1r, R3B)], C33, 2.6, r=6)
        wire(s, [(x1r, RGT), (x1r + 10, RGT), (x1r + 10, RGB), (x1r, RGB)], CGND, 2.6, r=6)
        s.text(x1r + 24, 400, "top and bottom rails joined", 8.5, MUTED, "middle", 600, rot=90)

    # ---------------- XIAO ESP32S3 Sense
    X = xiao_sense(s, 470, 200, 1.5, inside=True)
    s.text(548, 470, "XIAO ESP32S3 Sense", 12, INK, "middle", 800)
    s.text(548, 486, "(standing at the front, camera forward)", 9, MUTED, "middle", 600)

    # ---------------- power
    bat = battery_2s(s, 30, 64, 0.8)
    s.text(30, 58, "Motor battery 2 x 18650 (7.4 V)", 10, INK, "start", 800)
    pb = power_bank(s, 760, 14, 0.6)
    s.text(760, 10, "Power bank (ESP32 only)", 10, INK, "start", 800)
    D = drv8833(s, 230, 196, 1.32, flip=True)
    s.text(290, 360, "DRV8833 motor driver", 10.5, INK, "middle", 800)
    if "power" in g:
        ux, uy = pb["usbc"]
        wire(s, [(ux, uy), (ux + 16, uy), (ux + 16, 172), (548, 172), (548, 191)], CUSB, 6, r=10)
        tag(s, 790, 168, "USB-C cable", CUSB, 8.5, "middle")
        (bpx, bpy), (bnx, bny) = bat["+"], bat["-"]
        wire(s, [(bpx, bpy), (204, bpy), (204, D["VM"][1]), D["VM"]], CBAT, 3.4, r=5)
        wire(s, [(bnx, bny), (194, bny), (194, D["GND"][1]), D["GND"]], CGND, 3.4, r=5)
        wire(s, [D["GND"], (214, D["GND"][1]), (214, 150), (316, 150), (316, RGT)], CGND, 3, r=5)
        dot(s, 316, RGT, CGND)
        tag(s, 316, 160, "COMMON GROUND", CGND, 8, "middle")
        wire(s, [X["3V3"], (676, X["3V3"][1]), (676, R3T)], C33, 3, r=5)
        dot(s, 676, R3T, C33)
        wire(s, [X["GND"], (690, X["GND"][1]), (690, RGT)], CGND, 3, r=5)
        dot(s, 690, RGT, CGND)
    # ---------------- motors
    lm, rm = (40, 380), (40, 470)
    tt_motor(s, *lm, 0.95, wheel=False)
    tt_motor(s, *rm, 0.95, wheel=False)
    s.text(40, 372, "LEFT motor", 9.5, INK, "start", 800)
    s.text(40, 462, "RIGHT motor", 9.5, INK, "start", 800)
    tab = lambda m, i: (m[0] + 91 * 0.95, m[1] + (7.5 if i == 0 else 14.5) * 0.95)  # noqa: E731
    if "motors" in g:
        for n, (pin, lane) in {"AIN1": ("D0", 456), "AIN2": ("D1", 446), "BIN1": ("D2", 436), "BIN2": ("D3", 426)}.items():
            px, py = X[pin]
            wire(s, [(px, py), (lane, py), (lane, D[n][1]), D[n]], CM[pin], 3, r=5)
        for i, (out, m, lane) in enumerate((("AOUT1", lm, 186), ("AOUT2", lm, 176), ("BOUT1", rm, 166), ("BOUT2", rm, 156))):
            tx, ty = tab(m, i % 2)
            wire(s, [D[out], (lane, D[out][1]), (lane, ty), (tx, ty)], CMOT, 2.8, r=5)
    # ---------------- sensors
    M = gy521(s, 250, 530, 0.95)
    s.text(364, 560, "MPU6050", 9.5, INK, "start", 800)
    s.text(364, 573, "(heading)", 8.5, MUTED, "start", 600)
    A = aht20(s, 432, 548, 1.05)
    s.text(518, 572, "AHT20 + BMP280", 9.5, INK, "start", 800)
    s.text(518, 585, "(climate)", 8.5, MUTED, "start", 600)
    U = hcsr04p(s, 760, 420, 1.05)
    s.text(760, 412, "HC-SR04P (3.3 V) at the front", 9.5, INK, "start", 800)
    if "sensors" in g:
        SDA_Y, SCL_Y = 500, 490
        wire(s, [X["D4"], (462, X["D4"][1]), (462, SDA_Y)], CSDA, 3, r=5)
        wire(s, [X["D5"], (454, X["D5"][1]), (454, SCL_Y)], CSCL, 3, r=5)
        s.line(268, SDA_Y, 462, SDA_Y, CSDA, 3)
        s.line(268, SCL_Y, 454, SCL_Y, CSCL, 3)
        SDA_Y, SCL_Y = SDA_Y, SCL_Y
        for part, sda, scl in ((M, "SDA", "SCL"), (A, "SDA", "SCL")):
            wire(s, [(part[sda][0], SDA_Y), part[sda]], CSDA, 2.6, r=4)
            dot(s, part[sda][0], SDA_Y, CSDA)
            wire(s, [(part[scl][0], SCL_Y), part[scl]], CSCL, 2.6, r=4)
            dot(s, part[scl][0], SCL_Y, CSCL)
        tag(s, 340, SCL_Y - 10, "SDA D4 · SCL D5 (I²C)", CSDA, 8, "middle")
        for part, v in ((M, "VCC"), (A, "VIN")):
            wire(s, [part[v], (part[v][0], R3B)], C33, 2.6, r=4)
            dot(s, part[v][0], R3B, C33)
            wire(s, [part["GND"], (part["GND"][0], RGB)], CGND, 2.6, r=4)
            dot(s, part["GND"][0], RGB, CGND)
        wire(s, [X["D6"], (440, X["D6"][1]), (440, 520), (U["Trig"][0], 520), U["Trig"]], CM["D6"], 3, r=5)
        wire(s, [X["D7"], (1000, X["D7"][1]), (1000, 530), (U["Echo"][0], 530), U["Echo"]], CM["D7"], 3, r=5)
        wire(s, [U["VCC"], (U["VCC"][0], R3B)], C33, 2.6, r=4)
        dot(s, U["VCC"][0], R3B, C33)
        wire(s, [U["Gnd"], (U["Gnd"][0], RGB)], CGND, 2.6, r=4)
        dot(s, U["Gnd"][0], RGB, CGND)
        tag(s, 640, 516, "TRIG D6 · ECHO D7", CM["D6"], 8, "middle")
    # ---------------- legend
    items = [(C33, "3.3 V"), (CGND, "GND"), (CBAT, "motor battery +"), (CUSB, "USB cable"), (CM["D0"], "left motor D0/D1"),
             (CM["D2"], "right motor D2/D3"), (CMOT, "motor wires"), (CSDA, "SDA"), (CSCL, "SCL"), (CM["D6"], "TRIG"), (CM["D7"], "ECHO")]
    x = 30
    for c, t in items:
        s.rect(x, 712, 22, 7, c, rx=3)
        s.text(x + 27, 719, t, 9, INK, "start", 600)
        x += 36 + len(t) * 5.6
    return s.svg()


# ================================================================== the system: who does what
def fig_system() -> str:
    s = S(760, 330)

    def box(x, y, w, h, color, title, lines):
        s.rect(x, y, w, h, color, rx=14)
        s.text(x + w / 2, y + 26, title, 13, "#fff", "middle", 800)
        for i, ln in enumerate(lines):
            s.text(x + w / 2, y + 48 + i * 16, ln, 9.5, "#eef2ff", "middle", 500)

    box(20, 60, 180, 150, "#3355d1", "Phone app", ["drive, live video", "inspect rooms by voice", "exam alerts with photos",
                                                 "reports, history"])
    box(290, 40, 190, 190, "#1f7a4d", "PC = the brain", ["server + AI (Gemini)", "robot program:", "routes, safety, exam rules",
                                                         "photo checks (MediaPipe)", "reports and memory"])
    box(570, 60, 170, 150, "#0d1530", "Robot = the body", ["XIAO ESP32S3 Sense", "2 motors (DRV8833)", "distance, heading,",
                                                           "climate, camera, mic"])
    for x1, x2, y, t in ((200, 290, 135, "Wi-Fi"), (480, 570, 135, "Wi-Fi")):
        s.line(x1 + 4, y, x2 - 8, y, "#16202a", 2.4)
        s.path(f"M{x2 - 14} {y - 6} L{x2 - 4} {y} L{x2 - 14} {y + 6}", "#16202a")
        s.path(f"M{x1 + 14} {y - 6} L{x1 + 4} {y} L{x1 + 14} {y + 6}", "#16202a")
        s.text((x1 + x2) / 2, y - 10, t, 9.5, MUTED, "middle", 700)
    s.text(380, 262, "Same Wi-Fi for all three: your phone's hotspot is easiest (the PC keeps internet for the AI).",
           10, INK, "middle", 600)
    s.text(380, 282, "The robot stops by itself if the PC goes quiet for 0.6 s or something is closer than 15 cm.",
           10, INK, "middle", 600)
    s.text(380, 302, "The robot has no speaker: the phone speaks the replies and shows the alerts.", 10, MUTED, "middle", 600)
    return s.svg()


# ================================================================== XIAO pin map
USE = {"D0": ("DRV8833 AIN1 · left motor", CM["D0"]), "D1": ("DRV8833 AIN2 · left motor", CM["D1"]),
       "D2": ("DRV8833 BIN1 · right motor", CM["D2"]), "D3": ("DRV8833 BIN2 · right motor", CM["D3"]),
       "D4": ("SDA · MPU6050 + AHT20", CSDA), "D5": ("SCL · MPU6050 + AHT20", CSCL),
       "D6": ("HC-SR04P TRIG", CM["D6"]), "D7": ("HC-SR04P ECHO", CM["D7"]),
       "5V": ("not used", "#9aa3ab"), "GND": ("GND rail", CGND), "3V3": ("3V3 rail", C33),
       "D8": ("free", "#9aa3ab"), "D9": ("free", "#9aa3ab"), "D10": ("free", "#9aa3ab")}


def fig_xiao_map() -> str:
    s = S(760, 380)
    X = xiao_sense(s, 300, 60, 1.55, labels=False)
    for name, (px, py) in X.items():
        txt, c = USE[name]
        left = px < 380
        fg = INK if c in (CSCL, C33, "#9aa3ab") else "#fff"
        x2 = px - 34 if left else px + 34
        s.line(px, py, x2, py, c, 2)
        s.circle(px, py, 4, c, "#fff", 1.2)
        tag(s, x2 - (4 if left else -4), py + 4, f"{name}  {txt}", c, 9, "end" if left else "start", fg=fg)
    s.text(380, 30, "XIAO ESP32S3 Sense from above (USB-C at the top)", 13, INK, "middle", 800)
    s.text(380, 370, "D0-D7 are printed next to the pins on the board. The camera and microphone use inside pins: no wires.",
           10, MUTED, "middle", 600)
    return s.svg()


# ================================================================== layout on the chassis
def fig_layout_top() -> str:
    s = S(760, 350)
    k = 1.45
    x, y = 200, 64
    chassis_2wd(s, x, y, k)
    s.text(380, 20, "TOP DECK seen from above · front of the robot →", 12, INK, "middle", 800)

    def part(px, py, pw, ph, col, label, sub="", fg="#fff", rot=None):
        s.rect(x + px * k, y + py * k, pw * k, ph * k, col, rx=5)
        cx, cy = x + (px + pw / 2) * k, y + (py + ph / 2) * k
        s.text(cx, cy + (0 if sub else 3.5), label, 9, fg, "middle", 800, rot=rot)
        if sub:
            s.text(cx, cy + 12, sub, 7, fg, "middle", 500)

    part(44, 26, 92, 62, "#ece6d6", "half breadboard", "DRV8833, MPU6050, AHT20", INK)
    part(44, 96, 70, 40, "#2b2f36", "power bank", "for the ESP32")
    part(196, 58, 14, 44, "#1b1d20", "XIAO", rot=-90)
    part(228, 46, 16, 68, BLUE, "sonar", rot=-90)
    s.line(x + 212 * k, y + 80 * k, x + 226 * k, y + 80 * k, "#9fc3ff", 2)
    s.text(380, 340, "Under the deck: the 2 x 18650 motor battery (switch reachable). Camera and sonar face forward.",
           10, MUTED, "middle", 600)
    return s.svg()


def fig_layout_side() -> str:
    s = S(760, 270)
    gy = 220
    s.line(40, gy + 30, 720, gy + 30, "#c4ccd3", 3)
    s.circle(560, gy, 32, "#202326", "#111", 2)
    s.circle(560, gy, 13, "#f2c230")
    s.circle(170, gy + 16, 14, "#c9ced3", "#8b9399", 1.5)
    s.text(170, gy + 50, "caster", 8, MUTED, "middle", 600)
    s.rect(150, gy - 24, 470, 8, "#cfe6f5", "#7fa8c4", rx=3)
    s.rect(300, gy - 14, 150, 22, "#2f7dd1", "#1d4f87", rx=5)
    s.text(375, gy + 1, "motor battery (under)", 8, "#fff", "middle", 700)
    s.rect(500, gy - 22, 70, 22, "#f2c230", "#b38a12", rx=3)
    s.rect(220, gy - 44, 170, 20, "#ece6d6", "#cdc7b5", rx=3)
    s.text(305, gy - 30, "breadboard", 8, INK, "middle", 700)
    s.rect(400, gy - 46, 80, 22, "#2b2f36", rx=4)
    s.text(440, gy - 31, "power bank", 8, "#fff", "middle", 700)
    s.rect(560, gy - 120, 20, 96, "#1b1d20", rx=3)
    s.circle(586, gy - 100, 7, "#0f1a2a", "#4a4f55", 2)
    s.text(600, gy - 118, "XIAO + camera", 8.5, INK, "start", 700)
    s.text(600, gy - 104, "standing, lens forward", 8, MUTED, "start", 600)
    s.rect(596, gy - 50, 14, 36, BLUE, rx=2)
    s.text(616, gy - 30, "HC-SR04P", 8.5, INK, "start", 700)
    s.text(690, gy + 12, "front →", 9, INK, "end", 800)
    s.text(40, 26, "SIDE VIEW · one deck; the camera looks forward over the sonar", 12, INK, "start", 800)
    return s.svg()


# ================================================================== part cards
def card(name: str) -> str:
    sizes = {"xiao": (230, 230), "pbank": (200, 96), "bat2": (190, 96), "chassis": (300, 200), "motor": (200, 60),
             "drv": (150, 140), "hc": (175, 100), "imu": (140, 110), "aht": (110, 100), "breadboard": (300, 210),
             "wires": (190, 110), "tools": (330, 180)}
    w, h = sizes[name]
    s = S(w, h)
    if name == "xiao":
        xiao_sense(s, 64, 26, 0.95)
    elif name == "pbank":
        power_bank(s, 8, 9, 1.0)
    elif name == "bat2":
        battery_2s(s, 6, 2, 1.0)
    elif name == "chassis":
        chassis_2wd(s, 30, 30, 1.0)
    elif name == "motor":
        tt_motor(s, 40, 20, 1.3, wheel=False)
    elif name == "drv":
        drv8833(s, 28, 12, 1.05)
    elif name == "hc":
        hcsr04p(s, 18, 8, 1.0)
    elif name == "imu":
        gy521(s, 14, 6, 1.0)
    elif name == "aht":
        aht20(s, 16, 8, 1.0)
    elif name == "breadboard":
        half_breadboard(s, 6, 4, 1.0)
    else:
        from diagrams import fig_component

        return fig_component(name)
    return s.svg("comp")


__all__ = ["wiring", "fig_system", "fig_xiao_map", "fig_layout_top", "fig_layout_side", "card", "caster", "PURPLE"]
