"""Stable, distinguishable colours for box labels."""

from __future__ import annotations

import zlib

from tui_img_view.render.canvas import RGB

#: Hand-picked so neighbours differ in hue and all read on dark and light images.
PALETTE: tuple[RGB, ...] = (
    (255, 87, 51),
    (51, 204, 255),
    (255, 214, 10),
    (52, 235, 120),
    (255, 105, 180),
    (170, 120, 255),
    (255, 160, 0),
    (0, 230, 200),
    (240, 240, 240),
    (140, 255, 60),
    (255, 80, 120),
    (100, 160, 255),
)

_cache: dict[str, RGB] = {}


def color_for_label(label: str) -> RGB:
    """Deterministic colour per label string (same label → same colour on every run)."""
    color = _cache.get(label)
    if color is None:
        idx = zlib.crc32(label.encode("utf-8")) % len(PALETTE)
        color = PALETTE[idx]
        _cache[label] = color
    return color


def contrast_text(bg: RGB) -> RGB:
    """Black or white, whichever reads better on ``bg``."""
    r, g, b = bg
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if lum > 140 else (255, 255, 255)
