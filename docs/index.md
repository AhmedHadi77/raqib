# AI Agent Inspection Robot

**An IoT-enabled autonomous vision-language robotic platform for smart facility management.**
Final year project, Ahmed Mahram Saeed Saeed Hadi, UNISIRAJ.

The whole system already runs **without any hardware**. A simulated robot drives around a virtual
corridor with three rooms. It has the same motors, encoders, IMU, ultrasonic sensors, BME680/MQ-135,
camera and microphone interfaces as the real robot. When your components arrive you change **one line**
(`simulation: false` in `edge/config.yaml`) and the same code drives the real Raspberry Pi.

```
 ┌──────────────────────┐   HTTPS / WebSocket   ┌────────────────────────────┐   MQTT (TLS)   ┌──────────────────────────┐
 │  React Native app    │ ────────────────────▶ │  FastAPI backend            │ ─────────────▶ │  Raspberry Pi 4 (edge)   │
 │  (mobile/)           │ ◀──────────────────── │  LangGraph InspectionAgent  │ ◀───────────── │  robot/  (edge/)         │
 │  Dashboard · Agent   │      WebRTC video ◀───┼── signalling ───────────────┼──────────────▶ │  100 Hz safety loop      │
 │  Reports · History   │                       │  VLM · ChromaDB · SQLite    │                │  sim  ⇄  real hardware   │
 └──────────────────────┘                       └────────────────────────────┘                └──────────────────────────┘
```

## Folder map

| Folder | What it is | Proposal section |
|---|---|---|
| `edge/` | Raspberry Pi software: motors, sensors, safety, camera/WebRTC, audio, MQTT, state machine | 2.2.3.1 |
| `edge/robot/hal/sim.py` | **Simulated robot**: physics, sensors, camera renderer, sound synthesiser | (dev tool) |
| `edge/robot/hal/real.py` | **Real drivers**: PCA9685, L298N, HC-SR04, MPU6050, BME680, ADS1115+MQ-135, Pi Camera, mic, UPS | 2.2.2 |
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
11/11 checks passed
```

## Mobile app (Android / iPhone)

The app is one React Native (Expo SDK 57) codebase in `mobile/`. There are three ways to use it on a phone:

| Way | How | Best for |
|---|---|---|
| **Browser / home-screen app** | On the phone, open `http://<PC-IP>:8000`, then use the browser menu → **Add to Home Screen** | Quickest. No install, works on any phone |
| **Expo Go** | Run `setup_mobile.bat` once, then `start_mobile.bat`. Scan the QR code with the **Expo Go** app | Native app during development (video shows as snapshots) |
| **Android APK** | Run `build_apk.bat` (free Expo account). Install the `.apk` it gives you | A real installable app with live WebRTC video, for demos and the final presentation |

To pair a phone, open **`http://<PC-IP>:8000/connect`** on the PC and tap **Scan QR code from your PC** on the app's sign-in screen. The PC's IP is printed by `start_all.bat`.

What's in the app:
- **Robot:** a live floor plan with room status and the robot's position (tap a room to inspect it or drive there), the camera, room conditions with live trends, actions, manual drive and an activity log.
- **Assistant:** natural-language commands, with the plan and each step shown live.
- **Reports:** audit reports grouped by day. Open one to see photos, findings and prioritised actions, and **export it as a PDF** to share or print.
- **History:** temperature, humidity, air-quality and sound trends, plus a search of past inspections by meaning.
- **Alerts:** phone notifications and an in-app banner for poor air, obstacle stops, safe hold, low battery and finished inspections.
- **Look and accounts:** dark mode, and role-based access (admin / operator / viewer).

After changing the app, run `python tools/build_webapp.py` to update the browser version the backend serves.

## Turning on the real AI (optional)

By default the system runs **free and offline**:
- a rule-based planner turns your sentence into robot actions;
- a "mock VLM" reads the simulator's ground truth instead of looking at the image.

To use real models, edit `backend/.env`:

| Option | Settings | Cost |
|---|---|---|
| GPT-4o | `LLM_PROVIDER=openai`, `VLM_PROVIDER=openai`, `OPENAI_API_KEY=sk-...` | ~USD 0.005 / image |
| Gemini Flash | `LLM_PROVIDER=gemini`, `VLM_PROVIDER=gemini`, `GOOGLE_API_KEY=...` | cheaper |
| Ollama (local, free) | `ollama pull llama3.1` and `ollama pull qwen2.5vl`, then `LLM_PROVIDER=ollama`, `VLM_PROVIDER=ollama` | free |

Restart the backend after changing `.env`. Check `http://localhost:8000/health` to see which planner and VLM are active.

> With a real VLM in simulation mode, the model looks at the **rendered** simulator picture. That is a
> good test of the prompt and JSON pipeline. The real accuracy numbers (Table 4) must come from real photos.

## When the hardware arrives

Follow **[HARDWARE_BRINGUP.md](HARDWARE_BRINGUP.md)**. In short:

1. Flash Raspberry Pi OS 64-bit, copy the `edge/` folder to the Pi, and run `bash scripts/install_pi.sh`.
2. Wire the parts using **[WIRING.md](WIRING.md)**. Remember the voltage dividers on the HC-SR04 echo pins and on the MQ-135.
3. Run the bring-up tests in order: `python -m hwtest.i2c_scan` → `test_motors` → `test_sensors` → `test_env` → `test_camera_audio`.
4. In `edge/config.local.yaml`, set `simulation: false` and `mqtt.host: <your PC IP>`.
5. Start the robot: `sudo systemctl enable --now inspection-robot`.
6. Measure the real room positions and put them in `zones:` in `config.yaml`.

**Nothing changes in the backend or the mobile app.**

## Production stack (Docker, Mosquitto + TLS)

```
docker compose up --build                 # Mosquitto (auth + ACL) + backend
docker compose --profile sim up --build   # ... plus the simulated robot
python tools/generate_certs.py --host <server-ip>   # then enable the 8883 TLS listener (see mosquitto.conf)
```

## Notes on changes from the proposal

- **MQ-135 needs an ADC.** The Pi has no analog input, so an **ADS1115** (≈RM 12) has been added to the design (`docs/WIRING.md`).
- **`motor_controller.py` bug fixed.** In Appendix B.1, `stop()` called `GPIO.cleanup()`, so the motors could not run again after the first stop. Cleanup now happens only on shutdown.
- **"Gemini Pro Flash" is not a real model name.** The configurable default is `gemini-2.5-flash`.
- **The mobile app gets telemetry from the backend over a WebSocket, not directly from MQTT.** This keeps broker credentials off the phone (least privilege). Commands still travel over MQTT from the backend to the robot.
- **Login uses the backend's JWT + roles (admin / operator / viewer) instead of Firebase Auth.** There is no external account to set up. Firebase can be added later if your supervisor requires it.
- **WebRTC: the app sends the offer and the robot (aiortc) answers.** Signalling is relayed through the backend and MQTT. In **Expo Go** (no native WebRTC module) the app falls back to 2 fps JPEG frames. A development build (`npm run build:dev`) gives full WebRTC.
