# Testing & KPI evaluation (Table 4 / Table 8)

## Automated (simulation): run any time

| Command | What it checks |
|---|---|
| `cd edge && python -m pytest -q` | classifier thresholds, T-01 obstacle stop, navigation, E-STOP latch, privacy mode, audio classes |
| `cd backend && python -m pytest -q` | planner, fusion (D2/D3 samples), grounding, auth, memory filters, agent graph with a fake robot |
| `python tools/e2e_test.py` | whole system: T-01, T-03…T-10, E-STOP, MQTT latency |
| `cd mobile && npx tsc --noEmit` | app type-check |

## Table 8 test cases: how to run each one on the REAL robot

| ID | How | Where the number comes from |
|---|---|---|
| T-01 | Box at 30 cm, Agent: "move forward 1 m" | Dashboard → *Stop latency*; telemetry `safety.last_stop_latency_ms`; tape-measure the clearance |
| T-02 | 85 cm doorway, 20 runs of `go_to_zone` through it | count successes |
| T-03 | Empty room, lights + projector ON, "Inspect <room>" | report → energy_waste; repeat over the held-out image set |
| T-04 | Chair in front of the exit | report → blocked_exit |
| T-05 | Space heater + humidifier to 30 °C / 75 % | report comfort verdict vs reference meter |
| T-06 | Incense / non-toxic aerosol near the robot (supervised) | gas verdict WARNING; the robot also speaks a warning |
| T-07 | Play an AC recording | audio label `ac_fan` |
| T-08 | History tab query | `took_ms` shown under the search bar (< 2000) |
| T-09 | Switch off the PC Wi-Fi for 15 s mid-task | robot state SAFE_HOLD after 10 s (event log) |
| T-10 | "Inspect <room>" with the robot already in the room | `duration_s` under the agent's reply (target < 8 s) |

## KPI tools

- **MQTT round-trip:** Settings → *Measure command latency* (or `GET /robots/robot01/ping`)
- **Odometry ±5 %:** `python -m hwtest.test_motors --straight 10` vs tape measure
- **VLM precision/recall:** save 100+ labelled photos and run them through `VisionAnalyzer.analyze()`; compare with your labels (keep a held-out set, section 3.1.4)
- **Audio accuracy:** Edge Impulse 5-fold cross-validation + test set
- **Semantic search nDCG@5:** 50 queries; rate the top-5 results 0–2 and compute nDCG
- **MTBF:** let `python -m robot.main --real` run a patrol loop for 4+ h and count restarts (`journalctl -u inspection-robot`)
- **Audit trail:** `GET /audit` (admin) lists every command, login, E-STOP and video stream opened
