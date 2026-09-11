from __future__ import annotations

from types import SimpleNamespace

from tui_img_view.transports.ros2.detections import (
    DETECTION_ADAPTERS,
    register_detection_adapter,
    supported_detection_types,
)


def _header():
    return SimpleNamespace(stamp=SimpleNamespace(sec=1, nanosec=0), frame_id="cam")


def _humble_detection(cx, cy, w, h, results, det_id=""):
    return SimpleNamespace(
        header=_header(),
        id=det_id,
        bbox=SimpleNamespace(
            center=SimpleNamespace(position=SimpleNamespace(x=cx, y=cy), theta=0.0),
            size_x=w,
            size_y=h,
        ),
        results=[
            SimpleNamespace(hypothesis=SimpleNamespace(class_id=c, score=s)) for c, s in results
        ],
    )


def _foxy_detection(cx, cy, w, h, results):
    return SimpleNamespace(
        header=_header(),
        bbox=SimpleNamespace(center=SimpleNamespace(x=cx, y=cy, theta=0.0), size_x=w, size_y=h),
        results=[SimpleNamespace(id=c, score=s) for c, s in results],
    )


def test_detection2d_array_humble_picks_best_hypothesis():
    msg = SimpleNamespace(
        header=_header(),
        detections=[
            _humble_detection(50, 40, 20, 10, [("cat", 0.2), ("dog", 0.9)], det_id="7"),
            _humble_detection(5, 5, 2, 2, []),
        ],
    )
    dets = DETECTION_ADAPTERS["vision_msgs/msg/Detection2DArray"](msg)
    assert dets.stamp == 1.0 and dets.frame_id == "cam"
    a, b = dets.boxes
    assert (a.x, a.y, a.w, a.h) == (40, 35, 20, 10)
    assert a.label == "dog" and a.score == 0.9 and a.track_id == "7"
    assert b.label == "" and b.score is None and b.track_id is None


def test_detection2d_array_foxy_layout():
    msg = SimpleNamespace(
        header=_header(), detections=[_foxy_detection(10, 10, 4, 4, [("1", 0.5)])]
    )
    dets = DETECTION_ADAPTERS["vision_msgs/msg/Detection2DArray"](msg)
    assert dets.boxes[0].label == "1" and dets.boxes[0].x == 8


def test_single_detection2d_and_bbox_array():
    single = _humble_detection(10, 10, 4, 4, [("x", 1.0)])
    dets = DETECTION_ADAPTERS["vision_msgs/msg/Detection2D"](single)
    assert len(dets) == 1 and dets.boxes[0].label == "x"
    arr = SimpleNamespace(header=_header(), boxes=[single.bbox, single.bbox])
    dets = DETECTION_ADAPTERS["vision_msgs/msg/BoundingBox2DArray"](arr)
    assert len(dets) == 2 and dets.boxes[0].label == ""


def test_yolo_detection_array():
    det = SimpleNamespace(
        class_id=0,
        class_name="person",
        score=0.77,
        id="12",
        bbox=SimpleNamespace(
            center=SimpleNamespace(position=SimpleNamespace(x=100, y=50)),
            size=SimpleNamespace(x=40, y=80),
        ),
    )
    msg = SimpleNamespace(header=_header(), detections=[det])
    dets = DETECTION_ADAPTERS["yolo_msgs/msg/DetectionArray"](msg)
    box = dets.boxes[0]
    assert box.label == "person" and box.score == 0.77 and box.track_id == "12"
    assert (box.x, box.y, box.w, box.h) == (80, 10, 40, 80)


def test_register_custom_adapter():
    from tui_img_view.core.types import Detections

    @register_detection_adapter("my_msgs/msg/Boxes")
    def _adapter(msg):
        return Detections()

    assert "my_msgs/msg/Boxes" in supported_detection_types()
    del DETECTION_ADAPTERS["my_msgs/msg/Boxes"]
