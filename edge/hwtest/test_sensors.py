"""Step 3 - live view of the ultrasonics and the IMU.   python -m hwtest.test_sensors
Move your hand in front of each HC-SR04 and rotate the robot to see the yaw change.
"""
import time

from . import real_cfg


def main():
    from robot.hal import create_hardware

    hw = create_hardware(real_cfg())
    try:
        while True:
            us = hw.ultrasonics.read_cm()
            imu = hw.imu.read()
            extra = f" | enc={hw.encoders.ticks()}" if hw.extra.get("encoders") else ""
            print(f"US L={us['left']:6.1f} C={us['center']:6.1f} R={us['right']:6.1f} cm | "
                  f"yaw={imu.yaw_deg:7.1f} pitch={imu.pitch_deg:5.1f} roll={imu.roll_deg:5.1f}{extra}", end="\r")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print()
    finally:
        hw.close()


if __name__ == "__main__":
    main()
