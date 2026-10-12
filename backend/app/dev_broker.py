"""Tiny MQTT broker for development (no Docker / Mosquitto needed).

    python -m app.dev_broker            # listens on 0.0.0.0:1883

For the real deployment use Eclipse Mosquitto with TLS (see infra/ and docker-compose.yml).
The backend can also start this broker automatically when EMBEDDED_BROKER=true.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


def broker_config(port: int = 1883) -> dict:
    return {
        "listeners": {"default": {"type": "tcp", "bind": f"0.0.0.0:{port}"}},
        "plugins": {
            "amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True},
        },
    }


async def start_broker(port: int = 1883):
    from amqtt.broker import Broker

    for noisy in ("amqtt", "transitions"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    broker = Broker(broker_config(port))
    await broker.start()
    log.warning("Embedded DEV MQTT broker running on port %s (no TLS, anonymous) - dev only!", port)
    return broker


async def _main():
    logging.basicConfig(level=logging.INFO)
    await start_broker()
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
