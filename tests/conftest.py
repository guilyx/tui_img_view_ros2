from __future__ import annotations

import numpy as np
import pytest

from tui_img_view.core.types import BoundingBox, Detections, Frame


@pytest.fixture
def gradient_frame() -> Frame:
    """64x32 frame: red rising left→right, green rising top→bottom."""
    h, w = 32, 64
    yy, xx = np.mgrid[0:h, 0:w]
    px = np.zeros((h, w, 3), dtype=np.uint8)
    px[..., 0] = (xx * 255 // (w - 1)).astype(np.uint8)
    px[..., 1] = (yy * 255 // (h - 1)).astype(np.uint8)
    return Frame(px, stamp=123.0, frame_id="cam", encoding="rgb8")


@pytest.fixture
def two_boxes() -> Detections:
    return Detections(
        (
            BoundingBox(8, 4, 16, 8, label="cat", score=0.87),
            BoundingBox(40, 16, 20, 12, label="dog", track_id="3"),
        ),
        stamp=123.0,
        frame_id="cam",
        source="/dets",
    )
