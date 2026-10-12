"""Tiny image helpers that use OpenCV when installed and fall back to Pillow + NumPy.

OpenCV is a 44 MB download; the simulator and the snapshot pipeline only need a
few drawing primitives and JPEG encoding, so they run without it. Frames are
always BGR uint8 NumPy arrays (OpenCV convention), whichever backend is used.
"""
from __future__ import annotations

import io

import numpy as np

try:
    import cv2  # type: ignore

    HAVE_CV2 = True
except Exception:  # noqa: BLE001
    cv2 = None
    HAVE_CV2 = False


# ------------------------------------------------------------------ drawing
def rect(img: np.ndarray, p1, p2, color, thickness: int = -1):
    if HAVE_CV2:
        cv2.rectangle(img, p1, p2, color, thickness)
        return
    h, w = img.shape[:2]
    x0, y0 = max(0, min(p1[0], p2[0])), max(0, min(p1[1], p2[1]))
    x1, y1 = min(w, max(p1[0], p2[0]) + 1), min(h, max(p1[1], p2[1]) + 1)
    if x0 >= x1 or y0 >= y1:
        return
    if thickness < 0:
        img[y0:y1, x0:x1] = color
    else:
        t = thickness
        img[y0:min(y1, y0 + t), x0:x1] = color
        img[max(y0, y1 - t):y1, x0:x1] = color
        img[y0:y1, x0:min(x1, x0 + t)] = color
        img[y0:y1, max(x0, x1 - t):x1] = color


def circle(img: np.ndarray, center, radius: int, color):
    if HAVE_CV2:
        cv2.circle(img, center, radius, color, -1)
        return
    h, w = img.shape[:2]
    cx, cy = center
    y, x = np.ogrid[max(0, cy - radius):min(h, cy + radius + 1), max(0, cx - radius):min(w, cx + radius + 1)]
    mask = (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius
    region = img[max(0, cy - radius):min(h, cy + radius + 1), max(0, cx - radius):min(w, cx + radius + 1)]
    region[mask] = color


def line(img: np.ndarray, p1, p2, color, thickness: int = 1):
    if HAVE_CV2:
        cv2.line(img, p1, p2, color, thickness)
        return
    n = int(max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]))) + 1
    r = max(0, thickness // 2)
    for t in np.linspace(0, 1, n):
        x = int(round(p1[0] + (p2[0] - p1[0]) * t))
        y = int(round(p1[1] + (p2[1] - p1[1]) * t))
        rect(img, (x - r, y - r), (x + r, y + r), color, -1)


def text(img: np.ndarray, s: str, org, scale: float, color, thickness: int = 1):
    """org = bottom-left of the text (OpenCV convention)."""
    if HAVE_CV2:
        cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness)
        return
    from PIL import Image, ImageDraw, ImageFont

    size = max(8, int(28 * scale))
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        font = ImageFont.load_default()
    h, w = img.shape[:2]
    x, y = org
    top = max(0, y - size - 4)
    crop = img[top:min(h, y + 4), max(0, x):w]
    if crop.size == 0:
        return
    pil = Image.fromarray(np.ascontiguousarray(crop))
    ImageDraw.Draw(pil).text((0, 0), s, fill=tuple(int(c) for c in color), font=font)
    img[top:min(h, y + 4), max(0, x):w] = np.asarray(pil)


def add_noise(img: np.ndarray, amount: int = 6) -> np.ndarray:
    noise = np.random.randint(0, amount, img.shape, dtype=np.uint8)
    return np.minimum(img.astype(np.uint16) + noise, 255).astype(np.uint8)


# ------------------------------------------------------------------ encoding
def to_jpeg(frame_bgr: np.ndarray, max_side: int, quality: int = 80) -> tuple[bytes, int, int, float]:
    """Resize so the longest side = max_side, JPEG-encode. Returns (bytes, w, h, mean_brightness)."""
    h, w = frame_bgr.shape[:2]
    scale = max_side / max(h, w)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    if HAVE_CV2:
        small = cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("jpeg encode failed")
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return buf.tobytes(), nw, nh, float(gray.mean())
    from PIL import Image

    pil = Image.fromarray(np.ascontiguousarray(frame_bgr[:, :, ::-1])).resize((nw, nh), Image.BILINEAR)
    out = io.BytesIO()
    pil.save(out, format="JPEG", quality=quality)
    return out.getvalue(), nw, nh, float(np.asarray(pil.convert("L")).mean())


def save_jpeg(path: str, frame_bgr: np.ndarray):
    data, *_ = to_jpeg(frame_bgr, max(frame_bgr.shape[:2]), 90)
    with open(path, "wb") as f:
        f.write(data)
