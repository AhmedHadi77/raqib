"""Step 2 - wheels + pan/tilt.  PUT THE ROBOT ON A BOX SO THE WHEELS ARE IN THE AIR.

python -m hwtest.test_motors              # each side forward/back (wheels in the air)
python -m hwtest.test_motors --deadband   # wheels in the air: find the power where the wheels start to turn
python -m hwtest.test_motors --calibrate  # ON THE FLOOR: drive 3 s, type the distance you measured -> max_speed_mps
python -m hwtest.test_motors --straight 2 # Milestone 2: drive 2 m on the floor, measure drift and distance

The reliable budget build has no wheel encoders: distance = motor power x time, so do --deadband and --calibrate
once (and again if you change wheels, battery or floor). Put the printed values into edge/config.yaml.
"""
import argparse
import time

from . import real_cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--straight", type=float, default=0.0, help="drive this many metres (on the floor)")
    ap.add_argument("--calibrate", action="store_true", help="measure the robot's top speed (on the floor)")
    ap.add_argument("--deadband", action="store_true", help="find the lowest power that turns the wheels")
    args = ap.parse_args()
    cfg = real_cfg()

    if args.deadband:
        from robot.hal import create_hardware

        hw = create_hardware(cfg)
        try:
            print("Wheels in the air. Press Enter after each step; type 'y' + Enter as soon as ALL wheels turn.")
            p = 0.05
            while p <= 0.8:
                hw.motors.set_wheels(p, p)
                ans = input(f"  power {p:.2f}: do both wheels turn? [Enter = no, y = yes] ").strip().lower()
                if ans.startswith("y"):
                    print(f"\nSet in edge/config.yaml:  motion: motor_deadband: {max(0.0, p - 0.05):.2f}   "
                          f"and  min_power: {min(0.6, p + 0.10):.2f}")
                    break
                p = round(p + 0.05, 2)
        finally:
            hw.motors.set_wheels(0, 0)
            hw.close()
        return

    if args.calibrate:
        from robot.app import RobotApp

        app = RobotApp(cfg, connect_mqtt=False)
        app.safety.cloud_timeout = 1e9
        try:
            input("Robot ON THE FLOOR with 3 m of free space in front. Mark the start, then press Enter...")
            app.sensors.max_speed = 1.0                  # measure the model distance per 1 m/s of top speed
            d0 = app.sensors.distance
            t_end = time.monotonic() + 3.0
            while time.monotonic() < t_end and not app.safety.blocked:
                app.motors.set_speed(0.6, 0.6)
                time.sleep(0.05)
            app.motors.stop()
            time.sleep(0.5)
            model = app.sensors.distance - d0
            got = float(input("Distance driven, in cm (measure with a tape): ").strip()) / 100.0
            if model <= 0.01 or got <= 0:
                print("No movement measured - check the motors first (python -m hwtest.test_motors).")
                return
            print(f"\nSet in edge/config.yaml:  motion: max_speed_mps: {got / model:.3f}")
        finally:
            app.shutdown()
        return

    if args.straight:
        from robot.app import RobotApp

        app = RobotApp(cfg, connect_mqtt=False)
        app.safety.cloud_timeout = 1e9
        try:
            print(f"Driving {args.straight} m... measure the distance (target +-10 %) and the sideways drift (< 20 cm)")
            print(app.run_command("move", distance_m=args.straight))
            print("Pose estimate:", app.sensors.pose())
        finally:
            app.shutdown()
        return

    from robot.hal import create_hardware

    hw = create_hardware(cfg)
    try:
        for name, (l, r) in [("LEFT forward", (0.6, 0)), ("LEFT reverse", (-0.6, 0)),
                             ("RIGHT forward", (0, 0.6)), ("RIGHT reverse", (0, -0.6)),
                             ("BOTH forward", (0.6, 0.6)), ("spin left", (-0.6, 0.6))]:
            input(f"Press Enter to test {name}...")
            hw.motors.set_wheels(l, r)
            time.sleep(1.5)
            hw.motors.set_wheels(0, 0)
            if hw.extra.get("encoders"):
                print(f"  encoder ticks now: {hw.encoders.ticks()}")
        print("If a wheel spun the wrong way: swap that motor's two wires, or set invert: true for that motor (hardware: motor_left / motor_right) in config.yaml")
        if hw.extra.get("fixed_camera"):
            print("No pan/tilt servos (budget build): the robot turns its whole body to look around.")
            return
        for pan, tilt in [(0, 0), (-60, 0), (60, 0), (0, 30), (0, -20), (0, 0)]:
            print(f"pan={pan} tilt={tilt}")
            hw.pan_tilt.set_angles(pan, tilt)
            time.sleep(0.8)
    finally:
        hw.close()


if __name__ == "__main__":
    main()
