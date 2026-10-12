# Architecture & interfaces

## Edge (Raspberry Pi), `edge/robot/`

| Module | Proposal name | Thread / rate | Job |
|---|---|---|---|
| `hal/base.py` | — | — | Hardware interfaces (Motors, Ultrasonics, Imu, EnvSensor, Camera, ...) |
| `hal/sim.py` | — | physics 100 Hz | Simulated robot + building |
| `hal/real.py` | — | — | Real drivers (smbus2, gpiozero, bme680, picamera2, sounddevice) |
| `motor_controller.py` | motor_controller.py | — | Wheel power with interlocks (`forward_blocked`, `hold`), pan/tilt |
| `sensor_reader.py` | sensor_reader.py | 50 Hz | IMU + encoders → odometry pose (x, y, heading), battery |
| `safety_monitor.py` | safety_monitor.py | **100 Hz** | Obstacle stop (< 15 cm), cloud watchdog (10 s → SAFE_HOLD), low battery |
| `environmental_sensor.py` | environmental_sensor.py | 1 Hz | BME680/MQ-135, warm-up, sliding average, comfort/gas classification, voice alert |
| `camera_streamer.py` | camera_streamer.py | 15 fps | Snapshots for the VLM, WebRTC (aiortc), privacy mode |
| `audio_analyzer.py` | audio_analyzer.py | on demand | Edge Impulse model or heuristic fallback; dB level |
| `mqtt_client.py` | mqtt_client.py | paho thread | Topics below, LWT offline status, auto-reconnect |
| `state_machine.py` | (FSM) | — | IDLE · MANUAL · AUTONOMOUS_PATROL · EMERGENCY_STOP · SAFE_HOLD |
| `app.py` | (local control app) | worker pool | Command dispatcher, closed-loop move/turn, go_to_zone + reactive avoidance |

### Safety priority (Figure 2)

```
safety_monitor (100 Hz) ──► brake + forward_blocked     ← overrides everything
   cloud silent 10 s     ──► hold + SAFE_HOLD           ← until heartbeat returns
estop command            ──► hold + EMERGENCY_STOP      ← until explicit reset
teleop dead-man 0.6 s    ──► stop                       ← phone lost connection
motion commands          ──► only if state.can_move()
```

## MQTT contract (JSON, `"v": 1`)

| Topic | Direction | QoS | Payload |
|---|---|---|---|
| `robot/{id}/commands` | cloud → robot | 1 | `{"v":1,"id":"a1b2","action":"go_to_zone","params":{"zone":"IoT_Lab"}}` |
| `robot/{id}/acks` | robot → cloud | 1 | `{"id":"a1b2","status":"ok｜error｜blocked｜rejected｜timeout｜cancelled","result":{...},"error":null}` |
| `robot/{id}/telemetry` | robot → cloud | 0 | state, battery, pose+zone, ultrasonic_cm, imu, environment, audio, safety (2 Hz) |
| `robot/{id}/events` | robot → cloud | 1 | `obstacle_stop`, `obstacle_cleared`, `safe_hold`, `cloud_restored`, `gas_alert`, `state_change`, `avoiding_obstacle`, `low_battery`, `privacy_mode` |
| `robot/{id}/status` | robot → cloud | 1, retained | `{"online": true}`; last-will = `{"online": false}` |
| `robot/{id}/info` | robot → cloud | 1, retained | zones, supported actions, webrtc, audio model |
| `robot/{id}/heartbeat` | cloud → robot | 0 | every 2 s |

Actions: `drive, move, turn, go_to_zone, set_home, stop, estop, reset, pan_tilt, snapshot,
read_environment, listen_audio, speak, set_privacy, webrtc_offer, ping, status` (see `edge/robot/app.py`).

## Backend REST API (`http://<server>:8000/docs` has the interactive version)

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/health` | public | broker, robots, planner, VLM, memory status |
| POST | `/auth/login` | public | → JWT (12 h) |
| GET | `/robots`, `/robots/{id}` | viewer | status, telemetry, recent events |
| POST | `/robots/{id}/command` | operator (admin for privacy/set_home) | direct robot command |
| POST | `/robots/{id}/estop` | **any** | emergency stop |
| POST | `/robots/{id}/reset` | operator | clear E-STOP |
| GET | `/robots/{id}/ping` | viewer | MQTT round-trip latency (KPI) |
| GET | `/robots/{id}/frame.jpg` | viewer | JPEG frame (video fallback) |
| POST | `/webrtc/offer` | viewer | WebRTC signalling → robot answer |
| POST | `/chat` | operator | natural-language command → LangGraph agent |
| GET | `/reports`, `/reports/{id}` | viewer | audit reports |
| GET | `/images/{file}` | viewer | inspection snapshots |
| GET | `/search?q=&zone=&days=` | viewer | semantic history search |
| POST | `/memory/seed` | admin | 60 demo records |
| GET | `/audit` | admin | audit log (who did what) |
| WS | `/ws?token=` | viewer | live telemetry, events, agent progress |

## LangGraph InspectionAgent (`backend/app/agent/graph.py`)

```
START → parse_and_plan ─(no steps)──────────────────────────────► generate_report → END
              │                                                         ▲
              └─► execute_tool ─► decide ─ next ──► execute_tool        │
                                     ├─ retry (timeout/blocked, once) ──┘ (loops)
                                     ├─ fallback (stop robot, escalate) ─► generate_report
                                     └─ done ───────────────────────────► generate_report
```

Tools (`agent/tools.py`): `inspect_zone` (go → pan/tilt → snapshot + VLM ∥ environment ∥ audio → fusion),
`go_to_zone, return_home, move, turn, stop, pan_tilt, capture_and_analyze, read_environment,
listen_audio, search_history, get_status, speak`.

Planner: an LLM (JSON plan, validated against the tool list) when configured, or the rule-based planner
offline. If the LLM fails, the rules take over.

## Fusion rules (`backend/app/report.py`)

| Evidence | Finding |
|---|---|
| VLM occupants = 0 + lights/projector/monitors ON | energy_waste (high) |
| audio = ac_fan + room empty | energy_waste (high if over-cooled) |
| comfort ≠ COMFORTABLE | comfort (medium) |
| gas WARNING / HAZARD | air_quality (high / critical) |
| VLM exit not clear | blocked_exit (high) |
| VLM hazardous items | lab_hazard (high) |
| audio = alarm | equipment (critical) |
| VLM lights ON but the image is very dark, or confidence < 0.6 | `needs_human_review` (risk R3) |
