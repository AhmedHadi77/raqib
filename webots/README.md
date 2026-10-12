# Raqib in Webots (3D simulation)

The robot in `worlds/raqib_campus.wbt` is driven by **the same Raqib software that will run on the
Raspberry Pi** (`edge/`), through a Webots hardware layer (`edge/robot/hal/webots.py`). The app,
server, voice, AI and exam monitor work exactly as with the real robot.

## Run it

1. Install **Webots R2025a** (already on this PC: `C:\Program Files\Webots`).
2. Double-click **`start_all_webots.bat`** in the project folder. It starts the server if needed,
   opens the campus in Webots, connects the robot program and opens the app.
   (Or: `start_backend.bat`, then `start_robot_webots.bat`.)
3. Use the app as normal: drive it, say "inspect the IoT lab", "go to the exam hall and tell me what
   you see", or start **Exam monitor**. Watch the robot move in Webots.

Close `start_robot_sim.bat` first: only one robot can be connected. If you press **Reset** or close
Webots, the robot program stops; run `start_robot_webots.bat` again.

## What is simulated how

| Part | In Webots |
|---|---|
| 2 drive wheels + 2 casters, wheel encoders (20 slots) | 3D physics, encoder ticks from wheel rotation |
| 3 x HC-SR04 (left / centre / right) | Webots sonar sensors, 15 deg beam, 4 m |
| MPU-6050 | Webots inertial unit + gyro |
| Pan/tilt camera on a **1 m mast** | Webots camera 640x480, 62 deg, servo speed limited |
| Speaker | Webots speaker (spoken warnings) |
| BME680 / MQ-135, microphone | modelled per room (Webots has no such sensors), same as the 2D simulator |
| Exam students | animated by the controller: head turns, looking down, phone, cheat sheet, earpiece |

Navigation uses only the encoders + IMU (dead reckoning), exactly like the real robot, so drift and
wheel slip are real. The robot's true position is only used for the room's climate / sound and for
the free "mock" vision answers. With an AI model connected (More > AI settings) the real Webots
camera pictures are analysed instead.

## Change the campus

Rooms come from `edge/config.yaml` (`zones`, `webots:`) and `edge/sim_world.yaml` (walls, desks,
students, what each room is like). After editing them run:

    .venv\Scripts\python.exe webots\build_world.py

and reopen the world in Webots.

## What Webots taught us about the real build

* Mount the camera on a mast about **1 m** high. At chassis height it cannot see faces of seated
  students or the projector screens.
* Inspections face the room's equipment wall (`view_heading`), so the screen, bench, exit door and
  extinguisher are all in one photo. Measure the same heading for each real room.
