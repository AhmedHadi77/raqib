"""Step 1 - check that every I2C device answers.   python -m hwtest.i2c_scan
Works for both builds: budget (AHT20, no PCA9685) and full (BME680, PCA9685, UPS gauge)."""
from . import real_cfg

NAMES = {0x38: "AHT20 temperature/humidity (budget build)", 0x40: "PCA9685 PWM (full build: motors + servos)",
         0x48: "ADS1115 ADC (MQ-135 gas + battery voltage)", 0x68: "MPU6050 motion sensor",
         0x76: "BME680 or BMP280 (climate / pressure)", 0x77: "BME680 or BMP280 (climate / pressure)"}


def main():
    from smbus2 import SMBus

    hw = real_cfg()["hardware"]
    ups = hw.get("ups_ina219_address")
    if ups is not None:
        NAMES.setdefault(int(ups), "UPS battery gauge (INA219, full build)")
    found = []
    with SMBus(int(hw.get("i2c_bus", 1))) as bus:
        for addr in range(0x03, 0x78):
            try:
                bus.read_byte(addr)
                found.append(addr)
            except OSError:
                pass
    print("Devices found:", " ".join(hex(a) for a in found) or "none")
    for a in found:
        print(f"  {hex(a)}  {NAMES.get(a, 'unknown device')}")
    need = {"MPU6050 (0x68)": 0x68 in found, "ADS1115 (0x48)": 0x48 in found,
            "climate sensor (AHT20 0x38 or BME680 0x76/0x77)": bool({0x38, 0x76, 0x77} & set(found))}
    print()
    for name, ok in need.items():
        print(f"  [{'OK ' if ok else 'MISSING'}] {name}")
    print("\nMotor speed:", "PCA9685 (full build)" if 0x40 in found else "Pi GPIO 13 / 19 (budget build, no PCA9685)")
    print("All required devices present." if all(need.values()) else "Check SDA (pin 3), SCL (pin 5), 3.3 V and GND.")


if __name__ == "__main__":
    main()
