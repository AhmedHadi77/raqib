"""Board textures for the 3D model: each board drawing from ../draw.py, cropped to the board outline."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from draw import (S, ads1115, aht20, battery_2s, buck_xl4015, gy521, hcsr04, l298n, mq135, pam8403, pi4,  # noqa: E402
                  slot_encoder)
from diagrams import hub_board  # noqa: E402

TEX = {
    "pi": (289, 190.4, lambda s: pi4(s, 0, 0, 1.0)),
    "l298n": (170, 170, lambda s: l298n(s, 0, 0, 1.0)),
    "xl4015": (140, 70, lambda s: buck_xl4015(s, 0, 0, 1.0)),
    "hcsr04": (135, 64, lambda s: hcsr04(s, 0, 0, 1.0)),
    "mpu": (112, 82, lambda s: gy521(s, 0, 0, 1.0)),
    "aht": (76, 62, lambda s: aht20(s, 0, 0, 1.0)),
    "ads": (128, 76, lambda s: ads1115(s, 0, 0, 1.0)),
    "mq": (96, 84, lambda s: mq135(s, 0, 0, 1.0)),
    "pam": (90, 54, lambda s: pam8403(s, 0, 0, 1.0)),
    "enc": (70, 40, lambda s: slot_encoder(s, 0, 0, 1.0)),
    "battery": (150, 92, lambda s: battery_2s(s, 0, 0, 1.0)),
    "hub": (310, 180, lambda s: hub_board(s, 0, 0, 1.0)),
}

if __name__ == "__main__":
    out = HERE / "tex"
    out.mkdir(exist_ok=True)
    for name, (w, h, fn) in TEX.items():
        s = S(w, h)
        fn(s)
        (out / f"{name}.svg").write_text(s.svg().replace('<svg class="comp"', '<svg').replace('<svg class="fig"', '<svg')
                                         .replace("viewBox", f'width="{w}" height="{h}" viewBox', 1), encoding="utf-8")
    print("wrote", len(TEX), "svg textures")
