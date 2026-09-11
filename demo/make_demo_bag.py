#!/usr/bin/env python3
"""Build the demo ROS 2 bag (MCAP) from real photographs, without ROS.

Writes ``demo/bags/tui_demo/`` containing CDR-encoded
``sensor_msgs/msg/CompressedImage`` frames on ``/camera/image/compressed`` and
``vision_msgs/msg/Detection2DArray`` boxes on ``/detector/detections``, plus a
rosbag2 ``metadata.yaml`` so ``ros2 bag play`` and ``ros2 bag info`` work.

The frames are slow pans/zooms over four public-domain / CC0 photos shipped
with scikit-image (astronaut and rocket: NASA; chelsea: Stefan van der Walt,
CC0; coffee: Rachel Michetti, CC0). Boxes were annotated by hand in the
source images and are transformed through the same crop as the pixels.

Requires: ``pip install mcap mcap-ros2-support scikit-image pillow numpy``.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from mcap_ros2.writer import Writer
from PIL import Image

OUT_DIR = Path(__file__).parent / "bags" / "tui_demo"
BAG_NAME = "tui_demo_0.mcap"
IMAGE_TOPIC = "/camera/image/compressed"
BOX_TOPIC = "/detector/detections"
FRAME_W, FRAME_H = 400, 300
FPS = 10
SECONDS_PER_PHOTO = 3.0
JPEG_QUALITY = 72
FRAME_ID = "camera_optical_frame"
START_NS = 1_700_000_000 * 1_000_000_000  # a fixed, plausible wall-clock start

SEP = "=" * 80

TIME_DEF = "int32 sec\nuint32 nanosec"
HEADER_DEF = "builtin_interfaces/Time stamp\nstring frame_id"

COMPRESSED_IMAGE_MSGDEF = f"""std_msgs/Header header
string format
uint8[] data
{SEP}
MSG: std_msgs/Header
{HEADER_DEF}
{SEP}
MSG: builtin_interfaces/Time
{TIME_DEF}
"""

DETECTION2D_ARRAY_MSGDEF = f"""std_msgs/Header header
vision_msgs/Detection2D[] detections
{SEP}
MSG: std_msgs/Header
{HEADER_DEF}
{SEP}
MSG: builtin_interfaces/Time
{TIME_DEF}
{SEP}
MSG: vision_msgs/Detection2D
std_msgs/Header header
vision_msgs/ObjectHypothesisWithPose[] results
vision_msgs/BoundingBox2D bbox
string id
{SEP}
MSG: vision_msgs/ObjectHypothesisWithPose
vision_msgs/ObjectHypothesis hypothesis
geometry_msgs/PoseWithCovariance pose
{SEP}
MSG: vision_msgs/ObjectHypothesis
string class_id
float64 score
{SEP}
MSG: vision_msgs/BoundingBox2D
vision_msgs/Pose2D center
float64 size_x
float64 size_y
{SEP}
MSG: vision_msgs/Pose2D
vision_msgs/Point2D position
float64 theta
{SEP}
MSG: vision_msgs/Point2D
float64 x
float64 y
{SEP}
MSG: geometry_msgs/PoseWithCovariance
geometry_msgs/Pose pose
float64[36] covariance
{SEP}
MSG: geometry_msgs/Pose
geometry_msgs/Point position
geometry_msgs/Quaternion orientation
{SEP}
MSG: geometry_msgs/Point
float64 x
float64 y
float64 z
{SEP}
MSG: geometry_msgs/Quaternion
float64 x
float64 y
float64 z
float64 w
"""


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float
    label: str


@dataclass(frozen=True)
class Shot:
    """A pan/zoom from ``start`` to ``end`` crop rectangles (x, y, w, h) over a photo."""

    photo: str
    start: tuple[float, float, float, float]
    end: tuple[float, float, float, float]
    boxes: tuple[Box, ...]


SHOTS = (
    Shot(
        "astronaut",
        start=(0, 40, 512, 384),
        end=(120, 20, 320, 240),
        boxes=(
            Box(150, 40, 150, 200, "person"),
            Box(360, 0, 110, 290, "shuttle"),
            Box(290, 340, 222, 172, "helmet"),
            Box(0, 0, 120, 300, "flag"),
        ),
    ),
    Shot(
        "chelsea",
        start=(0, 0, 400, 300),
        end=(90, 45, 320, 240),
        boxes=(
            Box(130, 85, 80, 55, "eye"),
            Box(285, 105, 70, 55, "eye"),
            Box(240, 220, 70, 50, "nose"),
        ),
    ),
    Shot(
        "coffee",
        start=(0, 0, 533, 400),
        end=(110, 30, 400, 300),
        boxes=(
            Box(165, 20, 300, 290, "cup"),
            Box(80, 75, 415, 300, "saucer"),
            Box(310, 60, 130, 270, "spoon"),
        ),
    ),
    Shot(
        "rocket",
        start=(0, 0, 568, 427),
        end=(200, 90, 320, 240),
        boxes=(
            Box(290, 120, 60, 300, "rocket"),
            Box(170, 120, 60, 307, "tower"),
            Box(425, 120, 55, 307, "tower"),
        ),
    ),
)


def load_photo(name: str) -> np.ndarray:
    from skimage import data

    return np.asarray(getattr(data, name)(), dtype=np.uint8)


def smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def crop_at(shot: Shot, t: float) -> tuple[float, float, float, float]:
    s = smoothstep(t)
    return tuple(a + (b - a) * s for a, b in zip(shot.start, shot.end, strict=True))  # type: ignore[return-value]


def render_frame(photo: np.ndarray, crop: tuple[float, float, float, float]) -> bytes:
    x, y, w, h = crop
    img = Image.fromarray(photo)
    img = img.resize((FRAME_W, FRAME_H), Image.Resampling.LANCZOS, box=(x, y, x + w, y + h))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def boxes_in_frame(
    boxes: tuple[Box, ...], crop: tuple[float, float, float, float], t: float, first_id: int
) -> list[dict]:
    cx, cy, cw, ch = crop
    sx, sy = FRAME_W / cw, FRAME_H / ch
    out = []
    for i, b in enumerate(boxes):
        x1, y1 = (b.x - cx) * sx, (b.y - cy) * sy
        x2, y2 = (b.x + b.w - cx) * sx, (b.y + b.h - cy) * sy
        vx1, vy1 = max(0.0, x1), max(0.0, y1)
        vx2, vy2 = min(float(FRAME_W), x2), min(float(FRAME_H), y2)
        if vx2 <= vx1 or vy2 <= vy1:
            continue
        visible = ((vx2 - vx1) * (vy2 - vy1)) / max((x2 - x1) * (y2 - y1), 1e-6)
        if visible < 0.3:
            continue
        score = 0.6 + 0.38 * visible * (0.9 + 0.1 * math.sin(6.0 * t + i))
        out.append(
            {
                "cx": (vx1 + vx2) / 2,
                "cy": (vy1 + vy2) / 2,
                "w": vx2 - vx1,
                "h": vy2 - vy1,
                "label": b.label,
                "score": round(min(0.99, score), 3),
                "id": str(first_id + i),
            }
        )
    return out


def stamp(ns: int) -> dict:
    return {"sec": ns // 1_000_000_000, "nanosec": ns % 1_000_000_000}


def detection_msg(ns: int, boxes: list[dict]) -> dict:
    header = {"stamp": stamp(ns), "frame_id": FRAME_ID}
    identity = {
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
    }
    return {
        "header": header,
        "detections": [
            {
                "header": header,
                "results": [
                    {
                        "hypothesis": {"class_id": b["label"], "score": b["score"]},
                        "pose": {"pose": identity, "covariance": [0.0] * 36},
                    }
                ],
                "bbox": {
                    "center": {"position": {"x": b["cx"], "y": b["cy"]}, "theta": 0.0},
                    "size_x": b["w"],
                    "size_y": b["h"],
                },
                "id": b["id"],
            }
            for b in boxes
        ],
    }


def write_metadata(path: Path, start_ns: int, end_ns: int, counts: dict[str, int]) -> None:
    total = sum(counts.values())
    duration = end_ns - start_ns
    topics = ""
    for topic, type_name in (
        (IMAGE_TOPIC, "sensor_msgs/msg/CompressedImage"),
        (BOX_TOPIC, "vision_msgs/msg/Detection2DArray"),
    ):
        topics += (
            "    - topic_metadata:\n"
            f"        name: {topic}\n"
            f"        type: {type_name}\n"
            "        serialization_format: cdr\n"
            '        offered_qos_profiles: ""\n'
            f"      message_count: {counts[topic]}\n"
        )
    path.write_text(
        "rosbag2_bagfile_information:\n"
        "  version: 5\n"
        "  storage_identifier: mcap\n"
        f"  duration:\n    nanoseconds: {duration}\n"
        f"  starting_time:\n    nanoseconds_since_epoch: {start_ns}\n"
        f"  message_count: {total}\n"
        "  topics_with_message_count:\n"
        f"{topics}"
        '  compression_format: ""\n'
        '  compression_mode: ""\n'
        f"  relative_file_paths:\n    - {BAG_NAME}\n"
        "  files:\n"
        f"    - path: {BAG_NAME}\n"
        f"      starting_time:\n        nanoseconds_since_epoch: {start_ns}\n"
        f"      duration:\n        nanoseconds: {duration}\n"
        f"      message_count: {total}\n"
        "  custom_data: ~\n"
    )


def main() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bag_path = OUT_DIR / BAG_NAME
    frames_per_shot = int(SECONDS_PER_PHOTO * FPS)
    period_ns = 1_000_000_000 // FPS
    counts = {IMAGE_TOPIC: 0, BOX_TOPIC: 0}
    ns = START_NS
    with open(bag_path, "wb") as fh:
        writer = Writer(fh)
        image_schema = writer.register_msgdef(
            "sensor_msgs/msg/CompressedImage", COMPRESSED_IMAGE_MSGDEF
        )
        det_schema = writer.register_msgdef(
            "vision_msgs/msg/Detection2DArray", DETECTION2D_ARRAY_MSGDEF
        )
        seq = 0
        next_id = 1
        for shot in SHOTS:
            photo = load_photo(shot.photo)
            for k in range(frames_per_shot):
                t = k / max(frames_per_shot - 1, 1)
                crop = crop_at(shot, t)
                jpeg = render_frame(photo, crop)
                writer.write_message(
                    IMAGE_TOPIC,
                    image_schema,
                    {
                        "header": {"stamp": stamp(ns), "frame_id": FRAME_ID},
                        "format": "jpeg",
                        "data": jpeg,
                    },
                    log_time=ns,
                    publish_time=ns,
                    sequence=seq,
                )
                boxes = boxes_in_frame(shot.boxes, crop, ns / 1e9, next_id)
                det_ns = ns + 15_000_000  # the detector is 15 ms behind the camera
                writer.write_message(
                    BOX_TOPIC,
                    det_schema,
                    detection_msg(ns, boxes),
                    log_time=det_ns,
                    publish_time=det_ns,
                    sequence=seq,
                )
                counts[IMAGE_TOPIC] += 1
                counts[BOX_TOPIC] += 1
                seq += 1
                ns += period_ns
            next_id += len(shot.boxes)
        writer.finish()
    write_metadata(OUT_DIR / "metadata.yaml", START_NS, ns - period_ns + 15_000_000, counts)
    size_mb = bag_path.stat().st_size / 1e6
    print(f"wrote {bag_path} ({size_mb:.2f} MB), {sum(counts.values())} messages")
    return bag_path


if __name__ == "__main__":
    main()
