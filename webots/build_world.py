"""Builds the Webots world (worlds/raqib_campus.wbt) from the same files the robot uses.

    python webots/build_world.py

Rooms, desks, students and what each room "looks like" come from edge/config.yaml (zones) and
edge/sim_world.yaml (walls, obstacles, students, scenarios), so the Webots campus always matches the
built-in 2D simulator. Change a scenario there (e.g. lights_on: false) and run this again.

Only basic Webots nodes are used (no downloaded PROTOs), so the world opens offline.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
EDGE = ROOT.parent / "edge"
OUT = ROOT / "worlds" / "raqib_campus.wbt"
TEX = ROOT / "worlds" / "textures"

WALL_H = 2.5
PARTITIONS = [1.5, 4.5, 7.0, 10.5]      # default; edge/config.yaml webots.partitions wins
DOOR_HALF = 1.0
CAMERA_HEIGHT = 1.05                     # camera on a 1 m mast: sees desks and faces of seated people

LABELS = {"Home": "HOME / CHARGING", "IoT_Lab": "IoT LAB", "LectureHall_B": "LECTURE HALL B",
          "LectureHall_A": "LECTURE HALL A", "Exam_Hall": "EXAM HALL"}
FLOOR_TINT = {"Home": (0.72, 0.74, 0.78), "IoT_Lab": (0.62, 0.68, 0.74), "LectureHall_B": (0.70, 0.64, 0.58),
              "LectureHall_A": (0.64, 0.70, 0.62), "Exam_Hall": (0.74, 0.70, 0.62)}
SHIRTS = [(0.20, 0.35, 0.75), (0.75, 0.25, 0.25), (0.20, 0.55, 0.35), (0.55, 0.35, 0.65), (0.85, 0.6, 0.2)]
SKINS = [(0.87, 0.70, 0.55), (0.62, 0.43, 0.30), (0.95, 0.80, 0.68), (0.45, 0.30, 0.20)]


# ----------------------------------------------------------------------------- helpers
def f(v) -> str:
    return " ".join(f"{x:.4g}" for x in v) if isinstance(v, (list, tuple, np.ndarray)) else f"{v:.4g}"


def axis_angle(R: np.ndarray) -> list[float]:
    ang = math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))
    if ang < 1e-9:
        return [0, 0, 1, 0]
    if abs(ang - math.pi) < 1e-6:
        w, v = np.linalg.eigh((R + np.eye(3)) / 2)
        ax = v[:, np.argmax(w)]
        return [*ax, ang]
    ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(ang))
    return [*ax, ang]


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def look_rotation(pos, target) -> list[float]:
    d = np.array(target, float) - np.array(pos, float)
    yaw = math.atan2(d[1], d[0])
    pitch = math.atan2(-d[2], math.hypot(d[0], d[1]))      # positive = looking down
    return axis_angle(rz(yaw) @ ry(pitch))


def app(color, rough=0.8, emissive=None, metal=0.0, tex=None) -> str:
    em = f" emissiveColor {f(emissive)}" if emissive else ""
    t = f' baseColorMap ImageTexture {{ url ["textures/{tex}"] filtering 1 }}' if tex else ""
    return f"PBRAppearance {{ baseColor {f(color)} roughness {rough} metalness {metal}{em}{t} }}"


def box(size, pos, color, rot=None, **kw) -> str:
    r = f" rotation {f(rot)}" if rot else ""
    return (f"Pose {{ translation {f(pos)}{r} children [ Shape {{ appearance {app(color, **kw)} "
            f"geometry Box {{ size {f(size)} }} }} ] }}")


def cyl(h, r, pos, color, **kw) -> str:
    return (f"Pose {{ translation {f(pos)} children [ Shape {{ appearance {app(color, **kw)} "
            f"geometry Cylinder {{ height {f(h)} radius {f(r)} }} }} ] }}")


def sphere(r, pos, color, **kw) -> str:
    return (f"Pose {{ translation {f(pos)} children [ Shape {{ appearance {app(color, **kw)} "
            f"geometry Sphere {{ radius {f(r)} subdivision 2 }} }} ] }}")


def solid(name, pos, children, bounds=None, rot=None) -> str:
    r = f" rotation {f(rot)}" if rot else ""
    b = ""
    if bounds:
        size, off = bounds
        b = f" boundingObject Pose {{ translation {f(off)} children [ Box {{ size {f(size)} }} ] }}"
    return f'Solid {{ translation {f(pos)}{r} name "{name}" children [ {" ".join(children)} ]{b} }}'


def font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def texture(name, w, h, bg, lines, fg=(255, 255, 255), size=64, extra=None):
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    y = (h - len(lines) * size * 1.2) / 2
    for line in lines:
        fnt = font(size)
        tw = d.textlength(line, font=fnt)
        d.text(((w - tw) / 2, y), line, fill=fg, font=fnt)
        y += size * 1.2
    if extra:
        extra(d, w, h)
    TEX.mkdir(parents=True, exist_ok=True)
    im.save(TEX / name)
    return name


# ----------------------------------------------------------------------------- textures
def make_textures():
    for z, label in LABELS.items():
        texture(f"sign_{z}.png", 512, 128, (18, 32, 72), [label], size=54)
    texture("exit.png", 256, 128, (20, 140, 60), ["EXIT"], size=64)

    def slide(d, w, h):
        d.rectangle((40, 50, w - 40, 76), fill=(40, 90, 200))
        for i in range(5):
            d.rectangle((70, 310 + i * 36, 70 + (w - 360) * (0.5 + 0.1 * (i % 3)), 326 + i * 36), fill=(90, 90, 90))
        d.ellipse((w - 230, 300, w - 80, 450), fill=(240, 160, 40))
    texture("slide.png", 1024, 512, (250, 250, 248), ["Week 6: IoT Networks"], fg=(30, 40, 80), size=64, extra=slide)
    texture("whiteboard_exam.png", 1024, 512, (246, 247, 250), ["FINAL EXAM", "Silence please", "Phones off"],
            fg=(30, 60, 160), size=52)

    def paper(d, w, h):
        for i in range(9):
            d.line((20, 30 + i * 24, w - 20 - (i % 3) * 30, 30 + i * 24), fill=(70, 70, 70), width=3)
    texture("exam_paper.png", 256, 512, (252, 252, 252), [], extra=paper)

    def cheat(d, w, h):
        for i in range(6):
            d.line((10, 15 + i * 16, w - 10, 15 + i * 16), fill=(30, 30, 160), width=3)
    texture("cheat_sheet.png", 256, 128, (255, 236, 90), [], extra=cheat)
    texture("phone_screen.png", 128, 256, (40, 120, 230), ["12:04"], size=20)
    texture("monitor_on.png", 512, 256, (20, 60, 140), ["DASHBOARD"], size=34,
            extra=lambda d, w, h: [d.rectangle((20 + i * 70, 120, 70 + i * 70, 180 - i * 12), fill=(80, 200, 160))
                                   for i in range(4)])


# ----------------------------------------------------------------------------- building
def walls(bounds) -> list[str]:
    x0, y0, x1, y1 = bounds
    t, out = 0.1, []
    L, W = x1 - x0, y1 - y0
    wall_col = (0.86, 0.85, 0.82)
    for name, size, pos in (("wall north", (L + 2 * t, t, WALL_H), ((x0 + x1) / 2, y1 + t / 2, WALL_H / 2)),
                            ("wall south", (L + 2 * t, t, WALL_H), ((x0 + x1) / 2, y0 - t / 2, WALL_H / 2)),
                            ("wall west", (t, W, WALL_H), (x0 - t / 2, (y0 + y1) / 2, WALL_H / 2)),
                            ("wall east", (t, W, WALL_H), (x1 + t / 2, (y0 + y1) / 2, WALL_H / 2))):
        out.append(solid(name, pos, [box(size, (0, 0, 0), wall_col)], (size, (0, 0, 0))))
    for i, px in enumerate(PARTITIONS):
        for side in (1, -1):
            yin, yout = side * DOOR_HALF, side * (y1 if side > 0 else -y0)
            h = abs(yout - yin)
            pos = (px, (yin + yout) / 2, WALL_H / 2)
            out.append(solid(f"partition {i}{'L' if side > 0 else 'R'}", pos,
                             [box((0.1, h, WALL_H), (0, 0, 0), wall_col)], ((0.1, h, WALL_H), (0, 0, 0))))
    # floor + room tints
    floor = solid("floor", ((x0 + x1) / 2, (y0 + y1) / 2, -0.01),
                  [box((L + 0.4, W + 0.4, 0.02), (0, 0, 0), (0.66, 0.66, 0.64), rough=0.9)],
                  ((L + 0.4, W + 0.4, 0.02), (0, 0, 0)))
    out.append(floor)
    edges = [x0] + PARTITIONS + [x1]
    return out, edges


def room_of(x, edges, zones):
    for a, b in zip(edges, edges[1:]):
        if a <= x < b:
            for z, v in zones.items():
                if a <= float(v["x"]) < b:
                    return z, a, b
    return None, None, None


def student(st, i, side) -> str:
    """Seated student at a desk, facing +x. side = +1 desk on the left of the aisle, -1 on the right."""
    n = st["name"]
    shirt, skin = SHIRTS[i % len(SHIRTS)], SKINS[i % len(SKINS)]
    pants, hair = (0.18, 0.2, 0.28), (0.12, 0.09, 0.07)
    toward_aisle = -side
    head_rot = axis_angle(ry(math.radians(12)))
    parts = [
        # chair
        box((0.42, 0.42, 0.04), (-0.08, 0, 0.45), (0.25, 0.27, 0.32)),
        box((0.04, 0.42, 0.45), (-0.29, 0, 0.7), (0.25, 0.27, 0.32)),
        *[cyl(0.45, 0.015, (-0.08 + dx, dy, 0.225), (0.5, 0.5, 0.5), metal=0.6, rough=0.4)
          for dx in (-0.18, 0.18) for dy in (-0.18, 0.18)],
        # body
        box((0.4, 0.3, 0.12), (0.12, 0, 0.53), pants),
        box((0.11, 0.28, 0.47), (0.31, 0, 0.24), pants),
        box((0.24, 0.38, 0.5), (-0.04, 0, 0.78), shirt),
        box((0.36, 0.08, 0.09), (0.14, 0.2, 0.86), shirt),
        box((0.36, 0.08, 0.09), (0.14, -0.2, 0.86), shirt),
        sphere(0.045, (0.33, 0.2, 0.86), skin),
        sphere(0.045, (0.33, -0.2, 0.86), skin),
        cyl(0.08, 0.045, (-0.03, 0, 1.06), skin),
        # head: rotated by the robot's controller (head turns / looking down)
        f"DEF HEAD_{n} Pose {{ translation -0.03 0 1.09 rotation {f(head_rot)} children [ "
        + " ".join([
            sphere(0.105, (0, 0, 0.1), skin),
            sphere(0.108, (-0.02, 0, 0.125), hair),
            sphere(0.016, (0.095, 0.038, 0.115), (0.08, 0.08, 0.1)),
            sphere(0.016, (0.095, -0.038, 0.115), (0.08, 0.08, 0.1)),
            box((0.03, 0.02, 0.035), (0.105, 0, 0.09), skin),
            box((0.012, 0.05, 0.012), (0.095, 0, 0.055), (0.6, 0.25, 0.25)),
            f"DEF EAR_{n} Transform {{ scale 0.001 0.001 0.001 translation 0 {toward_aisle * 0.105:.3f} 0.1 "
            f"children [ {sphere(0.022, (0, 0, 0), (0.97, 0.97, 0.97), rough=0.3)} ] }}",
        ]) + " ] }",
        # phone held up near the chest (hidden until the 'phone' behaviour)
        f"DEF PHONE_{n} Transform {{ scale 0.001 0.001 0.001 translation 0.3 {toward_aisle * 0.12:.3f} 0.95 "
        f"rotation 0 0 1 {math.radians(180 + 55 * toward_aisle):.4f} children [ "
        + box((0.012, 0.085, 0.17), (0, 0, 0), (0.05, 0.05, 0.06), rough=0.3)
        + box((0.002, 0.075, 0.15), (0.007, 0, 0), (1, 1, 1), emissive=(0.4, 0.6, 1.0), tex="phone_screen.png")
        + " ] }",
        # cheat sheet in the hand on the aisle side (hidden until 'notes')
        f"DEF NOTES_{n} Transform {{ scale 0.001 0.001 0.001 translation 0.36 {toward_aisle * 0.24:.3f} 0.8 "
        f"rotation 1 0 0 {toward_aisle * 0.6:.3f} children [ "
        + box((0.16, 0.12, 0.003), (0, 0, 0), (1, 1, 1), tex="cheat_sheet.png", emissive=(0.25, 0.22, 0.05))
        + " ] }",
    ]
    return solid(f"student {n}", (float(st["x"]) - 0.3, float(st["y"]), 0), parts,
                 ((0.5, 0.45, 0.9), (-0.08, 0, 0.45)))


def desk(i, b) -> str:
    x0, y0, x1, y1 = b
    w, d = x1 - x0, y1 - y0
    legs = [cyl(0.72, 0.018, (dx, dy, 0.36), (0.35, 0.35, 0.38), metal=0.6, rough=0.4)
            for dx in (-w / 2 + 0.04, w / 2 - 0.04) for dy in (-d / 2 + 0.04, d / 2 - 0.04)]
    top = box((w, d, 0.03), (0, 0, 0.735), (0.78, 0.62, 0.42))
    paper = box((0.21, 0.297, 0.002), (-0.08, 0, 0.752), (1, 1, 1), tex="exam_paper.png", rot=(0, 0, 1, 1.5708))
    pen = cyl(0.14, 0.005, (0.05, 0.12, 0.756), (0.1, 0.2, 0.7))
    return solid(f"desk {i}", ((x0 + x1) / 2, (y0 + y1) / 2, 0), [top, paper, *legs],
                 ((w, d, 0.75), (0, 0, 0.375)))


def office_chair(name, pos, rot=0.0, color=(0.15, 0.2, 0.55)) -> str:
    parts = [box((0.45, 0.45, 0.05), (0, 0, 0.47), color), box((0.05, 0.45, 0.5), (-0.22, 0, 0.75), color),
             cyl(0.42, 0.025, (0, 0, 0.24), (0.3, 0.3, 0.3), metal=0.7, rough=0.3),
             box((0.5, 0.06, 0.03), (0, 0, 0.03), (0.2, 0.2, 0.2)), box((0.06, 0.5, 0.03), (0, 0, 0.03), (0.2, 0.2, 0.2))]
    return solid(name, pos, parts, ((0.5, 0.5, 1.0), (-0.02, 0, 0.5)), rot=(0, 0, 1, rot))


def wall_panel(name, x, z, w, h, tex=None, color=(1, 1, 1), emissive=None, side=1, depth=0.02) -> str:
    """Flat panel on the north (side=1) or south (side=-1) wall, facing into the room."""
    y = side * (2.0 - depth / 2 - 0.005)
    rot = (0, 0, 1, -math.pi / 2 if side > 0 else math.pi / 2)
    # box faces: texture shows on the +x face; rotate so +x faces into the room
    return f'Pose {{ translation {f((x, y, z))} rotation {f(rot)} children [ Shape {{ appearance {app(color, emissive=emissive, tex=tex)} geometry Box {{ size {f((depth, w, h))} }} }} ] }}'


def room_props(zone, sc, zx, a, b) -> list[str]:
    out = []
    lit = bool(sc.get("lights_on"))
    # room sign above the doorway on the entry partition (seen when driving in)
    out.append(f'Pose {{ translation {f((a + 0.06, 0, 2.25))} children [ Shape {{ appearance {app((1, 1, 1), tex=f"sign_{zone}.png", emissive=(0.5, 0.5, 0.5))} geometry Box {{ size 0.02 1.6 0.4 }} }} ] }}')
    # floor tint
    out.append(box((b - a - 0.1, 3.98, 0.002), ((a + b) / 2, 0, 0.001), FLOOR_TINT.get(zone, (0.7, 0.7, 0.7)), rough=0.9))
    # ceiling lamps (glow when on) + the light itself
    for dx in (-0.7, 0.7):
        out.append(box((0.6, 0.6, 0.03), (zx + dx, 0, 2.45), (0.9, 0.9, 0.9),
                       emissive=(1, 1, 0.95) if lit else None))
    out.append(f"PointLight {{ location {f((zx, 0, 2.3))} intensity {4.5 if lit else 0} attenuation 0 0 1 "
               f"color 1 0.97 0.92 radius 6 castShadows FALSE }}")
    if zone == "Exam_Hall":
        out.append(f'Pose {{ translation {f((b - 0.015, 0, 1.4))} rotation 0 0 1 3.1416 children [ Shape {{ '
                   f'appearance {app((1, 1, 1), tex="whiteboard_exam.png")} geometry Box {{ size 0.02 1.8 0.9 }} }} ] }}')
        out.append(solid("teacher desk", (14.9, 0.9, 0), [box((0.6, 1.0, 0.03), (0, 0, 0.735), (0.55, 0.42, 0.3)),
                                                        box((0.55, 0.95, 0.7), (0, 0, 0.36), (0.5, 0.38, 0.27))],
                         ((0.6, 1.0, 0.75), (0, 0, 0.375))))
    else:
        # North wall, seen by the robot when it faces the room (view_heading 90): screen above an
        # equipment bench on the left, exit door + extinguisher on the right. All inside the camera view.
        if zone != "Home":
            on = bool(sc.get("projector_on"))
            out.append(wall_panel("screen", zx - 0.4, 1.58, 1.25, 0.7, tex="slide.png" if on else None,
                                  color=(1, 1, 1) if on else (0.16, 0.16, 0.18),
                                  emissive=(0.9, 0.9, 0.9) if on else None))
        if zone in ("IoT_Lab", "Home") or sc.get("monitors_on"):
            mon = bool(sc.get("monitors_on"))
            parts = [box((1.3, 0.45, 0.04), (0, 0, 0.76), (0.35, 0.42, 0.55)),
                     box((1.25, 0.4, 0.7), (0, 0, 0.36), (0.42, 0.48, 0.58))]
            for dx in ((-0.42, 0.0, 0.42) if zone != "Home" else (0.0,)):
                # bench is turned 180 deg: larger local y = closer to the robot
                parts.append(box((0.36, 0.035, 0.24), (dx, 0.1, 0.97), (0.05, 0.05, 0.06)))
                parts.append(box((0.33, 0.004, 0.2), (dx, 0.12, 0.97), (1, 1, 1) if mon else (0.03, 0.03, 0.04),
                                 emissive=(0.6, 0.7, 0.9) if mon else None, tex="monitor_on.png" if mon else None,
                                 rot=(0, 0, 1, 3.1416)))
                parts.append(cyl(0.1, 0.02, (dx, 0.08, 0.82), (0.1, 0.1, 0.1)))
            if sc.get("hazardous_tools"):          # soldering iron left on, glowing tip, in its stand
                parts.append(box((0.12, 0.1, 0.07), (0.48, 0.12, 0.815), (0.8, 0.1, 0.1)))
                parts.append(box((0.26, 0.035, 0.035), (0.36, 0.17, 0.81), (0.3, 0.3, 0.32), rot=(0, 0, 1, -0.35)))
                parts.append(sphere(0.03, (0.23, 0.21, 0.81), (1, 0.3, 0.05), emissive=(1, 0.35, 0)))
            out.append(solid(f"bench {zone}", (zx - 0.4 if zone != "Home" else zx - 0.5, 1.75, 0), parts,
                             ((1.3, 0.45, 0.8), (0, 0, 0.4)), rot=(0, 0, 1, 3.1416)))
        dx = zx + 0.72
        out.append(wall_panel("door", dx, 0.98, 0.8, 1.96, color=(0.32, 0.5, 0.38), depth=0.04))
        out.append(wall_panel("exit sign", dx, 1.75, 0.42, 0.16, tex="exit.png", emissive=(0.2, 0.9, 0.3), depth=0.05))
        if sc.get("exit_blocked"):
            out.append(office_chair(f"chair blocking exit {zone}", (dx, 1.45, 0), rot=-1.2, color=(0.6, 0.15, 0.15)))
        if sc.get("extinguisher_present"):
            out.append(solid(f"extinguisher {zone}", (zx + 0.22, 1.86, 0),
                             [cyl(0.5, 0.08, (0, 0, 0.45), (0.85, 0.08, 0.06), rough=0.3),
                              cyl(0.08, 0.03, (0, 0, 0.74), (0.15, 0.15, 0.15))], ((0.17, 0.17, 0.8), (0, 0, 0.4))))
        if zone in ("LectureHall_A", "LectureHall_B"):
            for k in range(3):
                out.append(office_chair(f"hall chair {zone} {k}", (zx - 0.8 + k * 0.8, -1.55, 0), rot=1.5708,
                                        color=(0.3, 0.3, 0.35)))
    occupants = int(sc.get("occupants", 0))
    if zone == "Home" and occupants:
        out.append(solid("staff member", (zx + 0.3, 1.3, 0), [
            box((0.14, 0.3, 0.85), (0, 0, 0.43), (0.2, 0.22, 0.3)), box((0.24, 0.4, 0.6), (0, 0, 1.15), (0.3, 0.5, 0.6)),
            sphere(0.11, (0, 0, 1.57), SKINS[1]), sphere(0.112, (-0.02, 0, 1.6), (0.1, 0.08, 0.07))],
            ((0.3, 0.4, 1.7), (0, 0, 0.85)), rot=(0, 0, 1, -1.5708)))
    return out


# ----------------------------------------------------------------------------- robot
def robot(cfg) -> str:
    m = cfg.get("motion", {})
    r = float(m.get("wheel_diameter_m", 0.065)) / 2
    half_base = float(m.get("wheel_base_m", 0.15)) / 2
    vmax = float(m.get("max_speed_mps", 0.5)) / r * 1.15
    hfov = math.radians(float(cfg.get("camera", {}).get("hfov_deg", 62.2)))
    w, h = int(cfg.get("camera", {}).get("width", 640)), int(cfg.get("camera", {}).get("height", 480))
    body = (0.08, 0.30, 0.55)
    accent = (0.12, 0.78, 0.89)

    def wheel(side, name):
        y = side * half_base
        return f"""HingeJoint {{
      jointParameters HingeJointParameters {{ axis 0 1 0 anchor 0 {y:.4f} {r:.4f} }}
      device [ RotationalMotor {{ name "{name} wheel motor" maxVelocity {vmax:.2f} maxTorque 2 acceleration 25 }}
               PositionSensor {{ name "{name} wheel sensor" }} ]
      endPoint Solid {{ translation 0 {y:.4f} {r:.4f} rotation 1 0 0 1.5708 name "{name} wheel"
        children [ DEF WHEEL_{name.upper()} Shape {{ appearance {app((0.08, 0.08, 0.08), rough=0.9)} geometry Cylinder {{ height 0.026 radius {r:.4f} subdivision 24 }} }}
                   Pose {{ children [ Shape {{ appearance {app((0.9, 0.75, 0.1))} geometry Cylinder {{ height 0.028 radius {r * 0.45:.4f} }} }} ] }} ]
        boundingObject Cylinder {{ height 0.026 radius {r:.4f} }}
        physics Physics {{ density -1 mass 0.06 }} }} }}"""

    def caster(x, name):
        return (f'Solid {{ translation {x} 0 0.016 name "{name}" contactMaterial "caster" children [ Shape {{ appearance '
                f'{app((0.7, 0.7, 0.72), metal=0.8, rough=0.2)} geometry Sphere {{ radius 0.016 }} }} ] '
                f'boundingObject Sphere {{ radius 0.016 }} physics Physics {{ density -1 mass 0.01 }} }}')

    def sonar(name, ang):
        x, y = 0.12 * math.cos(ang), 0.06 * math.sin(ang) * 1.6
        return (f'DistanceSensor {{ translation {x:.3f} {y:.3f} 0.07 rotation 0 0 1 {ang:.4f} name "{name}" type "sonar" '
                f'numberOfRays 5 aperture 0.26 lookupTable [ 0.02 2 0, 4 400 0 ] '
                f'children [ {cyl(0.012, 0.012, (0.006, 0.014, 0), (0.75, 0.75, 0.78), metal=0.7)} '
                f'{cyl(0.012, 0.012, (0.006, -0.014, 0), (0.75, 0.75, 0.78), metal=0.7)} '
                f'{box((0.004, 0.05, 0.022), (0, 0, 0), (0.1, 0.35, 0.7))} ] }}')

    tilt = f"""HingeJoint {{
          jointParameters HingeJointParameters {{ axis 0 1 0 anchor 0 0 0.03 }}
          device [ RotationalMotor {{ name "tilt motor" minPosition -0.8 maxPosition 1.05 maxVelocity 6 }} PositionSensor {{ name "tilt sensor" }} ]
          endPoint Solid {{ translation 0 0 0.03 name "tilt head"
            children [
              {box((0.05, 0.1, 0.035), (0, 0, 0), (0.12, 0.12, 0.14))}
              {cyl(0.02, 0.012, (0.03, 0, 0), (0.05, 0.05, 0.05))}
              Camera {{ translation 0.035 0 0 name "camera" fieldOfView {hfov:.4f} width {w} height {h} far 25 }}
            ] }} }}"""
    pan = f"""HingeJoint {{
      jointParameters HingeJointParameters {{ axis 0 0 1 anchor 0 0 {CAMERA_HEIGHT - 0.03:.3f} }}
      device [ RotationalMotor {{ name "pan motor" minPosition -1.6 maxPosition 1.6 maxVelocity 6 }} PositionSensor {{ name "pan sensor" }} ]
      endPoint Solid {{ translation 0 0 {CAMERA_HEIGHT - 0.03:.3f} name "pan base"
        children [ {cyl(0.03, 0.035, (0, 0, 0.0), (0.12, 0.12, 0.14))}
          {tilt} ] }} }}"""
    return f"""DEF RAQIB Robot {{
  translation 0 0 0.0
  rotation 0 0 1 0
  name "raqib"
  controller "<extern>"
  supervisor TRUE
  children [
    {box((0.26, 0.11, 0.06), (0, 0, 0.065), body, rough=0.5)}
    {box((0.2, 0.105, 0.012), (0, 0, 0.101), accent, rough=0.4)}
    {box((0.09, 0.09, 0.05), (-0.05, 0, 0.13), (0.1, 0.1, 0.12))}
    {cyl(CAMERA_HEIGHT - 0.16, 0.012, (0.0, 0, 0.1 + (CAMERA_HEIGHT - 0.16) / 2), (0.75, 0.76, 0.8), metal=0.8, rough=0.3)}
    {box((0.07, 0.05, 0.1), (-0.05, 0, 0.2), (0.12, 0.13, 0.16))}
    {wheel(1, "left")}
    {wheel(-1, "right")}
    {caster(0.1, "front caster")}
    {caster(-0.1, "rear caster")}
    {sonar("us_left", math.radians(45))}
    {sonar("us_center", 0.0)}
    {sonar("us_right", math.radians(-45))}
    {pan}
    InertialUnit {{ name "imu" }}
    Gyro {{ name "gyro" }}
    Accelerometer {{ name "accelerometer" }}
    Speaker {{ name "speaker" }}
  ]
  boundingObject Pose {{ translation 0 0 0.065 children [ Box {{ size 0.26 0.11 0.06 }} ] }}
  physics Physics {{ density -1 mass 1.6 centerOfMass [ 0 0 0.04 ] }}
}}"""


# ----------------------------------------------------------------------------- world
def build():
    cfg = yaml.safe_load((EDGE / "config.yaml").read_text(encoding="utf-8"))
    world = yaml.safe_load((EDGE / "sim_world.yaml").read_text(encoding="utf-8"))
    zones = cfg["zones"]
    global PARTITIONS
    PARTITIONS = [float(v) for v in (cfg.get("webots") or {}).get("partitions", PARTITIONS)]
    scen = world.get("scenarios", {})
    bounds = world.get("bounds", [-1, -2, 15.5, 2])
    make_textures()
    nodes, edges = walls(bounds)
    for z, v in zones.items():
        _, a, b = room_of(float(v["x"]), edges, zones)
        if a is None:
            continue
        nodes += room_props(z, scen.get(z, {}), float(v["x"]), a, b)
    di = 0
    for bx in world.get("obstacles", []):
        x0, y0, x1, y1 = map(float, bx)
        zone, _, _ = room_of((x0 + x1) / 2, edges, zones)
        if zone == "Exam_Hall":
            nodes.append(desk(di, (x0, y0, x1, y1)))
            di += 1
        else:
            nodes.append(office_chair(f"corridor chair {di}", ((x0 + x1) / 2, (y0 + y1) / 2, 0), rot=0.4,
                                      color=(0.55, 0.3, 0.12)))
            di += 1
    for i, st in enumerate(world.get("students", []) or []):
        nodes.append(student(st, i, 1 if float(st["y"]) > 0 else -1))
    vp_pos, vp_target = (7.25, -6.2, 15.5), (7.25, 0.2, 0.0)
    text = f"""#VRML_SIM R2025a utf8
# Raqib campus - generated by webots/build_world.py from edge/config.yaml + edge/sim_world.yaml.
# The robot "raqib" runs the real Raqib software: start it with start_robot_webots.bat.

WorldInfo {{
  info [ "Raqib inspection robot - campus corridor, IoT lab, lecture halls and exam hall" ]
  title "Raqib campus"
  basicTimeStep 16
  contactProperties [ ContactProperties {{ material2 "caster" coulombFriction [ 0.02 ] }} ]
}}
Viewpoint {{
  orientation {f(look_rotation(vp_pos, vp_target))}
  position {f(vp_pos)}
  fieldOfView 1.05
  near 0.05
}}
Background {{ skyColor [ 0.78 0.82 0.88 ] luminosity 0.25 }}
DirectionalLight {{ direction 0.3 0.5 -1 intensity 0.22 castShadows FALSE }}
{chr(10).join(nodes)}
{(ROOT / 'my_robot.wbt').read_text(encoding='utf-8') if (ROOT / 'my_robot.wbt').exists() else robot(cfg)}
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {OUT} ({len(text) // 1024} KB, {len(nodes)} nodes)")


if __name__ == "__main__":
    build()
