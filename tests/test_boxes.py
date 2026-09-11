from __future__ import annotations

from tui_img_view.core.types import BoundingBox
from tui_img_view.render.boxes import BoxTransform, draw_boxes
from tui_img_view.render.canvas import Canvas
from tui_img_view.render.palette import color_for_label, contrast_text


def test_transform_to_cells_inclusive():
    t = BoxTransform(0.5, 0.25, offset_x=2, offset_y=1)
    assert t.to_cells(BoundingBox(10, 8, 20, 16)) == (7, 3, 16, 6)


def test_draw_box_outline_and_label():
    canvas = Canvas(20, 8)
    n = draw_boxes(canvas, [BoundingBox(2, 2, 8, 4, label="cat", score=0.5)], BoxTransform(1, 1))
    assert n == 1
    text = canvas.to_text().splitlines()
    assert text[2].startswith("  ┌cat 0.50")  # caption may overrun the top-right corner
    assert text[3][2] == "│" and text[3][9] == "│"
    assert text[5][2:10] == "└──────┘"
    # label cells carry the box colour as background
    color = color_for_label("cat")
    assert canvas.get(3, 2) == ("c", contrast_text(color), color)


def test_draw_box_without_labels_and_offscreen():
    canvas = Canvas(10, 4)
    boxes = [
        BoundingBox(1, 1, 3, 2, label="x"),
        BoundingBox(50, 50, 3, 3, label="far"),  # entirely outside
        BoundingBox(0, 0, 0, 5, label="empty"),  # zero width
    ]
    n = draw_boxes(canvas, boxes, BoxTransform(1, 1), show_labels=False)
    assert n == 1
    assert "x" not in canvas.to_text()
    assert canvas.get(1, 1)[0] == "┌"


def test_degenerate_boxes_do_not_crash():
    canvas = Canvas(10, 5)
    n = draw_boxes(
        canvas,
        [BoundingBox(1, 1, 0.5, 0.5), BoundingBox(3, 1, 4, 0.5), BoundingBox(1, 3, 0.5, 2)],
        BoxTransform(1, 1),
    )
    assert n == 3
    assert canvas.get(1, 1)[0] == "◆"
    assert canvas.get(3, 1)[0] == "╶" and canvas.get(6, 1)[0] == "╴"
    assert canvas.get(1, 3)[0] == "╷" and canvas.get(1, 4)[0] == "╵"


def test_label_truncates_at_canvas_edge():
    canvas = Canvas(8, 3)
    draw_boxes(canvas, [BoundingBox(4, 0, 10, 2, label="verylonglabel")], BoxTransform(1, 1))
    row = canvas.to_text().splitlines()[0]
    assert len(row) == 8
    assert row.endswith("…")


def test_keep_background_flag():
    canvas = Canvas(5, 5, [[("▀", (1, 2, 3), (4, 5, 6))] * 5 for _ in range(5)])
    draw_boxes(canvas, [BoundingBox(0, 0, 5, 5)], BoxTransform(1, 1), keep_background=True)
    assert canvas.get(0, 0)[2] == (4, 5, 6)
    draw_boxes(canvas, [BoundingBox(0, 0, 5, 5)], BoxTransform(1, 1), keep_background=False)
    assert canvas.get(0, 0)[2] is None


def test_palette_is_stable():
    assert color_for_label("person") == color_for_label("person")
    assert contrast_text((255, 255, 255)) == (0, 0, 0)
    assert contrast_text((0, 0, 0)) == (255, 255, 255)
