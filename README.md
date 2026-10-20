# Raqib: AI Agent Inspection Robot

**An IoT-enabled autonomous vision-language robotic platform for smart facility management.**
Final year project, Ahmed Mahram Saeed Saeed Hadi, UNISIRAJ.

Product name: **Raqib** (Arabic رقيب, "watcher / observer"): the robot keeps watch over the building.
The logo is an R whose bowl is the robot's eye. To rename, change `PRODUCT_NAME` in `backend/.env`,
`mobile/app.json`, `BRAND` in `mobile/src/theme.ts` and the `Wordmark` in `mobile/src/components/ui.tsx`.
Register the trademark (MyIPO, classes 7, 9 and 42) before selling.

**Raqib 3.0 is the easy ESP32 robot.** The robot itself is only a body: a XIAO ESP32S3 Sense (Wi-Fi, camera and
microphone on one thumb-size board), two TT motors on a DRV8833, one HC-SR04P distance sensor, an MPU6050 and an
AHT20 + BMP280, all on one half breadboard (≈ RM 232, no soldering except the XIAO's header pins). **Your laptop is the
brain:** it runs the server, the AI and the robot program, and talks to the ESP32 over Wi-Fi. The phone app speaks
and shows the alerts (the robot has no speaker).

The whole system also runs **without any hardware**: a simulated robot drives around a virtual corridor with the
same sensors, and `start_esp32_emulator.bat` even pretends to be the ESP32 board itself, so the real robot path
can be tested before the parts arrive.

```
 ┌──────────────────────┐   HTTPS / WebSocket   ┌────────────────────────────┐   MQTT (TLS)   ┌──────────────────────────┐
 │  React Native app    │ ────────────────────▶ │  FastAPI backend            │ ─────────────▶ │  Robot program (edge/)   │
 │  (mobile/)           │ ◀──────────────────── │  LangGraph InspectionAgent  │ ◀───────────── │  on the PC  ── Wi-Fi ──▶ │
 │  Dashboard · Agent   │      WebRTC video ◀───┼── signalling ───────────────┼──────────────▶ │  XIAO ESP32S3 (esp32/)   │
 │  Reports · History   │                       │  VLM · ChromaDB · SQLite    │                │  sim  ⇄  real robot      │
 └──────────────────────┘                       └────────────────────────────┘                └──────────────────────────┘
```

## Folder map

| Folder | What it is | Proposal section |
|---|---|---|
| `esp32/` | **Robot firmware** for the XIAO ESP32S3 Sense (Arduino) + a ready-to-flash `.bin`: motors, safety stop, sensors, camera, mic | 2.2.2 |
| `edge/` | Robot program (runs on the PC): navigation, inspections, safety, camera, audio, MQTT, state machine | 2.2.3.1 |
| `edge/robot/hal/esp32.py` | **ESP32 link**: finds the robot on Wi-Fi and drives it over HTTP | 2.2.2 |
| `edge/robot/hal/sim.py` | **Simulated robot**: physics, sensors, camera renderer, sound synthesiser | (dev tool) |
| `edge/robot/hal/real.py` | Older Raspberry Pi drivers (`hardware.board: pi`), kept for the Pi build | 2.2.2 |
| `edge/hwtest/` | Step-by-step hardware bring-up tests for when the parts arrive | 3.1.4 |
| `backend/` | FastAPI + LangGraph agent + VLM (GPT-4o / Gemini / Ollama) + ChromaDB memory + JWT/RBAC | 2.2.3.2 |
| `mobile/` | React Native (Expo, TypeScript) app: Dashboard, Agent chat, Reports, History, Settings | 2.2.3.3 |
| `infra/` | Mosquitto config, ACL, TLS certificates | 2.1.4 |
| `tools/` | End-to-end test (T-01…T-10), certificate generator | 3.1.4 |
| `docs/` | Wiring, hardware bring-up, architecture/API, testing, Edge Impulse guide | Appendices |

## Quick start on Windows (no hardware, no Docker)

1. Double-click **`first_run.bat`**. It installs Python 3.12 if needed, then the core packages
   (≈30 MB, they resume if the connection drops), and starts everything.
   Next time, just double-click **`start_all.bat`**.
2. Two windows open:
   - **Backend** – API, AI agent, an embedded MQTT broker and the web app, on port 8000.
   - **Robot (simulation)** – the virtual robot.
3. Your browser opens **http://localhost:8000**. Sign in with **operator / operator123**.
   From a phone on the same Wi-Fi, use `http://<your-PC-IP>:8000`, and allow Python through Windows Firewall when asked.
4. Agent tab → *"Inspect the IoT Lab and Lecture Hall B, then return home"*

Optional, when you have a fast connection:

| Script | Adds | Download |
|---|---|---|
| `install_extras.bat` | GPT-4o / Gemini / Ollama clients, ChromaDB, WebRTC live video, OpenCV | ~140 MB |
| `setup_mobile.bat` then `start_mobile.bat` | Native app in **Expo Go** on your phone | ~300 MB |

Without the extras, the system uses lightweight fallbacks:
- a built-in vector store instead of ChromaDB;
- 2 fps camera snapshots instead of WebRTC video;
- the offline rule-based planner and a simulated vision model.

The simulated building (`edge/sim_world.yaml`) is set up to reproduce the proposal's sample reports:

| Room | What it simulates | Expected verdicts |
|---|---|---|
| `IoT_Lab` | Appendix D2: 29.4 °C / 74 %, VOC, lights + monitors on, chair blocking the exit, soldering iron, AC running | hot & humid, gas WARNING, energy waste, blocked exit, lab hazard |
| `LectureHall_B` | Empty hall, lights + projector on, over-cooled to 18.5 °C, AC running | energy waste, over-cooled |
| `LectureHall_A` | Appendix D3: all clear | compliant |
| corridor | A chair between Hall B and Hall A | obstacle stop (< 50 ms) and avoidance |

Edit the YAML to create any other scenario: occupants, gas level (`extreme` → HAZARD), alarm sound and so on.

### Tests

```
run_tests.bat            (or: cd edge && pytest ; cd backend && pytest ; python tools/e2e_test.py)
```

`tools/e2e_test.py` starts the backend and the simulated robot, then checks T-01 and T-03 to T-10, the
emergency stop and the MQTT latency KPI:

```
[PASS] KPI MQTT round-trip < 80 ms 2.1 ms
[PASS] T-10 conversational inspection produces a report
[PASS] T-03 energy waste flagged     [PASS] T-04 blocked exit flagged
[PASS] T-05 hot & humid              [PASS] T-06 gas WARNING        [PASS] T-07 AC audio
[PASS] T-01 obstacle stop < 50 ms, then avoided (10 ms)
[PASS] T-08 semantic search < 2 s    [PASS] E-STOP latch            [PASS] T-09 SAFE HOLD after 10 s
[PASS] V-1 "check the aircon in hall B" -> over-cooling found and spoken
[PASS] V-2 "what did you find" recalls the last report   [PASS] V-3 relative moves by voice
14/14 checks passed
```

## 3D simulation in Webots

Double-click **`start_all_webots.bat`** to run the same robot software on a 3D robot in Webots
(campus corridor, IoT lab, two lecture halls and an exam hall with animated students). Everything in
the app works with it: driving, voice orders, inspections, "what do you see" and the exam monitor.
Details, and how to change the campus: [webots/README.md](webots/README.md).

## The app (Android / iPhone / browser)

One React Native (Expo SDK 57) codebase in `mobile/`, also served as a web app by the backend.

| Way | How | Best for |
|---|---|---|
| **Browser / home-screen app** | Open `http://<PC-IP>:8000` on any device, then browser menu > **Add to Home Screen** | Quickest. On the PC itself (localhost) the microphone works in Chrome / Edge |
| **Expo Go** | `setup_mobile.bat` once, then `start_mobile.bat`, scan the QR code with **Expo Go** | Native app with voice, haptics and notifications (video as snapshots) |
| **Android APK** | `build_apk.bat` (free Expo account), install the `.apk` | The installable product with live WebRTC video |

Pair a phone: open **`http://<PC-IP>:8000/connect`** on the PC and tap **Change > Scan the code** on the sign-in screen.

**Screens**
- **Home:** live blueprint floor plan (rooms tagged clear / findings / urgent, robot with its camera cone and trail), robot status, one-tap Patrol all / Check AC / Dock / Drive, room cards (tap for Inspect, Check AC, Anyone in?, Drive there, Last report), live readings and activity.
- **Drive:** live camera with the three distance sensors drawn on it, an 8-way pad (forward, back, curves, spin left/right, stop), an analog joystick, camera pan/tilt, Slow / Normal / Fast, exact moves (50 cm, 90°, U-turn) and voice. On a PC: arrows / WASD, Q E Z C for curves, space to stop. Releasing a button stops the robot; it also stops by itself 0.6 s after the last command if Wi-Fi drops, and never drives forward into an obstacle.
- **Assistant** (centre button): talk or type. The robot says what it is about to do, does it, then answers out loud and in the chat (with photos and a link to the report).
- **Reports:** every inspection with photos, findings and prioritised actions; **Listen** reads it aloud, **Export PDF** shares it.
- **More:** Insights (trends + search by meaning), **Scheduled patrols** (e.g. weekdays 07:45 "Patrol all rooms and return home"), **Robot health** (each motor/sensor with how to fix it), **Users** (admins add people as viewer / operator / admin), Settings (voice, speaking speed, dark mode, notifications, connection, change password).

**Things you can say** (or type)

| Say | What happens |
|---|---|
| "Inspect the IoT Lab and Lecture Hall B, then return home" | Full audit of both rooms, report saved |
| "Patrol all rooms" / "Inspect everything" | Audits every room |
| "Check the aircon in Hall B" / "Is the AC working in the lab?" / "Check the aircon in all rooms" | Drives there, listens for the compressor, measures temperature and humidity, looks at the unit, then says if it is running, over-cooling, not cooling or could be switched off |
| "What did you find?" / "What did you find in the lab?" | Reads back the latest results and the most urgent action |
| "Is anyone in Hall A?" / "Are the lights on in Hall A?" | Drives there and looks |
| "What's the temperature here?" | Reads the air sensors where it is |
| "Go to the lab" / "Go there" (the room you talked about last) / "Come back home" | Navigation |
| "Move forward one meter" / "Move left 50 cm" / "Turn right" / "Turn around" / "Stop" | Exact moves |
| "Look up" / "Look left" / "What do you see?" / "Take a photo" | Camera |
| "Go 5 meters, take a picture and tell me what it is" / "Turn left, go forward 2 m, look up and take a photo, then come back" | Any chain of orders, done in the order you said them. Long moves stop safely at the first obstacle and say where |
| "What do you see in front of you?" / "What is that?" | Takes a photo and answers in first person: "I see ..." |
| "Who is talking?" / "Go to the noise" | Listens and takes photos around it for you to check (the ESP32's single microphone hears talking but cannot point at the talker; the phone shows the photo and can read out a warning) |
| "Monitor the exam in Exam Hall for 90 minutes" / "Watch for cheating in Exam Hall and stay in one place" / "How is the exam going?" / "Stop monitoring" | **Exam monitor** (proctoring): patrols the room, looks all the way round and listens. Flags phones, notes / cheat sheets, earpieces, a head turned to a neighbour's paper (3 s), looking down at the lap (8 s), talking, whispering and sudden noises. Goes to the student and sends you the photo at once (the phone can read the warning out) (More > Exam monitor; every session prints as a PDF report) |
| "Where are you?" / "Help" | Status / list of commands |

**Free wording.** The built-in planner understands the commands above and any chain of them, offline and free.
To follow *any* wording ("could you have a look whether someone left the lab tap running"), sign in as admin and
open **More > AI settings**: choose Google Gemini, paste a free key from aistudio.google.com/apikey, press
**Save and switch on**, then **Test**. No restart needed (it is saved in `backend/.env`). OpenAI and Ollama (free,
offline on the PC) work the same way. The same model also understands photos, which the real robot needs.

**How exam proctoring sees.** In the simulator, the four exam-hall students act out a head turn, a phone, notes, an
earpiece and looking down on a timer, so every check works. On real photos, head direction and phones are checked
on the server PC with **MediaPipe** (offline, installed by `upgrade.bat`), and the vision AI (if connected) also
spots notes and earpieces. To try it on yourself, close the robot window and run **`start_robot_sim_webcam.bat`**:
the simulated robot then uses the PC webcam as its camera. Thresholds are in `backend/.env` (`PROCTOR_*`).

**Exam monitoring and privacy.** The robot never identifies people: students are anonymous seats. It takes a photo
of what triggered a flag for the invigilator, visible only to signed-in users. Privacy mode turns the camera off,
and monitoring then works on sound alone.

**Voice recognition.** In Chrome/Edge on the PC the browser recognises speech itself. Phones send the recording to
your server: run **`install_voice.bat`** once (free, offline, ~140 MB model), or put an OpenAI / Gemini key in
`backend/.env`. Replies are spoken with the phone's or browser's own voice.

**Accounts.** On the first start the server creates `admin / admin123`, `operator / operator123` and
`viewer / viewer123` (from `USERS=` in `backend/.env`). After that, accounts live in the database:
change passwords in **Settings > Change password** and manage people in **More > Users**.

After changing the app, run `python tools/build_webapp.py` to update the browser version the backend serves.

## Turning on the real AI (optional)

By default the system runs **free and offline**:
- a rule-based planner turns your sentence into robot actions;
- a "mock VLM" reads the simulator's ground truth instead of looking at the image.

The easy way is the app: **More > AI settings** (admin). Or edit `backend/.env` yourself:

| Option | Settings | Cost |
|---|---|---|
| GPT-4o | `LLM_PROVIDER=openai`, `VLM_PROVIDER=openai`, `OPENAI_API_KEY=sk-...` | ~USD 0.005 / image |
| Gemini Flash | `LLM_PROVIDER=gemini`, `VLM_PROVIDER=gemini`, `GOOGLE_API_KEY=...` | cheaper |
| Ollama (local, free) | `ollama pull llama3.1` and `ollama pull qwen2.5vl`, then `LLM_PROVIDER=ollama`, `VLM_PROVIDER=ollama` | free |

Restart the backend after changing `.env`. Check `http://localhost:8000/health` to see which planner and VLM are active.

> With a real VLM in simulation mode, the model looks at the **rendered** simulator picture. That is a
> good test of the prompt and JSON pipeline. The real accuracy numbers (Table 4) must come from real photos.

## When the hardware arrives

**What the finished robot looks like:** [docs/Raqib_Finished_Robot_3D.pdf](docs/Raqib_Finished_Robot_3D.pdf) and
`docs/robot_renders/` (3D model, real size; sources in `docs/build_guide/robot3d/`).

**The whole robot's wiring on one page:** [docs/Raqib_Full_Wiring_Diagram.pdf](docs/Raqib_Full_Wiring_Diagram.pdf)
(A3 poster, also as .png; `python docs/build_guide/poster.py`).

**What to buy and how to build it:** [docs/Raqib_Robot_Build_Guide.pdf](docs/Raqib_Robot_Build_Guide.pdf), the ESP32
edition 3.0 (≈ RM 232): XIAO ESP32S3 Sense on a USB power bank, two TT motors on a DRV8833 fed by 2 × 18650, 2WD
chassis with a caster, HC-SR04P, MPU6050, AHT20 + BMP280, half breadboard. Every step ends with a check.

**Try the wiring first, on the PC:** `start_robot_sim.bat`, then open `http://localhost:8000/bench`. Place the same
wires on the virtual XIAO; the simulated robot then behaves exactly as that wiring would (a swapped motor wire really
spins backwards).

In short:

1. `allow_robot_connections.bat` once (lets the robot find the PC).
2. Flash the firmware: Chrome → https://espressif.github.io/esptool-js/ → Connect → `esp32/raqib_esp32_xiao.bin` at
   address `0x0` → Program. Details: [esp32/README.md](esp32/README.md).
3. Connect the robot to your phone's hotspot: join its Wi-Fi "Raqib-Robot" (password `raqib1234`), open
   http://192.168.4.1 and save your hotspot name and password.
4. Wire it with the build guide (or [docs/WIRING.md](docs/WIRING.md)), then double-click **`start_my_robot.bat`**.
   It starts the server and the robot program, which finds the ESP32 by itself.
5. Open the app on the same Wi-Fi, tap **Find automatically**, then **More > Robot health**: every part shows green
   or red with the fix. Paste your AI key once in **More > AI settings**.
6. Calibrate the driving once (`python -m hwtest.test_motors --calibrate`, build guide step 10) and measure the room
   positions into `zones:` in `edge/config.yaml`. More detail: [docs/HARDWARE_BRINGUP.md](docs/HARDWARE_BRINGUP.md).

Safety lives on the ESP32 itself: it stops the motors 0.6 s after the PC stops talking to it, and refuses to drive
forward when something is closer than 15 cm (or the distance sensor does not answer).

Before the robot exists, the app's **Try the demo robot** button runs a simulated robot inside the phone, so every
screen works anywhere with no laptop and no internet.

**Nothing changes in the backend or the mobile app.** The older Raspberry Pi build still works with
`hardware.board: pi` in `edge/config.yaml`.

## Production stack (Docker, Mosquitto + TLS)

```
docker compose up --build                 # Mosquitto (auth + ACL) + backend
docker compose --profile sim up --build   # ... plus the simulated robot
python tools/generate_certs.py --host <server-ip>   # then enable the 8883 TLS listener (see mosquitto.conf)
```

## Notes on changes from the proposal

- **The brain moved to the PC (3.0).** A Raspberry Pi made the robot expensive and hard to build. The ESP32 robot is a Wi-Fi body (≈ RM 232) and the laptop runs the same robot software. No speaker and no gas sensor: the phone speaks, and air quality shows as "not measured".
- **`motor_controller.py` bug fixed.** In Appendix B.1, `stop()` called `GPIO.cleanup()`, so the motors could not run again after the first stop. Cleanup now happens only on shutdown.
- **"Gemini Pro Flash" is not a real model name.** The configurable default is `gemini-2.5-flash`.
- **The mobile app gets telemetry from the backend over a WebSocket, not directly from MQTT.** This keeps broker credentials off the phone (least privilege). Commands still travel over MQTT from the backend to the robot.
- **Login uses the backend's JWT + roles (admin / operator / viewer) instead of Firebase Auth.** There is no external account to set up. Firebase can be added later if your supervisor requires it.
- **WebRTC: the app sends the offer and the robot (aiortc) answers.** Signalling is relayed through the backend and MQTT. In **Expo Go** (no native WebRTC module) the app falls back to 2 fps JPEG frames. A development build (`npm run build:dev`) gives full WebRTC.
