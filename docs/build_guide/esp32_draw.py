"""Drawings of the ESP32 robot's parts (same style as draw.py): XIAO ESP32S3 Sense, DRV8833, half breadboard, 2WD chassis."""
from __future__ import annotations

from draw import BLUE, BLUE_D, GOLD, INK, METAL, METAL_D, MUTED, PURPLE, PURPLE_D, SILK, board, chip, header_row

XIAO_LEFT = ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]
XIAO_RIGHT = ["5V", "GND", "3V3", "D10", "D9", "D8", "D7"]
XIAO_SUB = {"D0": "GPIO1", "D1": "GPIO2", "D2": "GPIO3", "D3": "GPIO4", "D4": "SDA", "D5": "SCL", "D6": "TX · GPIO43",
            "D7": "RX · GPIO44", "D8": "GPIO7", "D9": "GPIO8", "D10": "GPIO9", "5V": "", "GND": "", "3V3": ""}


def xiao_sense(s, x, y, sc=1.0, labels=True, label_color=INK, camera=True, inside=False):
    """Seeed XIAO ESP32S3 Sense seen from above, USB-C at the top. Returns {pin: (x, y)} at the pad edges."""
    k = sc
    w, h = 104 * k, 128 * k
    if camera:   # the Sense board under it, with the camera on its short ribbon, peeking out at the bottom
        s.rect(x + 18 * k, y + h - 6 * k, w - 36 * k, 34 * k, "#16191c", "#0b0d0f", rx=4 * k)
        s.circle(x + w / 2, y + h + 12 * k, 9 * k, "#0f1a2a", "#4a4f55", 1.5)
        s.circle(x + w / 2 - 2.5 * k, y + h + 9.5 * k, 2.5 * k, "#9fc3ff")
        s.text(x + w / 2, y + h + 34 * k, "camera (Sense board)", 6.5 * k, MUTED, "middle", 600)
    s.rect(x, y, w, h, "#1b1d20", "#0b0d0f", rx=7 * k, sw=1.4)
    s.rect(x + w / 2 - 16 * k, y - 6 * k, 32 * k, 14 * k, METAL, METAL_D, rx=5 * k)        # USB-C
    s.text(x + w / 2, y + 18 * k, "USB-C", 6 * k, "#9aa1a7", "middle", 700)
    s.rect(x + 28 * k, y + 30 * k, w - 56 * k, 52 * k, METAL, METAL_D, rx=3 * k)        # ESP32-S3 shield can
    s.text(x + w / 2, y + 52 * k, "ESP32-S3", 8.5 * k, "#3a3f44", "middle", 800)
    s.text(x + w / 2, y + 65 * k, "XIAO", 7 * k, "#5b6670", "middle", 700)
    s.circle(x + 26 * k, y + h - 16 * k, 2.6 * k, "#f2a03d")                              # orange user LED
    s.text(x + 34 * k, y + h - 13 * k, "LED", 5.5 * k, "#9aa1a7", "start", 600)
    s.rect(x + w - 30 * k, y + h - 22 * k, 14 * k, 9 * k, "#c9ced3", "#8b9399", rx=2)     # boot / reset buttons
    s.text(x + w - 23 * k, y + h - 6 * k, "B  R", 5 * k, "#9aa1a7", "middle", 600)
    out = {}
    pitch = 15 * k
    for i, (lp, rp) in enumerate(zip(XIAO_LEFT, XIAO_RIGHT)):
        py = y + 16 * k + i * pitch
        for side, name, px in (("l", lp, x), ("r", rp, x + w)):
            s.add(f'<path d="M{px:.1f} {py - 4.5 * k:.1f} a{4.5 * k:.1f} {4.5 * k:.1f} 0 0 {1 if side == "l" else 0} 0 {9 * k:.1f}" '
                  f'fill="{GOLD}" stroke="#a5821f" stroke-width="0.8"/>')
            s.circle(px, py, 1.6 * k, "#1b1d20")
            if labels and inside:      # labels on the board itself, so wires can arrive from outside
                lx = px + 8 * k if side == "l" else px - 8 * k
                s.text(lx, py + 3 * k, name, 7 * k, "#f4f8f5", "start" if side == "l" else "end", 800)
            elif labels:
                lx = px - 8 * k if side == "l" else px + 8 * k
                s.text(lx, py + 3 * k, name, 8 * k, label_color, "end" if side == "l" else "start", 800)
            out[name] = (px, py)
    return out


def drv8833(s, x, y, sc=1.0, label_color=SILK, flip=False):
    """DRV8833 dual motor driver module (the common red/purple board).
    Inputs (AIN1..BIN2, EEP, ULT) on one side, power and outputs (VM, GND, AOUT, BOUT) on the other;
    flip=True puts the inputs on the right (facing a board on the right)."""
    k = sc
    board(s, x, y, 92 * k, 112 * k, "#7b2d8e", "#4f1b5c", holes=False, rx=4)
    chip(s, x + 30 * k, y + 38 * k, 32 * k, 28 * k, "", size=5 * k)
    s.text(x + 46 * k, y + 104 * k, "DRV8833", 7.5 * k, label_color, "middle", 800)
    out = {}
    left = ["VM", "GND", "AOUT1", "AOUT2", "BOUT1", "BOUT2"] if flip else ["AIN1", "AIN2", "BIN1", "BIN2", "EEP", "ULT"]
    right = ["AIN1", "AIN2", "BIN1", "BIN2", "EEP", "ULT"] if flip else ["VM", "GND", "AOUT1", "AOUT2", "BOUT1", "BOUT2"]
    for i, n in enumerate(left):
        py = y + 14 * k + i * 14 * k
        s.rect(x + 3 * k, py - 4, 8, 8, "#1b1b1b", rx=1)
        s.circle(x + 7 * k, py, 2.2, GOLD)
        s.text(x + 14 * k, py + 2.5 * k, n, 5.8 * k, label_color, "start", 700)
        out[n] = (x + 3 * k, py)
    for i, n in enumerate(right):
        py = y + 14 * k + i * 14 * k
        s.rect(x + 81 * k, py - 4, 8, 8, "#1b1b1b", rx=1)
        s.circle(x + 85 * k, py, 2.2, GOLD)
        s.text(x + 78 * k, py + 2.5 * k, n, 5.8 * k, label_color, "end", 700)
        out[n] = (x + 89 * k, py)
    return out


def half_breadboard(s, x, y, sc=1.0, rails=("3V3", "GND"), cols=30):
    """Half-size breadboard (400 points) seen from above with a power rail pair top and bottom.
    Returns {"rail+": [(x,y)...], "rail-": [...], "col": fn(col, row)->(x,y)}."""
    k = sc
    pitch = 9 * k
    w = (cols + 2) * pitch
    h = 22 * pitch
    s.rect(x, y, w, h, "#f3f1ea", "#cdc7b5", rx=6 * k, sw=1.4)
    rail_y = {"top+": y + 1.6 * pitch, "top-": y + 2.6 * pitch, "bot-": y + h - 2.6 * pitch, "bot+": y + h - 1.6 * pitch}
    cols_x = [x + (1.5 + i) * pitch for i in range(cols)]
    for key, ry in rail_y.items():
        for cx in cols_x:
            if (round((cx - cols_x[0]) / pitch) % 6) != 5:
                s.rect(cx - 1.6 * k, ry - 1.6 * k, 3.2 * k, 3.2 * k, "#4a4f55", rx=0.6)
    s.line(x + pitch, rail_y["top+"] - 5 * k, x + w - pitch, rail_y["top+"] - 5 * k, "#e23b2e", 1.4)
    s.line(x + pitch, rail_y["top-"] + 5 * k, x + w - pitch, rail_y["top-"] + 5 * k, "#2d6be0", 1.4)
    s.line(x + pitch, rail_y["bot-"] - 5 * k, x + w - pitch, rail_y["bot-"] - 5 * k, "#2d6be0", 1.4)
    s.line(x + pitch, rail_y["bot+"] + 5 * k, x + w - pitch, rail_y["bot+"] + 5 * k, "#e23b2e", 1.4)
    if rails:
        s.text(x + 3 * k, rail_y["top+"] + 3 * k, "+", 8 * k, "#e23b2e", "start", 800)
        s.text(x + 3 * k, rail_y["top-"] + 3 * k, "−", 8 * k, "#2d6be0", "start", 800)
    grid_top = y + 4.6 * pitch
    rows = []
    for r in range(10):
        ry = grid_top + r * pitch + (pitch * 1.4 if r >= 5 else 0)
        rows.append(ry)
        for cx in cols_x:
            s.rect(cx - 1.6 * k, ry - 1.6 * k, 3.2 * k, 3.2 * k, "#5b6066", rx=0.6)
    s.rect(x + pitch, grid_top + 4.6 * pitch, w - 2 * pitch, 1.2 * pitch, "#e2ddd0", rx=2)   # centre channel
    return {"rails": rail_y, "cols": cols_x, "rows": rows, "w": w, "h": h, "pitch": pitch}


def chassis_2wd(s, x, y, sc=1.0, show_parts=False):
    """2WD acrylic chassis from above: two TT motors and wheels at the front, a caster at the back."""
    k = sc
    w, h = 250 * k, 160 * k
    s.path(f"M{x + 30 * k} {y} L{x + w - 50 * k} {y} Q{x + w} {y} {x + w} {y + 45 * k} L{x + w} {y + h - 45 * k} "
           f"Q{x + w} {y + h} {x + w - 50 * k} {y + h} L{x + 30 * k} {y + h} Q{x} {y + h} {x} {y + h - 30 * k} "
           f"L{x} {y + 30 * k} Q{x} {y} {x + 30 * k} {y} Z", "#d9ecf8", "#7fa8c4", 1.6)
    for i in range(6):
        for j in range(4):
            s.circle(x + (40 + i * 32) * k, y + (32 + j * 32) * k, 2.4 * k, "#f6fbff", "#9cbad0", 0.8)
    for wy in (y - 20 * k, y + h - 2 * k):            # wheels at the front (right side = front)
        s.rect(x + w - 92 * k, wy, 64 * k, 22 * k, "#202326", "#111", rx=8 * k)
        for t in range(7):
            tx = x + w - (88 - t * 9) * k
            s.line(tx, wy + 2 * k, tx, wy + 20 * k, "#3a3f44", 1.6)
    for my in (y + 6 * k, y + h - 28 * k):
        s.rect(x + w - 110 * k, my, 70 * k, 22 * k, "#f2c230", "#b38a12", rx=3 * k, op=0.9)
        s.text(x + w - 75 * k, my + 14.5 * k, "TT motor", 7 * k, "#5c4500", "middle", 700)
    s.circle(x + 26 * k, y + h / 2, 14 * k, "#c9ced3", "#8b9399", 1.5)            # caster at the back
    s.circle(x + 26 * k, y + h / 2, 8 * k, "#202326")
    s.text(x + 26 * k, y + h / 2 + 26 * k, "caster", 7 * k, MUTED, "middle", 600)
    return {"w": w, "h": h}


def hcsr04p(s, x, y, sc=1.0):
    from draw import hcsr04

    return hcsr04(s, x, y, sc, title="HC-SR04P  3.3 V")


def gy521_small(s, x, y, sc=1.0):
    from draw import gy521

    return gy521(s, x, y, sc)


__all__ = ["xiao_sense", "drv8833", "half_breadboard", "chassis_2wd", "hcsr04p", "XIAO_LEFT", "XIAO_RIGHT", "XIAO_SUB",
           "BLUE", "BLUE_D", "PURPLE", "PURPLE_D", "header_row"]
