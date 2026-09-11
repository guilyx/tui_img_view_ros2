from __future__ import annotations

import numpy as np
import pytest

from tui_img_view.render.rasterize import (
    ASCII_RAMP,
    MODE_ORDER,
    MODES,
    get_mode,
    next_mode,
    to_grayscale,
)


@pytest.mark.parametrize("name", MODE_ORDER)
def test_mode_output_size(name):
    mode = MODES[name]
    pw, ph = mode.cell_px
    cols, rows = 7, 5
    img = (np.random.default_rng(0).random((rows * ph, cols * pw, 3)) * 255).astype(np.uint8)
    canvas = mode.rasterize(img)
    assert (canvas.width, canvas.height) == (cols, rows)
    assert all(len(row) == cols for row in canvas.cells)


@pytest.mark.parametrize("name", MODE_ORDER)
def test_mode_rejects_misaligned(name):
    mode = MODES[name]
    pw, ph = mode.cell_px
    img = np.zeros((ph * 2 + 1, pw * 2 + 1, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        mode.rasterize(img)


def test_half_block_uses_top_as_fg_and_bottom_as_bg():
    img = np.zeros((2, 1, 3), dtype=np.uint8)
    img[0] = (255, 0, 0)
    img[1] = (0, 0, 255)
    cell = MODES["half"].rasterize(img).get(0, 0)
    assert cell == ("▀", (255, 0, 0), (0, 0, 255))


def test_quadrant_picks_glyph_from_bright_pixels():
    img = np.zeros((2, 2, 3), dtype=np.uint8)
    img[0, 0] = (255, 255, 255)  # only top-left bright → ▘
    cell = MODES["quadrant"].rasterize(img).get(0, 0)
    assert cell[0] == "▘"
    assert cell[1] == (255, 255, 255)
    assert cell[2] == (0, 0, 0)
    flat = np.full((2, 2, 3), 90, dtype=np.uint8)
    assert MODES["quadrant"].rasterize(flat).get(0, 0) == ("█", (90, 90, 90), (90, 90, 90))


def test_braille_black_is_empty_white_is_full():
    black = np.zeros((4, 2, 3), dtype=np.uint8)
    white = np.full((4, 2, 3), 255, dtype=np.uint8)
    assert MODES["braille"].rasterize(black).get(0, 0)[0] == "⠀"
    assert MODES["braille"].rasterize(white).get(0, 0)[0] == "⣿"
    mid = np.full((4, 2, 3), 128, dtype=np.uint8)
    ch = MODES["braille"].rasterize(mid).get(0, 0)[0]
    dots = bin(ord(ch) - 0x2800).count("1")
    assert 2 <= dots <= 6  # dithering: roughly half on


def test_ascii_ramp_is_monotonic_in_luminance():
    values = [0, 64, 128, 192, 255]
    chars = []
    for v in values:
        img = np.full((2, 1, 3), v, dtype=np.uint8)
        chars.append(MODES["ascii"].rasterize(img).get(0, 0)[0])
    idx = [ASCII_RAMP.index(c) for c in chars]
    assert idx == sorted(idx) and idx[0] == 0 and idx[-1] == len(ASCII_RAMP) - 1


def test_get_mode_and_next_mode():
    assert get_mode("half").name == "half"
    with pytest.raises(KeyError):
        get_mode("nope")
    assert next_mode(MODE_ORDER[-1]) == MODE_ORDER[0]
    assert next_mode("half", -1) == MODE_ORDER[-1]


def test_to_grayscale_shape():
    img = np.zeros((2, 3, 3), dtype=np.uint8)
    img[..., 1] = 255
    gray = to_grayscale(img)
    assert gray.shape == img.shape
    assert gray[0, 0, 0] == gray[0, 0, 1] == gray[0, 0, 2] == 150
