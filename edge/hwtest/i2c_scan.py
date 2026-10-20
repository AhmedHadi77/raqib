"""Step 1 - check that every I2C device answers.   python -m hwtest.i2c_scan
Works for both builds: budget (AHT20, no PCA9685) and full (BME680, PCA9685, UPS gauge)."""
from . import real_cfg

NAMES = {0x38: "AHT20 temperature/humidity (budget build)", 0x40: "PCA9685 PWM (full build: motors + servos)",
         0x48: "ADS1115 ADC (only if you fitted the MQ-135 gas upgrade)", 0x68: "MPU6050 motion sensor",
         0x76: "BME680 or BMP280 (climate / pressure)", 0x77: "BME680 or BMP280 (climate / pressure)"}


def esp32_scan(cfg):
    """The ESP32 checks its own I2C bus: ask it what answers."""
    from robot.hal.esp32 import _get_json, resolve_host

    host = resolve_host(cfg["hardware"].get("esp32_host", "auto"))
    s = _get_json(host, "/status") if host else None
    if not s:
        print("The ESP32 robot is not answering on Wi-Fi. Is it on (power bank) and on the same Wi-Fi as this PC?")
        return
    print(f"ESP32 robot at {host}, firmware {s.get('fw')}, Wi-Fi {s.get('ssid')}")
    for name, ok in (("MPU6050 motion sensor (0x68)", s.get("imu_ok")), ("AHT20 temperature/humidity (0x38)", s.get("aht_ok")),
                     ("BMP280 air pressure (0x77/0x76)", s.get("bmp_ok"))):
        print(f"  [{'OK ' if ok else 'MISSING'}] {name}")
    if not (s.get("imu_ok") and s.get("aht_ok")):
        print("\nMissing parts: VCC to 3V3, GND to GND, SDA to D4, SCL to D5 (both boards share these four wires).")


def main():
    cfg = real_cfg()
    if str(cfg["hardware"].get("board", "esp32")).lower() == "esp32":
        return esp32_scan(cfg)
    from smbus2 import SMBus

    hw = cfg["hardware"]
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
    need = {"MPU6050 (0x68)": 0x68 in found,
            "climate sensor (AHT20 0x38 or BME680 0x76/0x77)": bool({0x38, 0x76, 0x77} & set(found))}
    print()
    for name, ok in need.items():
        print(f"  [{'OK ' if ok else 'MISSING'}] {name}")
    print("\nMotor speed:", "PCA9685 (full build)" if 0x40 in found else "Pi GPIO 13 / 19 (budget build, no PCA9685)")
    print("All required devices present." if all(need.values()) else "Check SDA (pin 3), SCL (pin 5), 3.3 V and GND.")


if __name__ == "__main__":
    main()
