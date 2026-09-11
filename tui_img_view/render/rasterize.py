"""Pixel block → terminal cell conversions.

Every :class:`RasterMode` consumes an RGB image whose size is an exact
multiple of its ``cell_px`` and returns one :class:`Canvas` cell per block.
All modes are vectorised with numpy; only the final cell assembly is Python.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import numpy as np

from tui_img_view.render.canvas import Canvas, Cell

QUADRANT_CHARS = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"
ASCII_RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
_BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32)
#: Braille dot bit for (row, col) inside a 4x2 block.
_BRAILLE_BITS = np.array([[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]], dtype=np.int32)


def luminance(rgb: np.ndarray) -> np.ndarray:
    rgb = rgb.astype(np.float32)
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def to_grayscale(rgb: np.ndarray) -> np.ndarray:
    lum = np.clip(np.rint(luminance(rgb)), 0, 255).astype(np.uint8)
    return np.repeat(lum[..., None], 3, axis=2)


class RasterMode(ABC):
    name: ClassVar[str]
    #: Source pixels consumed per cell: (width, height).
    cell_px: ClassVar[tuple[int, int]]
    #: Whether the mode paints cell backgrounds (affects how overlays are blended).
    paints_background: ClassVar[bool] = True

    def check(self, img: np.ndarray) -> tuple[int, int]:
        if img.ndim != 3 or img.shape[2] != 3:
            raise ValueError(f"expected HxWx3 image, got {img.shape}")
        pw, ph = self.cell_px
        h, w = img.shape[:2]
        if h % ph or w % pw:
            raise ValueError(f"image {w}x{h} is not a multiple of cell size {pw}x{ph}")
        return w // pw, h // ph

    @abstractmethod
    def rasterize(self, img: np.ndarray) -> Canvas: ...


def _rows_from_arrays(
    chars: list[list[str]],
    fg: np.ndarray | None,
    bg: np.ndarray | None,
) -> list[list[Cell]]:
    rows = len(chars)
    cols = len(chars[0]) if rows else 0
    fg_l = fg.astype(np.uint8).tolist() if fg is not None else None
    bg_l = bg.astype(np.uint8).tolist() if bg is not None else None
    out: list[list[Cell]] = []
    for r in range(rows):
        crow = chars[r]
        frow = fg_l[r] if fg_l is not None else None
        brow = bg_l[r] if bg_l is not None else None
        row: list[Cell] = []
        append = row.append
        for c in range(cols):
            append(
                (
                    crow[c],
                    tuple(frow[c]) if frow is not None else None,  # type: ignore[arg-type]
                    tuple(brow[c]) if brow is not None else None,  # type: ignore[arg-type]
                )
            )
        out.append(row)
    return out


class HalfBlockMode(RasterMode):
    """``▀`` with foreground = upper pixel, background = lower pixel. 1x2 px per cell."""

    name = "half"
    cell_px = (1, 2)

    def rasterize(self, img: np.ndarray) -> Canvas:
        cols, rows = self.check(img)
        top = img[0::2]
        bot = img[1::2]
        chars = [["▀"] * cols for _ in range(rows)]
        return Canvas(cols, rows, _rows_from_arrays(chars, top, bot))


class QuadrantMode(RasterMode):
    """2x2 px per cell using quadrant glyphs; two colours per cell, split on luminance."""

    name = "quadrant"
    cell_px = (2, 2)

    def rasterize(self, img: np.ndarray) -> Canvas:
        cols, rows = self.check(img)
        blocks = img.reshape(rows, 2, cols, 2, 3).transpose(0, 2, 1, 3, 4).astype(np.float32)
        lum = luminance(blocks)  # rows, cols, 2, 2
        mean = lum.mean(axis=(2, 3), keepdims=True)
        above = lum >= mean
        bits = (
            above[..., 0, 0].astype(np.int32) * 1
            + above[..., 0, 1] * 2
            + above[..., 1, 0] * 4
            + above[..., 1, 1] * 8
        )
        n_above = above.sum(axis=(2, 3))[..., None]
        n_below = 4 - n_above
        fg = (blocks * above[..., None]).sum(axis=(2, 3)) / np.maximum(n_above, 1)
        bg = (blocks * (~above)[..., None]).sum(axis=(2, 3)) / np.maximum(n_below, 1)
        bg = np.where(n_below == 0, fg, bg)
        chars = [[QUADRANT_CHARS[b] for b in row] for row in bits.tolist()]
        return Canvas(cols, rows, _rows_from_arrays(chars, np.rint(fg), np.rint(bg)))


class BrailleMode(RasterMode):
    """2x4 px per cell as braille dots with ordered dithering; foreground colour only."""

    name = "braille"
    cell_px = (2, 4)
    paints_background = False

    def rasterize(self, img: np.ndarray) -> Canvas:
        cols, rows = self.check(img)
        blocks = img.reshape(rows, 4, cols, 2, 3).transpose(0, 2, 1, 3, 4).astype(np.float32)
        lum = luminance(blocks)  # rows, cols, 4, 2
        ys = (np.arange(rows)[:, None, None, None] * 4 + np.arange(4)[None, None, :, None]) % 4
        xs = (np.arange(cols)[None, :, None, None] * 2 + np.arange(2)[None, None, None, :]) % 4
        threshold = (_BAYER4[ys, xs] + 0.5) * (255.0 / 16.0)
        on = lum > threshold
        bits = (on * _BRAILLE_BITS[None, None]).sum(axis=(2, 3))
        fg = blocks.mean(axis=(2, 3))
        chars = [[chr(0x2800 + b) for b in row] for row in bits.tolist()]
        return Canvas(cols, rows, _rows_from_arrays(chars, np.rint(fg), None))


class AsciiMode(RasterMode):
    """Classic ASCII ramp, coloured by the block's mean colour. 1x2 px per cell."""

    name = "ascii"
    cell_px = (1, 2)
    paints_background = False

    def rasterize(self, img: np.ndarray) -> Canvas:
        cols, rows = self.check(img)
        blocks = img.reshape(rows, 2, cols, 3).astype(np.float32)
        mean = blocks.mean(axis=1)  # rows, cols, 3
        lum = luminance(mean)
        idx = np.clip((lum / 255.0) * (len(ASCII_RAMP) - 1), 0, len(ASCII_RAMP) - 1)
        idx = np.rint(idx).astype(np.int32)
        chars = [[ASCII_RAMP[i] for i in row] for row in idx.tolist()]
        return Canvas(cols, rows, _rows_from_arrays(chars, np.rint(mean), None))


MODES: dict[str, RasterMode] = {
    m.name: m for m in (HalfBlockMode(), QuadrantMode(), BrailleMode(), AsciiMode())
}
MODE_ORDER: tuple[str, ...] = tuple(MODES)


def get_mode(name: str) -> RasterMode:
    try:
        return MODES[name]
    except KeyError:
        raise KeyError(
            f"unknown render mode '{name}'. Choose from: {', '.join(MODE_ORDER)}"
        ) from None


def next_mode(name: str, step: int = 1) -> str:
    idx = MODE_ORDER.index(name) if name in MODE_ORDER else 0
    return MODE_ORDER[(idx + step) % len(MODE_ORDER)]
