"""Lays the rendered views (out/*.png) into docs/Raqib_Finished_Robot_3D.pdf.

    python textures.py && node tex2png.js && node render.js && python build_pdf.py
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_PDF = HERE.parent.parent / "Raqib_Finished_Robot_3D.pdf"

PAGES = [
    ("hero", "The finished robot", "Raqib 3.0, the easy ESP32 inspection robot, fully built: one acrylic deck, two-wheel drive with a caster, "
     "a XIAO ESP32S3 Sense (camera + microphone) standing at the front over one distance sensor, and every other part on a half breadboard. "
     "No soldering of the sensors, no Raspberry Pi: your laptop is the brain."),
    ("hero_labels", "Every part, labelled", "All parts in their final place. Front of the robot = the side with the camera and the distance sensor."),
    ("top_labels", "Seen from above: how the deck is organised",
     "Front: the HC-SR04P at the edge and the XIAO on its bracket just behind it, camera looking forward. Middle: the half breadboard "
     "with the DRV8833, MPU6050 and AHT20 + BMP280 plugged in. Back: the USB power bank, which powers only the XIAO."),
    ("front", "Front view", "What the robot looks at: the distance sensor straight ahead and the camera just above it. "
     "The camera is fixed: the robot turns its whole body to look around."),
    ("left", "Side view", "One deck. On top: power bank, breadboard, XIAO and sensor. Under it: the 2 × 18650 motor battery and the "
     "two TT motors at the front; the caster ball at the back."),
    ("rear_labels", "From the back", "The power bank's USB-C cable goes to the top of the XIAO. The motor battery's red and black leads come up "
     "through the deck to the DRV8833 (VM and GND); the DRV8833's GND row is also joined to the 3V3 / GND rails, so everything shares one ground."),
    ("under_labels", "Underneath", "The 2 × 18650 holder sits under the deck with its switch reachable and powers only the motors. "
     "Two TT motors at the front (left and right), the caster at the back. No encoders: the robot uses its gyro to turn and times its motors."),
    ("close", "Close-up of the wiring", "Colour-coded jumper wires from the XIAO down to the breadboard: green / purple motor direction "
     "(D0–D3), blue SDA (D4), yellow SCL (D5), pink TRIG (D6), cyan ECHO (D7), orange 3V3, black GND."),
]

CSS = """@page { size: A4 landscape; margin: 10mm 12mm 12mm; }
html,body{margin:0;font-family:Inter,'DejaVu Sans',sans-serif;color:#16202a}
section{break-after:page;display:flex;flex-direction:column;height:186mm}
section:last-child{break-after:auto}
h1{font-size:20pt;margin:0 0 2mm;font-weight:800;letter-spacing:-.01em}
p{margin:0 0 3mm;font-size:10pt;color:#3b4652;line-height:1.4;max-width:250mm}
.img{flex:1;display:flex;align-items:center;justify-content:center;background:#eef2f6;border-radius:10px;overflow:hidden}
.img img{max-width:100%;max-height:100%;}
.cover h1{font-size:30pt} .kick{font-size:9pt;letter-spacing:.18em;font-weight:800;color:#1f5fbf;margin-bottom:1mm}
.note{font-size:8.5pt;color:#6a7480;margin-top:2mm}"""


def main():
    secs = []
    for i, (img, title, text) in enumerate(PAGES):
        kick = '<div class="kick">RAQIB · THE FINISHED ROBOT · 3D VIEW</div>' if i == 0 else ""
        note = ('<div class="note">A 3D model at real size (mm), built from the parts and layout of the build guide. Board colours and '
                'printed labels follow the common versions of each part; your boards may differ slightly.</div>') if i == 0 else ""
        secs.append(f'<section class="{"cover" if i == 0 else ""}">{kick}<h1>{title}</h1><p>{text}</p>'
                    f'<div class="img"><img src="out/{img}.png"></div>{note}</section>')
    html = HERE / "finished.html"
    html.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(secs)}</body></html>",
                    encoding="utf-8")
    js = HERE / "_pdf.js"
    js.write_text(f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://{html}'); await p.waitForTimeout(800);
  await p.pdf({{ path: '{OUT_PDF}', format: 'A4', landscape: true, printBackground: true }});
  await b.close(); }})();""")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js)], check=True, env={**os.environ, "NODE_PATH": npm_root})
    js.unlink()
    html.unlink()
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    main()
