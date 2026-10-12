"""Camera capture, VLM snapshots and WebRTC live video (aiortc).

* A capture thread keeps the latest frame.
* snapshot() returns a resized JPEG (base64) for the cloud VLM.
* handle_webrtc_offer() answers a WebRTC offer from the mobile app (signalled via
  backend -> MQTT) and streams the camera with DTLS-SRTP encryption.
* privacy mode replaces every frame with a black "PRIVACY MODE" image.
"""
from __future__ import annotations

import asyncio
import base64
import fractions
import logging
import threading
import time

import numpy as np

from . import imaging as im

from .hal.base import Hardware

log = logging.getLogger(__name__)

try:  # WebRTC is optional (pip install aiortc)
    from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
    from aiortc.mediastreams import VideoStreamTrack
    from av import VideoFrame

    HAVE_AIORTC = True
except Exception:  # noqa: BLE001
    HAVE_AIORTC = False
    VideoStreamTrack = object  # type: ignore[misc,assignment]


class CameraStreamer:
    def __init__(self, hw: Hardware, cfg: dict):
        c = cfg.get("camera", {})
        self.hw = hw
        self.fps = float(c.get("fps", 15))
        self.snapshot_size = int(c.get("snapshot_size", 512))
        self.quality = int(c.get("jpeg_quality", 80))
        self.ice_servers = c.get("ice_servers", ["stun:stun.l.google.com:19302"])
        self.privacy = False
        self.lock = threading.Lock()
        self.frame: np.ndarray | None = None
        self.frame_ts = 0.0
        self.errors = 0
        self.pcs: set = set()
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, name="camera", daemon=True)
        self._t.start()

    def _privacy_frame(self) -> np.ndarray:
        img = np.zeros((480, 640, 3), np.uint8)
        im.text(img, "PRIVACY MODE", (150, 240), 1.4, (255, 255, 255), 3)
        return img

    def _loop(self):
        period = 1.0 / self.fps
        while not self._stop.is_set():
            t0 = time.monotonic()
            try:
                f = self._privacy_frame() if self.privacy else self.hw.camera.capture()
                with self.lock:
                    self.frame, self.frame_ts = f, time.time()
            except Exception as e:  # noqa: BLE001
                self.errors += 1
                if self.errors % 50 == 1:
                    log.warning("camera capture failed: %s", e)
                if self.errors >= 10:
                    self.hw.set_health("camera", False, f"capture failing: {e}"[:160])
            self._stop.wait(max(0.0, period - (time.monotonic() - t0)))

    def latest(self) -> np.ndarray:
        with self.lock:
            f = self.frame
        if f is None:
            f = self.hw.camera.capture() if not self.privacy else self._privacy_frame()
        return f

    # ------------------------------------------------------------------ VLM snapshot
    def snapshot(self, size: int | None = None) -> dict:
        if self.privacy:
            raise PermissionError("privacy mode is ON - recording disabled")
        size = int(size or self.snapshot_size)
        # use a frame taken AFTER this request (the pan/tilt may just have moved)
        t_req, deadline = time.time(), time.time() + 1.5
        while self._t.is_alive() and time.time() < deadline:
            with self.lock:
                if self.frame is not None and self.frame_ts >= t_req:
                    break
            time.sleep(0.02)
        frame = self.latest()
        jpeg, w, h, brightness = im.to_jpeg(frame, size, self.quality)
        out = {
            "image_b64": base64.b64encode(jpeg).decode("ascii"),
            "mime": "image/jpeg",
            "width": w,
            "height": h,
            "mean_brightness": round(brightness, 1),
            "captured_at": time.time(),
        }
        truth = self.hw.camera.scene_truth()
        if truth is not None:
            out["sim_truth"] = truth
        return out

    # ------------------------------------------------------------------ WebRTC
    async def handle_webrtc_offer(self, sdp: str, type_: str = "offer") -> dict:
        if not HAVE_AIORTC:
            raise RuntimeError("aiortc not installed on the robot (pip install aiortc)")
        if self.privacy:
            raise PermissionError("privacy mode is ON - streaming disabled")
        config = RTCConfiguration(iceServers=[RTCIceServer(urls=u) for u in self.ice_servers]) \
            if self.ice_servers else RTCConfiguration()
        pc = RTCPeerConnection(configuration=config)
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def _on_state():
            log.info("WebRTC state: %s", pc.connectionState)
            if pc.connectionState in ("failed", "closed"):
                await pc.close()
                self.pcs.discard(pc)

        pc.addTrack(CameraTrack(self))
        await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=type_))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        # keep at most 3 viewers
        while len(self.pcs) > 3:
            old = next(iter(self.pcs))
            self.pcs.discard(old)
            await old.close()
        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

    async def close_webrtc(self):
        for pc in list(self.pcs):
            await pc.close()
        self.pcs.clear()

    def close(self):
        self._stop.set()


class CameraTrack(VideoStreamTrack):  # type: ignore[misc]
    kind = "video"

    def __init__(self, streamer: CameraStreamer):
        super().__init__()
        self.streamer = streamer
        self._start = None

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.streamer.latest()
        vf = VideoFrame.from_ndarray(frame, format="bgr24")
        vf.pts, vf.time_base = pts, time_base
        return vf


__all__ = ["CameraStreamer", "HAVE_AIORTC", "asyncio", "fractions"]
