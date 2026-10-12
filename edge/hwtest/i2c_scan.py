"""Step 1 - check that every I2C device answers.   python -m hwtest.i2c_scan"""
from . import real_cfg

EXPECTED = {
    "pca9685_address": "PCA9685 PWM (motors + servos)",
    "mpu6050_address": "MPU6050 IMU",
    "bme680_address": "BME680 climate/gas",
    "ads1115_address": "ADS1115 ADC (MQ-135)",
    "ups_ina219_address": "UPS hat battery gauge (INA219)",
}


def main():
    from smbus2 import SMBus

    hw = real_cfg()["hardware"]
    found = []
    with SMBus(int(hw.get("i2c_bus", 1))) as bus:
        for addr in range(0x03, 0x78):
            try:
                bus.read_byte(addr)
                found.append(addr)
            except OSError:
                pass
    print("Devices found:", " ".join(hex(a) for a in found) or "none")
    ok = True
    for key, name in EXPECTED.items():
        addr = hw.get(key)
        if addr is None:
            continue
        status = "OK " if addr in found else "MISSING"
        ok &= addr in found
        print(f"  [{status}] {name:35s} at {hex(addr)}")
    print("\nAll expected devices present." if ok else "\nCheck wiring/addresses in config.yaml (hardware: section).")


if __name__ == "__main__":
    main()
