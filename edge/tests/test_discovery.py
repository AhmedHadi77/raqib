"""Zero-config: a robot with mqtt.host=auto finds the server from its UDP beacon and connects."""
import asyncio
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from robot import discovery
from robot.config import load_config
from robot.mqtt_client import RobotMqttClient

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def _free_port(kind=socket.SOCK_STREAM):
    s = socket.socket(socket.AF_INET, kind)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_parse_beacon_uses_sender_address_unless_broker_is_elsewhere():
    b = b'{"service":"raqib","mqtt_port":1883,"api_port":8000,"site":"Lab"}'
    assert discovery.parse_beacon(b, "192.168.1.50")["host"] == "192.168.1.50"
    b2 = b'{"service":"raqib","mqtt_port":8883,"mqtt_host":"broker.example.com"}'
    assert discovery.parse_beacon(b2, "192.168.1.50")["host"] == "broker.example.com"
    assert discovery.parse_beacon(b'{"service":"other"}', "1.2.3.4") is None
    assert discovery.parse_beacon(b"not json", "1.2.3.4") is None
    assert discovery.is_auto("auto") and discovery.is_auto("") and not discovery.is_auto("192.168.1.5")


def test_backend_beacon_is_heard_by_the_robot():
    sys.path.insert(0, str(BACKEND))
    from app import discovery as server_disc  # noqa: E402

    class S:
        site_name, mqtt_port, mqtt_tls, robot_id, mqtt_host, embedded_broker = "Lab", 1883, False, "robot01", "localhost", True

    port = _free_port(socket.SOCK_DGRAM)
    got = {}
    t = threading.Thread(target=lambda: got.update(discovery.listen(5, port) or {}))
    t.start()
    time.sleep(0.3)
    for _ in range(5):
        server_disc.send_beacon(server_disc.beacon_payload(S), ["127.0.0.1"], port)
        time.sleep(0.2)
    t.join()
    assert got["host"] == "127.0.0.1" and got["port"] == 1883 and got["site"] == "Lab"


def test_robot_with_auto_host_connects_to_the_announced_broker(monkeypatch, tmp_path):
    pytest.importorskip("amqtt")
    sys.path.insert(0, str(BACKEND))
    from app.dev_broker import start_broker  # noqa: E402
    from app import discovery as server_disc  # noqa: E402

    mqtt_port, udp_port = _free_port(), _free_port(socket.SOCK_DGRAM)
    monkeypatch.setattr(discovery, "DISCOVERY_PORT", udp_port)
    monkeypatch.setattr(discovery, "CACHE_FILE", tmp_path / "server.json")

    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def run_broker():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_broker(mqtt_port))
        ready.set()
        loop.run_forever()

    threading.Thread(target=run_broker, daemon=True).start()
    assert ready.wait(10)

    cfg = load_config(None, {"mqtt": {"host": "auto", "port": 1}})
    client = RobotMqttClient(cfg, on_command=lambda c: None, on_heartbeat=lambda h: None)
    client.start()
    payload = {"service": "raqib", "mqtt_port": mqtt_port, "api_port": 8000, "site": "Test"}
    try:
        end = time.time() + 15
        while time.time() < end and not client.connected:
            server_disc.send_beacon(payload, ["127.0.0.1"], udp_port)
            time.sleep(0.3)
        assert client.connected, "robot did not connect to the broker it discovered"
        assert client.server == ("127.0.0.1", mqtt_port)
        assert discovery.load_cache()["port"] == mqtt_port      # remembered for the next boot
    finally:
        client.stop()
        loop.call_soon_threadsafe(loop.stop)
