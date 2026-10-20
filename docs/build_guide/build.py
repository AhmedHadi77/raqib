"""Builds docs/Raqib_Robot_Build_Guide.pdf for the ESP32 robot 3.0: parts, pictures, wiring, steps, tests.

    python docs/build_guide/build.py        (needs Playwright + Chromium for the HTML -> PDF step)
"""
from __future__ import annotations

import base64
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import esp32_figs as F  # noqa: E402
from draw import W  # noqa: E402

OUT_HTML = HERE / "guide.html"
OUT_PDF = HERE.parent / "Raqib_Robot_Build_Guide.pdf"
HERO = HERE.parent / "robot_renders" / "hero.png"

# ----------------------------------------------------------------------------------------------- shopping list
BOM = [
    ("The robot's body (one small board does Wi-Fi, camera and microphone)", [
        ("Seeed XIAO ESP32S3 Sense (camera + microphone board included)", 1, 75,
         "Drives the motors, reads the sensors, streams the camera and microphone to the PC over Wi-Fi"),
        ("USB-C data cable (a phone cable that charges AND transfers files)", 1, 6, "To put the firmware on the XIAO, then to power it"),
    ]),
    ("Power (two separate batteries: motor starts can never restart the ESP32)", [
        ("Slim USB power bank 5,000 mAh, 2 A or more", 1, 25, "Powers the XIAO, its camera and the sensors"),
        ("18650 Li-ion cells, flat top, 2500-3000 mAh", 2, 15, "Motors only. Known brands; avoid fake '9900 mAh' cells"),
        ("2 x 18650 battery holder with on/off switch and leads", 1, 6, "7.4 V motor pack; its switch is the motor power switch"),
        ("2-slot USB 18650 charger", 1, 12, "Charges the two motor cells"),
    ]),
    ("Moving", [
        ("2WD smart car chassis kit: acrylic deck, 2 TT motors (3-6 V), 2 wheels, caster wheel, screws", 1, 25,
         "The body: two driven wheels and a caster; turns on the spot"),
        ("DRV8833 dual motor driver module", 1, 7, "Turns the ESP32's 3.3 V signals into motor power; efficient and tiny"),
    ]),
    ("Sensing", [
        ("HC-SR04P ultrasonic distance sensor (3.3 V version)", 2, 5, "One at the front + one spare. The 'P' version needs no resistors"),
        ("MPU6050 motion sensor (GY-521 board)", 1, 8, "Knows how far the robot has turned and keeps it straight"),
        ("AHT20 + BMP280 combo board", 1, 10, "Temperature, humidity and air pressure"),
    ]),
    ("Wiring and mounting (no soldered hub board: everything plugs into a breadboard)", [
        ("Half-size breadboard, 400 points, self-adhesive", 1, 5, "The robot's wiring hub: its rails are 3.3 V and GND"),
        ("Jumper wires: male-male and female-male, 40 of each", 1, 8, "Every connection plugs in"),
        ("Foam tape, zip ties, a small plastic or card bracket for the XIAO", 1, 5, "Holds the XIAO upright at the front"),
    ]),
]
TOOLS = [
    ("Your laptop / PC (Windows)", 0, "The robot's brain: runs the server, the AI and the robot program"),
    ("Soldering iron with solder", 50, "Only for header pins: XIAO (14), MPU6050 (8), AHT20 (4), DRV8833 if not pre-soldered"),
    ("Small screwdriver set", 15, "Chassis and battery holder"),
    ("Tape measure (3 m)", 10, "Calibrating the driving and measuring the rooms"),
    ("Multimeter (optional)", 40, "Checks the motor battery voltage and finds loose wires"),
]
UPGRADES = [
    ("Longer patrols", "10,000 mAh power bank", "≈ 15 more", "Same USB-C cable; the robot lasts about twice as long."),
    ("Better grip on carpet", "4WD chassis kit", "≈ 15 more", "The DRV8833 drives both motors of a side together (joined red-red, black-black)."),
    ("The bigger Raspberry Pi robot", "Pi 4 + servos + gas sensor", "≈ 270 more",
     "Set hardware: board: pi in edge/config.yaml. The same server, app and AI work with it."),
]

# ----------------------------------------------------------------------------------------------- parts
CARDS = [
    ("xiao", "XIAO ESP32S3 Sense", "The robot's body: Wi-Fi, a 240 MHz dual-core ESP32-S3, 8 MB memory, plus the Sense board with camera and microphone.",
     "D0-D3 motors · D4/D5 I²C (SDA/SCL) · D6/D7 distance sensor · 3V3 and GND to the breadboard rails · USB-C power",
     "Press the Sense board on until it clicks, and click the camera ribbon into its socket BEFORE you power it."),
    ("pbank", "USB power bank (ESP32 battery)", "Powers the XIAO, its camera and the sensors, and nothing else.",
     "USB-C (or USB-A) output → its cable → the XIAO's USB-C",
     "Any 5,000 mAh bank works. Its LEDs show how full it is; charge it like a phone."),
    ("bat2", "Motor battery: 2 x 18650", "Powers the two motors only, through the DRV8833.",
     "Red + → DRV8833 VM · black − → DRV8833 GND",
     "7.4 V nominal, 8.4 V full. Never more than 2 cells: the DRV8833 allows 10.8 V at most."),
    ("chassis", "2WD chassis kit", "One acrylic deck, two TT gear motors with wheels, and a caster wheel at the back.",
     "2 motors at the front · caster at the back · battery holder under the deck",
     "Two driven wheels turn on the spot exactly; the gyro measures every turn."),
    ("motor", "TT gear motor (x2)", "3-6 V geared motor; one per side.",
     "2 solder tabs or 2 wires per motor → AOUT1/AOUT2 (left) and BOUT1/BOUT2 (right)",
     "Many kits come with the wires already soldered on."),
    ("drv", "DRV8833 motor driver", "Switches motor-battery power to the motors, forwards or backwards, at the speed the ESP32 asks.",
     "AIN1/AIN2/BIN1/BIN2 ← D0/D1/D2/D3 · VM/GND ← motor battery · GND also → breadboard GND rail · AOUT/BOUT → motors",
     "If your board has an EEP (or SLP) pin, connect it to 3V3, or the motors stay asleep."),
    ("hc", "HC-SR04P (3.3 V)", "Measures distance with sound, 2 cm to 4 m: the robot stops before obstacles.",
     "VCC 3V3 · TRIG ← D6 · ECHO → D7 · GND",
     "Buy the 'P' (3.3 V) version, or the RCWL-1601. The old 5 V HC-SR04 would need resistors."),
    ("imu", "MPU6050 (GY-521)", "Gyroscope + accelerometer: the robot's sense of turning.",
     "VCC 3V3 · GND · SCL ← D5 · SDA ← D4 (the others stay free)",
     "Mount it flat. Keep the robot still for 2 s after switching on: it learns the gyro's offset."),
    ("aht", "AHT20 + BMP280", "Temperature and humidity (AHT20) plus air pressure (BMP280) on one board.",
     "VIN 3V3 · GND · SCL ← D5 · SDA ← D4",
     "Shares the four I²C wires with the MPU6050. Keep it away from the warm XIAO."),
    ("breadboard", "Half breadboard (the wiring hub)", "Every part plugs into it. Its long side rails carry 3.3 V and GND to all sensors.",
     "+ rail = 3V3 from the XIAO · − rail = GND (XIAO, DRV8833 and sensors)",
     "Join the top and bottom rails with two short wires, so both sides have 3V3 and GND."),
    ("wires", "Jumper wires", "Plug-in connections.", "M = pin end · F = socket end",
     "Use colours: orange 3.3 V, black GND, blue SDA, yellow SCL."),
    ("tools", "Tools", "What you need on the desk.", "Soldering iron (header pins only), screwdriver, tape measure",
     "Solder the header pins straight: push them into the breadboard first, then solder."),
]


def bom_table() -> tuple[str, int]:
    rows, total, n = [], 0, 0
    for group, items in BOM:
        rows.append(f'<tr class="grp"><td colspan="5">{escape(group)}</td></tr>')
        for name, qty, price, why in items:
            n += 1
            total += qty * price
            rows.append(f"<tr><td class='num'>{n}</td><td><b>{escape(name)}</b><div class='why'>{escape(why)}</div></td>"
                        f"<td class='c'>{qty}</td><td class='r'>{price}</td><td class='r'>{qty * price}</td></tr>")
    rows.append(f"<tr class='tot'><td></td><td>Total for the robot (estimate)</td><td></td><td></td><td class='r'>≈ {total}</td></tr>")
    return ("<table class='bom'><thead><tr><th>#</th><th>Part</th><th>Qty</th><th>RM each</th><th>RM</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>"), total


def tools_table() -> str:
    rows = "".join(f"<tr><td><b>{escape(t)}</b><div class='why'>{escape(w)}</div></td><td class='r'>{p or 'you have it'}</td></tr>"
                   for t, p, w in TOOLS)
    return f"<table class='bom tools'><thead><tr><th>Tool</th><th>RM</th></tr></thead><tbody>{rows}</tbody></table>"


def cards_html() -> str:
    out = []
    for key, title, what, pins, tip in CARDS:
        out.append(f"""<div class="card"><div class="pic">{F.card(key)}</div>
<h4>{escape(title)}</h4><p>{escape(what)}</p><p class="pins"><b>Connections:</b> {escape(pins)}</p><p class="tip">💡 {escape(tip)}</p></div>""")
    return '<div class="cards">' + "".join(out) + "</div>"


def figure(svg: str, caption: str = "") -> str:
    cap = f"<figcaption>{caption}</figcaption>" if caption else ""
    return f'<figure>{svg}{cap}</figure>'


def check(items: list[str]) -> str:
    return '<div class="check"><b>Check before you continue</b><ul>' + "".join(f"<li>☐ {i}</li>" for i in items) + "</ul></div>"


def cmd(c: str) -> str:
    return f'<pre class="cmd">{escape(c)}</pre>'


def step(n: int, title: str, need: str, body: str) -> str:
    return (f'<section class="step"><div class="stephead"><span class="stepn">{n}</span><div><h2>{escape(title)}</h2>'
            f'<p class="need"><b>You need:</b> {escape(need)}</p></div></div>{body}</section>')


def upgrades_table() -> str:
    rows = "".join(f"<tr><td><b>{escape(w)}</b><div class='why'>{escape(h)}</div></td><td>{escape(part)}</td><td class='r'>{escape(rm)}</td></tr>"
                   for w, part, rm, h in UPGRADES)
    return f"<table class='bom'><thead><tr><th>You want</th><th>Add</th><th>Extra RM</th></tr></thead><tbody>{rows}</tbody></table>"


def hero_img() -> str:
    if HERO.exists():
        b64 = base64.b64encode(HERO.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="width:150mm;border-radius:10px">'
    return F.fig_system()


def build_html() -> str:
    bom, total = bom_table()
    legend = "".join(f'<span><i style="background:{c}"></i>{t}</span>' for c, t in (
        (W["3v3"], "3.3 V"), (W["gnd"], "GND"), (W["bat"], "motor battery +"), (W["sda"], "SDA"), (W["scl"], "SCL"),
        ("#1e9e55", "left motor"), ("#8a55e8", "right motor"), (W["mot"], "motor wires"), ("#e0458b", "TRIG"), ("#0ea5c6", "ECHO")))
    css = (HERE / "style.css").read_text() + ".cover .coverart img{display:block}"
    H = []
    # ---------------------------------------------------------------- cover
    H.append(f"""<section class="cover">
<div class="kicker">RAQIB · AI INSPECTION ROBOT · ESP32 EDITION</div>
<h1>Build the robot</h1>
<p class="sub">About RM {total}: a 2WD robot with one small ESP32 board for its body and your laptop as its brain.
Every part pictured, every wire shown, a test after every step.</p>
<div class="coverart">{hero_img()}</div>
<div class="covermeta"><div><b>Ahmed Mahram Saeed Saeed Hadi</b><br>Final-year IoT project · UNISIRAJ</div>
<div style="text-align:right">Guide version 3.0 · October 2026<br>Matches the Raqib software 3.0 · parts ≈ RM {total}</div></div>
</section>""")
    # ---------------------------------------------------------------- contents
    H.append("""<section class="page toc"><h2>Inside this guide</h2>
<ol class="tocl">
<li><b>How the robot works</b> - the body, the brain and what each part does</li>
<li><b>Shopping list</b> - every part, how many, why, and an estimated price</li>
<li><b>Meet the parts</b> - a picture of each part and the pins you will use</li>
<li><b>Safety first</b> - batteries, 3.3 V pins and moving wheels</li>
<li><b>The pin map</b> - the 8 XIAO pins the robot uses</li>
<li><b>Build it in 11 steps</b> - from the firmware to the first patrol, with a test after each step</li>
<li><b>Troubleshooting</b> - what to do when something does not answer</li>
<li><b>Final checklist</b> - before the first demo</li>
</ol>
<div class="note"><b>The golden rule:</b> wire one part, test it, then add the next. The robot has its own test page
(<code>http://raqib.local</code>) showing the camera and every sensor live, so you can test each step with just a phone.</div>
<div class="note"><b>Wire colours used in every diagram</b><div class="legend">""" + legend + """</div>
Use the same colours for your real jumper wires where you can: it makes mistakes easy to spot.</div>
<div class="note"><b>Try it before you buy:</b> <code>start_esp32_emulator.bat</code> runs a pretend ESP32 robot on your PC,
and the app's <i>Try the demo robot</i> works with no PC at all. The Wiring Bench lets you wire the XIAO virtually.</div>
</section>""")
    # ---------------------------------------------------------------- 1 overview
    H.append(f"""<section class="page"><h2 class="sec"><span>1</span>How the robot works</h2>
<p>The robot is split in two. The <b>body</b> is one thumb-size board, the <b>XIAO ESP32S3 Sense</b>: it drives the two motors,
reads the sensors and sends its camera picture and microphone sound over Wi-Fi. The <b>brain</b> is your laptop: it runs the
Raqib server, the AI and the robot program that plans routes, checks photos and writes reports. The phone app talks to the brain.</p>
{figure(F.fig_system(), "Figure 1 - phone, PC (brain) and robot (body) on the same Wi-Fi.")}
<div class="two"><div><h3>What it does</h3>
<p><b>Energy and comfort patrol:</b> visits each room, measures temperature, humidity and pressure, and uses the camera + AI to
spot lights or the AC left on in an empty room.</p>
<p><b>Live video and manual drive</b> from the phone.</p>
<p><b>Exam monitor:</b> patrols the hall, spots phones and talking, and sends you a photo, so you can go over.</p></div>
<div><h3>Why it is easy and reliable</h3>
<p>Only 8 signal wires. Everything is 3.3 V, so no resistors and no voltage to adjust. Two batteries: motors can never reset the
ESP32. The robot stops by itself when Wi-Fi drops (0.6 s) or something is closer than 15 cm, and it turns using its own gyro.</p></div></div>
<div class="note"><b>Honest limits:</b> the PC must be on (the robot has no brain of its own); the microphone hears all round, so
it hears talking but cannot point at the talker; there is no speaker, so warnings go to your phone; and the camera sits low
(about 15 cm), so it sees faces and laps, not papers lying on desks.</div>
</section>""")
    # ---------------------------------------------------------------- 2 shopping
    H.append(f"""<section class="page"><h2 class="sec"><span>2</span>Shopping list</h2>
<p>Prices are <b>estimates in Malaysian ringgit</b> from typical Malaysian electronics shops (Cytron, Shopee / Lazada sellers)
in 2026. Check current prices and stock before you buy.</p>
{bom}
<h3>Tools (not counted in the RM {total})</h3>{tools_table()}
<div class="note"><b>Buying tips</b><ul>
<li><b>XIAO ESP32S3 <u>Sense</u></b>: the plain XIAO ESP32S3 has no camera or microphone. Some shops sell it with the header pins already soldered.</li>
<li><b>HC-SR04P</b> (or RCWL-1601) works on 3.3 V. The ordinary HC-SR04 is a 5 V part: do not use it here.</li>
<li><b>18650 cells:</b> buy known brands from a trusted seller. Real cells are 2500-3500 mAh.</li>
<li><b>USB-C cable:</b> some cheap cables only charge. If the PC does not see the XIAO, try another cable.</li>
</ul></div>
</section>""")
    # ---------------------------------------------------------------- 3 parts
    H.append(f"""<section class="page"><h2 class="sec"><span>3</span>Meet the parts</h2>
<p>What each part looks like, what it does, which pins you will use and one tip. Your boards may differ slightly in colour or
pin order: always read the labels printed on the board.</p>
{cards_html()}</section>""")
    # ---------------------------------------------------------------- 4 safety
    H.append("""<section class="page"><h2 class="sec"><span>4</span>Safety first</h2>
<div class="warn"><b>Lithium batteries store a lot of energy.</b><ul>
<li>Never short the + and − of a cell or pack. Check polarity three times before inserting a cell.</li>
<li>Charge only with a proper Li-ion charger, never unattended, on a non-flammable surface.</li>
<li>Switch the motor battery off before changing any wire.</li></ul></div>
<div class="warn"><b>Protect the XIAO.</b><ul>
<li>Its pins are <b>3.3 V only</b>. Never connect the motor battery, or a 5 V signal, to any XIAO pin.</li>
<li>The motor battery goes to the DRV8833 <b>VM</b> and <b>GND</b> only. At most 2 cells (8.4 V): the DRV8833 allows 10.8 V.</li>
<li>Press the Sense board on and click the camera ribbon in <b>before</b> plugging in USB.</li></ul></div>
<div class="warn"><b>Moving parts.</b><ul>
<li>Test motors with the robot on a box, <b>wheels in the air</b>.</li>
<li>Keep fingers and hair away from the wheels.</li></ul></div>
<div class="note"><b>Built-in safety:</b> the ESP32 stops the motors by itself 0.6 s after the PC stops talking to it, and it
refuses to drive forward when the distance sensor sees something closer than 15 cm (or when the sensor is not answering).
Turning and reversing are still allowed, so the robot can get itself out.</div>
</section>""")
    # ---------------------------------------------------------------- 5 pin map
    H.append(f"""<section class="page"><h2 class="sec"><span>5</span>The pin map</h2>
<p>The robot uses 8 of the XIAO's 11 signal pins, plus 3V3 and GND. These pins are fixed in the firmware, the Wiring Bench
and the PC program: wire them exactly like this.</p>
{figure(F.fig_xiao_map(), "Figure 2 - every XIAO pin and where it goes.")}
<table class="bom"><thead><tr><th>XIAO pin</th><th>Goes to</th><th>Why</th></tr></thead><tbody>
<tr><td><b>D0, D1</b></td><td>DRV8833 AIN1, AIN2</td><td class="why">Left motor: forward / reverse (PWM)</td></tr>
<tr><td><b>D2, D3</b></td><td>DRV8833 BIN1, BIN2</td><td class="why">Right motor: forward / reverse (PWM)</td></tr>
<tr><td><b>D4, D5</b></td><td>SDA, SCL of the MPU6050 and the AHT20 + BMP280</td><td class="why">I²C bus shared by both boards</td></tr>
<tr><td><b>D6, D7</b></td><td>HC-SR04P TRIG, ECHO</td><td class="why">Distance sensor</td></tr>
<tr><td><b>3V3, GND</b></td><td>Breadboard + and − rails</td><td class="why">Power for all sensors; GND joins the motor side too</td></tr>
</tbody></table>
</section>""")
    # ---------------------------------------------------------------- 6 steps
    H.append('<section class="page"><h2 class="sec"><span>6</span>Build it in 11 steps</h2><p>Each step lists what you need, '
             'what to do, a picture, and a check. Do them in order.</p>'
             + figure(F.fig_layout_top(), "Where everything goes on the robot.")
             + figure(F.fig_layout_side(), "Side view.") + '</section>')
    H.append(step(1, "Get the PC (the brain) ready", "your laptop with the Raqib project folder",
                  """<ol>
<li>If you have not yet: double-click <code>setup_windows.bat</code> in the project folder (installs everything once).</li>
<li>Double-click <code>allow_robot_connections.bat</code> once and click <b>Yes</b>: it lets the phone reach the server and lets
the PC hear the robot's "here I am" message.</li>
<li>Try it with no parts: double-click <code>start_esp32_emulator.bat</code>. A pretend ESP32 robot drives in the app at
<code>http://localhost:8000</code>. Close its windows when done.</li></ol>"""
                  + check(["The app opens at http://localhost:8000 and the pretend robot moves", "More → Robot health: all green"])))
    H.append(step(2, "Put the firmware on the XIAO", "XIAO ESP32S3 Sense, its Sense board and camera, USB-C data cable, Chrome or Edge",
                  """<ol>
<li>Press the <b>Sense board</b> onto the XIAO's back until it clicks. Lift the little latch of the camera socket on the Sense
board, push the camera ribbon in, close the latch. Click on the small Wi-Fi antenna if your kit has one.</li>
<li>Plug the XIAO into the PC with the USB-C cable.</li>
<li>In Chrome or Edge open <b>https://espressif.github.io/esptool-js/</b>. Click <b>Connect</b> and pick the XIAO's port
(often "USB JTAG/serial debug unit").</li>
<li>Flash Address <b>0x0</b>, choose the file <code>esp32\\raqib_esp32_xiao.bin</code> from the project folder, click
<b>Program</b>. When it finishes, unplug and replug the XIAO.</li>
<li>Not connecting? Hold the tiny <b>B</b> (boot) button while plugging the USB in, then try again.</li></ol>
<p>Prefer Arduino IDE? Open <code>esp32\\raqib_esp32\\raqib_esp32.ino</code>, board <b>XIAO_ESP32S3</b>,
Tools → PSRAM → <b>OPI PSRAM</b>, Upload. See <code>esp32\\README.md</code>.</p>"""
                  + check(["The orange LED on the XIAO blinks slowly: it made its own Wi-Fi \"Raqib-Robot\""])))
    H.append(step(3, "Connect the robot to your Wi-Fi", "the XIAO on USB (PC or power bank), your phone",
                  """<ol>
<li>Turn on your <b>phone's hotspot</b> (2.4 GHz; on iPhone turn on "Maximise Compatibility").</li>
<li>With the phone or the PC, join the Wi-Fi <b>Raqib-Robot</b>, password <code>raqib1234</code>.</li>
<li>Open <b>http://192.168.4.1</b>. Under <b>Wi-Fi</b>, type your hotspot's name and password, press <b>Save</b>.</li>
<li>The robot restarts and joins your hotspot. Its LED now stays on (it blinks off briefly while parts are still missing).</li>
<li>Join the hotspot with the PC too, and open <b>http://raqib.local</b>: the robot's test page with its camera picture.</li></ol>
<p>Not working? The robot remakes the Raqib-Robot network after 20 s if it cannot join: check the name and password.
<code>raqib.local</code> not opening? Use the robot's address instead: your phone's hotspot screen lists it under connected devices.</p>"""
                  + check(["http://raqib.local shows the camera picture, updating every second",
                           "The status shows \"cam_ok\": true and \"mic_ok\": true"])))
    H.append(step(4, "Build the chassis", "2WD chassis kit, battery holder, screwdriver",
                  """<ol>
<li>Fix the two TT motors under the deck at the front with the kit's brackets, wires towards the middle.</li>
<li>Push the wheels on; fix the caster wheel at the back.</li>
<li>Fix the 2 x 18650 holder under the deck (foam tape or screws) with its switch reachable. No cells in it yet.</li>
<li>Stick the half breadboard on the deck behind the motors, long side across the robot.</li></ol>"""
                  + check(["Both wheels turn freely by hand", "The robot stands level on its two wheels and the caster"])))
    H.append(step(5, "Mount the XIAO and make the rails", "XIAO, bracket, foam tape, jumper wires (F-M)",
                  """<ol>
<li>Solder the XIAO's header pins if they are not soldered yet (14 joints; push the pins into the breadboard to hold them straight).</li>
<li>Stand the XIAO upright at the front on a small bracket (folded card or plastic + foam tape): <b>USB-C up, camera looking forward</b>
over the front edge.</li>
<li>Jumper from the XIAO <b>3V3</b> pin to the breadboard <b>+</b> rail, and from <b>GND</b> to the <b>−</b> rail.</li>
<li>Join the top and bottom rails with two short wires (+ to +, − to −).</li></ol>"""
                  + figure(F.wiring(groups=()), "The parts in place before wiring: XIAO, breadboard rails, DRV8833 and sensors.")
                  + check(["The camera looks straight ahead, not at the floor", "3V3 is on the + rail, GND on the − rail, not swapped"])))
    H.append(step(6, "Power: two batteries and one shared ground", "power bank, 2 x 18650 cells, DRV8833, jumper wires",
                  """<ol>
<li>Push the DRV8833 into the breadboard.</li>
<li>Battery holder <b>red</b> → DRV8833 <b>VM</b>; <b>black</b> → DRV8833 <b>GND</b>.</li>
<li>A second wire from DRV8833 <b>GND</b> → breadboard <b>− rail</b>. This is the <b>common ground</b>: without it the motors do nothing.</li>
<li>If the DRV8833 has an <b>EEP</b> (or SLP) pin: wire it to the <b>+ rail</b> (3V3).</li>
<li>Power bank → USB-C cable → XIAO. Insert the cells (check polarity!), switch the holder on.</li></ol>"""
                  + figure(F.wiring(groups=("power",)), "Figure 3 - power: the power bank feeds the XIAO, the 18650 pack feeds the motors, one shared ground.")
                  + check(["The XIAO runs from the power bank (test page opens)", "The battery's + goes only to VM, nowhere else",
                           "DRV8833 GND is joined to the breadboard − rail"])))
    H.append(step(7, "Motors", "jumper wires (M-M)",
                  """<ol>
<li>XIAO <b>D0 → AIN1</b>, <b>D1 → AIN2</b> (left motor); <b>D2 → BIN1</b>, <b>D3 → BIN2</b> (right motor).</li>
<li>Left motor's two wires → <b>AOUT1</b> and <b>AOUT2</b>; right motor's two wires → <b>BOUT1</b> and <b>BOUT2</b>.</li>
<li>Robot on a box, wheels in the air. On the test page (<code>http://raqib.local</code>) hold <b>◀</b>: the robot turns left.</li>
<li>A wheel turns backwards? Swap that motor's two wires. Left and right mixed up? Swap the motors between AOUT and BOUT.</li></ol>"""
                  + figure(F.wiring(groups=("power", "motors")), "Figure 4 - motor wiring.")
                  + check(["◀ turns the robot left, ▶ right, ▼ backwards", "The wheels stop within a second of releasing the button",
                           "▲ does nothing yet? Correct: the distance sensor is not wired, so forward is refused"])))
    H.append(step(8, "Sensors", "MPU6050, AHT20 + BMP280, HC-SR04P, jumper wires",
                  """<ol>
<li>Push the MPU6050 and the AHT20 + BMP280 into the breadboard (MPU6050 flat, near the middle).</li>
<li>Each: <b>VCC/VIN → + rail</b>, <b>GND → − rail</b>, <b>SDA → XIAO D4</b>, <b>SCL → XIAO D5</b>.</li>
<li>Mount the HC-SR04P at the front edge, below the camera, looking straight ahead.</li>
<li>HC-SR04P <b>VCC → + rail</b> (3.3 V!), <b>GND → − rail</b>, <b>TRIG → D6</b>, <b>ECHO → D7</b>.</li>
<li>Switch everything off and on again, and keep the robot still for 2 s (the gyro learns its offset).</li></ol>"""
                  + figure(F.wiring(groups=("power", "motors", "sensors")), "Figure 5 - the whole robot: sensors on the rails, I²C on D4/D5, distance sensor on D6/D7.")
                  + check(["Test page: imu_ok, aht_ok, bmp_ok and us_ok are all true", "dist_cm follows your hand in front of the sensor",
                           "yaw changes when you turn the robot by hand; temperature and humidity look right",
                           "▲ now drives forward, and stops by itself in front of your hand",
                           "The orange LED stays on steadily (all parts found)"])))
    H.append(step(9, "Connect the brain", "the PC on the same hotspot, the phone with the Raqib app",
                  """<ol>
<li>PC and phone on the same hotspot as the robot.</li>
<li>Double-click <code>start_my_robot.bat</code>. It starts the server and the robot program, which finds the robot by itself.</li>
<li>Phone: open the Raqib app → <b>Find automatically</b> → sign in. <b>More → AI settings</b>: paste your Gemini key once.</li>
<li><b>More → Robot health</b>: every part green.</li></ol>
<p>Robot not found? Read its address on the test page (for example 192.168.43.57) and write it in <code>edge\\config.yaml</code>
under <code>hardware:</code> → <code>esp32_host: 192.168.43.57</code>.</p>"""
                  + check(["Robot health: all green; Speaker says \"no speaker: the phone app speaks\"", "Drive tab: live video and the arrows work",
                           "STOP in the app stops the robot at once"])))
    H.append(step(10, "Calibrate the driving (10 minutes, once)", "the robot, a tape measure, 3 m of free floor",
                  """<p>The robot measures distance from motor power × time, so it learns how fast <i>your</i> motors are. Close the
"Robot brain" window first (two programs must not drive at once). In the project folder's <code>edge</code> folder:</p>"""
                  + cmd("..\\.venv\\Scripts\\python -m hwtest.test_motors --deadband     # wheels in the air\n"
                        "..\\.venv\\Scripts\\python -m hwtest.test_motors --calibrate    # on the floor, measure with the tape\n"
                        "..\\.venv\\Scripts\\python -m hwtest.test_motors --straight 2   # check: should end 1.8-2.2 m")
                  + "<p>Write the numbers each one prints (<code>motor_deadband</code>, <code>min_power</code>, <code>max_speed_mps</code>) "
                    "into <code>edge\\config.yaml</code> under <code>motion:</code>. Turns need no calibration: the ESP32 turns with its own gyro.</p>"
                  + check(["--straight 2 ends between 1.8 m and 2.2 m", "It drifts sideways less than 20 cm"])))
    H.append(step(11, "Everything together", "the finished robot",
                  "<ol><li>Start <code>start_my_robot.bat</code> again. Tidy the wires with zip ties; nothing near the wheels.</li>"
                  "<li>Drive to each room, read the position on the Home screen, and write them under <code>zones:</code> in "
                  "<code>edge\\config.local.yaml</code> (your building's rooms).</li>"
                  "<li>Try it: \"Check the aircon in all rooms\", and More → Exam monitor in the exam room.</li></ol>"
                  + check(["Every part green in Robot health", "A hand 30 cm in front of the moving robot stops it before 15 cm",
                           "Switching the PC's Wi-Fi off stops the robot within a second",
                           "\"Turn left 90\" ends within a few degrees of 90"])))
    # ---------------------------------------------------------------- 7 troubleshooting
    trouble = [
        ("Esptool page cannot connect", "Charge-only cable, or the XIAO is not in download mode", "Another USB-C cable; hold B while plugging in"),
        ("Camera picture missing (cam_ok false)", "Sense board not clicked on, ribbon latch open, or flashed without PSRAM",
         "Re-seat the Sense board and the ribbon; use the .bin file (it has PSRAM on)"),
        ("Robot never joins the hotspot", "5 GHz hotspot or wrong password", "2.4 GHz / Maximise Compatibility; type it again on 192.168.4.1"),
        ("raqib.local does not open", "Some phones and PCs do not support .local names", "Use the IP address (hotspot's connected devices)"),
        ("PC program says 'robot not found'", "Different Wi-Fi, or Windows Firewall", "Same hotspot; run allow_robot_connections.bat; set esp32_host"),
        ("Wheels do nothing", "No common ground, battery off, or EEP pin low", "DRV8833 GND to − rail; switch on; EEP to 3V3"),
        ("Forward is refused, turning works", "Distance sensor not answering (us_ok false) or something in front",
         "HC-SR04P on 3V3, TRIG D6, ECHO D7; try the spare sensor"),
        ("One wheel turns backwards", "Motor wires reversed", "Swap that motor's two wires (or set invert: true in config.yaml)"),
        ("imu_ok or aht_ok false", "I²C wires", "VCC on the + rail, GND on −, SDA on D4, SCL on D5 (not swapped)"),
        ("The robot drives too far or too short", "Not calibrated on this floor, or weak cells", "Charge the cells and redo step 10"),
        ("Robot stops every few seconds", "Weak Wi-Fi: the 0.6 s safety stop", "Keep the PC near the robot; use the phone hotspot"),
        ("AI does not answer", "No internet on the PC", "The PC needs internet for the AI: the hotspot gives it"),
    ]
    rows = "".join(f"<tr><td><b>{escape(a)}</b></td><td>{escape(b)}</td><td>{escape(c)}</td></tr>" for a, b, c in trouble)
    H.append(f"""<section class="page"><h2 class="sec"><span>7</span>Troubleshooting</h2>
<table class="bom trouble"><thead><tr><th>What you see</th><th>Usual cause</th><th>Fix</th></tr></thead><tbody>{rows}</tbody></table>
<div class="note">The robot's own test page (<code>http://raqib.local</code>) shows every sensor live, and the app's
<b>Robot health</b> screen shows every part with a hint when it is red.</div>
</section>
<section class="page"><h2 class="sec"><span>8</span>Final checklist before a demo</h2>
<div class="check big"><ul>
<li>☐ Power bank full and motor cells charged; a spare charged pair in the bag</li>
<li>☐ Phone hotspot on; PC and robot joined to it; <code>start_my_robot.bat</code> running</li>
<li>☐ Every part green in Robot health</li>
<li>☐ STOP in the app stops the robot; Reset is needed to move again</li>
<li>☐ A hand 30 cm in front of the moving robot stops it before 15 cm</li>
<li>☐ Driving calibrated on this floor (step 10)</li>
<li>☐ The robot starts at the Home spot, facing the same direction as when you measured the rooms</li>
<li>☐ AI key entered in More → AI settings; "Test" says it works</li>
</ul></div>
<h3>Upgrades later</h3>
{upgrades_table()}
<p class="end">Built it? Run the final checklist, then show it off.</p>
</section>""")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Raqib Robot Build Guide</title><style>{css}</style></head><body>{''.join(H)}</body></html>"


def main():
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    js = HERE / "_pdf.js"
    js.write_text(f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://{OUT_HTML}'); await p.waitForTimeout(500);
  await p.pdf({{ path: '{OUT_PDF}', format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-family:Inter,sans-serif;font-size:8px;color:#8a949c;width:100%;padding:0 14mm;display:flex;justify-content:space-between"><span>Raqib · ESP32 robot build guide</span><span class="pageNumber"></span></div>',
    margin: {{ top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' }} }});
  await b.close(); }})();""")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js)], check=True, env={**__import__("os").environ, "NODE_PATH": npm_root})
    js.unlink()
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    main()
