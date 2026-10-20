"""One big wiring poster of the whole ESP32 robot (Raqib 3.0): every part, every wire, plus the pin table.

    python docs/build_guide/poster.py      -> docs/Raqib_Full_Wiring_Diagram.pdf (A3 landscape) + .png

The drawing is the same one the build guide uses (esp32_figs.wiring), at poster size. Pins and wire colours match
esp32/raqib_esp32/raqib_esp32.ino, edge/robot/wiring_spec.py, the Wiring Bench and the build guide.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from esp32_figs import wiring  # noqa: E402

OUT_PDF = HERE.parent / "Raqib_Full_Wiring_Diagram.pdf"
OUT_PNG = HERE.parent / "Raqib_Full_Wiring_Diagram.png"

PINS = [
    ("D0", "DRV8833 AIN1", "left motor"), ("D1", "DRV8833 AIN2", "left motor"),
    ("D2", "DRV8833 BIN1", "right motor"), ("D3", "DRV8833 BIN2", "right motor"),
    ("D4", "SDA → MPU6050 + AHT20/BMP280", "I²C data"), ("D5", "SCL → MPU6050 + AHT20/BMP280", "I²C clock"),
    ("D6", "HC-SR04P TRIG", "distance"), ("D7", "HC-SR04P ECHO", "distance"),
    ("3V3", "breadboard + rail", "all sensors, DRV8833 EEP"), ("GND", "breadboard − rail", "the one shared ground"),
    ("USB-C", "power bank", "powers the XIAO only"),
]
POWER = [
    ("2 × 18650 (7.4 V)", "DRV8833 VM (+) and GND (−)", "motors only"),
    ("DRV8833 AOUT1/2", "left TT motor", "swap the two wires if it runs backwards"),
    ("DRV8833 BOUT1/2", "right TT motor", "swap the two wires if it runs backwards"),
    ("DRV8833 GND", "breadboard − rail", "joins the two batteries' grounds"),
]

CSS = """@page { size: A3 landscape; margin: 0 }
html,body{margin:0;background:#fff;font-family:Inter,'DejaVu Sans',sans-serif;color:#16202a}
.page{width:420mm;height:297mm;box-sizing:border-box;padding:10mm 12mm;display:grid;grid-template-columns:1fr 92mm;gap:8mm}
.draw svg{width:100%;height:auto;display:block}
h1{font-size:22pt;margin:0 0 1mm;font-weight:800} .sub{font-size:10pt;color:#56616d;margin:0 0 4mm}
h2{font-size:11pt;margin:5mm 0 2mm;font-weight:800}
table{border-collapse:collapse;width:100%;font-size:8.6pt} td,th{padding:1.4mm 1.6mm;border-bottom:1px solid #e3e8ee;text-align:left;vertical-align:top}
th{background:#16202a;color:#fff;font-weight:700} td:first-child{font-weight:800;white-space:nowrap}
td:last-child{color:#56616d}
.rule{margin-top:5mm;padding:3mm 4mm;background:#fff4e5;border-left:3px solid #f08a00;border-radius:4px;font-size:9pt;line-height:1.4}
.ok{background:#eaf6ee;border-left-color:#2e9e5b}"""


def build() -> str:
    svg = wiring(title=None, big=True)
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in PINS)
    prow = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in POWER)
    return (f"<div class='page'><div><h1>Raqib 3.0 · the whole robot's wiring</h1>"
            f"<p class='sub'>XIAO ESP32S3 Sense + DRV8833 + HC-SR04P + MPU6050 + AHT20/BMP280 on one half breadboard · "
            f"about 22 jumper wires · no soldering except the XIAO's header pins</p><div class='draw'>{svg}</div></div>"
            f"<div><h2>XIAO pins</h2><table><tr><th>Pin</th><th>Goes to</th><th>Why</th></tr>{rows}</table>"
            f"<h2>Motor power</h2><table><tr><th>From</th><th>To</th><th>Note</th></tr>{prow}</table>"
            f"<div class='rule'><b>3.3 V only on the XIAO.</b> Never connect the motor battery or any 5 V signal to a XIAO pin. "
            f"Use the HC-SR04<b>P</b> (3.3 V version).</div>"
            f"<div class='rule ok'><b>Check it on the PC first:</b> open the Wiring Bench (start_robot_sim.bat → "
            f"http://localhost:8000/bench) and place the same wires; it tells you what would work before you plug anything in.</div>"
            f"</div></div>")


def main():
    html = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{build()}</body></html>"
    page = HERE / "poster.html"
    page.write_text(html, encoding="utf-8")
    js = HERE / "_poster.js"
    js.write_text(f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch(); const p = await b.newPage({{ viewport: {{ width: 1587, height: 1123 }}, deviceScaleFactor: 2 }});
  await p.goto('file://{page}'); await p.waitForTimeout(500);
  await p.pdf({{ path: '{OUT_PDF}', width: '420mm', height: '297mm', printBackground: true, margin: {{ top: 0, bottom: 0, left: 0, right: 0 }} }});
  await p.screenshot({{ path: '{OUT_PNG}', fullPage: true }});
  await b.close(); }})();""")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js)], check=True, env={**os.environ, "NODE_PATH": npm_root})
    js.unlink()
    page.unlink()
    print("wrote", OUT_PDF, "and", OUT_PNG)


if __name__ == "__main__":
    main()
