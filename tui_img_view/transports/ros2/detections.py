"""Convert detection messages into :class:`~tui_img_view.core.types.Detections`.

Adapters are keyed by ROS type string and duck-typed on the message. Register
your own with :func:`register_detection_adapter`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tui_img_view.core.types import BoundingBox, Detections
from tui_img_view.transports.ros2.codecs import stamp_seconds

DetectionAdapter = Callable[[Any], Detections]
DETECTION_ADAPTERS: dict[str, DetectionAdapter] = {}


def register_detection_adapter(type_name: str) -> Callable[[DetectionAdapter], DetectionAdapter]:
    def _register(fn: DetectionAdapter) -> DetectionAdapter:
        DETECTION_ADAPTERS[type_name] = fn
        return fn

    return _register


def _center_xy(center: Any) -> tuple[float, float]:
    # Humble+: Pose2D has .position.x; Foxy/Galactic: geometry_msgs/Pose2D has .x.
    position = getattr(center, "position", None)
    if position is not None:
        return float(position.x), float(position.y)
    return float(center.x), float(center.y)


def _best_hypothesis(results: Any) -> tuple[str, float | None]:
    best_label, best_score = "", None
    for result in results or ():
        hyp = getattr(result, "hypothesis", result)
        label = getattr(hyp, "class_id", None)
        if label is None:
            label = getattr(hyp, "id", "")
        score = getattr(hyp, "score", None)
        score = float(score) if score is not None else None
        if best_score is None or (score is not None and score > best_score):
            best_label, best_score = str(label), score
    return best_label, best_score


def _vision_detection_to_box(det: Any) -> BoundingBox:
    bbox = det.bbox
    cx, cy = _center_xy(bbox.center)
    label, score = _best_hypothesis(getattr(det, "results", ()))
    track_id = str(getattr(det, "id", "") or "") or None
    return BoundingBox.from_center(
        cx, cy, float(bbox.size_x), float(bbox.size_y), label=label, score=score, track_id=track_id
    )


def _header_fields(msg: Any) -> tuple[float, str]:
    header = getattr(msg, "header", None)
    return stamp_seconds(header), str(getattr(header, "frame_id", "") or "")


@register_detection_adapter("vision_msgs/msg/Detection2DArray")
def vision_detection2d_array(msg: Any) -> Detections:
    stamp, frame_id = _header_fields(msg)
    boxes = tuple(_vision_detection_to_box(d) for d in msg.detections)
    return Detections(boxes, stamp=stamp, frame_id=frame_id)


@register_detection_adapter("vision_msgs/msg/Detection2D")
def vision_detection2d(msg: Any) -> Detections:
    stamp, frame_id = _header_fields(msg)
    return Detections((_vision_detection_to_box(msg),), stamp=stamp, frame_id=frame_id)


@register_detection_adapter("vision_msgs/msg/BoundingBox2DArray")
def vision_bbox2d_array(msg: Any) -> Detections:
    stamp, frame_id = _header_fields(msg)
    boxes = []
    for bbox in msg.boxes:
        cx, cy = _center_xy(bbox.center)
        boxes.append(BoundingBox.from_center(cx, cy, float(bbox.size_x), float(bbox.size_y)))
    return Detections(tuple(boxes), stamp=stamp, frame_id=frame_id)


@register_detection_adapter("yolo_msgs/msg/DetectionArray")
def yolo_detection_array(msg: Any) -> Detections:
    """yolo_ros / yolov8_ros ``DetectionArray``: class_name, score, id, bbox.center/size."""
    stamp, frame_id = _header_fields(msg)
    boxes = []
    for det in msg.detections:
        bbox = det.bbox
        cx, cy = _center_xy(bbox.center)
        size = bbox.size
        track_id = str(getattr(det, "id", "") or "") or None
        boxes.append(
            BoundingBox.from_center(
                cx,
                cy,
                float(size.x),
                float(size.y),
                label=str(getattr(det, "class_name", "") or getattr(det, "class_id", "")),
                score=float(det.score) if getattr(det, "score", None) is not None else None,
                track_id=track_id,
            )
        )
    return Detections(tuple(boxes), stamp=stamp, frame_id=frame_id)


def supported_detection_types() -> list[str]:
    return sorted(DETECTION_ADAPTERS)
