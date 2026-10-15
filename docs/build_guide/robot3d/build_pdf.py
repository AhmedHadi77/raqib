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
    ("hero", "The finished robot", "Raqib, the budget AI inspection robot, fully built and wired: two acrylic decks, three ultrasonic "
     "sensors and a USB webcam at the front, the Raspberry Pi and sensors on top, motors and battery below."),
    ("hero_labels", "Every part, labelled", "All parts in their final place. Front of the robot = the side with the webcam."),
    ("top_labels", "Seen from above: how the top deck is organised",
     "Front (top of the picture): three HC-SR04 fanned left / centre / right and the webcam on its post. Middle: Raspberry Pi with its "
     "40-pin header facing the hub board, MPU6050 near the centre, ADS1115, AHT20. Back: XL4015, speaker + PAM8403, MQ-135 "
     "(warm parts away from the AHT20)."),
    ("front", "Front view", "What the robot looks at: the centre sonar straight ahead, the left and right sonars turned 45°, the webcam "
     "above them. The camera is fixed: the robot turns its whole body to look around."),
    ("left", "Side view", "Two decks on 40 mm brass standoffs. Bottom deck: L298N motor driver; under it the battery, the TT motors with "
     "wheels at the front and the caster at the back. Top deck: Pi, sensors, speaker, webcam."),
    ("rear_labels", "From the back", "The XL4015 converter, the cut USB cable to the Pi's power socket, the MQ-135 and the speaker sit at the "
     "back; the wires from the Pi go down through the deck to the L298N."),
    ("under_labels", "Underneath", "The 2 × 18650 holder hangs under the bottom deck with its switch reachable; the TT motors carry the "
     "encoder discs on their inner shafts, read by the slot sensors; the caster wheel at the back."),
    ("close", "Close-up of the top deck", "Colour-coded jumper wires from the Pi's 40-pin header: red 5 V, orange 3.3 V, black GND, blue SDA, "
     "yellow SCL, green motor direction, amber motor speed, pink / olive / brown sonars, cyan encoders."),
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
