# Raqib robot check on a Raspberry Pi Pico in Wokwi - the same tests as hwtest on the real robot.
# Wiring: see the Raqib Wokwi guide (diagram.json in this folder has every wire).
from machine import ADC, I2C, PWM, Pin, time_pulse_us
import struct
import time

print("Raqib robot check")

# ---- I2C bus (like: python -m hwtest.i2c_scan)
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
print("I2C devices:", [hex(a) for a in i2c.scan()], "(MPU6050 = 0x68)")

# ---- MPU6050 motion sensor
i2c.writeto_mem(0x68, 0x6B, b"\x00")                 # wake it up
ax, ay, az, temp, gx, gy, gz = struct.unpack(">hhhhhhh", i2c.readfrom_mem(0x68, 0x3B, 14))
print("IMU accel g: %.2f %.2f %.2f   gyro deg/s: %.1f %.1f %.1f" % (ax / 16384, ay / 16384, az / 16384, gx / 131, gy / 131, gz / 131))

# ---- ultrasonic sensors (like: python -m hwtest.test_sensors)
SONARS = {"left": (12, 13), "center": (10, 11), "right": (8, 9)}      # (TRIG, ECHO)
sonar = {k: (Pin(t, Pin.OUT, value=0), Pin(e, Pin.IN)) for k, (t, e) in SONARS.items()}


def distance_cm(trig, echo):
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    us = time_pulse_us(echo, 1, 30000)                # echo pulse length; 58 us per cm
    return 400 if us < 0 else round(us / 58)


print("Distances cm:", {k: distance_cm(*p) for k, p in sonar.items()})

# ---- servos (pan / tilt)
pan, tilt = PWM(Pin(14)), PWM(Pin(15))
for s in (pan, tilt):
    s.freq(50)


def angle(servo, deg):                                # 0..180 deg -> 500..2400 us, as in config.yaml
    servo.duty_ns(int((500 + 1900 * deg / 180) * 1000))


for a in (90, 30, 150, 90):
    angle(pan, a)
    angle(tilt, 90 + (a - 90) // 3)
    time.sleep(0.6)
print("Servos swept")

# ---- L298N motor driver (like: python -m hwtest.test_motors)
ena, enb = PWM(Pin(16)), PWM(Pin(21))
for en in (ena, enb):
    en.freq(1000)
in1, in2, in3, in4 = [Pin(n, Pin.OUT, value=0) for n in (17, 18, 19, 20)]


def wheels(left, right):                              # -1..1, like set_wheels() in the robot software
    for en, a, b, v in ((ena, in1, in2, left), (enb, in3, in4, right)):
        a.value(1 if v > 0 else 0)
        b.value(1 if v < 0 else 0)
        en.duty_u16(int(min(1, abs(v)) * 65535))


for left, right, what in ((0.8, 0.8, "forward"), (-0.8, -0.8, "back"), (-0.6, 0.6, "turn left"), (0, 0, "stop")):
    print("Motors:", what)
    wheels(left, right)
    time.sleep(1.5)

# ---- wheel encoders (turn the KY-040 knobs while this runs)
counts = {"left": 0, "right": 0}


def counter(name):
    def irq(_pin):
        counts[name] += 1
    return irq


enc_l = Pin(6, Pin.IN, Pin.PULL_UP)
enc_r = Pin(7, Pin.IN, Pin.PULL_UP)
enc_l.irq(counter("left"), Pin.IRQ_FALLING)
enc_r.irq(counter("right"), Pin.IRQ_FALLING)

# ---- gas sensor (analog) and speaker
gas = ADC(26)
speaker = PWM(Pin(22))
speaker.freq(880)
speaker.duty_u16(20000)
time.sleep(0.3)
speaker.duty_u16(0)
print("Speaker beeped")

M_PER_TICK = 3.1416 * 0.065 / 20                      # 65 mm wheel, 20-slot encoder disc
while True:
    volts = gas.read_u16() * 3.3 / 65535
    print("encoders", counts, "left %.2f m" % (counts["left"] * M_PER_TICK),
          "| gas %.2f V" % volts, "| front", distance_cm(*sonar["center"]), "cm")
    time.sleep(1)
