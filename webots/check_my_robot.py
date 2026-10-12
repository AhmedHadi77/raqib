"""Raqib parts check: tests the robot you are building in Webots, like hwtest does on the real robot.

Run it with check_my_robot.bat (Webots must be open with your world and the robot named "raqib",
controller "<extern>"). Run it after every build step: parts you have not added yet show as "not yet".

    .venv\\Scripts\\python.exe webots\\check_my_robot.py
"""
from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "edge"))

from robot.hal.webots import import_webots_controller  # noqa: E402

GREEN, RED, YELLOW, DIM, END = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"
if os.name == "nt":
    os.system("")                                   # turn on colours in the Windows console
results: list[tuple[str, str]] = []


def report(status: str, what: str, detail: str = ""):
    col = {"PASS": GREEN, "FAIL": RED, "NOT YET": YELLOW}.get(status, DIM)
    print(f"  {col}{status:<8}{END} {what}" + (f"\n           {DIM}{detail}{END}" if detail else ""))
    results.append((status, what))


def main():
    controller, home = import_webots_controller(os.environ.get("WEBOTS_HOME"))
    os.environ.setdefault("WEBOTS_CONTROLLER_URL", "raqib")
    print(f"\nRaqib parts check  (Webots: {home})\nConnecting to the robot named \"raqib\" ...")
    robot = controller.Supervisor()
    Node = controller.Node
    ts = int(robot.getBasicTimeStep())
    step = lambda n=1: [robot.step(ts) for _ in range(n)]  # noqa: E731
    secs = lambda s: max(1, int(s * 1000 / ts))           # noqa: E731
    print(f"Connected. Simulation step {ts} ms.\n")

    def dev(name, kind, label):
        try:
            d = robot.getDevice(name)
        except Exception:  # noqa: BLE001
            d = None
        if d is None:
            report("NOT YET", f"{label}: device \"{name}\"", "Not found. Check the spelling of its name field (lower case, spaces as shown).")
            return None
        if d.getNodeType() != kind:
            report("FAIL", f"{label}: \"{name}\" is the wrong kind of device",
                   "Delete it and add the device type the guide names for this step.")
            return None
        return d

    me = robot.getSelf()
    print("Robot")
    if me is None:
        report("FAIL", "Supervisor is FALSE", "Set the Robot's supervisor field to TRUE (the Raqib software needs it).")
    else:
        report("PASS", "Robot \"raqib\" with supervisor TRUE")
    z0 = me.getPosition()[2] if me else None

    print("\nStep 3 - wheels and encoders")
    lm = dev("left wheel motor", Node.ROTATIONAL_MOTOR, "Left motor")
    rm = dev("right wheel motor", Node.ROTATIONAL_MOTOR, "Right motor")
    ls = dev("left wheel sensor", Node.POSITION_SENSOR, "Left encoder")
    rs = dev("right wheel sensor", Node.POSITION_SENSOR, "Right encoder")
    imu = None

    print("\nStep 6 - ultrasonic sensors")
    sonars = {k: dev(f"us_{k}", Node.DISTANCE_SENSOR, f"Ultrasonic {k}") for k in ("left", "center", "right")}
    print("\nStep 7 - motion sensor (MPU6050)")
    imu = dev("imu", Node.INERTIAL_UNIT, "IMU")
    gyro = dev("gyro", Node.GYRO, "Gyro")
    print("\nStep 8 - pan/tilt camera")
    pan = dev("pan motor", Node.ROTATIONAL_MOTOR, "Pan servo")
    tilt = dev("tilt motor", Node.ROTATIONAL_MOTOR, "Tilt servo")
    pan_s = dev("pan sensor", Node.POSITION_SENSOR, "Pan angle sensor")
    tilt_s = dev("tilt sensor", Node.POSITION_SENSOR, "Tilt angle sensor")
    cam = dev("camera", Node.CAMERA, "Camera")
    print("\nStep 9 - speaker")
    spk = dev("speaker", Node.SPEAKER, "Speaker")

    for d in (ls, rs, imu, gyro, pan_s, tilt_s, *sonars.values()):
        if d is not None:
            d.enable(ts)
    if cam is not None:
        cam.enable(64)
    step(secs(0.5))

    print("\nTests")
    # --- standing level on its wheels
    if imu is not None:
        r, p, _ = imu.getRollPitchYaw()
        tilt_deg = math.degrees(max(abs(r), abs(p)))
        report("PASS" if tilt_deg < 3 else "FAIL", f"Stands level ({tilt_deg:.1f} deg)",
               "" if tilt_deg < 3 else "The chassis leans: add both casters (step 4) and check the wheel height.")

    # --- ultrasonics: in the build lab a cardboard box stands 1.5 m ahead of the start mark
    if all(sonars.values()):
        vals = {k: d.getValue() for k, d in sonars.items()}
        txt = ", ".join(f"{k} {v:.0f} cm" for k, v in vals.items())
        sane = all(2 <= v <= 400 for v in vals.values())
        report("PASS" if sane else "FAIL", f"Ultrasonics read centimetres ({txt})",
               "" if sane else "Values must be 2..400: set lookupTable [ 0.02 2 0, 4 400 0 ] and type \"sonar\".")
        if sane:
            box_ok = 100 <= vals["center"] <= 170
            report("PASS" if box_ok else "FAIL", f"Centre sensor sees the cardboard box ahead ({vals['center']:.0f} cm, expected about 140)",
                   "" if box_ok else "In the build lab, start on the blue mark facing the box. If it reads 400, the centre sensor points the wrong way.")
        if me:
            hz = [robot.getFromDevice(d._tag).getPosition()[2] - (me.getPosition()[2]) for d in sonars.values()]
            okz = all(0.03 < h < 0.15 for h in hz)
            report("PASS" if okz else "FAIL", f"Ultrasonics at bumper height ({hz[1] * 100:.0f} cm)",
                   "" if okz else "Mount them 5-12 cm above the floor so they see chair legs and boxes.")
    else:
        report("NOT YET", "Ultrasonic readings")

    # --- IMU agrees with the real heading
    if imu and gyro and me:
        R = me.getOrientation()
        true = math.atan2(R[3], R[0])
        err = abs((imu.getRollPitchYaw()[2] - true + math.pi) % (2 * math.pi) - math.pi)
        report("PASS" if math.degrees(err) < 3 else "FAIL", f"IMU heading matches the robot ({math.degrees(err):.1f} deg off)",
               "" if math.degrees(err) < 3 else "Put the InertialUnit directly in the Robot's children, not rotated.")

    # --- pan / tilt
    if pan and tilt and pan_s and tilt_s:
        pan.setPosition(1.0)
        tilt.setPosition(0.4)
        step(secs(1.0))
        okp = abs(pan_s.getValue() - 1.0) < 0.08 and abs(tilt_s.getValue() - 0.4) < 0.08
        report("PASS" if okp else "FAIL", f"Pan/tilt reach their angles (pan {math.degrees(pan_s.getValue()):.0f}, tilt {math.degrees(tilt_s.getValue()):.0f} deg)",
               "" if okp else "Each angle sensor must be in the same HingeJoint device list as its motor.")
        pan.setPosition(0.0)
        tilt.setPosition(0.0)
        step(secs(1.0))
    else:
        report("NOT YET", "Pan/tilt test")

    # --- camera height + photo
    if cam is not None:
        h = robot.getFromDevice(cam._tag).getPosition()[2] if me else None
        if h is not None:
            okh = 0.9 <= h <= 1.2
            report("PASS" if okh else "FAIL", f"Camera height {h:.2f} m (target about 1.05 m)",
                   "" if okh else "At chassis height it cannot see faces or screens. Raise the mast (step 8).")
        out = ROOT / "my_robot_photo.jpg"
        step(secs(0.3))
        ok = cam.saveImage(str(out), 90) == 0
        report("PASS" if ok else "FAIL", f"Camera photo saved: {out}", "Open it: the cross on the test card should be in the middle of the photo." if ok else "")
    else:
        report("NOT YET", "Camera photo")

    # --- driving: forward, then a left turn
    if lm and rm and ls and rs and me:
        for m in (lm, rm):
            m.setPosition(float("inf"))
            m.setVelocity(0.0)
        step(secs(0.3))
        p0, e0 = me.getPosition()[:2], (ls.getValue(), rs.getValue())
        R = me.getOrientation()
        fwd = (R[0], R[3])                                     # the robot's own +x axis on the floor
        lm.setVelocity(6.0)
        rm.setVelocity(6.0)
        step(secs(1.5))
        lm.setVelocity(0.0)
        rm.setVelocity(0.0)
        step(secs(0.5))
        p1, e1 = me.getPosition()[:2], (ls.getValue(), rs.getValue())
        moved = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        along = (p1[0] - p0[0]) * fwd[0] + (p1[1] - p0[1]) * fwd[1]
        dl, dr = e1[0] - e0[0], e1[1] - e0[1]
        if moved < 0.05:
            report("FAIL", "Drives", "The wheels turn but the robot does not move: are the wheels touching the floor? "
                                     "Check each wheel's translation z = 0.0325 and its boundingObject + physics.")
        elif along < 0:
            report("FAIL", f"Drives forward (it went {moved:.2f} m BACKWARDS)",
                   "Forward wheel speed must move the robot along +x. Flip the axis of both wheels' HingeJoint (0 1 0 -> 0 -1 0) "
                   "- on the real robot you would swap the motor wires or set invert: true.")
        else:
            report("PASS", f"Drives forward {along:.2f} m")
            rad = (dl + dr) / 2
            radius = along / rad if rad else 0
            ok = abs(radius - 0.0325) < 0.004
            report("PASS" if ok else "FAIL", f"Wheel size from encoders: {radius * 2000:.0f} mm (config.yaml: 65 mm)",
                   "" if ok else "Wheel radius must be 0.0325 in the Cylinder and the joint anchor, or change wheel_diameter_m.")
        if dl * dr <= 0:
            report("FAIL", "Both encoders count forward", f"left {dl:+.1f} rad, right {dr:+.1f} rad: one wheel is reversed "
                                                           "or its sensor sits on the other joint.")
        y0 = imu.getRollPitchYaw()[2] if imu else math.atan2(R[3], R[0])
        e0 = (ls.getValue(), rs.getValue())
        lm.setVelocity(-3.0)
        rm.setVelocity(3.0)
        step(secs(1.0))
        lm.setVelocity(0.0)
        rm.setVelocity(0.0)
        step(secs(0.4))
        R = me.getOrientation()
        y1 = imu.getRollPitchYaw()[2] if imu else math.atan2(R[3], R[0])
        dyaw = (y1 - y0 + math.pi) % (2 * math.pi) - math.pi
        if dyaw <= 0.05:
            report("FAIL", "Turns left when the right wheel drives faster",
                   "It turned right: the left and right wheels are swapped. Swap the names \"left ...\" / \"right ...\" "
                   "or the y of the two wheels (+0.075 is left).")
        else:
            e1 = (ls.getValue(), rs.getValue())
            track = ((e1[1] - e0[1]) - (e1[0] - e0[0])) * 0.0325 / dyaw
            ok = abs(track - 0.15) < 0.04
            report("PASS", f"Turns left ({math.degrees(dyaw):.0f} deg)")
            report("PASS" if ok else "FAIL", f"Wheel spacing from the turn: about {track * 100:.0f} cm (config.yaml: 15 cm; a little more is normal wheel slip)",
                   "" if ok else "Put the wheels at y = +0.075 and -0.075, or change wheel_base_m in config.yaml.")
    else:
        report("NOT YET", "Driving tests", "Need both wheel motors and encoders (step 3).")

    # --- does not tip over on a hard stop (tall mast!)
    if lm and rm and imu:
        lm.setVelocity(15.0)
        rm.setVelocity(15.0)
        step(secs(0.8))
        lm.setVelocity(0.0)
        rm.setVelocity(0.0)
        worst = 0.0
        for _ in range(secs(1.0)):
            step()
            r, p, _ = imu.getRollPitchYaw()
            worst = max(worst, math.degrees(max(abs(r), abs(p))))
        okt = worst < 20
        report("PASS" if okt else "FAIL", f"Stays upright after an emergency stop at full speed (leans {worst:.0f} deg)",
               "" if okt else "Too top-heavy: keep the battery low and centred, and lower centerOfMass in the Robot physics.")

    if spk is not None:
        spk.speak("Raqib parts check complete.", 1.0)
        step(secs(2.0))
        report("PASS", "Speaker said \"Raqib parts check complete\"")

    if me is not None and z0 is not None:
        me.getField("translation").setSFVec3f([0, 0, z0])
        me.getField("rotation").setSFRotation([0, 0, 1, 0])
        me.resetPhysics()
        step(2)

    n_pass = sum(1 for s, _ in results if s == "PASS")
    n_fail = sum(1 for s, _ in results if s == "FAIL")
    n_todo = sum(1 for s, _ in results if s == "NOT YET")
    print(f"\n{GREEN}{n_pass} passed{END}, {RED}{n_fail} failed{END}, {YELLOW}{n_todo} not built yet{END}")
    if not n_fail and not n_todo:
        print("Your robot is complete. Next: put it in the campus (guide step 11) and drive it from the app.")
    print("The robot was put back on the start mark.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"\n{RED}{e}{END}")
        sys.exit(1)
