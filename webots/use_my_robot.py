"""Put the robot you built in the build lab into the Raqib campus (guide step 11).

    python webots/use_my_robot.py            copy your robot from worlds/raqib_build_lab.wbt into the campus
    python webots/use_my_robot.py --original put the original Raqib back

Your robot is saved as webots/my_robot.wbt; build_world.py uses it from then on, so rebuilding the
campus keeps your robot.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT / "worlds" / "raqib_build_lab.wbt"
CAMPUS = ROOT / "worlds" / "raqib_campus.wbt"
MINE = ROOT / "my_robot.wbt"


def node_block(text: str, start: int) -> tuple[int, int]:
    """(start, end) of the node whose '{' follows `start`, matching braces (strings skipped)."""
    i = text.index("{", start)
    depth, in_str = 0, False
    while i < len(text):
        c = text[i]
        if c == '"' and text[i - 1] != "\\":
            in_str = not in_str
        elif not in_str and c == "#":
            i = text.index("\n", i)
            continue
        elif not in_str and c == "{":
            depth += 1
        elif not in_str and c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1
    raise ValueError("unbalanced braces")


def find_robot(text: str) -> tuple[int, int]:
    """The top-level Robot node named "raqib"."""
    for m in re.finditer(r"^(DEF \w+ )?Robot \{", text, re.M):
        s, e = node_block(text, m.start())
        if re.search(r'^\s{2}name "raqib"', text[s:e], re.M):
            return s, e
    raise LookupError('no Robot named "raqib" at the top level of the world')


def main():
    if "--original" in sys.argv:
        if MINE.exists():
            MINE.unlink()
        import build_world
        build_world.build()
        print("The original Raqib is back in the campus. Reopen raqib_campus.wbt in Webots.")
        return
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else LAB
    text = src.read_text(encoding="utf-8")
    try:
        s, e = find_robot(text)
    except LookupError as err:
        sys.exit(f"{err}. Build it in {src.name} and save the world in Webots (Ctrl+S) first.")
    robot = text[s:e]
    robot = re.sub(r"^(DEF \w+ )?Robot \{", "DEF RAQIB Robot {", robot, count=1)
    robot = re.sub(r"^  translation .*$", "  translation 0 0 0", robot, count=1, flags=re.M)
    robot = re.sub(r"^  rotation .*$", "  rotation 0 0 1 0", robot, count=1, flags=re.M)
    missing = [n for n in ("left wheel motor", "right wheel motor", "us_center", "imu", "camera", "pan motor", "tilt motor")
               if f'"{n}"' not in robot]
    if missing:
        print("Warning: your robot has no " + ", ".join(missing) + ". The app needs every part: finish the guide first.")
    if 'controller "<extern>"' not in robot or "supervisor TRUE" not in robot:
        sys.exit('Your robot needs controller "<extern>" and supervisor TRUE (guide step 2).')
    MINE.write_text(robot + "\n", encoding="utf-8")
    campus = CAMPUS.read_text(encoding="utf-8")
    cs, ce = find_robot(campus)
    CAMPUS.write_text(campus[:cs] + robot + campus[ce:], encoding="utf-8", newline="\n")
    print(f"Your robot from {src.name} is now in the campus (saved as {MINE.name}).")
    print("Open webots/worlds/raqib_campus.wbt in Webots (or File > Reload World), then run start_all_webots.bat.")


if __name__ == "__main__":
    main()
