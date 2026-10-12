"""Acoustic equipment audit: Edge Impulse model, with a feature-based fallback (risk R7).

Canonical classes (Table 3):
  quiet_room  - Quiet Unoccupied Room
  ac_fan      - Active Air-Conditioner / Exhaust Fan
  crowd       - High Student Crowd Noise
  alarm       - Emergency Alarm / Water Leak
  speech      - People talking (one or a few voices) - used by exam monitoring
  whisper     - Whispering (quiet, breathy, syllable rhythm)
  sudden_noise - A short loud bang, drop or knock
"""
from __future__ import annotations

import logging
import os
import threading
import time

import numpy as np

from .hal.base import Hardware

log = logging.getLogger(__name__)

CLASSES = ["quiet_room", "ac_fan", "crowd", "alarm", "speech", "whisper", "sudden_noise"]
CLASS_TITLES = {
    "quiet_room": "Quiet Unoccupied Room",
    "ac_fan": "Active Air-Conditioner / Exhaust Fan",
    "crowd": "High Student Crowd Noise",
    "alarm": "Emergency Alarm / Water Leak",
    "speech": "People Talking",
    "whisper": "Whispering",
    "sudden_noise": "Sudden Noise",
}


def audio_features(samples: np.ndarray, sr: int) -> dict:
    x = samples.astype(np.float32) / 32768.0
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x ** 2)) + 1e-12)
    dbfs = 20 * np.log10(rms)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1 / sr)
    p = spec ** 2
    peak_i = int(np.argmax(p[1:]) + 1)
    tonality = float(p[peak_i] / (p.mean() + 1e-12))
    centroid = float((freqs * p).sum() / (p.sum() + 1e-12))
    frame = int(0.05 * sr)
    frames = x[: len(x) // frame * frame].reshape(-1, frame) if len(x) >= frame else x.reshape(1, -1)
    fr = np.sqrt((frames ** 2).mean(axis=1)) + 1e-9
    env_cv = float(fr.std() / fr.mean())
    band = (freqs >= 150) & (freqs <= 3400)
    voice_band = float(p[band].sum() / (p.sum() + 1e-12))
    # syllable rhythm: energy envelope modulated at 2-8 Hz is typical of speech
    voice_like = bool(env_cv > 0.25 and voice_band > 0.6 and 150 < centroid < 3000 and dbfs > -60)
    # whisper: unvoiced (breathy, 1-4 kHz) but with the same syllable rhythm
    hiss = (freqs >= 900) & (freqs <= 4500)
    hiss_band = float(p[hiss].sum() / (p.sum() + 1e-12))
    whisper_like = bool(env_cv > 0.3 and hiss_band > 0.55 and 800 < centroid < 4800 and -62 < dbfs < -36
                        and tonality < 200)
    # sudden noise: one short frame far louder than the rest
    crest = float(fr.max() / (np.median(fr) + 1e-9))
    peak_db = float(20 * np.log10(fr.max() + 1e-12))
    loud_frames = int((fr > fr.max() * 10 ** (-12 / 20)).sum())      # frames within 12 dB of the peak
    transient = bool(crest > 8 and peak_db > -35 and loud_frames <= 3)
    return {"rms": rms, "dbfs": float(dbfs), "dominant_hz": float(freqs[peak_i]), "tonality": tonality,
            "centroid_hz": centroid, "envelope_cv": env_cv, "voice_band": voice_band, "voice_like": voice_like,
            "whisper_like": whisper_like, "crest": crest, "peak_dbfs": peak_db, "transient": transient}


def heuristic_classify(f: dict) -> tuple[str, float, dict]:
    """Simple threshold rules - used when no Edge Impulse model is available."""
    if f["tonality"] > 200 and 1500 <= f["dominant_hz"] <= 5000 and f["dbfs"] > -45:
        label, conf = "alarm", 0.85
    elif f.get("transient"):
        label, conf = "sudden_noise", 0.75
    elif f.get("whisper_like") and not f.get("voice_like"):
        label, conf = "whisper", 0.65
    elif f.get("voice_like") and -44 < f["dbfs"] <= -20:
        label, conf = "speech", 0.7          # one or a few voices
    elif f["dbfs"] < -38:
        label, conf = "quiet_room", 0.9
    elif f["envelope_cv"] > 0.2:
        label, conf = "crowd", 0.7
    else:
        label, conf = "ac_fan", 0.75
    scores = {c: (conf if c == label else round((1 - conf) / (len(CLASSES) - 1), 3)) for c in CLASSES}
    return label, conf, scores


class AudioAnalyzer:
    def __init__(self, hw: Hardware, cfg: dict):
        a = cfg.get("audio", {})
        self.hw = hw
        self.sr = int(a.get("sample_rate", 16000))
        self.window_s = float(a.get("window_s", 1.0))
        self.db_offset = float(a.get("db_calibration_offset", 83.0))
        self.label_map = {k.lower(): v for k, v in (a.get("label_map") or {}).items()}
        self.lock = threading.Lock()
        self.latest: dict | None = None
        self.runner = None
        self.model_info = None
        path = a.get("model_path")
        if path and not os.path.isabs(path):
            path = os.path.join(cfg.get("_edge_dir", "."), path)
        if path and os.path.exists(path) and not hw.simulated:
            try:
                from edge_impulse_linux.runner import ImpulseRunner

                os.chmod(path, 0o755)
                self.runner = ImpulseRunner(path)
                self.model_info = self.runner.init()
                params = self.model_info["model_parameters"]
                self.sr = int(params.get("frequency", self.sr))
                log.info("Edge Impulse model loaded: %s (%s Hz, labels=%s)",
                         self.model_info["project"]["name"], self.sr, params.get("labels"))
            except Exception as e:  # noqa: BLE001
                log.warning("Edge Impulse model not usable (%s) - using heuristic classifier", e)
                self.runner = None
        else:
            log.info("Audio: heuristic classifier (no Edge Impulse model at %s)", path)

    def _map(self, label: str) -> str:
        return self.label_map.get(label.lower(), label.lower())

    def listen(self, seconds: float | None = None) -> dict:
        seconds = float(seconds or self.window_s)
        with self.lock:
            samples = self.hw.microphone.record(seconds, self.sr)
            f = audio_features(samples, self.sr)
            method = "heuristic"
            if self.runner is not None:
                try:
                    need = int(self.model_info["model_parameters"]["input_features_count"])
                    feats = samples[:need]
                    if len(feats) < need:
                        feats = np.pad(feats, (0, need - len(feats)))
                    res = self.runner.classify(feats.astype(int).tolist())
                    raw = res["result"]["classification"]
                    scores: dict[str, float] = {}
                    for k, v in raw.items():
                        scores[self._map(k)] = max(scores.get(self._map(k), 0.0), float(v))
                    label = max(scores, key=scores.get)
                    conf = scores[label]
                    method = "edge_impulse"
                except Exception as e:  # noqa: BLE001
                    log.warning("Edge Impulse classify failed (%s) - heuristic fallback", e)
                    label, conf, scores = heuristic_classify(f)
            else:
                label, conf, scores = heuristic_classify(f)
            result = {
                "label": label,
                "title": CLASS_TITLES.get(label, label),
                "confidence": round(conf, 3),
                "scores": {k: round(v, 3) for k, v in scores.items()},
                "db": round(f["dbfs"] + self.db_offset, 1),
                "dominant_hz": round(f["dominant_hz"], 1),
                "voice_like": f["voice_like"] or label == "speech",
                "whisper": label == "whisper",
                "sudden": label == "sudden_noise",
                "peak_db": round(f["peak_dbfs"] + self.db_offset, 1),
                "envelope_cv": round(f["envelope_cv"], 3),
                "method": method,
                "duration_s": seconds,
                "ts": time.time(),
            }
            self.latest = result
            return result

    def close(self):
        if self.runner is not None:
            try:
                self.runner.stop()
            except Exception:  # noqa: BLE001
                pass
