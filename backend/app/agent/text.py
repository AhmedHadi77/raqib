"""Small text helpers shared by the planner, tools and reply writer (no imports -> no cycles)."""
from __future__ import annotations

import re


def spoken_zone(zone: str | None) -> str:
    """'LectureHall_B' -> 'Lecture Hall B' (for replies and speech)."""
    if not zone:
        return "the corridor"
    return re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", zone).replace("_", " ")


def to_speech(text: str, limit: int = 600) -> str:
    """Markdown chat reply -> plain sentences suitable for text-to-speech."""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)                # images
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                 # links
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"[☀-➿\U0001F300-\U0001FAFF️]", "", t)  # emoji
    t = t.replace("°C", " degrees").replace("°", " degrees").replace("% RH", " percent humidity").replace("%", " percent")
    t = re.sub(r"\bAQI\b", "air quality index", t)
    t = re.sub(r"\bAC\b", "air conditioner", t)
    t = re.sub(r"\s*\n\s*-\s*", ". ", t)
    t = re.sub(r"\s*\n+\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"\.\s*\.", ".", t)
    if len(t) > limit:
        cut = t[:limit].rsplit(". ", 1)[0]
        t = cut + "."
    return t
