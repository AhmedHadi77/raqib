"""Step 4 - climate sensor (AHT20 or BME680) + MQ-135.

python -m hwtest.test_env                  # live readings + verdicts
python -m hwtest.test_env --burn-in        # 5 min in clean air -> prints gas_baseline_ohm for config.yaml
python -m hwtest.test_env --calibrate-mq135  # clean outdoor air (~420 ppm) -> prints mq135_r0
"""
import argparse
import time

from . import real_cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--burn-in", action="store_true")
    ap.add_argument("--calibrate-mq135", action="store_true")
    args = ap.parse_args()
    cfg = real_cfg()
    from robot.environmental_sensor import MQ135_A, MQ135_B, EnvironmentalSensor
    from robot.hal import create_hardware

    hw = create_hardware(cfg)
    try:
        if args.burn_in:
            if hw.env.read().gas_resistance_ohm is None:
                print("Burn-in is only for the BME680 gas sensor. Budget build (AHT20): nothing to do.")
                return
            vals = []
            t_end = time.time() + 300
            while time.time() < t_end:
                r = hw.env.read()
                if r.gas_resistance_ohm:
                    vals.append(r.gas_resistance_ohm)
                print(f"{int(t_end-time.time()):4d}s left  gas={r.gas_resistance_ohm}", end="\r")
                time.sleep(1)
            base = sum(vals[-50:]) / len(vals[-50:])
            print(f"\nSet environment.gas_baseline_ohm: {base:.0f}")
            return
        if args.calibrate_mq135:
            if not hw.env.read().mq135_volts:
                print("No MQ-135 fitted (reliable budget build): nothing to calibrate.")
                return
            rl = float(cfg["hardware"].get("mq135_load_resistor_kohm", 10))
            vs = []
            for _ in range(60):
                v = hw.env.read().mq135_volts
                if v:
                    vs.append(v)
                time.sleep(1)
            v = sum(vs) / len(vs)
            rs = rl * (5.0 - v) / v
            r0 = rs / ((420.0 / MQ135_A) ** (1 / MQ135_B))
            print(f"Set environment.mq135_r0: {r0:.2f}")
            return
        env = EnvironmentalSensor(hw, cfg)
        while True:
            time.sleep(2)
            print(env.current())
    except KeyboardInterrupt:
        pass
    finally:
        hw.close()


if __name__ == "__main__":
    main()
