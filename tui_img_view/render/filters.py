"""Image filters applied before rasterisation.

Filters are pure functions on ``HxWx3`` ``uint8`` RGB arrays and compose as a
stack in the order the user enabled them. They run on the already-resized
image, so cost is tied to the terminal size, not the camera resolution.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np
from PIL import Image, ImageFilter, ImageOps

FilterFn = Callable[[np.ndarray], np.ndarray]

_SEPIA = np.array(
    [[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]], dtype=np.float32
)


def _pil(fn: Callable[[Image.Image], Image.Image]) -> FilterFn:
    def _apply(px: np.ndarray) -> np.ndarray:
        return np.asarray(fn(Image.fromarray(px, "RGB")).convert("RGB"), dtype=np.uint8)

    return _apply


def gray(px: np.ndarray) -> np.ndarray:
    lum = px.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    return np.repeat(np.clip(np.rint(lum), 0, 255).astype(np.uint8)[..., None], 3, axis=2)


def invert(px: np.ndarray) -> np.ndarray:
    return (255 - px).astype(np.uint8)


def sepia(px: np.ndarray) -> np.ndarray:
    out = px.astype(np.float32) @ _SEPIA.T
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def threshold(px: np.ndarray, level: int = 128) -> np.ndarray:
    lum = px.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = np.where(lum >= level, 255, 0).astype(np.uint8)
    return np.repeat(out[..., None], 3, axis=2)


#: name -> (function, one-line description). Order is the cycling order for the ``f`` key.
FILTERS: dict[str, tuple[FilterFn, str]] = {
    "gray": (gray, "grayscale"),
    "invert": (invert, "negative"),
    "sepia": (sepia, "warm sepia tone"),
    "blur": (_pil(lambda im: im.filter(ImageFilter.GaussianBlur(1.5))), "gaussian blur"),
    "sharpen": (_pil(lambda im: im.filter(ImageFilter.UnsharpMask(2, 150, 3))), "unsharp mask"),
    "edges": (_pil(lambda im: im.filter(ImageFilter.FIND_EDGES)), "edge detection"),
    "emboss": (_pil(lambda im: im.filter(ImageFilter.EMBOSS)), "emboss relief"),
    "threshold": (threshold, "black and white at 50 % luminance"),
    "posterize": (_pil(lambda im: ImageOps.posterize(im, 3)), "3 bits per channel"),
    "contrast": (_pil(lambda im: ImageOps.autocontrast(im, cutoff=1)), "stretch contrast"),
    "equalize": (_pil(ImageOps.equalize), "histogram equalisation"),
}
FILTER_ORDER: tuple[str, ...] = tuple(FILTERS)


def get_filter(name: str) -> FilterFn:
    try:
        return FILTERS[name][0]
    except KeyError:
        raise KeyError(f"unknown filter '{name}'. Choose from: {', '.join(FILTER_ORDER)}") from None


def apply_filters(px: np.ndarray, names: Iterable[str]) -> np.ndarray:
    """Apply ``names`` in order. Unknown names raise ``KeyError`` before any work."""
    fns = [get_filter(n) for n in names]
    for fn in fns:
        px = fn(px)
    return np.ascontiguousarray(px, dtype=np.uint8)


def next_filter(active: Iterable[str]) -> list[str]:
    """Cycle for the ``f`` key: none → each filter alone in order → none."""
    active = list(active)
    if len(active) != 1 or active[0] not in FILTER_ORDER:
        return [FILTER_ORDER[0]] if not active else []
    idx = FILTER_ORDER.index(active[0]) + 1
    return [FILTER_ORDER[idx]] if idx < len(FILTER_ORDER) else []
