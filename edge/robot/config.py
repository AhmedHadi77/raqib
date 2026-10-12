"""Configuration loading for the edge application."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

EDGE_DIR = Path(__file__).resolve().parent.parent


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | os.PathLike | None = None, overrides: dict | None = None) -> dict[str, Any]:
    """Load config.yaml (+ optional config.local.yaml next to it) and env overrides.

    Environment overrides (handy for Docker):
      ROBOT_ID, ROBOT_SIMULATION=true/false, MQTT_HOST, MQTT_PORT, MQTT_USERNAME,
      MQTT_PASSWORD, MQTT_TLS=true/false, MQTT_CA_CERT
    """
    cfg_path = Path(path) if path else EDGE_DIR / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    local = cfg_path.with_name("config.local.yaml")
    if local.exists():
        with open(local, "r", encoding="utf-8") as f:
            loc = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, loc)
        if loc.get("zones"):
            cfg["zones"] = loc["zones"]   # your building's rooms REPLACE the sample rooms

    env = os.environ
    if "ROBOT_ID" in env:
        cfg["robot_id"] = env["ROBOT_ID"]
    if "ROBOT_SIMULATION" in env:
        cfg["simulation"] = env["ROBOT_SIMULATION"].lower() in ("1", "true", "yes")
    m = cfg.setdefault("mqtt", {})
    for key, envname, cast in [
        ("host", "MQTT_HOST", str),
        ("port", "MQTT_PORT", int),
        ("username", "MQTT_USERNAME", str),
        ("password", "MQTT_PASSWORD", str),
        ("ca_cert", "MQTT_CA_CERT", str),
    ]:
        if envname in env:
            m[key] = cast(env[envname])
    if "MQTT_TLS" in env:
        m["tls"] = env["MQTT_TLS"].lower() in ("1", "true", "yes")

    if overrides:
        cfg = _deep_merge(cfg, overrides)

    if cfg.get("simulator") == "webots":         # face each room's equipment wall when inspecting in Webots
        for z, h in ((cfg.get("webots") or {}).get("view_headings") or {}).items():
            if z in cfg.get("zones", {}) and "view_heading" not in cfg["zones"][z]:
                cfg["zones"][z]["view_heading"] = h
    cfg["_edge_dir"] = str(EDGE_DIR)
    return cfg


def load_sim_world(path: str | os.PathLike | None = None) -> dict[str, Any]:
    p = Path(path) if path else EDGE_DIR / "sim_world.yaml"
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
