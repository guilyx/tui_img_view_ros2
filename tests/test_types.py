from __future__ import annotations

import numpy as np
import pytest

from tui_img_view.core.types import BoundingBox, Detections, Frame


def test_bounding_box_from_center_and_caption():
    box = BoundingBox.from_center(50, 40, 20, 10, label="car", score=0.5, track_id="9")
    assert (box.x, box.y, box.w, box.h) == (40, 35, 20, 10)
    assert (box.x2, box.y2) == (60, 45)
    assert box.caption == "#9 car 0.50"
    assert BoundingBox(0, 0, 1, 1).caption == ""
    assert BoundingBox(0, 0, 1, 1, label="x").caption == "x"


def test_frame_normalises_gray_and_dtype():
    gray = np.full((4, 5), 7, dtype=np.uint8)
    frame = Frame(gray)
    assert frame.pixels.shape == (4, 5, 3)
    assert frame.width == 5 and frame.height == 4
    floats = np.full((2, 2, 3), 300.0)
    assert Frame(floats).pixels.dtype == np.uint8
    assert Frame(floats).pixels.max() == 255


def test_frame_rejects_bad_shape():
    with pytest.raises(ValueError):
        Frame(np.zeros((2, 2, 4), dtype=np.uint8))


def test_detections_len_and_tuple():
    dets = Detections([BoundingBox(0, 0, 1, 1)])
    assert len(dets) == 1
    assert isinstance(dets.boxes, tuple)
