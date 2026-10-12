"""Find the Raqib server on the local network (used when config says `mqtt: host: auto`).

The backend broadcasts a small JSON beacon on UDP port 47800 every 2 s (backend/app/discovery.py).
We listen for it, take the sender's IP address as the MQTT broker, and remember it in
~/.raqib_server.json so the next boot can try it straight away.
"""
from __future__ import annotations

import json
import logging
import socket
import time
from pathlib import Path

log = logging.getLogger(__name__)
DISCOVERY_PORT = 47800
CACHE_FILE = Path.home() / ".raqib_server.json"


def is_auto(host) -> bool:
    return host is None or str(host).strip().lower() in ("", "auto", "discover")


def parse_beacon(data: bytes, sender_ip: str) -> dict | None:
    try:
        p = json.loads(data.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(p, dict) or p.get("service") != "raqib":
        return None
    return {"host": p.get("mqtt_host") or sender_ip, "port": int(p.get("mqtt_port") or 1883),
            "api": f"http://{sender_ip}:{int(p.get('api_port') or 8000)}", "site": p.get("site"),
            "tls": bool(p.get("tls")), "seen": time.time()}


def listen(timeout_s: float = 10.0, port: int = DISCOVERY_PORT, stop=None) -> dict | None:
    """Wait up to timeout_s for a beacon. Returns {"host","port","api",...} or None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        s.bind(("", port))
        end = time.time() + timeout_s
        while time.time() < end and not (stop and stop.is_set()):
            s.settimeout(max(0.1, min(1.0, end - time.time())))
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                continue
            found = parse_beacon(data, addr[0])
            if found:
                return found
    except OSError as e:
        log.warning("Discovery: cannot listen on UDP %s (%s)", port, e)
    finally:
        s.close()
    return None


def load_cache() -> dict | None:
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:  # noqa: BLE001
        return None


def save_cache(found: dict) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(found))
    except Exception:  # noqa: BLE001
        pass
