"""Builds docs/Raqib_Robot_Build_Guide.pdf: shopping list, every part pictured, wiring diagrams, assembly steps.

    python docs/build_guide/build.py        (needs Playwright + Chromium for the HTML -> PDF step)
"""
from __future__ import annotations

import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diagrams as D  # noqa: E402
from draw import W  # noqa: E402

OUT_HTML = HERE / "guide.html"
OUT_PDF = HERE.parent / "Raqib_Robot_Build_Guide.pdf"

# ----------------------------------------------------------------------------------------------- shopping list
BOM = [
    ("The brain", [
        ("Raspberry Pi 4 Model B, 2 GB", 1, 240, "Runs the robot program and its own server. 2 GB is enough: the AI runs in the cloud"),
        ("microSD card 16 GB, A1 / Class 10", 1, 12, "Holds Raspberry Pi OS and the robot software"),
        ("Aluminium heatsink set for the Pi 4", 1, 4, "Keeps the Pi from slowing down when it gets warm"),
    ]),
    ("Power (one battery for everything)", [
        ("18650 Li-ion cells, flat top, 2500-3000 mAh", 2, 15, "Known brands only. Avoid fake '9900 mAh' cells"),
        ("2 x 18650 battery holder with on/off switch and leads", 1, 6, "7.4 V pack; its switch is the robot's power switch"),
        ("XL4015 5 A step-down converter (adjustable)", 1, 9, "Makes a steady 5.1 V for the Pi from the battery"),
        ("USB-A to USB-C cable, 3 A (you cut the A end off)", 1, 5, "XL4015 output → Pi power input"),
        ("1000 µF 16 V electrolytic capacitor", 1, 1, "Stops motor starts from resetting the Pi"),
        ("2-slot USB 18650 charger", 1, 12, "Charges the two cells"),
    ]),
    ("Moving", [
        ("4WD smart car chassis kit: 2 acrylic decks, 4 TT motors (3-6 V), 4 wheels, brass standoffs, screws", 1, 40,
         "The body: four driven wheels. Choose a kit whose motors have a shaft on both sides (for the encoder discs)"),
        ("L298N dual H-bridge motor driver", 1, 9, "Turns the Pi's small signals into motor power"),
        ("Speed encoder module (LM393 slot sensor) + 20-slot disc", 2, 4, "Counts wheel turns: 'go forward 2 m' stops at 2 m"),
    ]),
    ("Sensing", [
        ("HC-SR04 ultrasonic distance sensor", 3, 4, "Left, centre, right: stops before obstacles and steers round them"),
        ("MPU6050 motion sensor (GY-521 board)", 1, 8, "Knows how far the robot has turned"),
        ("AHT20 + BMP280 combo board", 1, 10, "Temperature, humidity and air pressure"),
        ("MQ-135 gas sensor module", 1, 8, "CO2 / gas level"),
        ("ADS1115 16-bit ADC board", 1, 12, "Reads the gas sensor and the battery voltage (the Pi has no analog input)"),
    ]),
    ("Camera and sound", [
        ("USB webcam 720p with built-in microphone", 1, 30, "Photos, live video and hearing in one part"),
        ("PAM8403 amplifier board", 1, 4, "Makes the voice loud enough"),
        ("Speaker 3 W 4 Ω, about 40 mm", 1, 5, "The robot's voice"),
        ("3.5 mm male audio cable (you will cut one end)", 1, 3, "Pi audio jack → amplifier"),
    ]),
    ("Wiring and mounting", [
        ("Resistors: 1 kΩ x 3, 2 kΩ x 3, 4.7 kΩ x 1, 10 kΩ x 2, 20 kΩ x 1", 1, 3, "Voltage dividers: protect the Pi and measure the battery"),
        ("Perfboard / stripboard about 7 x 9 cm", 1, 3, "Your 'hub board'"),
        ("Jumper wires: F-F and M-F, 40 of each", 1, 8, "Most connections plug in, no soldering"),
        ("Male + female pin header strips", 1, 3, "Plug-in points on the hub board"),
        ("22 AWG wire, red + black, 1 m each", 1, 5, "Motor and battery wiring"),
        ("M2.5 screws + nylon washers (the kit already has the deck standoffs)", 1, 4, "Raspberry Pi and board mounting"),
        ("Zip ties, double-sided foam tape, heat-shrink", 1, 4, "Tidy, safe, nothing rattles loose"),
    ]),
]
TOOLS = [
    ("Soldering iron with solder and stand", 50, "Motor leads, hub board, header pins"),
    ("Digital multimeter", 40, "Set the XL4015 to 5.1 V and check every voltage BEFORE connecting the Pi"),
    ("Small screwdriver set (Phillips + flat)", 15, "Screw terminals and chassis"),
    ("Wire stripper / side cutter", 15, "Clean wire ends"),
    ("Hot glue gun", 20, "Fix cables and the encoder sensors"),
]
UPGRADES = [
    ("Look around without turning", "PCA9685 + 2 SG90 servos + pan/tilt bracket", "≈ 40",
     "PCA9685 on the I²C rails, its ch0/ch1 → ENA/ENB (instead of pins 33/35), servos on ch14/ch15, webcam on the bracket."),
    ("Sharper photos", "Pi Camera OV5647 (≈ RM 35) or v2 (≈ RM 120) + long ribbon", "35-128",
     "Ribbon into the CAMERA port. The robot tries the ribbon camera first, then the webcam."),
    ("Air quality (VOC)", "BME680 board", "≈ 45", "Replaces the AHT20 on the same 4 wires."),
    ("Longer run time", "UPS module 3S + 3 more 18650 cells", "≈ 175",
     "Pi on its own battery; the motors keep the 2 x 18650 pack. Its battery gauge joins the I²C rails."),
    ("Smoother video", "Raspberry Pi 4, 4 GB instead of 2 GB", "≈ 50", "Same wiring."),
]

# ----------------------------------------------------------------------------------------------- parts
CARDS = [
    ("pi", "Raspberry Pi 4", "The robot's computer: drives, senses, runs its own server for the phone.",
     "40-pin GPIO header (top edge) · USB-C power · USB ports for the webcam · 3.5 mm audio jack for the speaker",
     "2 GB is enough. Put the microSD card in the slot underneath on the short edge."),
    ("bat2", "Battery: 2 x 18650", "The only battery: motors straight from it, the Pi through the XL4015.",
     "Red + → L298N +12V and XL4015 IN+ · black − → L298N GND and XL4015 IN−",
     "7.4 V nominal, 8.4 V full, about 6.6 V empty. Its switch turns the whole robot on and off."),
    ("buck", "XL4015 step-down converter", "Turns the battery's 7-8 V into a steady 5.1 V for the Pi.",
     "IN+ / IN− from the battery (1000 µF across them) · OUT+ / OUT− → the cut USB cable → Pi",
     "Turn the brass screw until OUT reads 5.1 V, BEFORE the Pi is plugged in."),
    ("chassis", "4WD chassis kit", "Two acrylic decks, four TT gear motors, four wheels and brass standoffs.",
     "4 motors under the bottom deck · second deck on the standoffs",
     "Check the motors have a shaft on both sides for the encoder discs."),
    ("motor", "TT gear motor + encoder disc", "3-6 V geared motor; the 20-slot disc tells how far it turned.",
     "2 solder tabs per motor (red / black wires)",
     "Solder wires before you mount the motors; it is hard afterwards."),
    ("l298n", "L298N motor driver", "Switches battery power to the motors forwards or backwards.",
     "+12V / GND from the battery · OUT1/OUT2 left motor pair · OUT3/OUT4 right motor pair · IN1-IN4 and ENA/ENB from the Pi",
     "Remove the ENA and ENB jumpers. Keep the 5V-EN jumper."),
    ("hc", "HC-SR04 ultrasonic", "Measures distance with sound, 2 cm to 4 m.",
     "VCC 5V · Trig (from Pi) · Echo (5 V out! needs a divider) · Gnd",
     "Buy 3 + a spare if you can; they sometimes arrive dead."),
    ("enc", "Speed encoder (slot sensor)", "Gives one pulse each time a slot of the disc passes.",
     "VCC 3.3V · GND · D0 (digital, to the Pi) · A0 (not used)",
     "The disc must spin inside the slot without touching it."),
    ("imu", "MPU6050 (GY-521)", "Gyroscope + accelerometer: the robot's sense of turning.",
     "VCC · GND · SCL · SDA (the others are not used)",
     "Mount it flat, near the middle of the chassis, with foam tape."),
    ("aht", "AHT20 + BMP280", "Temperature and humidity (AHT20) plus air pressure (BMP280) on one board.",
     "VIN · GND · SCL · SDA",
     "Keep it away from the Pi and the MQ-135: they are warm."),
    ("mq", "MQ-135 gas sensor", "Heated sensor whose voltage rises with CO2 and gases.",
     "VCC 5V · GND · AO (analog, via divider) · DO (not used)",
     "Burn it in for 24-48 h the first time. It gets hot: no plastic touching it."),
    ("ads", "ADS1115 ADC", "Turns the gas sensor and battery voltages into numbers for the Pi.",
     "VDD 3.3V · GND · SCL · SDA · ADDR → GND · A0 = gas · A1 = battery",
     "Powered from 3.3 V so it is safe on the Pi's I²C bus."),
    ("webcam", "USB webcam with microphone", "The robot's eyes and ears: photos, live video and sound.",
     "Any USB port (a blue USB 3 port is best)",
     "Choose one sold as 'plug and play / UVC' with a built-in microphone."),
    ("pam", "PAM8403 amplifier", "Small 3 W amplifier for the speaker.", "5V/GND power · L G R input from the Pi's audio jack · L+ L− output",
     "Use only the left channel (L+ / L−)."),
    ("spk", "Speaker 3 W 4 Ω", "The robot's voice.", "2 wires to L+ and L−", "Face it outwards at the back of the top deck."),
    ("res", "Resistors", "Voltage dividers: protect the Pi and measure the battery.", "No polarity: either way round",
     "No 2 kΩ? Two 1 kΩ in series. No 4.7 kΩ? Use 5.1 kΩ and set battery_divider_gain: 2.96."),
    ("wires", "Jumper wires", "Plug-in connections.", "F = socket (fits on a pin) · M = pin", "Use colours: red 5 V, orange 3.3 V, black GND."),
    ("hub", "Hub board (you make it)", "One place where power, the I²C bus and all dividers meet.",
     "5V · 3V3 · GND · SDA · SCL rails + 5 dividers", "Step 5 shows how to build it."),
    ("standoff", "Standoffs and screws", "Hold the second deck and the boards.", "M3 for the deck, M2.5 for the Pi", "Nylon washers stop shorts under boards."),
    ("tools", "Tools", "What you need on the desk (borrow them from the lab).", "Soldering iron, multimeter, screwdrivers, stripper, hot glue", "Measure, then connect. Always."),
]


def bom_table() -> str:
    rows, total, n = [], 0, 0
    for group, items in BOM:
        rows.append(f'<tr class="grp"><td colspan="5">{escape(group)}</td></tr>')
        for name, qty, price, why in items:
            n += 1
            total += qty * price
            rows.append(f"<tr><td class='num'>{n}</td><td><b>{escape(name)}</b><div class='why'>{escape(why)}</div></td>"
                        f"<td class='c'>{qty}</td><td class='r'>{price}</td><td class='r'>{qty * price}</td></tr>")
    rows.append(f"<tr class='tot'><td></td><td>Total for the robot (estimate, under RM 500)</td><td></td><td></td><td class='r'>≈ {total}</td></tr>")
    return ("<table class='bom'><thead><tr><th>#</th><th>Part</th><th>Qty</th><th>RM each</th><th>RM</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>"), total


def tools_table() -> str:
    rows = "".join(f"<tr><td><b>{escape(t)}</b><div class='why'>{escape(w)}</div></td><td class='r'>{p}</td></tr>" for t, p, w in TOOLS)
    return f"<table class='bom tools'><thead><tr><th>Tool</th><th>RM</th></tr></thead><tbody>{rows}</tbody></table>"


def cards_html() -> str:
    out = []
    for key, title, what, pins, tip in CARDS:
        out.append(f"""<div class="card"><div class="pic">{D.fig_component(key)}</div>
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


def build_html() -> str:
    bom, total = bom_table()
    assert total <= 500, total
    legend = "".join(f'<span><i style="background:{c}"></i>{t}</span>' for c, t in (
        (W["5v"], "5 V"), (W["3v3"], "3.3 V"), (W["gnd"], "GND"), (W["sda"], "SDA"), (W["scl"], "SCL"),
        (W["bat"], "battery +"), (W["mot"], "motor"), (W["pwm"], "PWM"), (W["sig1"], "signal")))
    css = (HERE / "style.css").read_text()
    H = []
    # ---------------------------------------------------------------- cover
    H.append(f"""<section class="cover">
<div class="kicker">RAQIB · AI INSPECTION ROBOT · BUDGET EDITION</div>
<h1>Build the robot</h1>
<p class="sub">Under RM 500: what to buy, every part pictured and explained, how to wire each sensor, and how to put the robot together, step by step.</p>
<div class="coverart">{D.fig_cover_robot()}</div>
<div class="covermeta"><div><b>Ahmed Mahram Saeed Saeed Hadi</b><br>Final-year IoT project · UNISIRAJ</div>
<div style="text-align:right">Guide version 2.4 · October 2026<br>Matches the Raqib software 2.4 · parts ≈ RM {total}</div></div>
</section>""")
    # ---------------------------------------------------------------- contents
    H.append("""<section class="page toc"><h2>Inside this guide</h2>
<ol class="tocl">
<li><b>How the robot works</b> - the parts and how they talk to each other</li>
<li><b>Shopping list</b> - every part, how many, why, and an estimated price (under RM 500)</li>
<li><b>Meet the parts</b> - a picture of each part and the pins you will use</li>
<li><b>Safety first</b> - the battery, voltages and moving wheels</li>
<li><b>The pin map</b> - every Raspberry Pi pin the robot uses</li>
<li><b>Build it in 12 steps</b> - assembly and wiring, one part at a time, with a test after each</li>
<li><b>Troubleshooting</b> - what to do when something does not answer</li>
<li><b>Final checklist</b> - before the first demo</li>
<li><b>Upgrades later</b> - parts you can add when you have more budget</li>
</ol>
<div class="note"><b>The golden rule:</b> wire one part, test it, then add the next. When something does not work, you know it is the
part you just added. Every step ends with a check box list and a test command.</div>
<div class="note"><b>Wire colours used in every diagram</b><div class="legend">""" + legend + """</div>
Use the same colours for your real jumper wires where you can: it makes mistakes easy to spot.</div>
<div class="note"><b>Practise first, for free:</b> the Wokwi picture guide lets you wire most of these sensors in a browser
simulator, and the phone app's <i>Try the demo robot</i> button shows what the finished robot does.</div>
</section>""")
    # ---------------------------------------------------------------- 1 overview
    H.append(f"""<section class="page"><h2 class="sec"><span>1</span>How the robot works</h2>
<p>The Raspberry Pi 4 is the brain. It runs the robot program and also its own small server, so the phone app talks
straight to the robot over Wi-Fi: no laptop. One battery pack powers everything: the motors directly, the Pi through a
small 5 V converter. A hand-made <b>hub board</b> shares power and the I²C bus with the sensors, and each sensor group has one job.</p>
{figure(D.fig_overview(), "Figure 1 - the five groups of parts around the Raspberry Pi.")}
<div class="two"><div><h3>Two kinds of connection</h3>
<p><b>I²C bus</b> (2 wires, SDA + SCL): three boards share it, each with its own address -
ADS1115 0x48, MPU6050 0x68, AHT20 0x38 + BMP280 0x77.</p>
<p><b>GPIO pins</b>: one wire per signal - motor direction and speed, sonar trigger/echo and wheel encoders.</p></div>
<div><h3>Two voltages</h3>
<p><b>5 V</b> for the sonars, gas heater and amplifier.</p>
<p><b>3.3 V</b> for everything that talks to the Pi. A Pi pin must <b>never</b> see 5 V: the voltage
dividers on the hub board take care of the 5 V outputs (sonar Echo and MQ-135) and the battery voltage.</p></div></div>
<div class="note"><b>The camera does not move.</b> Instead of servos, the robot turns its whole body to look left or right
(the app's <i>Drive → Camera</i> pad works the same), and turns back before it drives on. This saves about RM 40.</div>
</section>""")
    # ---------------------------------------------------------------- 2 shopping
    H.append(f"""<section class="page"><h2 class="sec"><span>2</span>Shopping list</h2>
<p>Prices are <b>estimates in Malaysian ringgit</b> from typical Malaysian online electronics shops (Cytron, Techmakers,
Shopee / Lazada sellers) in 2026. Check current prices and stock before you buy; shop around and the total can drop further.</p>
{bom}
</section>
<section class="page"><h3>Tools (borrow them from the lab: not counted in the RM {total})</h3>{tools_table()}
<div class="note"><b>Buying tips</b><ul>
<li><b>Save more:</b> a used Raspberry Pi 4 (2 GB or 4 GB) often sells for RM 150-200. Ask your department too: many labs lend Pis to final-year students.</li>
<li><b>18650 cells:</b> buy known brands from a trusted seller. Real cells are 2500-3500 mAh; anything claiming
"9900 mAh" is fake and unsafe. Flat-top cells fit most holders.</li>
<li>Check the <b>chassis kit</b> photo: TT motors with a shaft on <b>both</b> sides, encoder discs included is a bonus.</li>
<li><b>Webcam:</b> any small UVC "plug and play" USB webcam with a built-in microphone works; the robot finds it by itself.</li>
<li>No 2 kΩ resistors? Two 1 kΩ in series make 2 kΩ.</li>
<li>Have a phone charger with a USB-C cable? Use it to power the Pi on your desk while you install the software.</li>
</ul></div>
<div class="note"><b>Budget:</b> about <b>RM {total:,}</b> for the robot. Nothing in the app is lost: the same software runs
this build and the bigger one, and finds by itself which parts you fitted. See <i>Upgrades later</i> at the end.</div>
</section>""")
    # ---------------------------------------------------------------- 3 parts
    H.append(f"""<section class="page"><h2 class="sec"><span>3</span>Meet the parts</h2>
<p>What each part looks like, what it does, which pins you will use and one tip. The pictures are drawings of the
common versions; your boards may differ slightly in colour or pin order, so always read the labels printed on the board.</p>
{cards_html()}</section>""")
    # ---------------------------------------------------------------- 4 safety
    H.append("""<section class="page"><h2 class="sec"><span>4</span>Safety first</h2>
<div class="warn"><b>Lithium batteries store a lot of energy.</b><ul>
<li>Never short the + and − of a cell or pack (no loose wires, no metal tools across terminals).</li>
<li>Check polarity three times before inserting a cell: + goes to the + mark.</li>
<li>Charge only with a proper Li-ion charger, never unattended, on a non-flammable surface.</li>
<li>Do not use cells with dents, torn wrapping or that get hot; recycle them.</li>
<li>Switch the battery off before changing any wire.</li></ul></div>
<div class="warn"><b>Protect the Raspberry Pi.</b><ul>
<li>Its GPIO pins are <b>3.3 V only</b>. 5 V on a GPIO pin damages it instantly, so every 5 V output goes through a divider.</li>
<li>Set the XL4015 to <b>5.1 V</b> with the multimeter <b>before</b> the Pi is plugged in: straight from the box it may give 12 V or more.</li>
<li>Never power motors from the Pi's pins.</li>
<li>Measure each power rail with the multimeter before plugging a board in.</li>
<li>Touch something metal before handling boards (static electricity).</li></ul></div>
<div class="warn"><b>Moving parts.</b><ul>
<li>Test motors with the robot on a box, <b>wheels in the air</b>.</li>
<li>Keep fingers and hair away from the wheels.</li>
<li>The MQ-135 heater, the XL4015 and the L298N heatsink get hot.</li></ul></div>
<h3>The two rules you will use most</h3>""" + figure(D.fig_divider_why(), "A voltage divider: 5 V × 2 kΩ / (1 kΩ + 2 kΩ) = 3.33 V, safe for the Pi.") + """
<p>And: <b>measure, then connect</b>. Put the multimeter on DC volts, black probe on GND, red probe on the rail.
5 V rail: 4.9-5.2 V. 3.3 V rail: 3.2-3.4 V. Battery: 6.6-8.4 V. XL4015 output: 5.0-5.2 V.</p></section>""")
    # ---------------------------------------------------------------- 5 pin map
    H.append(f"""<section class="page"><h2 class="sec"><span>5</span>The pin map</h2>
<p>Every Raspberry Pi pin the robot uses. Physical pin numbers (1-40) are what you count on the header; the GPIO names
are what the software uses (they are already set in <code>edge/config.yaml</code>).</p>
{figure(D.fig_pi_header(), "Figure 2 - Raspberry Pi 4 header, top view, USB ports pointing down the page.")}
<div class="note">Everything else does not touch the header: the webcam (camera + microphone) uses USB, the speaker amplifier
uses the 3.5 mm audio jack, and the gas sensor and battery voltage go through the ADS1115.</div>
</section>""")
    # ---------------------------------------------------------------- 6 steps
    H.append('<section class="page"><h2 class="sec"><span>6</span>Build it in 12 steps</h2><p>Each step lists what you need, '
             'what to do, a picture, and a check. Do them in order.</p></section>')
    H.append(step(1, "Prepare the Raspberry Pi (software first)", "Pi 4, microSD card, a USB-C phone charger, your PC",
                  """<ol>
<li>On the PC install <b>Raspberry Pi Imager</b>. Choose <i>Raspberry Pi 4</i> → <i>Raspberry Pi OS (64-bit)</i> (the Lite version is fine) → your microSD card.</li>
<li>In the settings (gear / "Edit settings"): hostname <code>robot01</code>, a username and password, <b>enable SSH</b>, and add a Wi-Fi.
Your <b>phone's hotspot</b> is the best one: the robot then has internet for the AI wherever you go.</li>
<li>Write the card, put it in the Pi (slot underneath), power the Pi from a USB-C phone charger. Wait 2 minutes.</li>
<li>On the PC, double-click <code>pack_robot_for_pi.bat</code> in the project folder. It makes <code>raqib-robot.zip</code>.</li>
<li>Copy the zip to the Pi (WinSCP to <code>robot01.local</code>, or a USB stick) and run on the Pi:</li></ol>"""
                  + cmd("unzip raqib-robot.zip -d ~/raqib\ncd ~/raqib && bash edge/scripts/install_pi.sh\nsudo reboot")
                  + "<p>The installer sets real-hardware mode, starts the robot and its server at every power-on, and makes the robot's own "
                    "Wi-Fi <b>Raqib-Robot</b> (password <code>raqib1234</code>) when no known Wi-Fi is around.</p>"
                  + check(["The Pi boots and you can log in (SSH or keyboard + screen)", "The installer ended with 'Done'",
                           "The phone app finds the robot ('Find automatically'); Robot health shows every part red: correct, nothing is wired yet"])))
    H.append(step(2, "Chassis, 4 motors and wheel encoders", "4WD chassis kit (4 TT motors, 4 wheels), 2 encoder discs + modules, wire, soldering iron",
                  """<ol>
<li><b>Solder</b> a red and a black 20 cm wire to the two tabs of each of the 4 motors. Twist each pair.</li>
<li>Fix the 4 motors under the bottom deck with the kit's brackets and long screws, all wires towards the middle.</li>
<li>Push an <b>encoder disc</b> onto the inner shaft of the two <b>front</b> motors (one per side is enough).</li>
<li>Mount each encoder module so its disc spins inside the slot without touching (small bracket, standoff or hot glue).</li>
<li>Push the 4 wheels onto the outer shafts.</li>
<li>Join the two motors of each side: red to red, black to black. Each side now has one red + one black wire.</li></ol>
<div class="note"><b>How 4 wheels steer (skid steering):</b> the two left wheels always turn together, and so do the two right
wheels. Both sides forward = straight; one side slower = curve; sides in opposite directions = turn on the spot (the wheels
skid a little sideways, which is normal). This is why one L298N is enough: one channel per side.</div>"""
                  + figure(D.fig_motor_mount(), "Four motors under the bottom deck; the encoder disc spins in the sensor's slot.")
                  + figure(D.fig_motor_pairs(), "Each side's two motors in parallel.")
                  + check(["All 4 wheels turn freely by hand", "Each encoder disc passes through its slot without rubbing",
                           "Left pair and right pair each have one red + one black wire to go to the L298N"])))
    H.append(step(3, "Power: one battery, the 5 V converter and the motor driver",
                  "battery holder + 2 cells, XL4015, 1000 µF capacitor, USB-A to USB-C cable, L298N, wire, multimeter",
                  """<ol>
<li>Cut the USB-A plug off the cable, about 15 cm from the plug. Strip the outer jacket: keep the <b>red</b> (+5 V) and <b>black</b> (GND)
wires, cut the thin green and white wires short and tape them.</li>
<li>Battery holder <b>red</b> → XL4015 <b>IN+</b> and L298N <b>+12V</b>; <b>black</b> → XL4015 <b>IN−</b> and L298N <b>GND</b>
(two wires under one screw is fine, or twist and solder a short splice).</li>
<li>Put the 1000 µF capacitor across XL4015 IN+ / IN−: the long leg to IN+, the striped side to IN−.</li>
<li>Insert the cells (<b>check polarity</b>), switch on. Measure XL4015 OUT+ to OUT− and turn its brass screw until it reads <b>5.1 V</b>.
(It may start at 12 V or more.) Switch off.</li>
<li>Cable red → XL4015 OUT+, black → OUT−. Fix the XL4015 and L298N on the bottom deck, the battery holder underneath.</li>
<li>Plug the USB-C end into the Pi and switch on: the Pi boots from the battery.</li></ol>"""
                  + figure(D.fig_power(), "Figure 3 - power wiring, and the battery divider used in step 10.")
                  + check(["Battery reads 7-8.4 V at the L298N +12V terminal", "XL4015 OUT reads 5.0-5.2 V",
                           "The Pi boots from the battery alone", "Charging: take the 2 cells out and put them in the USB charger"])))
    H.append(step(4, "Mount the boards", "the kit's top deck and standoffs, screws, foam tape",
                  "<p>Follow the layout: the battery low and central, warm parts (Pi, XL4015, MQ-135) away from the AHT20, sonars on the front edge, "
                  "the webcam at the front looking forward.</p>"
                  + figure(D.fig_layout_side(), "Side view: two decks on 35-40 mm standoffs.")
                  + figure(D.fig_layout_top(), "Top deck layout.")
                  + check(["Nothing touches the wheels", "No board's underside touches metal (use nylon washers)",
                           "The top deck can still come off to reach the L298N and the battery"])))
    H.append(step(5, "Build the hub board", "perfboard, resistors (3 x 1k, 3 x 2k, 2 x 10k, 1 x 20k, 1 x 4.7k), header strips, wire, soldering iron",
                  """<p>The hub board is the heart of the wiring: five rails that every sensor plugs into, and the five voltage dividers.</p><ol>
<li>Solder five long rails (bare wire or the board's strips): <b>5V, 3V3, GND, SDA, SCL</b>. Label them with a marker.</li>
<li>Solder a female header strip along each rail so jumper wires can plug in.</li>
<li>Solder the three sonar dividers (1 kΩ on top, 2 kΩ to GND), the MQ-135 divider (10 kΩ on top, 20 kΩ to GND) and the
battery divider (10 kΩ on top, 4.7 kΩ to GND). Put a header pin on the input and on the middle point of each.</li>
<li>Connect the rails to the Pi with F-F jumpers: pin 2 → 5V, pin 1 → 3V3, pin 6 → GND, pin 3 → SDA, pin 5 → SCL.</li></ol>"""
                  + figure(D.fig_hub(), "Figure 4 - the hub board: rails on top, dividers below.")
                  + check(["Multimeter, Pi on, nothing else plugged in: 5V rail ≈ 5 V, 3V3 rail ≈ 3.3 V",
                           "No two rails are shorted (continuity mode: no beep between rails)",
                           "Each sonar/MQ divider: 5 V on its input reads ≈ 3.3 V at its middle point",
                           "Battery divider: 8 V on its input reads ≈ 2.6 V at its middle point"])))
    H.append(step(6, "I²C boards: MPU6050, AHT20 + BMP280, ADS1115", "the three boards, F-F jumpers",
                  "<p>Every I²C board gets four wires from the hub rails: <b>3V3, GND, SDA, SCL</b>. ADS1115 ADDR → GND as well.</p>"
                  + figure(D.fig_i2c(), "Figure 5 - the I²C bus.")
                  + cmd("sudo systemctl stop inspection-robot     # stop the robot program while you test\ncd ~/raqib/edge && source .venv/bin/activate\npython -m hwtest.i2c_scan")
                  + check(["i2c_scan shows 0x38 + 0x77 or 0x76 (AHT20 + BMP280), 0x48 (ADS1115) and 0x68 (MPU6050)",
                           "It says motor speed will come from GPIO 13/19 (no PCA9685 found): correct for this build"])))
    H.append(step(7, "Motors: the L298N and the Pi", "L298N (already powered), M-F / F-F jumpers",
                  """<ol><li>Pull the <b>ENA</b> and <b>ENB</b> jumpers off the L298N. Leave the 5V-EN jumper.</li>
<li>Pi pins 11, 13, 15, 16 → L298N IN1, IN2, IN3, IN4 (direction).</li>
<li>Pi pin 33 → ENA, pin 35 → ENB (speed).</li>
<li>Left motor pair → OUT1/OUT2, right motor pair → OUT3/OUT4.</li>
<li>L298N GND → Pi pin 9 (a short signal ground).</li></ol>"""
                  + figure(D.fig_motors(), "Figure 6 - motor wiring.")
                  + cmd("python -m hwtest.test_motors          # robot on a box, wheels in the air!")
                  + check(["Each side turns forwards when told 'forward'. Wrong way: swap that pair's OUT wires (or invert: true in config)",
                           "Encoder ticks rise for both wheels (shown by the test)",
                           "The Pi does not restart when all 4 wheels start",
                           "Floor test: python -m hwtest.test_motors --straight 5 drifts less than 20 cm"])))
    H.append(step(8, "Three distance sensors", "3 HC-SR04, F-F jumpers, hot glue or brackets",
                  "<ol><li>Mount the sensors on the front edge: left one turned 45° left, centre straight, right one 45° right.</li>"
                  "<li>VCC → hub 5V, Gnd → hub GND.</li><li>Trig → Pi pin directly (3.3 V is enough to trigger).</li>"
                  "<li>Echo → its divider's input on the hub board; the divider's middle point → the Pi pin.</li></ol>"
                  + figure(D.fig_sonar(), "Figure 7 - ultrasonic sensors and their dividers.")
                  + cmd("python -m hwtest.test_sensors")
                  + check(["Each distance follows your hand (left, centre, right)", "A constant 400 cm or 0 means Trig/Echo swapped or a divider fault"])))
    H.append(step(9, "Wheel encoders", "the two encoder modules from step 2, F-F jumpers",
                  "<ol><li>VCC → hub <b>3V3</b> (not 5 V), GND → hub GND.</li><li>Left D0 → Pi pin 29, right D0 → Pi pin 31.</li></ol>"
                  + figure(D.fig_encoders(), "Figure 8 - encoders.")
                  + check(["test_sensors: the 'enc' numbers rise when you turn each wheel by hand", "The module's LED blinks as slots pass"])))
    H.append(step(10, "Gas sensor and battery level", "MQ-135, ADS1115 (wired in step 6), the hub's MQ and battery dividers",
                  "<ol><li>MQ-135 VCC → hub 5V, GND → hub GND.</li><li>MQ-135 AO → the 10 kΩ/20 kΩ divider input; divider middle → ADS1115 <b>A0</b>.</li>"
                  "<li>Battery + (the holder's red wire, at the L298N +12V screw) → the 10 kΩ/4.7 kΩ divider input; divider middle → ADS1115 <b>A1</b> (Figure 3).</li>"
                  "<li>Mount the MQ-135 and AHT20 at the back edge, away from the Pi.</li></ol>"
                  + figure(D.fig_gas(), "Figure 9 - MQ-135 through the divider into the ADS1115.")
                  + cmd("python -m hwtest.test_env                    # live readings\npython -m hwtest.test_env --calibrate-mq135  # outdoors, after 24 h warm-up")
                  + check(["Temperature and humidity are close to a room thermometer", "Gas value settles after a few minutes of warm-up",
                           "Robot health shows the battery: a full pack (8.4 V) is 100 %"])))
    H.append(step(11, "Webcam, microphone and speaker", "USB webcam, PAM8403, speaker, 3.5 mm cable",
                  "<ol><li>Webcam into a USB port; clip or glue it to the front of the top deck, level and looking forward.</li>"
                  "<li>Cut the 3.5 mm cable: the tip wire → PAM8403 L, the shield → G. Plug the other end into the Pi's audio jack. PAM8403 5V/GND from the hub.</li>"
                  "<li>Speaker → PAM8403 L+ and L−.</li></ol>"
                  "<p>The robot finds the webcam, its microphone and the audio jack by itself.</p>"
                  + figure(D.fig_audio(), "Figure 10 - webcam, audio jack, amplifier and speaker.")
                  + cmd("python -m hwtest.test_camera_audio\nspeaker-test -D plughw:CARD=Headphones -c1 -t wav -l1   # quick speaker check")
                  + check(["test_snapshot.jpg shows the room the right way up", "test_audio.wav has your voice", "The speaker says the test sentence"])))
    H.append(step(12, "Everything together", "the finished robot, the phone with the Raqib app",
                  "<ol><li>Tidy the cables with zip ties; nothing near the wheels.</li>"
                  "<li>Start the robot program again: <code>sudo systemctl start inspection-robot</code> (or reboot).</li>"
                  "<li>Phone on the same Wi-Fi (or join <b>Raqib-Robot</b>). Open the app → <b>Find automatically</b> → sign in.</li>"
                  "<li><b>More → AI settings</b>: paste your Gemini key once.</li>"
                  "<li><b>More → Robot health</b>: every part should be green; <i>Camera mount</i> says <i>fixed camera</i>, which is correct. "
                  "Red? Tap it for the fix, then <b>Re-check parts</b>.</li>"
                  "<li>Drive to each room, read the position on the Home screen, and write them under <code>zones:</code> in <code>edge/config.yaml</code>.</li></ol>"
                  + figure(D.fig_full_harness(), "Figure 11 - the complete harness on one page.")
                  + check(["Every part green in Robot health", "STOP in the app stops the robot immediately",
                           "A hand 30 cm in front of the moving robot stops it before 15 cm",
                           "Drive → Camera: left turns the whole robot left, centre turns it back"])))
    # ---------------------------------------------------------------- 7 troubleshooting
    trouble = [
        ("i2c_scan finds nothing", "I²C off, SDA/SCL swapped, or no 3.3 V on the rail", "sudo raspi-config → Interface → I2C on; check pins 3/5; measure the 3V3 rail"),
        ("One I²C board is missing", "Loose jumper", "Re-seat its 4 wires; run i2c_scan again"),
        ("Wheels do not turn", "ENA/ENB jumpers still on, ENA/ENB not on pins 33/35, battery off", "Remove the jumpers, check pins 33/35, switch on"),
        ("One side turns backwards", "Motor wires reversed", "Swap that pair's two OUT wires, or set invert: true"),
        ("One wheel of a pair turns the wrong way", "That motor's red/black reversed", "Swap its two wires where the pair is joined"),
        ("Robot will not turn on the spot", "4 wheels skid hard on carpet / rubber floor", "Raise min_power to 0.45 and turn_speed to 0.6 in config.yaml"),
        ("Pi restarts when the motors start", "Weak cells, no capacitor, XL4015 set too low", "Charge the cells; 1000 µF on the XL4015 input; set 5.1-5.2 V"),
        ("Lightning-bolt / 'low voltage' warning", "XL4015 below 5 V or thin wires", "Set 5.1-5.2 V; keep the USB cable short"),
        ("Sonar always 400 cm (or 0)", "Trig/Echo swapped, no 5 V, wrong divider", "Check the pin numbers and measure 5 V at the sensor"),
        ("Encoder count stays 0", "Disc not in the slot, D0 on the wrong pin, no 3.3 V", "Watch the module's LED blink while turning the wheel"),
        ("Camera not found", "Webcam not detected", "ls /dev/video* should list it; try another USB port or cable"),
        ("No sound", "No amp power, cable on the wrong pins", "5 V on the PAM8403; speaker-test (step 11); tip → L, shield → G"),
        ("Battery shows 0 % or nothing", "Divider not on A1, or wrong resistors", "Divider middle → A1; 10k on top, 4.7k to GND; ≈ 2.6 V at A1 when full"),
        ("Gas value strange", "Sensor still warming up, divider wrong", "Wait 2-5 min; check 10k on top, 20k to GND"),
        ("App cannot find the robot", "Phone on another network", "Same Wi-Fi or join Raqib-Robot; the robot says its address at start-up"),
    ]
    rows = "".join(f"<tr><td><b>{escape(a)}</b></td><td>{escape(b)}</td><td>{escape(c)}</td></tr>" for a, b, c in trouble)
    H.append(f"""<section class="page"><h2 class="sec"><span>7</span>Troubleshooting</h2>
<table class="bom trouble"><thead><tr><th>What you see</th><th>Usual cause</th><th>Fix</th></tr></thead><tbody>{rows}</tbody></table>
<div class="note">Logs on the Pi: <code>journalctl -u inspection-robot -f</code> (robot) and <code>journalctl -u raqib-server -f</code> (server).
The app's <b>Robot health</b> screen shows every part with a hint when it is red.</div>
</section>
<section class="page"><h2 class="sec"><span>8</span>Final checklist before a demo</h2>
<div class="check big"><ul>
<li>☐ Cells charged; a spare charged pair in the bag</li>
<li>☐ Every part green in Robot health</li>
<li>☐ STOP in the app stops the robot; Reset is needed to move again</li>
<li>☐ A hand 30 cm in front of the moving robot stops it before 15 cm</li>
<li>☐ Stopping the server (sudo systemctl stop raqib-server) puts the robot in SAFE HOLD within about 10 s</li>
<li>☐ The robot starts at the Home spot, facing the same direction as when you measured the rooms</li>
<li>☐ The admin password in the app has been changed from admin123</li>
<li>☐ AI key entered in More → AI settings; "Test" says it works</li>
</ul></div>
</section>""")
    # ---------------------------------------------------------------- 9 upgrades
    H.append(f"""<section><h2 class="sec" style="margin-top:18px"><span>9</span>Upgrades later</h2>
<p>When you have more budget, add any of these. You do not change the software: at start-up the robot checks which parts
answer and uses them (servos if a PCA9685 is found, the ribbon camera before the webcam, a BME680 before the AHT20, a UPS gauge
before the battery divider). Press <b>Re-check parts</b> in Robot health after fitting one.</p>
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
    footerTemplate: '<div style="font-family:Inter,sans-serif;font-size:8px;color:#8a949c;width:100%;padding:0 14mm;display:flex;justify-content:space-between"><span>Raqib · robot build guide</span><span class="pageNumber"></span></div>',
    margin: {{ top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' }} }});
  await b.close(); }})();""")
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", str(js)], check=True, env={**__import__("os").environ, "NODE_PATH": npm_root})
    js.unlink()
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    main()
