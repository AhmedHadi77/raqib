"""One big colourful wiring poster of the whole budget robot: every part, every wire.

    python docs/build_guide/poster.py      -> docs/Raqib_Full_Wiring_Diagram.pdf (A3 landscape) + .png

Layout: the hub board's five rails (5V, 3V3, GND, SDA, SCL) run as bus lines down both sides; every sensor
taps them (a dot = a real connection, lines crossing without a dot are not connected). Signal wires go to the
enlarged 40-pin header of the Raspberry Pi in the middle. Pins and wire colours match edge/config.yaml,
the build guide and the atlas.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from draw import (BANDS, BLUE, INK, MUTED, PCB, PCB_D, PI_PINS, S, W, ads1115, aht20, battery_2s, buck_xl4015,  # noqa: E402
                  gpio_header, gy521, hcsr04, l298n, mq135, pam8403, pi4, resistor, slot_encoder, speaker, tag,
                  tt_motor, webcam, wire)

OUT_PDF = HERE.parent / "Raqib_Full_Wiring_Diagram.pdf"
OUT_PNG = HERE.parent / "Raqib_Full_Wiring_Diagram.png"
CW, CH = 2000, 1414

C5, C33, CG, CSDA, CSCL = W["5v"], W["3v3"], W["gnd"], W["sda"], W["scl"]
CBAT, CMOT, CPWM, CSIG, CAUD = W["bat"], W["mot"], W["pwm"], W["sig1"], W["audio"]
SW = 3.0


def dot(s, x, y, c):
    s.circle(x, y, 5, c, "#fff", 1.6)


def label(s, x, y, t, c, anchor="start", size=10):
    tag(s, x, y, t, c, size, anchor, fg=INK if c in (CSCL, CPWM, C33) else "#fff")


def title(s, x, y, t, size=13, c=INK):
    s.text(x, y, t, size, c, "start", 800)


def build() -> str:
    s = S(CW, CH, bg="#ffffff")
    s.text(40, 46, "RAQIB · FULL WIRING DIAGRAM", 30, INK, "start", 800)
    s.text(40, 74, "Budget robot (under RM 500) · every part and every wire · physical Pi pin numbers · "
           "a dot = connected, crossing lines without a dot are not connected", 13, MUTED, "start", 600)

    # ------------------------------------------------------------------ hub rails (top centre) + buses
    RY = {"5V": 150, "3V3": 175, "GND": 200, "SDA": 225, "SCL": 250}
    RC = {"5V": C5, "3V3": C33, "GND": CG, "SDA": CSDA, "SCL": CSCL}
    HX0, HX1 = 760, 1250
    s.rect(730, 112, 550, 166, "#d8b77a", "#9c7f42", rx=10, sw=2)
    for gx in range(53):
        for gy in range(15):
            s.circle(738 + gx * 10, 120 + gy * 10.5, 1.1, "#b39258")
    s.text(1005, 132, "HUB BOARD (perfboard) · power and I²C rails", 12, "#5b4520", "middle", 800)
    for n, y in RY.items():
        s.line(HX0, y, HX1, y, RC[n], 5)
        s.text(HX0 + 8, y - 5, n, 9, RC[n] if n != "GND" else INK, "start", 800)
    # left bus: all five rails run down the left side
    LB = {"5V": 650, "3V3": 664, "GND": 678, "SDA": 692, "SCL": 706}
    for n, x in LB.items():
        wire(s, [(HX0, RY[n]), (x, RY[n]), (x, 1300)], RC[n], 4, r=6)
        s.text(x, 1318, n, 8.5, RC[n] if n != "GND" else INK, "middle", 800, rot=-90)
    # right bus: 5V and GND for the sonars and the amplifier
    RB = {"GND": 1300, "5V": 1314}
    for n, x in RB.items():
        wire(s, [(HX1, RY[n]), (x, RY[n]), (x, 1080)], RC[n], 4, r=6)
        s.text(x, 1098, n, 8.5, RC[n] if n != "GND" else INK, "middle", 800, rot=-90)

    # ------------------------------------------------------------------ the enlarged 40-pin header (centre)
    used = {1: C33, 2: C5, 3: CSDA, 5: CSCL, 6: CG, 9: CG, 11: CSIG, 13: CSIG, 15: CSIG, 16: CSIG, 18: W["sig3"],
            22: W["sig3"], 29: W["sig4"], 31: W["sig4"], 32: W["sig5"], 33: CPWM, 35: CPWM, 36: W["sig5"], 38: W["sig6"],
            40: W["sig6"]}
    HXH, HYH = 978, 420
    P = gpio_header(s, HXH, HYH, used, pitch=28, labels="none")
    s.text(HXH + 23, HYH + 628, "40-pin header", 11, INK, "middle", 800)
    s.text(HXH + 23, HYH + 644, "(enlarged)", 10, MUTED, "middle", 600)
    # header -> hub rails
    for pin, rail, x in ((1, "3V3", 952), (3, "SDA", 940), (5, "SCL", 928)):
        px, py, _ = P[pin]
        wire(s, [(px, py), (x, py), (x, RY[rail])], used[pin], SW, r=5)
        dot(s, x, RY[rail], used[pin])
    for pin, rail, x in ((2, "5V", 1048), (6, "GND", 1062)):
        px, py, _ = P[pin]
        wire(s, [(px, py), (x, py), (x, RY[rail])], used[pin], SW, r=5)
        dot(s, x, RY[rail], used[pin])

    # ------------------------------------------------------------------ Raspberry Pi board (top right)
    pk = 0.9
    k = 3.4 * pk
    PX, PY = 1500, 96
    pins = pi4(s, PX, PY, pk)
    title(s, PX, PY - 10, "Raspberry Pi 4 (2 GB)")
    s.path(f"M{pins[1][0]} {pins[1][1]} L{HXH} {HYH - 22}", stroke="#9aa3ab", sw=1.4, extra='stroke-dasharray="6 5"')
    s.path(f"M{pins[40][0]} {pins[40][1]} L{HXH + 54} {HYH - 22}", stroke="#9aa3ab", sw=1.4, extra='stroke-dasharray="6 5"')
    s.text(1150, 372, "the header, enlarged ↓", 10, MUTED, "start", 600, italic=True)
    usbc = (PX + 11.5 * k, PY + 56 * k + 2)
    jack = (PX + 54 * k, PY + 56 * k)
    usb3 = (PX + 85 * k + 2, PY + 27 * k)

    # ------------------------------------------------------------------ power (top left)
    title(s, 30, 104, "Battery 2 × 18650 · 7.4 V")
    bat = battery_2s(s, 30, 116, 1.0)
    title(s, 250, 104, "XL4015 → 5.1 V")
    bk = buck_xl4015(s, 250, 116, 1.0)
    (bpx, bpy), (bnx, bny) = bat["+"], bat["-"]
    wire(s, [(bpx, bpy), (230, bpy), (230, bk["IN+"][1]), bk["IN+"]], CBAT, SW, r=4)
    wire(s, [(bnx, bny), (214, bny), (214, bk["IN-"][1] + 0), (240, bk["IN-"][1]), bk["IN-"]], CG, SW, r=4)
    s.rect(236, bk["IN+"][1] - 6, 14, bk["IN-"][1] - bk["IN+"][1] + 12, "#1d3f8f", "#0f2457", rx=3)
    s.text(243, 116 + 92, "1000 µF", 9, "#1d3f8f", "middle", 800)
    # XL4015 out -> cut USB cable -> Pi USB-C
    ox, oyp = bk["OUT+"]
    _, oyn = bk["OUT-"]
    wire(s, [(ox, oyp), (412, oyp), (412, 96)], "#e23b2e", 2.6, r=4)
    wire(s, [(ox, oyn), (424, oyn), (424, 96)], "#2a2e31", 2.6, r=4)
    wire(s, [(418, 96), (418, 88), (1460, 88), (1460, 300), (usbc[0], 300), usbc], "#555b62", 7, r=12)
    label(s, 700, 92, "cut USB cable: XL4015 OUT → Pi USB-C power (5.1 V)", "#555b62")
    # battery -> L298N (+12V / GND)
    LX, LY = 300, 470
    l2 = l298n(s, LX, LY, 1.0)
    title(s, LX, LY - 10, "L298N motor driver")
    wire(s, [(bpx, bpy), (bpx + 6, bpy), (bpx + 6, 690), (l2["+12V"][0], 690), l2["+12V"]], CBAT, SW, r=5)
    dot(s, bpx + 6, bpy, CBAT)
    wire(s, [(bnx, bny), (bnx + 20, bny), (bnx + 20, 702), (l2["GND"][0], 702), l2["GND"]], CG, SW, r=5)
    dot(s, bnx + 20, bny, CG)
    label(s, 190, 420, "battery + → L298N +12V", CBAT, "end", 9)
    # motors: 4WD, the front and rear motor of each side joined (red to red, black to black)
    k = 0.9
    s.text(40, 462, "LEFT pair (front + rear)", 10, INK, "start", 800)
    for my in (520, 586):
        tt_motor(s, 40, my, k, wheel=(my == 520))
    s.text(40, 618, "rear motor", 8.5, MUTED, "start", 600)
    for i, (o, c) in enumerate((("OUT1", "#e23b2e"), ("OUT2", "#2a2e31"))):
        x0, y0 = l2[o]
        t1 = (40 + 94 * k, 520 + (7.5 if i == 0 else 14.5) * k)
        t2 = (40 + 94 * k, 586 + (7.5 if i == 0 else 14.5) * k)
        wire(s, [(x0, y0), (286 - i * 8, y0), (286 - i * 8, t1[1]), t1], c, 2.6, r=4)
        jx = 140 + i * 10
        wire(s, [(jx, t1[1]), (jx, t2[1]), t2], c, 2.4, r=3)
        dot(s, jx, t1[1], c)
    s.text(470, 352, "RIGHT pair (front + rear)", 10, INK, "start", 800)
    tt_motor(s, 470, 380, k, wheel=False)
    tt_motor(s, 470, 412, k, wheel=False)
    for i, (o, c) in enumerate((("OUT3", "#e23b2e"), ("OUT4", "#2a2e31"))):
        x0, y0 = l2[o]
        t1 = (470 + 94 * k, 380 + (7.5 if i == 0 else 14.5) * k)
        t2 = (470 + 94 * k, 412 + (7.5 if i == 0 else 14.5) * k)
        lane = t1[0] + 10 + i * 8
        wire(s, [(x0, y0), (510 + i * 8, y0), (510 + i * 8, 446), (lane, 446), (lane, t1[1]), t1], c, 2.6, r=4)
        wire(s, [(lane, t2[1]), t2], c, 2.4, r=3)
        dot(s, lane, t2[1], c)

    # header -> L298N signals: row -> lane -> level below the board -> pin
    routes = [(9, "GND", CG), (33, "ENA", CPWM), (11, "IN1", CSIG), (13, "IN2", CSIG), (15, "IN3", CSIG), (16, "IN4", CSIG),
              (35, "ENB", CPWM)]
    for i, (pin, tgt, c) in enumerate(routes):
        px, py, side = P[pin]
        tx, ty = l2[tgt]
        level = 760 - i * 9
        lane = 920 - i * 12 if side == "L" else None
        if side == "L":
            pts = [(px, py), (lane, py), (lane, level), (tx, level), (tx, ty)]
        else:
            pts = [(px, py), (1076, py), (1076, 1010), (838, 1010), (838, level), (tx, level), (tx, ty)]
        wire(s, pts, c, SW, r=5)
    label(s, 40, 806, "pin 33 → ENA · pin 35 → ENB (speed) · pins 11/13/15/16 → IN1-IN4 · pin 9 → GND", CSIG, "start", 9)

    # ------------------------------------------------------------------ I2C sensors (left middle)
    title(s, 40, 842, "MPU6050 (0x68)")
    mpu = gy521(s, 40, 856, 1.0)
    title(s, 210, 842, "AHT20 + BMP280")
    aht = aht20(s, 210, 856, 1.1)
    title(s, 360, 842, "ADS1115 (0x48)")
    ads = ads1115(s, 360, 856, 1.0)
    taps = [(mpu, "VCC", "3V3"), (mpu, "GND", "GND"), (mpu, "SCL", "SCL"), (mpu, "SDA", "SDA"),
            (aht, "VIN", "3V3"), (aht, "GND", "GND"), (aht, "SCL", "SCL"), (aht, "SDA", "SDA"),
            (ads, "VDD", "3V3"), (ads, "GND", "GND"), (ads, "SCL", "SCL"), (ads, "SDA", "SDA"), (ads, "ADDR", "GND")]
    taps.sort(key=lambda t: t[0][t[1]][0])
    for i, (dev, pin, rail) in enumerate(taps):
        px, py = dev[pin]
        lvl = 1004 - i * 6.5
        wire(s, [(px, py), (px, lvl), (LB[rail], lvl)], RC[rail], 2.4, r=3)
        dot(s, LB[rail], lvl, RC[rail])

    # gas sensor + dividers (bottom left)
    title(s, 40, 1056, "MQ-135 gas sensor")
    mq = mq135(s, 40, 1068, 1.0)
    for pin, rail, lvl in (("VCC", "5V", 1196), ("GND", "GND", 1186)):
        px, py = mq[pin]
        wire(s, [(px, py), (px, lvl), (LB[rail], lvl)], RC[rail], 2.4, r=3)
        dot(s, LB[rail], lvl, RC[rail])
    ax, ay = mq["AO"]
    resistor(s, 230, 1080, 230, 1120, BANDS["10k"])
    resistor(s, 230, 1120, 230, 1160, BANDS["20k"])
    s.circle(230, 1120, 3.4, INK)
    s.text(240, 1102, "10k", 8.5, INK, "start", 700)
    s.text(240, 1146, "20k", 8.5, INK, "start", 700)
    wire(s, [(ax, ay), (ax, 1212), (204, 1212), (204, 1068), (230, 1068), (230, 1080)], "#7a7f87", 2.4, r=4)
    wire(s, [(230, 1160), (230, 1176), (LB["GND"], 1176)], CG, 2.4, r=3)
    dot(s, LB["GND"], 1176, CG)
    a0x, a0y = ads["A0"]
    wire(s, [(230, 1120), (300, 1120), (300, 1030), (a0x, 1030), (a0x, a0y)], "#7a7f87", 2.4, r=4)
    label(s, 252, 1240, "MQ-135 divider (on the hub)", "#7a7f87", "start", 8.5)
    # battery divider -> A1
    resistor(s, 610, 640, 610, 690, BANDS["10k"])
    resistor(s, 610, 690, 610, 740, BANDS["4k7"])
    s.circle(610, 690, 3.4, INK)
    s.text(596, 668, "10k", 8.5, INK, "end", 700)
    s.text(596, 720, "4.7k", 8.5, INK, "end", 700)
    wire(s, [(bpx + 6, 300), (610, 300), (610, 640)], CBAT, 2.4, r=4)
    dot(s, bpx + 6, 300, CBAT)
    wire(s, [(610, 740), (610, 760), (LB["GND"], 760)], CG, 2.4, r=3)
    dot(s, LB["GND"], 760, CG)
    a1x, a1y = ads["A1"]
    wire(s, [(610, 690), (632, 690), (632, 1018), (a1x, 1018), (a1x, a1y)], CBAT, 2.4, r=4)
    label(s, 602, 628, "battery divider (hub)", CBAT, "end", 8)

    # wheel encoders (bottom middle-left)
    for j, (name, pin, x) in enumerate((("LEFT encoder", 29, 360), ("RIGHT encoder", 31, 510))):
        title(s, x, 1078, name, 11)
        e = slot_encoder(s, x, 1110, 1.1)
        for p_, rail, lvl in (("VCC", "3V3", 1262 - j * 20), ("GND", "GND", 1252 - j * 20)):
            px, py = e[p_]
            wire(s, [(px, py), (px, lvl), (LB[rail], lvl)], RC[rail], 2.4, r=3)
            dot(s, LB[rail], lvl, RC[rail])
        dx, dy = e["D0"]
        hx, hy, _ = P[pin]
        lane = 836 - j * 12
        wire(s, [(dx, dy), (dx, 1282 + j * 10), (lane, 1282 + j * 10), (lane, hy), (hx, hy)], W["sig4"], SW, r=5)

    # ------------------------------------------------------------------ ultrasonic sensors (right)
    sonars = [("CENTRE", 470, 18, 22), ("LEFT (45° left)", 680, 32, 36), ("RIGHT (45° right)", 890, 38, 40)]
    for i, (name, y, trig, echo) in enumerate(sonars):
        c = used[trig]
        sx = 1560
        title(s, sx, y - 8, f"HC-SR04 {name}", 11)
        h = hcsr04(s, sx, y, 1.0)
        # power from the right bus
        for p_, rail, lvl in (("VCC", "5V", y + 110), ("Gnd", "GND", y + 120)):
            px, py = h[p_]
            wire(s, [(px, py), (px, lvl), (RB[rail], lvl)], RC[rail], 2.4, r=3)
            dot(s, RB[rail], lvl, RC[rail])
        # echo divider (on the hub board)
        dxr = 1420
        resistor(s, dxr, y + 4, dxr, y + 44, BANDS["1k"])
        resistor(s, dxr, y + 44, dxr, y + 84, BANDS["2k"])
        s.circle(dxr, y + 44, 3.2, INK)
        s.text(dxr + 8, y + 26, "1k", 8, INK, "start", 700)
        s.text(dxr + 8, y + 70, "2k", 8, INK, "start", 700)
        wire(s, [(dxr, y + 84), (dxr, y + 96), (RB["GND"], y + 96)], CG, 2.2, r=3)
        dot(s, RB["GND"], y + 96, CG)
        ex, ey = h["Echo"]
        wire(s, [(ex, ey), (ex, ey + 14), (1532, ey + 14), (1532, y - 4), (dxr, y - 4), (dxr, y + 4)], "#7a7f87", 2.4, r=4)
        hx, hy, _ = P[echo]
        wire(s, [(dxr, y + 44), (1370 - i * 10, y + 44), (1370 - i * 10, hy), (hx, hy)], c, SW, r=5)
        tx_, ty_ = h["Trig"]
        hx, hy, _ = P[trig]
        wire(s, [(tx_, ty_), (tx_, ty_ + 30), (1384 - i * 10, ty_ + 30), (1384 - i * 10, hy), (hx, hy)], c, SW, r=5)
    label(s, 1450, 1150, "Trig straight to the Pi · Echo (5 V) through 1k/2k to the Pi", W["sig3"], "start", 9)

    # ------------------------------------------------------------------ sound (right top)
    title(s, 1600, 418, "PAM8403 amplifier", 11)
    pam = pam8403(s, 1600, 344, 1.0)
    speaker(s, 1770, 372, 26)
    wire(s, [jack, (jack[0], 318), (1580, 318), (1580, pam["L"][1]), pam["L"]], CAUD, 2.6, r=4)
    wire(s, [(jack[0] + 6, jack[1]), (jack[0] + 6, 326), (1588, 326), (1588, pam["G"][1]), pam["G"]], CG, 2.2, r=4)
    label(s, 1690, 304, "3.5 mm cable from the Pi audio jack", CAUD, "start", 8.5)
    wire(s, [pam["out L+"], (1720, pam["out L+"][1]), (1720, 366), (1746, 366)], "#e23b2e", 2.4, r=3)
    wire(s, [pam["out L-"], (1712, pam["out L-"][1]), (1712, 380), (1746, 380)], "#2a2e31", 2.4, r=3)
    wire(s, [pam["5V"], (1560, pam["5V"][1]), (1560, 420), (RB["5V"], 420)], C5, 2.4, r=3)
    dot(s, RB["5V"], 420, C5)
    wire(s, [pam["G"], (1594, pam["G"][1]), (1594, 432), (RB["GND"], 432)], CG, 2.2, r=3)
    dot(s, RB["GND"], 432, CG)

    # ------------------------------------------------------------------ webcam (top right)
    title(s, 1800, 470, "USB webcam + mic", 11)
    cam = webcam(s, 1800, 486, 0.85)
    ux, uy = cam["usb"]
    wire(s, [(ux, uy), (1960, uy), (1960, usb3[1]), usb3], "#555b62", 6, r=10)
    label(s, 1952, 420, "USB → Pi USB 3", "#555b62", "end", 9)

    # ------------------------------------------------------------------ legend
    ly = 1370
    items = [(C5, "5 V"), (C33, "3.3 V"), (CG, "GND"), (CSDA, "I²C SDA"), (CSCL, "I²C SCL"), (CBAT, "battery 7.4 V"),
             (CPWM, "PWM speed"), (CSIG, "motor direction"), (W["sig3"], "sonar centre"), (W["sig5"], "sonar left"),
             (W["sig6"], "sonar right"), (W["sig4"], "encoders"), ("#7a7f87", "analog / divider"), ("#555b62", "USB cable")]
    x = 40
    for c, t in items:
        s.rect(x, ly - 8, 26, 8, c, rx=4)
        s.text(x + 32, ly, t, 11, INK, "start", 600)
        x += 40 + len(t) * 6.6
    s.text(CW - 40, CH - 14, "Raqib · full wiring diagram · matches edge/config.yaml and the build guide", 10, MUTED, "end", 500)
    return s.svg()


def main():
    svg = build()
    html = (f"<!doctype html><html><head><meta charset='utf-8'><style>@page {{ size: A3 landscape; margin: 0 }} "
            f"html,body {{ margin:0; background:#fff }} svg {{ width: 420mm; height: 297mm; display:block }}</style></head>"
            f"<body>{svg}</body></html>")
    page = HERE / "poster.html"
    page.write_text(html, encoding="utf-8")
    js = HERE / "_poster.js"
    js.write_text(f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch(); const p = await b.newPage({{ viewport: {{ width: {CW}, height: {CH} }}, deviceScaleFactor: 2 }});
  await p.goto('file://{page}'); await p.waitForTimeout(400);
  await p.pdf({{ path: '{OUT_PDF}', width: '420mm', height: '297mm', printBackground: true, margin: {{ top: 0, bottom: 0, left: 0, right: 0 }} }});
  await p.setContent(`<html><body style="margin:0">${{require('fs').readFileSync('{page}', 'utf8').match(/<svg[\\s\\S]*<\\/svg>/)[0].replace('<svg ', '<svg width="{CW}" height="{CH}" ')}}</body></html>`);
  await p.waitForTimeout(300);
  await p.locator('svg').screenshot({{ path: '{OUT_PNG}' }});
  await b.close(); }})();""")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js)], check=True, env={**os.environ, "NODE_PATH": npm_root})
    js.unlink()
    page.unlink()
    print("wrote", OUT_PDF, "and", OUT_PNG)


if __name__ == "__main__":
    main()
