"""Tiny SVG drawing kit for the Raqib build guide: boards, pins, wires and the robot's components."""
from __future__ import annotations

import math
from html import escape

# ---------------------------------------------------------------- colours
PCB, PCB_D = "#1f7a4d", "#145a37"
BLUE, BLUE_D = "#1f5fbf", "#163f80"
RED_B, RED_D = "#b8322a", "#7d1f1a"
PURPLE, PURPLE_D = "#6b3fa0", "#4a2a70"
BLACK_B = "#26292c"
GOLD = "#e3b94b"
SILK = "#f4f8f5"
METAL, METAL_D = "#c9ced3", "#8b9399"
INK, MUTED, LINE = "#16202a", "#5b6670", "#d3d9df"
W = {  # wire colours (same meaning on every page)
    "5v": "#e23b2e", "3v3": "#f08a00", "gnd": "#2a2e31", "sda": "#2d6be0", "scl": "#d9a800",
    "bat": "#c0151b", "mot": "#8d5a3b", "sig1": "#1e9e55", "sig2": "#8a55e8", "sig3": "#e0458b",
    "sig4": "#0ea5c6", "sig5": "#6d7a12", "sig6": "#b4530f", "pwm": "#f2b705", "audio": "#7a7f87",
}


class S:
    def __init__(self, w: float, h: float, bg: str | None = None):
        self.w, self.h, self.items = w, h, []
        if bg:
            self.rect(0, 0, w, h, bg, rx=0)

    def add(self, s: str):
        self.items.append(s)
        return self

    def rect(self, x, y, w, h, fill, stroke=None, rx=4, sw=1.2, op=1):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        return self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{st} opacity="{op}"/>')

    def circle(self, cx, cy, r, fill, stroke=None, sw=1.2):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        return self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{st}/>')

    def line(self, x1, y1, x2, y2, color, sw=1.5, dash=None, cap="round"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{sw}" stroke-linecap="{cap}"{d}/>')

    def path(self, d, fill="none", stroke=None, sw=1.5, extra=""):
        st = f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"' if stroke else ""
        return self.add(f'<path d="{d}" fill="{fill}"{st} {extra}/>')

    def text(self, x, y, t, size=11, fill=INK, anchor="start", weight=400, mono=False, rot=None, italic=False):
        fam = "DejaVu Sans Mono" if mono else "Inter"
        tr = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else ""
        it = ' font-style="italic"' if italic else ""
        return self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}, DejaVu Sans, sans-serif" font-size="{size}" '
                        f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{tr}{it}>{escape(str(t))}</text>')

    def svg(self, cls="fig"):
        return (f'<svg class="{cls}" viewBox="0 0 {self.w} {self.h}" xmlns="http://www.w3.org/2000/svg">'
                + "".join(self.items) + "</svg>")


# ---------------------------------------------------------------- building blocks
def board(s, x, y, w, h, fill, edge, holes=True, rx=6):
    s.rect(x, y, w, h, fill, edge, rx=rx, sw=1.5)
    if holes:
        for hx, hy in ((x + 7, y + 7), (x + w - 7, y + 7), (x + 7, y + h - 7), (x + w - 7, y + h - 7)):
            s.circle(hx, hy, 3.2, "#f3f3f3", edge, 1)


def chip(s, x, y, w, h, label="", fill="#15181b", size=7):
    s.rect(x, y, w, h, fill, rx=2)
    if label:
        s.text(x + w / 2, y + h / 2 + size / 3, label, size, "#d9dde0", "middle", 600)


def header_row(s, x, y, labels, pitch=14, side="below", label_color=SILK, size=7.5, gold=GOLD, rotate_labels=False):
    """Pins in a row starting at (x, y). Returns {label: (px, py)}."""
    out = {}
    for i, lab in enumerate(labels):
        px = x + i * pitch
        s.rect(px - 4, y - 4, 8, 8, "#1b1b1b", rx=1)
        s.circle(px, y, 2.2, gold)
        if lab:
            ty = y + 15 if side == "below" else y - 9
            if rotate_labels:
                if side == "above":
                    s.text(px + 2.5, y - 8, lab, size, label_color, "start", 600, rot=-90)
                else:
                    s.text(px + 2.5, y + 8, lab, size, label_color, "end", 600, rot=-90)
            else:
                s.text(px, ty, lab, size, label_color, "middle", 600)
        out[lab] = (px, y)
    return out


def header_col(s, x, y, labels, pitch=14, side="left", label_color=SILK, size=7.5):
    out = {}
    for i, lab in enumerate(labels):
        py = y + i * pitch
        s.rect(x - 4, py - 4, 8, 8, "#1b1b1b", rx=1)
        s.circle(x, py, 2.2, GOLD)
        if lab:
            if side == "left":
                s.text(x - 9, py + 2.5, lab, size, label_color, "end", 600)
            else:
                s.text(x + 9, py + 2.5, lab, size, label_color, "start", 600)
        out[lab] = (x, py)
    return out


def screw_terminal(s, x, y, n, labels=None, color="#2a63b8", horizontal=True, size=7, label_side="below", lc=SILK, cw=13):
    out = {}
    if horizontal:
        s.rect(x, y, n * cw, 14, color, "#163c70", rx=2)
        for i in range(n):
            cx = x + cw / 2 + i * cw
            s.circle(cx, y + 7, 3.6, "#d8dde2", "#6b737a", 0.8)
            s.line(cx - 2.4, y + 7, cx + 2.4, y + 7, "#6b737a", 1)
            if labels and labels[i]:
                ty = y + 24 if label_side == "below" else y - 5
                s.text(cx, ty, labels[i], size, lc, "middle", 700)
            out[labels[i] if labels else i] = (cx, y + 7)
    else:
        s.rect(x, y, 14, n * cw, color, "#163c70", rx=2)
        for i in range(n):
            cy = y + cw / 2 + i * cw
            s.circle(x + 7, cy, 3.6, "#d8dde2", "#6b737a", 0.8)
            s.line(x + 7, cy - 2.4, x + 7, cy + 2.4, "#6b737a", 1)
            if labels and labels[i]:
                if label_side == "left":
                    s.text(x - 4, cy + 2.5, labels[i], size, lc, "end", 700)
                else:
                    s.text(x + 18, cy + 2.5, labels[i], size, lc, "start", 700)
            out[labels[i] if labels else i] = (x + 7, cy)
    return out


def rounded_path(pts, r=8):
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(1, len(pts) - 1):
        (ax, ay), (bx, by), (cx, cy) = pts[i - 1], pts[i], pts[i + 1]
        l1 = math.hypot(bx - ax, by - ay) or 1
        l2 = math.hypot(cx - bx, cy - by) or 1
        rr = min(r, l1 / 2, l2 / 2)
        p1 = (bx - (bx - ax) / l1 * rr, by - (by - ay) / l1 * rr)
        p2 = (bx + (cx - bx) / l2 * rr, by + (cy - by) / l2 * rr)
        d += f" L{p1[0]:.1f} {p1[1]:.1f} Q{bx:.1f} {by:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    d += f" L{pts[-1][0]:.1f} {pts[-1][1]:.1f}"
    return d


def wire(s, pts, color, sw=3.2, case="#ffffff", r=8):
    d = rounded_path(pts, r)
    s.path(d, stroke=case, sw=sw + 2.6)
    s.path(d, stroke=color, sw=sw)
    for (x, y) in (pts[0], pts[-1]):
        s.circle(x, y, sw * 0.75, color)


def tag(s, x, y, t, color, size=9, anchor="start", fg="#fff"):
    w = len(t) * size * 0.6 + 10
    x0 = x if anchor == "start" else x - w if anchor == "end" else x - w / 2
    s.rect(x0, y - size - 2, w, size + 7, color, rx=(size + 7) / 2)
    s.text(x0 + w / 2, y + 1.5, t, size, fg, "middle", 700)


def resistor(s, x1, y1, x2, y2, bands, label=None, lc=INK):
    """Resistor drawn between two points with colour bands."""
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    L = math.hypot(x2 - x1, y2 - y1)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    body = 34
    g = [f'<g transform="translate({cx:.1f},{cy:.1f}) rotate({ang:.1f})">',
         f'<line x1="{-L/2:.1f}" y1="0" x2="{L/2:.1f}" y2="0" stroke="#8a8f94" stroke-width="2"/>',
         f'<rect x="{-body/2}" y="-6" width="{body}" height="12" rx="5" fill="#e3cfa4" stroke="#9b8253"/>']
    for i, c in enumerate(bands):
        g.append(f'<rect x="{-body/2 + 6 + i*6:.1f}" y="-6" width="3.2" height="12" fill="{c}"/>')
    g.append(f'<rect x="{body/2 - 8}" y="-6" width="2.6" height="12" fill="#c9a227"/>')
    g.append("</g>")
    s.add("".join(g))
    if label:
        s.text(cx + (0 if abs(ang) < 45 else 14), cy - (12 if abs(ang) < 45 else -3), label, 9, lc, "middle" if abs(ang) < 45 else "start", 700)


BANDS = {"1k": ["#7a4a1c", "#111", "#d22"], "2k": ["#d22", "#111", "#d22"],
         "10k": ["#7a4a1c", "#111", "#f08a00"], "20k": ["#d22", "#111", "#f08a00"]}


# ================================================================= components (each returns its pin map)
def pi4(s, x, y, sc=1.0, show_header_labels=False):
    """Raspberry Pi 4 Model B, top view, 85 x 56 mm scaled to 3.4 px/mm * sc."""
    k = 3.4 * sc
    w, h = 85 * k, 56 * k
    board(s, x, y, w, h, PCB, PCB_D, rx=10 * sc)
    # GPIO header along the top edge: pin 1 at the left (SD-card end)
    pins = {}
    for i in range(20):
        px = x + (7 + 3.5) * k + i * 2.54 * k
        for row, num in ((0, 2 * i + 2), (1, 2 * i + 1)):
            py = y + (1.6 + row * 2.54) * k + 2 * k
            s.rect(px - 1.1 * k, py - 1.1 * k, 2.2 * k, 2.2 * k, "#111", rx=1)
            s.circle(px, py, 0.65 * k, GOLD)
            pins[num] = (px, py)
    s.text(x + 7 * k, y + 13 * k, "40-pin GPIO", 7.5 * sc, SILK, "start", 600)
    # SoC + RAM + chips
    s.rect(x + 22 * k, y + 22 * k, 15 * k, 15 * k, METAL, METAL_D, rx=2)
    s.text(x + 29.5 * k, y + 30.5 * k, "CPU", 7 * sc, "#4b5258", "middle", 700)
    chip(s, x + 42 * k, y + 22 * k, 10 * k, 13 * k, "RAM", size=6 * sc)
    chip(s, x + 10 * k, y + 40 * k, 7 * k, 5 * k)
    # ports on the right edge: USB 3 (blue), USB 2, Ethernet
    s.rect(x + w - 17 * k, y + 2 * k, 21 * k, 16 * k, METAL, METAL_D, rx=1)
    s.text(x + w - 7 * k, y + 11 * k, "ETH", 6.5 * sc, "#3d434a", "middle", 700)
    for i, col in enumerate(("#2d6be0", "#2d6be0")):
        yy = y + (21 + i * 0) * k
    s.rect(x + w - 17 * k, y + 20.5 * k, 21 * k, 14 * k, METAL, METAL_D, rx=1)
    s.rect(x + w - 15 * k, y + 23 * k, 16 * k, 3.5 * k, "#2d6be0")
    s.rect(x + w - 15 * k, y + 29 * k, 16 * k, 3.5 * k, "#2d6be0")
    s.text(x + w - 18.5 * k, y + 29 * k, "USB 3", 6 * sc, SILK, "end", 600)
    s.rect(x + w - 17 * k, y + 37.5 * k, 21 * k, 14 * k, METAL, METAL_D, rx=1)
    s.rect(x + w - 15 * k, y + 40 * k, 16 * k, 3.5 * k, "#222")
    s.rect(x + w - 15 * k, y + 46 * k, 16 * k, 3.5 * k, "#222")
    s.text(x + w - 18.5 * k, y + 46 * k, "USB 2", 6 * sc, SILK, "end", 600)
    # bottom edge: USB-C power, 2 micro-HDMI, audio
    s.rect(x + 7 * k, y + h - 5 * k, 9 * k, 6 * k, METAL, METAL_D, rx=2)
    s.text(x + 11.5 * k, y + h - 7 * k, "USB-C power", 6 * sc, SILK, "middle", 600)
    for i in range(2):
        s.rect(x + (24 + i * 13.5) * k, y + h - 4.5 * k, 7 * k, 5 * k, METAL, METAL_D, rx=1)
    s.text(x + 34 * k, y + h - 7 * k, "micro-HDMI", 6 * sc, SILK, "middle", 600)
    s.circle(x + 54 * k, y + h - 2 * k, 3 * k, "#222")
    s.text(x + 54 * k, y + h - 7 * k, "audio", 6 * sc, SILK, "middle", 600)
    # camera CSI connector
    s.rect(x + 44 * k, y + 39 * k, 3 * k, 13 * k, "#f2f2f2", "#999", rx=1)
    s.text(x + 49 * k, y + 47 * k, "CAMERA", 5.5 * sc, SILK, "start", 700)
    s.rect(x + 1 * k, y + 21 * k, 3 * k, 13 * k, "#f2f2f2", "#999", rx=1)
    s.text(x + 5 * k, y + 29 * k, "DISPLAY", 5.5 * sc, SILK, "start", 700, rot=None)
    s.text(x + 2 * k, y + h + 10 * sc, "microSD card slot is underneath, on this short edge", 7 * sc, MUTED, "start", 400, italic=True)
    return pins


def sd_card(s, x, y):
    s.path(f"M{x} {y} h46 l10 10 v62 h-56 z", "#2b2f35", "#14171a", 1.5)
    s.rect(x + 6, y + 8, 40, 30, "#c8102e", rx=2)
    s.text(x + 26, y + 27, "32GB", 10, "#fff", "middle", 800)
    s.text(x + 28, y + 56, "A1 · C10", 8, "#d0d4d8", "middle", 600)
    for i in range(7):
        s.rect(x + 6 + i * 6.6, y + 62, 4, 9, GOLD, rx=1)


def cell_18650(s, x, y, w=110, h=36, label="18650  3.7 V"):
    s.rect(x, y, w, h, "#2f7dd1", "#1d4f87", rx=8)
    s.rect(x + w - 6, y + 8, 8, h - 16, METAL, METAL_D, rx=2)
    s.rect(x, y, 14, h, "#1d4f87", rx=8)
    s.text(x + w / 2 + 4, y + h / 2 + 4, label, 10, "#fff", "middle", 700)
    s.text(x + w - 18, y + h / 2 + 4, "+", 13, "#fff", "middle", 800)


def ups_3s(s, x, y, sc=1.0):
    """Waveshare-style UPS Module 3S: 3 x 18650 holder + charger/5V converter board."""
    k = sc
    board(s, x, y, 250 * k, 150 * k, "#1d3d8f", "#0f2457")
    for i in range(3):
        s.rect(x + 12 * k, y + (14 + i * 40) * k, 166 * k, 34 * k, "#141618", rx=6)
        cell_18650(s, x + 18 * k, y + (17 + i * 40) * k, 154 * k, 28 * k, "18650")
    # electronics column
    chip(s, x + 190 * k, y + 16 * k, 22 * k, 16 * k, "5V", size=7)
    chip(s, x + 190 * k, y + 40 * k, 22 * k, 12 * k, "INA219", size=5.5)
    for i in range(4):
        s.circle(x + 222 * k + (i % 2) * 10 * k, y + 70 * k + (i // 2) * 10 * k, 2.5 * k, "#55e07a" if i < 3 else "#2a4a2e")
    s.text(x + 228 * k, y + 98 * k, "charge", 6.5 * k, SILK, "middle", 600)
    # switch, DC jack, USB-C out, 4-pin output
    s.rect(x + 186 * k, y + 108 * k, 18 * k, 10 * k, "#e8e8e8", "#888", rx=2)
    s.text(x + 195 * k, y + 128 * k, "ON/OFF", 6 * k, SILK, "middle", 700)
    s.rect(x + 250 * k - 4, y + 18 * k, 12 * k, 16 * k, "#111", rx=2)
    s.text(x + 246 * k, y + 44 * k, "12.6V in", 6 * k, SILK, "end", 700)
    s.rect(x + 250 * k - 4, y + 104 * k, 9 * k, 14 * k, METAL, METAL_D, rx=2)
    s.text(x + 246 * k, y + 126 * k, "USB-C 5V out", 6 * k, SILK, "end", 700)
    pins = header_row(s, x + 150 * k, y + 150 * k + 6, ["5V", "GND", "SCL", "SDA"], pitch=16 * k, side="above", label_color=SILK, size=6.5)
    return pins


def battery_2s(s, x, y, sc=1.0):
    """2 x 18650 holder with switch (motor battery)."""
    k = sc
    s.rect(x, y, 150 * k, 92 * k, "#141618", rx=8)
    cell_18650(s, x + 10 * k, y + 8 * k, 130 * k, 34 * k)
    cell_18650(s, x + 10 * k, y + 50 * k, 130 * k, 34 * k)
    s.rect(x + 150 * k, y + 32 * k, 22 * k, 26 * k, "#2a2e31", rx=3)
    s.rect(x + 155 * k, y + 37 * k, 12 * k, 16 * k, "#e23b2e", rx=2)
    s.text(x + 161 * k, y + 70 * k, "switch", 7, MUTED, "middle", 600)
    return {"+": (x + 172 * k, y + 38 * k), "-": (x + 172 * k, y + 52 * k)}


def tt_motor(s, x, y, sc=1.0, wheel=True, flip=False):
    """Yellow TT gear motor seen from above, wheel on its output shaft."""
    k = sc
    s.rect(x, y, 64 * k, 22 * k, "#f2c230", "#b38a12", rx=3)
    s.rect(x + 64 * k, y + 3 * k, 26 * k, 16 * k, "#d0d3d6", "#8b9399", rx=6)
    s.text(x + 30 * k, y + 14.5 * k, "TT motor", 7.5 * k, "#5c4500", "middle", 700)
    s.rect(x + 88 * k, y + 6 * k, 6 * k, 3 * k, GOLD)
    s.rect(x + 88 * k, y + 13 * k, 6 * k, 3 * k, GOLD)
    if wheel:
        s.rect(x + 12 * k, y - 22 * k, 6 * k, 22 * k, "#b0b5ba")
        s.rect(x - 14 * k, y - 50 * k, 58 * k, 28 * k, "#202326", "#111", rx=8)
        for i in range(6):
            s.line(x + (-8 + i * 9) * k, y - 50 * k, x + (-8 + i * 9) * k, y - 22 * k, "#3a3f44", 2)
        s.text(x + 15 * k, y - 56 * k, "wheel", 7 * k, MUTED, "middle", 600)


def encoder_disc(s, cx, cy, r=26, slots=20):
    s.circle(cx, cy, r, "#1b1b1b")
    for i in range(slots):
        a = math.radians(i * 360 / slots)
        s.add(f'<rect x="{cx + (r - 9) * math.cos(a) - 2:.1f}" y="{cy + (r - 9) * math.sin(a) - 4:.1f}" width="4" height="8" '
              f'fill="#f4f4f4" transform="rotate({i * 360 / slots + 90:.1f} {cx + (r - 9) * math.cos(a):.1f} {cy + (r - 9) * math.sin(a):.1f})"/>')
    s.circle(cx, cy, 6, "#555")


def l298n(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 170 * k, 170 * k, RED_B, RED_D)
    for i in range(7):  # heatsink
        s.rect(x + (52 + i * 10) * k, y + 18 * k, 7 * k, 62 * k, "#15171a", rx=1)
    s.rect(x + 48 * k, y + 78 * k, 76 * k, 20 * k, "#15171a", rx=2)
    s.text(x + 86 * k, y + 92 * k, "L298N", 9 * k, "#ddd", "middle", 800)
    out = {}
    out.update(screw_terminal(s, x + 6 * k, y + 22 * k, 2, ["OUT1", "OUT2"], horizontal=False, label_side="right", size=6.5))
    out.update(screw_terminal(s, x + 150 * k, y + 22 * k, 2, ["OUT3", "OUT4"], horizontal=False, label_side="left", size=6.5))
    out.update(screw_terminal(s, x + 14 * k, y + 136 * k, 3, ["+12V", "GND", "+5V"], size=6.5, cw=22, label_side="above"))
    hdr = header_row(s, x + 92 * k, y + 148 * k, ["ENA", "IN1", "IN2", "IN3", "IN4", "ENB"], pitch=12 * k, side="above", size=6,
                     rotate_labels=True)
    out.update(hdr)
    # jumpers on ENA / ENB (remove them) and the 5V regulator jumper
    s.rect(x + 88 * k, y + 120 * k, 8 * k, 14 * k, "#111", rx=1)
    s.rect(x + 148 * k, y + 120 * k, 8 * k, 14 * k, "#111", rx=1)
    s.rect(x + 20 * k, y + 110 * k, 14 * k, 8 * k, "#111", rx=1)
    s.text(x + 27 * k, y + 106 * k, "5V-EN", 6 * k, SILK, "middle", 700)
    return out


def pca9685(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 250 * k, 92 * k, BLUE, BLUE_D)
    chip(s, x + 52 * k, y + 32 * k, 26 * k, 26 * k, "PCA9685", size=5.5)
    left = header_col(s, x + 14 * k, y + 14 * k, ["GND", "OE", "SCL", "SDA", "VCC", "V+"], pitch=12 * k, side="right", size=6.5)
    term = screw_terminal(s, x + 92 * k, y + 6 * k, 2, ["V+", "GND"], size=6.5, label_side="below")
    out = dict(left)
    out["term V+"], out["term GND"] = term["V+"], term["GND"]
    # 16 channels, 3 rows (PWM yellow, V+ red, GND black)
    for ch in range(16):
        cx = x + (100 + ch * 9.2 + (ch // 4) * 2) * k
        for r, col in enumerate(("#f2b705", "#e23b2e", "#222")):
            s.rect(cx - 3.5 * k, y + (50 + r * 10) * k - 3.5 * k, 7 * k, 7 * k, "#111", rx=1)
            s.circle(cx, y + (50 + r * 10) * k, 1.8 * k, GOLD)
        if ch in (0, 1, 14, 15) or ch % 4 == 0:
            s.text(cx, y + 86 * k, str(ch), 6 * k, SILK, "middle", 700)
        out[f"ch{ch}"] = (cx, y + 50 * k)
    s.text(x + 245 * k, y + 52 * k, "PWM", 5.5 * k, "#f2b705", "end", 700)
    return out


def sg90(s, x, y, sc=1.0, name="SG90"):
    k = sc
    s.rect(x, y, 70 * k, 36 * k, "#2f6fd1", "#1d4f87", rx=3)
    s.rect(x - 8 * k, y + 13 * k, 86 * k, 6 * k, "#2f6fd1", "#1d4f87", rx=2)
    s.circle(x + 18 * k, y - 4 * k, 9 * k, "#ffffff", "#999")
    s.rect(x + 14 * k, y - 26 * k, 8 * k, 26 * k, "#fff", "#999", rx=4)
    s.text(x + 42 * k, y + 26 * k, name, 8 * k, "#fff", "middle", 800)
    # 3-wire cable
    for i, col in enumerate(("#6b3b1f", "#e23b2e", "#f08a00")):
        s.path(f"M{x + 66 * k} {y + (10 + i * 4) * k} C {x + 95 * k} {y + (10 + i * 4) * k}, {x + 95 * k} {y + (52 + i * 4) * k}, {x + 120 * k} {y + (52 + i * 4) * k}",
               stroke=col, sw=2.2)
    s.rect(x + 118 * k, y + 46 * k, 14 * k, 18 * k, "#222", rx=2)
    return {"plug": (x + 132 * k, y + 55 * k)}


def pi_camera(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 84 * k, 84 * k, PCB, PCB_D, rx=6)
    s.rect(x + 27 * k, y + 22 * k, 30 * k, 30 * k, "#111", rx=3)
    s.circle(x + 42 * k, y + 37 * k, 11 * k, "#2b3d55", "#0a0f16", 2)
    s.circle(x + 38 * k, y + 33 * k, 3 * k, "#9fc3ff")
    s.rect(x + 16 * k, y + 84 * k, 52 * k, 50 * k, "#e7e1d3", "#b9b09a", rx=1)
    s.rect(x + 16 * k, y + 84 * k, 52 * k, 8 * k, "#2a63b8")
    s.text(x + 42 * k, y + 116 * k, "ribbon", 7 * k, "#7a705a", "middle", 600)
    s.text(x + 42 * k, y + 14 * k, "Camera v2", 7 * k, SILK, "middle", 700)
    return {"ribbon": (x + 42 * k, y + 134 * k)}


def hcsr04(s, x, y, sc=1.0, title=None):
    k = sc
    board(s, x, y, 135 * k, 64 * k, BLUE, BLUE_D, holes=True)
    for cx in (x + 33 * k, x + 102 * k):
        s.circle(cx, y + 30 * k, 24 * k, METAL, METAL_D, 2)
        s.circle(cx, y + 30 * k, 16 * k, "#4a4f55")
        for r in (12, 8, 4):
            s.circle(cx, y + 30 * k, r * k, "none", "#6d747b", 0.8)
    s.text(x + 67.5 * k, y + 13 * k, title or "HC-SR04", 7 * k, SILK, "middle", 700)
    chip(s, x + 57 * k, y + 24 * k, 21 * k, 12 * k)
    pins = header_row(s, x + 38 * k, y + 64 * k + 6, ["VCC", "Trig", "Echo", "Gnd"], pitch=20 * k, side="above", label_color=SILK, size=7)
    return pins


def slot_encoder(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 70 * k, 40 * k, BLUE, BLUE_D, holes=False, rx=4)
    s.rect(x + 46 * k, y - 18 * k, 8 * k, 26 * k, "#111", rx=1)
    s.rect(x + 58 * k, y - 18 * k, 8 * k, 26 * k, "#111", rx=1)
    s.text(x + 56 * k, y - 22 * k, "slot", 7 * k, MUTED, "middle", 600)
    chip(s, x + 10 * k, y + 5 * k, 18 * k, 10 * k, "LM393", size=4.5)
    s.circle(x + 36 * k, y + 9 * k, 2.5 * k, "#e33")
    pins = header_row(s, x + 8 * k, y + 40 * k + 6, ["VCC", "GND", "D0", "A0"], pitch=18 * k, side="above", label_color=SILK, size=6.5)
    return pins


def gy521(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 112 * k, 82 * k, BLUE, BLUE_D, holes=False, rx=4)
    chip(s, x + 12 * k, y + 8 * k, 24 * k, 24 * k, "MPU", size=6)
    s.text(x + 78 * k, y + 20 * k, "GY-521", 7 * k, SILK, "middle", 700)
    s.line(x + 60 * k, y + 40 * k, x + 78 * k, y + 40 * k, SILK, 1.5)
    s.line(x + 60 * k, y + 40 * k, x + 60 * k, y + 26 * k, SILK, 1.5)
    s.text(x + 81 * k, y + 43 * k, "X", 7, SILK)
    s.text(x + 58 * k, y + 24 * k, "Y", 7, SILK)
    return header_row(s, x + 10 * k, y + 82 * k + 6, ["VCC", "GND", "SCL", "SDA", "XDA", "XCL", "AD0", "INT"], pitch=13 * k,
                      side="above", label_color=SILK, size=6.5, rotate_labels=True)

def bme680(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 80 * k, 74 * k, PURPLE, PURPLE_D, holes=False, rx=4)
    s.rect(x + 56 * k, y + 8 * k, 12 * k, 12 * k, METAL, METAL_D, rx=1)
    s.circle(x + 62 * k, y + 14 * k, 1.5 * k, "#333")
    s.text(x + 26 * k, y + 17 * k, "BME680", 7 * k, SILK, "middle", 700)
    return header_row(s, x + 8 * k, y + 74 * k + 6, ["VCC", "GND", "SCL", "SDA", "SDO", "CS"], pitch=12.8 * k, side="above",
                      label_color=SILK, size=6.5, rotate_labels=True)

def mq135(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 96 * k, 84 * k, BLUE, BLUE_D, holes=False, rx=4)
    s.circle(x + 36 * k, y + 30 * k, 24 * k, "#c47e2a", "#8a5517", 1.5)
    s.circle(x + 36 * k, y + 30 * k, 18 * k, "#e7e9eb", "#9aa1a7")
    for o in range(-14, 15, 4):
        s.line(x + (36 + o) * k, y + 14 * k, x + (36 + o) * k, y + 46 * k, "#9aa1a7", 0.8)
        s.line(x + 20 * k, y + (30 + o) * k, x + 52 * k, y + (30 + o) * k, "#9aa1a7", 0.8)
    s.circle(x + 78 * k, y + 20 * k, 6 * k, "#2a63b8", "#163c70")
    s.text(x + 78 * k, y + 40 * k, "MQ-135", 6.5 * k, SILK, "middle", 700)
    return header_row(s, x + 20 * k, y + 84 * k + 6, ["VCC", "GND", "DO", "AO"], pitch=18 * k, side="above", label_color=SILK, size=6.5)

def ads1115(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 128 * k, 76 * k, PURPLE, PURPLE_D, holes=False, rx=4)
    chip(s, x + 10 * k, y + 8 * k, 22 * k, 14 * k, "ADS", size=5.5)
    s.text(x + 82 * k, y + 18 * k, "ADS1115 16-bit ADC", 6.5 * k, SILK, "middle", 700)
    return header_row(s, x + 8 * k, y + 76 * k + 6, ["VDD", "GND", "SCL", "SDA", "ADDR", "ALRT", "A0", "A1", "A2", "A3"],
                      pitch=12.4 * k, side="above", label_color=SILK, size=6.5, rotate_labels=True)

def usb_mic(s, x, y, sc=1.0):
    k = sc
    s.rect(x, y, 30 * k, 16 * k, METAL, METAL_D, rx=2)
    s.rect(x + 30 * k, y - 2 * k, 26 * k, 20 * k, "#222", rx=4)
    s.circle(x + 66 * k, y + 8 * k, 12 * k, "#333", "#111")
    for o in (-5, 0, 5):
        s.line(x + (66 + o) * k, y, x + (66 + o) * k, y + 16 * k, "#555", 1)
    s.text(x + 40 * k, y + 40 * k, "USB microphone", 8, MUTED, "middle", 600)


def usb_soundcard(s, x, y, sc=1.0):
    k = sc
    s.rect(x, y, 30 * k, 16 * k, METAL, METAL_D, rx=2)
    s.rect(x + 30 * k, y - 4 * k, 46 * k, 24 * k, "#d8dce0", "#8b9399", rx=5)
    s.circle(x + 62 * k, y + 2 * k, 3.5 * k, "#e94b8a")
    s.circle(x + 62 * k, y + 14 * k, 3.5 * k, "#4caf50")
    s.text(x + 44 * k, y + 40 * k, "USB sound card", 8, MUTED, "middle", 600)
    return {"out": (x + 66 * k, y + 14 * k)}


def pam8403(s, x, y, sc=1.0):
    k = sc
    board(s, x, y, 90 * k, 54 * k, PCB, PCB_D, holes=False, rx=4)
    chip(s, x + 36 * k, y + 18 * k, 18 * k, 14 * k, "8403", size=5)
    s.text(x + 45 * k, y + 46 * k, "PAM8403", 6.5 * k, SILK, "middle", 700)
    left = header_col(s, x + 8 * k, y + 10 * k, ["L", "G", "R"], pitch=11 * k, side="right", size=6)
    pw = header_col(s, x + 8 * k, y + 44 * k - 4, ["5V"], pitch=11 * k, side="right", size=6)
    out = header_col(s, x + 82 * k, y + 8 * k, ["L+", "L-", "R-", "R+"], pitch=10 * k, side="left", size=6)
    res = dict(left)
    res.update(pw)
    res.update({f"out {kk}": v for kk, v in out.items()})
    return res


def speaker(s, cx, cy, r=34):
    s.circle(cx, cy, r, "#2b2f35", "#111", 2)
    s.circle(cx, cy, r * 0.72, "#3b4048")
    s.circle(cx, cy, r * 0.25, "#1b1e22")
    s.text(cx, cy + r + 14, "3 W 4 Ω speaker", 8, MUTED, "middle", 600)


def jumper(s, x, y, kind="F-F", color="#e23b2e"):
    def end(px, female):
        if female:
            s.rect(px - 5, y - 7, 18, 14, "#111", rx=2)
        else:
            s.rect(px - 5, y - 5, 14, 10, "#111", rx=2)
            s.line(px + 9, y, px + 18, y, "#d6b25a", 2.5)
    s.path(f"M{x + 12} {y} C {x + 50} {y - 26}, {x + 90} {y + 26}, {x + 130} {y}", stroke=color, sw=3)
    end(x, kind[0] == "F")
    end(x + 130, kind[2] == "F")
    s.text(x + 70, y + 30, kind.replace("-", "–"), 9, MUTED, "middle", 700)


def multimeter(s, x, y):
    s.rect(x, y, 90, 140, "#f2b705", "#a57c00", rx=12)
    s.rect(x + 12, y + 12, 66, 32, "#c9dcc0", "#6d7a63", rx=3)
    s.text(x + 45, y + 35, "11.84", 15, "#1c2a18", "middle", 700, mono=True)
    s.circle(x + 45, y + 82, 22, "#2a2e31")
    s.line(x + 45, y + 82, x + 45, y + 64, "#ddd", 3)
    for i, c in enumerate(("#111", "#e23b2e", "#e23b2e")):
        s.circle(x + 20 + i * 25, y + 122, 6, c, "#333")


def soldering_iron(s, x, y):
    s.path(f"M{x} {y + 10} L{x + 40} {y + 6} L{x + 40} {y + 14} Z", "#bfc5ca", "#7d858b")
    s.rect(x + 40, y + 2, 34, 16, "#9aa1a7", rx=3)
    s.rect(x + 74, y - 1, 70, 22, "#2a63b8", rx=8)
    s.path(f"M{x + 144} {y + 10} C {x + 170} {y + 10}, {x + 170} {y + 40}, {x + 190} {y + 40}", stroke="#222", sw=3)


PI_PINS = {1: "3V3", 2: "5V", 3: "GPIO2 SDA", 4: "5V", 5: "GPIO3 SCL", 6: "GND", 7: "GPIO4", 8: "GPIO14", 9: "GND",
           10: "GPIO15", 11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22", 16: "GPIO23", 17: "3V3",
           18: "GPIO24", 19: "GPIO10", 20: "GND", 21: "GPIO9", 22: "GPIO25", 23: "GPIO11", 24: "GPIO8", 25: "GND",
           26: "GPIO7", 27: "ID_SD", 28: "ID_SC", 29: "GPIO5", 30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13",
           34: "GND", 35: "GPIO19", 36: "GPIO16", 37: "GPIO26", 38: "GPIO20", 39: "GND", 40: "GPIO21"}


def gpio_header(s, x, y, used: dict | None = None, pitch=17, labels="used"):
    """Raspberry Pi 4 40-pin header, drawn tall (pin 1 at the top). used = {pin: colour}.
    Odd pins are the left column, even pins the right column. Returns {pin: (x, y, side)}."""
    used = used or {}
    w = 46
    s.rect(x - 8, y - 22, w + 16, 20 * pitch + 30, PCB, PCB_D, rx=8)
    s.text(x + w / 2, y - 8, "Raspberry Pi 4", 8.5, SILK, "middle", 700)
    s.rect(x, y - 2, w, 20 * pitch - 4, "#111", rx=3)
    out = {}
    for n in range(1, 41):
        row = (n - 1) // 2
        odd = n % 2 == 1
        px = x + (12 if odd else w - 12)
        py = y + 6 + row * pitch
        col = used.get(n)
        gnd = PI_PINS[n] == "GND"
        fill = col or ("#3b3f44" if gnd else GOLD)
        if n == 1:
            s.rect(px - 5.5, py - 5.5, 11, 11, fill, "#fff" if col else None, rx=1)
        else:
            s.circle(px, py, 5.5, fill, "#fff" if col else None, 1.2)
        s.text(px, py + 2.6, n, 6.5, "#fff" if (col or gnd) else "#3a2e0a", "middle", 700)
        if labels == "all" or (labels == "used" and col):
            name = PI_PINS[n]
            if odd:
                s.text(x - 14, py + 3, name, 8.5, col or MUTED, "end", 700)
            else:
                s.text(x + w + 14, py + 3, name, 8.5, col or MUTED, "start", 700)
        out[n] = (px, py, "L" if odd else "R")
    return out
