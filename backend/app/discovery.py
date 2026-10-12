"""Zero-config discovery: the server announces itself on the local network.

Every 2 s the backend sends a small UDP broadcast ("beacon") on port 47800. A robot whose config says
`mqtt: host: auto` listens for it and connects to the sender's address, so nobody has to type the PC's IP
into the Raspberry Pi. The beacon carries no secrets: only the service name, ports and site name.
"""
from __future__ import annotations

import asyncio
import json
import logging
import socket

log = logging.getLogger(__name__)
DISCOVERY_PORT = 47800


def local_ipv4s() -> list[str]:
    """IPv4 addresses of this machine (not loopback), primary one first."""
    ips: list[str] = []
    try:  # the address the OS would use to reach the internet / LAN (no packet is sent)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    out = []
    for ip in ips:
        if ip and not ip.startswith("127.") and not ip.startswith("169.254.") and ip not in out:
            out.append(ip)
    return out


def broadcast_targets() -> list[str]:
    """Global broadcast plus the /24 broadcast of every local address (Windows only sends 255.255.255.255
    out of one adapter, so the directed ones make it work with VirtualBox / WSL / VPN adapters present)."""
    targets = ["255.255.255.255"]
    for ip in local_ipv4s():
        b = ".".join(ip.split(".")[:3] + ["255"])
        if b not in targets:
            targets.append(b)
    return targets


def beacon_payload(settings, api_port: int = 8000) -> dict:
    p = {"service": "raqib", "v": 1, "site": settings.site_name, "api_port": api_port,
         "mqtt_port": settings.mqtt_port, "tls": bool(settings.mqtt_tls), "robot_id": settings.robot_id,
         "addresses": local_ipv4s()}
    host = (settings.mqtt_host or "").strip()
    if not settings.embedded_broker and host not in ("", "localhost", "127.0.0.1", "0.0.0.0", "mosquitto"):
        p["mqtt_host"] = host       # the broker lives elsewhere (cloud VM): tell the robot where
    return p


def send_beacon(payload: dict, targets: list[str], port: int = DISCOVERY_PORT) -> int:
    data = json.dumps(payload).encode()
    sent = 0
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for t in targets:
            try:
                s.sendto(data, (t, port))
                sent += 1
            except OSError:
                pass
    finally:
        s.close()
    return sent


async def beacon_loop(settings, api_port: int = 8000, interval_s: float = 2.0, port: int = DISCOVERY_PORT):
    log.info("Announcing the server on the local network (UDP %s) so robots find it automatically", port)
    warned = False
    while True:
        try:
            n = await asyncio.to_thread(send_beacon, beacon_payload(settings, api_port), broadcast_targets(), port)
            if n == 0 and not warned:
                log.warning("Discovery beacon could not be sent (no network?) - robots need mqtt.host set by hand")
                warned = True
        except Exception:  # noqa: BLE001
            log.debug("beacon failed", exc_info=True)
        await asyncio.sleep(interval_s)
