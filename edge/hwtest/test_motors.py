"""Step 2 - wheels + pan/tilt.  PUT THE ROBOT ON A BOX SO THE WHEELS ARE IN THE AIR.

python -m hwtest.test_motors            # each wheel forward/back, then servos
python -m hwtest.test_motors --straight 5   # Milestone 2: drive 5 m on the floor, measure drift
"""
import argparse
import time

from . import real_cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--straight", type=float, default=0.0, help="drive this many metres (on the floor)")
    args = ap.parse_args()
    cfg = real_cfg()

    if args.straight:
        from robot.app import RobotApp

        app = RobotApp(cfg, connect_mqtt=False)
        app.safety.cloud_timeout = 1e9
        try:
            print(f"Driving {args.straight} m... measure the sideways drift (target < 20 cm)")
            print(app.run_command("move", distance_m=args.straight))
            print("Pose estimate:", app.sensors.pose())
        finally:
            app.shutdown()
        return

    from robot.hal.real import create_real_hardware

    hw = create_real_hardware(cfg)
    try:
        for name, (l, r) in [("LEFT forward", (0.6, 0)), ("LEFT reverse", (-0.6, 0)),
                             ("RIGHT forward", (0, 0.6)), ("RIGHT reverse", (0, -0.6)),
                             ("BOTH forward", (0.6, 0.6)), ("spin left", (-0.6, 0.6))]:
            input(f"Press Enter to test {name}...")
            t0 = hw.encoders.ticks()
            hw.motors.set_wheels(l, r)
            time.sleep(1.5)
            hw.motors.stop()
            t1 = hw.encoders.ticks()
            print(f"  encoder ticks: left +{t1[0]-t0[0]}  right +{t1[1]-t0[1]}")
        print("If a wheel spun the wrong way set invert: true for that motor in config.yaml")
        for pan, tilt in [(0, 0), (-60, 0), (60, 0), (0, 30), (0, -20), (0, 0)]:
            print(f"pan={pan} tilt={tilt}")
            hw.pan_tilt.set_angles(pan, tilt)
            time.sleep(0.8)
    finally:
        hw.close()


if __name__ == "__main__":
    main()
