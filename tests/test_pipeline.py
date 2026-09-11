from __future__ import annotations

import numpy as np

from tui_img_view.core.types import Frame
from tui_img_view.render.ansi import canvas_to_ansi
from tui_img_view.render.pipeline import Renderer, fit_image


def test_fit_image_keeps_aspect_and_centres():
    # 2:1 image in a wide region: height-limited.
    p = fit_image(200, 100, 200, 20)
    assert p.rows == 20 and p.cols == 80 and p.x0 == 60 and p.y0 == 0
    # Square image in a tall region: width-limited.
    p = fit_image(100, 100, 40, 100)
    assert p.cols == 40 and p.rows == 20 and p.y0 == 40
    assert abs(p.scale_x - 0.4) < 1e-9 and abs(p.scale_y - 0.2) < 1e-9
    assert fit_image(0, 10, 10, 10).cols == 0


def test_renderer_empty_frame_gives_blank_canvas():
    canvas = Renderer().render(None, (), 10, 4)
    assert canvas.to_text() == "\n".join([" " * 10] * 4)


def test_renderer_places_boxes_in_scaled_coordinates(gradient_frame, two_boxes):
    r = Renderer("ascii")
    canvas = r.render(gradient_frame, [two_boxes], 64, 40)
    assert r.last_placement is not None
    p = r.last_placement
    assert p.cols == 64 and p.rows == 16  # 64x32 image at 0.5 cell aspect
    assert r.last_box_count == 2
    text = canvas.to_text().splitlines()
    # "cat" box: x=8 → col 8, y=4 → row 2 + y0
    row = p.y0 + 2
    assert text[row][8] == "┌"
    assert "cat 0.87" in text[row]
    assert "#3 dog" in canvas.to_text()


def test_renderer_flags(gradient_frame, two_boxes):
    r = Renderer("half", color=False, show_boxes=False)
    canvas = r.render(gradient_frame, [two_boxes], 30, 10)
    assert r.last_box_count == 0
    cell = canvas.get(15, 5)
    assert cell[1] is not None and cell[1][0] == cell[1][1] == cell[1][2]
    r.mode = "braille"
    assert r.mode == "braille"
    r.show_labels = False
    r.show_boxes = True
    assert "cat" not in r.render(gradient_frame, [two_boxes], 30, 10).to_text()


def test_renderer_upscales_small_images():
    frame = Frame(np.full((2, 2, 3), 200, dtype=np.uint8))
    canvas = Renderer("half").render(frame, (), 40, 20)
    assert canvas.get(20, 10)[1] == (200, 200, 200)


def test_canvas_to_ansi_emits_truecolor_and_resets(gradient_frame):
    canvas = Renderer("half").render(gradient_frame, (), 16, 4)
    out = canvas_to_ansi(canvas)
    assert out.count("\n") == 3
    assert "\x1b[38;2;" in out and "\x1b[0m" in out
    plain = canvas_to_ansi(canvas, color=False)
    assert "\x1b[" not in plain
