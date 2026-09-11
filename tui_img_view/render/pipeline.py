"""Frame + detections → Canvas, sized to fit a terminal region."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from PIL import Image

from tui_img_view.core.types import Detections, Frame
from tui_img_view.render.boxes import BoxTransform, draw_boxes
from tui_img_view.render.canvas import Canvas
from tui_img_view.render.rasterize import RasterMode, get_mode, to_grayscale


@dataclass(frozen=True)
class Placement:
    """Where the image lands inside a ``cols x rows`` region, in cells."""

    cols: int
    rows: int
    x0: int
    y0: int
    image_w: int
    image_h: int

    @property
    def scale_x(self) -> float:
        return self.cols / self.image_w

    @property
    def scale_y(self) -> float:
        return self.rows / self.image_h

    def transform(self) -> BoxTransform:
        return BoxTransform(self.scale_x, self.scale_y, self.x0, self.y0)


def fit_image(
    image_w: int, image_h: int, cols: int, rows: int, *, cell_aspect: float = 0.5
) -> Placement:
    """Largest cell rectangle inside ``cols x rows`` with the image's aspect ratio.

    ``cell_aspect`` is the terminal cell width/height ratio (most fonts ≈ 0.5).
    """
    if image_w <= 0 or image_h <= 0 or cols <= 0 or rows <= 0:
        return Placement(0, 0, 0, 0, max(image_w, 1), max(image_h, 1))
    # Physical aspect of a cell rectangle: (cols * cell_aspect) / rows.
    fit_cols = cols
    fit_rows = int(round(cols * cell_aspect * image_h / image_w))
    if fit_rows > rows:
        fit_rows = rows
        fit_cols = int(round(rows * image_w / (image_h * cell_aspect)))
    fit_cols = max(1, min(cols, fit_cols))
    fit_rows = max(1, min(rows, fit_rows))
    return Placement(
        fit_cols, fit_rows, (cols - fit_cols) // 2, (rows - fit_rows) // 2, image_w, image_h
    )


def resize_rgb(pixels: np.ndarray, width: int, height: int) -> np.ndarray:
    if pixels.shape[1] == width and pixels.shape[0] == height:
        return pixels
    shrinking = width < pixels.shape[1] or height < pixels.shape[0]
    resample = Image.Resampling.BOX if shrinking else Image.Resampling.BILINEAR
    out = Image.fromarray(pixels, "RGB").resize((width, height), resample)
    return np.asarray(out, dtype=np.uint8)


class Renderer:
    """Stateful renderer holding the user's display preferences."""

    def __init__(
        self,
        mode: str = "half",
        *,
        color: bool = True,
        show_boxes: bool = True,
        show_labels: bool = True,
        cell_aspect: float = 0.5,
    ) -> None:
        self._mode: RasterMode = get_mode(mode)
        self.color = color
        self.show_boxes = show_boxes
        self.show_labels = show_labels
        self.cell_aspect = cell_aspect
        self.last_placement: Placement | None = None
        self.last_box_count = 0

    @property
    def mode(self) -> str:
        return self._mode.name

    @mode.setter
    def mode(self, name: str) -> None:
        self._mode = get_mode(name)

    def render(
        self,
        frame: Frame | None,
        detections: Iterable[Detections] = (),
        cols: int = 80,
        rows: int = 24,
    ) -> Canvas:
        canvas = Canvas(cols, rows)
        self.last_box_count = 0
        if frame is None or cols <= 0 or rows <= 0:
            self.last_placement = None
            return canvas
        placement = fit_image(frame.width, frame.height, cols, rows, cell_aspect=self.cell_aspect)
        self.last_placement = placement
        if placement.cols == 0 or placement.rows == 0:
            return canvas
        pw, ph = self._mode.cell_px
        pixels = frame.pixels if self.color else to_grayscale(frame.pixels)
        small = resize_rgb(pixels, placement.cols * pw, placement.rows * ph)
        canvas.blit(self._mode.rasterize(small), placement.x0, placement.y0)
        if self.show_boxes:
            boxes = [b for d in detections for b in d.boxes]
            self.last_box_count = draw_boxes(
                canvas,
                boxes,
                placement.transform(),
                show_labels=self.show_labels,
                keep_background=self._mode.paints_background,
            )
        return canvas
