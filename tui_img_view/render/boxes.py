"""Draw bounding boxes and captions on a :class:`Canvas`, in cell space."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from tui_img_view.core.types import BoundingBox
from tui_img_view.render.canvas import RGB, Canvas
from tui_img_view.render.palette import color_for_label, contrast_text


@dataclass(frozen=True)
class BoxTransform:
    """Maps source-pixel coordinates to canvas cells."""

    scale_x: float  # cells per source pixel
    scale_y: float
    offset_x: int = 0  # cells
    offset_y: int = 0

    def to_cells(self, box: BoundingBox) -> tuple[int, int, int, int]:
        """Inclusive (c1, r1, c2, r2) covering the box."""
        c1 = int(math.floor(box.x * self.scale_x)) + self.offset_x
        r1 = int(math.floor(box.y * self.scale_y)) + self.offset_y
        c2 = int(math.ceil(box.x2 * self.scale_x)) - 1 + self.offset_x
        r2 = int(math.ceil(box.y2 * self.scale_y)) - 1 + self.offset_y
        return c1, r1, max(c1, c2), max(r1, r2)


ColorFn = Callable[[BoundingBox], RGB]


def default_box_color(box: BoundingBox) -> RGB:
    return color_for_label(box.label or box.track_id or "")


def draw_boxes(
    canvas: Canvas,
    boxes: Iterable[BoundingBox],
    transform: BoxTransform,
    *,
    show_labels: bool = True,
    color_fn: ColorFn = default_box_color,
    keep_background: bool = True,
) -> int:
    """Overlay ``boxes`` on ``canvas``. Returns how many boxes touched the canvas."""
    drawn = 0
    for box in boxes:
        if box.w <= 0 or box.h <= 0:
            continue
        color = color_fn(box)
        c1, r1, c2, r2 = transform.to_cells(box)
        if c2 < 0 or r2 < 0 or c1 >= canvas.width or r1 >= canvas.height:
            continue
        drawn += 1
        _outline(canvas, c1, r1, c2, r2, color, keep_background)
        if show_labels:
            caption = box.caption
            if caption:
                _caption(canvas, caption, c1 + 1 if c2 > c1 else c1, r1, color)
    return drawn


def _paint(canvas: Canvas, x: int, y: int, char: str, fg: RGB, keep_background: bool) -> None:
    if not (0 <= x < canvas.width and 0 <= y < canvas.height):
        return
    bg = canvas.cells[y][x][2] if keep_background else None
    canvas.cells[y][x] = (char, fg, bg)


def _outline(canvas: Canvas, c1: int, r1: int, c2: int, r2: int, color: RGB, keep_bg: bool) -> None:
    if c1 == c2 and r1 == r2:
        _paint(canvas, c1, r1, "◆", color, keep_bg)
        return
    if r1 == r2:  # single row: a bracketed line
        _paint(canvas, c1, r1, "╶", color, keep_bg)
        for x in range(c1 + 1, c2):
            _paint(canvas, x, r1, "─", color, keep_bg)
        _paint(canvas, c2, r1, "╴", color, keep_bg)
        return
    if c1 == c2:  # single column
        _paint(canvas, c1, r1, "╷", color, keep_bg)
        for y in range(r1 + 1, r2):
            _paint(canvas, c1, y, "│", color, keep_bg)
        _paint(canvas, c1, r2, "╵", color, keep_bg)
        return
    for x in range(c1 + 1, c2):
        _paint(canvas, x, r1, "─", color, keep_bg)
        _paint(canvas, x, r2, "─", color, keep_bg)
    for y in range(r1 + 1, r2):
        _paint(canvas, c1, y, "│", color, keep_bg)
        _paint(canvas, c2, y, "│", color, keep_bg)
    _paint(canvas, c1, r1, "┌", color, keep_bg)
    _paint(canvas, c2, r1, "┐", color, keep_bg)
    _paint(canvas, c1, r2, "└", color, keep_bg)
    _paint(canvas, c2, r2, "┘", color, keep_bg)


def _caption(canvas: Canvas, text: str, x0: int, y: int, color: RGB) -> None:
    if not (0 <= y < canvas.height):
        return
    fg = contrast_text(color)
    x0 = max(0, x0)
    room = canvas.width - x0
    if room <= 0:
        return
    if len(text) > room:
        text = text[: max(0, room - 1)] + "…" if room > 1 else text[:room]
    for i, ch in enumerate(text):
        canvas.cells[y][x0 + i] = (ch, fg, color)
