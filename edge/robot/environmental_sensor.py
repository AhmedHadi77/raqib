"""BME680 / MQ-135 polling + thermal-comfort and gas-safety classification.

Classification (Table 3 of the proposal):
  overall = COMFORTABLE_SAFE | THERMALLY_UNCOMFORTABLE | POOR_AIR_QUALITY
  comfort_verdict = COMFORTABLE | UNCOMFORTABLE_HOT_HUMID | UNCOMFORTABLE_HOT | UNCOMFORTABLE_HUMID
                    | UNCOMFORTABLE_COLD | OVERCOOLED_ENERGY_WASTE | UNCOMFORTABLE_DRY
  gas_verdict = NORMAL | ELEVATED | WARNING | HAZARD
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

from .hal.base import Hardware

log = logging.getLogger(__name__)

MQ135_A, MQ135_B = 116.6020682, -2.769034857  # CO2-equivalent curve


def estimate_aqi(gas_ohm: float | None, humidity: float, baseline_ohm: float | None) -> float | None:
    """BME680 gas resistance + humidity -> indoor air quality index (0 good .. 500 hazardous).

    Same scoring idea as the Pimoroni/Bosch examples: 25 % humidity score + 75 % gas score.
    """
    if gas_ohm is None or not baseline_ohm:
        return None
    hum_baseline, hum_weight = 40.0, 0.25
    hum_offset = humidity - hum_baseline
    if hum_offset > 0:
        hum_score = (100 - hum_baseline - hum_offset) / (100 - hum_baseline) * (hum_weight * 100)
    else:
        hum_score = (hum_baseline + hum_offset) / hum_baseline * (hum_weight * 100)
    hum_score = max(0.0, hum_score)
    if gas_ohm < baseline_ohm:
        gas_score = (gas_ohm / baseline_ohm) * (100 - hum_weight * 100)
    else:
        gas_score = 100 - hum_weight * 100
    score = max(0.0, min(100.0, hum_score + gas_score))
    return round((100.0 - score) * 5.0, 1)


def aqi_from_ppm(ppm: float | None) -> float | None:
    """Budget build (no BME680 gas sensor): an air-quality index from the MQ-135 CO2-equivalent ppm, scaled so the
    MQ-135 warning (1000 ppm) and hazard (2000 ppm) levels line up with AQI 150 and 300."""
    if ppm is None:
        return None
    pts = [(400.0, 25.0), (1000.0, 150.0), (2000.0, 300.0), (4000.0, 500.0)]
    if ppm <= pts[0][0]:
        return round(max(0.0, pts[0][1] * ppm / pts[0][0]), 1)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if ppm <= x1:
            return round(y0 + (ppm - x0) * (y1 - y0) / (x1 - x0), 1)
    return 500.0


def mq135_ppm(volts: float | None, r0_kohm: float, rl_kohm: float = 10.0, vcc: float = 5.0) -> float | None:
    if volts is None or volts <= 0.01:
        return None
    rs = rl_kohm * (vcc - volts) / volts
    return round(MQ135_A * (rs / r0_kohm) ** MQ135_B, 1)


def aqi_label(aqi: float | None) -> str:
    if aqi is None:
        return "Unknown"
    for limit, label in ((50, "Good"), (100, "Moderate"), (150, "Unhealthy for Sensitive Groups"),
                         (200, "Unhealthy"), (300, "Very Unhealthy")):
        if aqi <= limit:
            return label
    return "Hazardous"


def classify(temp_c: float, rh: float, aqi: float | None, ppm: float | None, cfg: dict,
             occupied: bool | None = None) -> dict:
    t_lo, t_hi = cfg.get("comfort_temp_c", [22.0, 26.0])
    h_lo, h_hi = cfg.get("comfort_rh_pct", [40.0, 60.0])
    over_c = float(cfg.get("overcooled_below_c", 20.0))

    hot, humid = temp_c > t_hi, rh > h_hi
    if hot and humid:
        comfort = "UNCOMFORTABLE_HOT_HUMID"
    elif hot:
        comfort = "UNCOMFORTABLE_HOT"
    elif temp_c < t_lo:
        comfort = "OVERCOOLED_ENERGY_WASTE" if temp_c < over_c and occupied is not True else "UNCOMFORTABLE_COLD"
    elif humid:
        comfort = "UNCOMFORTABLE_HUMID"
    elif rh < h_lo:
        comfort = "UNCOMFORTABLE_DRY"
    else:
        comfort = "COMFORTABLE"

    gas = "NORMAL" if (aqi is not None or ppm is not None) else "NOT_MEASURED"   # no gas sensor fitted
    a_el, a_w, a_h = cfg.get("aqi_elevated", 100), cfg.get("aqi_warning", 150), cfg.get("aqi_hazard", 300)
    p_w, p_h = cfg.get("mq135_warning_ppm", 1000), cfg.get("mq135_hazard_ppm", 2000)
    if (aqi is not None and aqi > a_h) or (ppm is not None and ppm > p_h):
        gas = "HAZARD"
    elif (aqi is not None and aqi > a_w) or (ppm is not None and ppm > p_w):
        gas = "WARNING"
    elif aqi is not None and aqi > a_el:
        gas = "ELEVATED"

    if gas in ("WARNING", "HAZARD"):
        overall = "POOR_AIR_QUALITY"
    elif comfort != "COMFORTABLE":
        overall = "THERMALLY_UNCOMFORTABLE"
    else:
        overall = "COMFORTABLE_SAFE"
    return {"comfort_verdict": comfort, "gas_verdict": gas, "overall": overall}


class EnvironmentalSensor:
    """Polls the module, keeps a sliding average and handles warm-up per inspection stop."""

    def __init__(self, hw: Hardware, cfg: dict, on_alert=None):
        self.hw = hw
        self.cfg = cfg.get("environment", {})
        self.rl = float(cfg.get("hardware", {}).get("mq135_load_resistor_kohm", 10.0))
        self.warmup_s = float(self.cfg.get("sim_warmup_s" if hw.simulated else "warmup_s", 20))
        self.window = deque(maxlen=int(self.cfg.get("window", 10)))
        self.baseline = self.cfg.get("gas_baseline_ohm") or hw.extra.get("gas_baseline_ohm")
        self._auto_baseline = self.baseline is None
        self.ready_at = time.monotonic() + self.warmup_s
        self.on_alert = on_alert
        self.lock = threading.Lock()
        self.latest: dict | None = None
        self._last_gas_verdict = "NORMAL"
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, name="env", daemon=True)
        self._t.start()

    # ------------------------------------------------------------------
    def begin_stop(self):
        """Call when the robot arrives at a new inspection stop: restart warm-up + averaging."""
        with self.lock:
            self.window.clear()
            self.ready_at = time.monotonic() + self.warmup_s

    def _loop(self):
        period = 1.0 / float(self.cfg.get("poll_hz", 1))
        if self.hw.simulated:
            period = min(period, 0.25)
        while not self._stop.is_set():
            try:
                raw = self.hw.env.read()
                if self._auto_baseline and raw.gas_resistance_ohm:
                    # clean air has the highest resistance: track the max, decaying slowly
                    self.baseline = max(raw.gas_resistance_ohm, (self.baseline or 0) * 0.9999)
                with self.lock:
                    self.window.append(raw)
                self._update()
                if not self.hw.health.get("environment", {}).get("ok", True):
                    self.hw.set_health("environment", True, "reading again")
                self._fails = 0
            except Exception as e:  # noqa: BLE001
                self._fails = getattr(self, "_fails", 0) + 1
                if self._fails in (1, 30) or self._fails % 600 == 0:
                    log.warning("environment read failed: %s", e)
                if self._fails >= 3:
                    self.hw.set_health("environment", False, str(e)[:160])
            self._stop.wait(period)

    def _update(self):
        with self.lock:
            samples = list(self.window)
            warmed = time.monotonic() >= self.ready_at
        if not samples:
            return
        n = len(samples)
        t = sum(s.temperature_c for s in samples) / n
        h = sum(s.humidity_pct for s in samples) / n
        p = sum(s.pressure_hpa for s in samples) / n
        gases = [s.gas_resistance_ohm for s in samples if s.gas_resistance_ohm]
        gas = sum(gases) / len(gases) if gases else None
        mqs = [s.mq135_volts for s in samples if s.mq135_volts]
        mqv = sum(mqs) / len(mqs) if mqs else None
        aqi = estimate_aqi(gas, h, self.baseline)
        ppm = mq135_ppm(mqv, float(self.cfg.get("mq135_r0", 76.63)), self.rl)
        if aqi is None and gas is None:
            aqi = aqi_from_ppm(ppm)
        verdicts = classify(t, h, aqi, ppm, self.cfg)
        reading = {
            "temperature_c": round(t, 2),
            "humidity_pct": round(h, 1),
            "pressure_hpa": round(p, 1),
            "gas_resistance_ohm": round(gas) if gas else None,
            "aqi": aqi,
            "aqi_label": aqi_label(aqi),
            "mq135_ppm": ppm,
            "warmed_up": warmed,
            "samples": n,
            **verdicts,
        }
        with self.lock:
            self.latest = reading
        if warmed and self.on_alert and verdicts["gas_verdict"] in ("WARNING", "HAZARD") \
                and verdicts["gas_verdict"] != self._last_gas_verdict:
            self.on_alert(reading)
        if warmed:
            self._last_gas_verdict = verdicts["gas_verdict"]

    def current(self) -> dict | None:
        with self.lock:
            return dict(self.latest) if self.latest else None

    def read_settled(self, timeout: float | None = None, occupied: bool | None = None) -> dict:
        """Block until warm-up is over (or timeout), then return the averaged reading."""
        deadline = time.monotonic() + (timeout if timeout is not None else self.warmup_s + 5)
        while time.monotonic() < deadline:
            r = self.current()
            if r and r["warmed_up"] and r["samples"] >= min(3, self.window.maxlen):
                break
            time.sleep(0.1)
        r = self.current() or {}
        if r and occupied is not None:
            r.update(classify(r["temperature_c"], r["humidity_pct"], r.get("aqi"), r.get("mq135_ppm"),
                              self.cfg, occupied))
        return r

    def close(self):
        self._stop.set()
