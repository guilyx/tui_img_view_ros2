"""Synthetic camera + detector. Lets you try the viewer with no ROS at all.

Publishes a moving scene with bouncing objects on ``/camera/image_raw`` and
matching boxes on ``/detector/detections`` (scored classes) and
``/tracker/tracks`` (track ids). Pass ``file=<image>`` to show a real picture
with a scanning box instead.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from tui_img_view.core.transport import Subscription, Transport
from tui_img_view.core.types import BoundingBox, Detections, Frame, TopicInfo, TopicKind
from tui_img_view.transports.manual import ManualTransport

IMAGE_TOPIC = "/camera/image_raw"
GRAY_TOPIC = "/camera/mono/image_raw"
DETECTIONS_TOPIC = "/detector/detections"
TRACKS_TOPIC = "/tracker/tracks"
log = logging.getLogger(__name__)


class _Ball:
    __slots__ = ("x", "y", "vx", "vy", "r", "color", "label")

    def __init__(self, rng: np.random.Generator, w: int, h: int, idx: int) -> None:
        labels = ("ball", "robot", "cone", "person")
        colors = ((240, 80, 60), (60, 200, 90), (250, 200, 40), (80, 120, 250))
        self.r = int(min(w, h) * rng.uniform(0.06, 0.12))
        self.x = float(rng.uniform(self.r, w - self.r))
        self.y = float(rng.uniform(self.r, h - self.r))
        speed = min(w, h) * 0.35
        angle = rng.uniform(0, 2 * math.pi)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = colors[idx % len(colors)]
        self.label = labels[idx % len(labels)]

    def step(self, dt: float, w: int, h: int) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x - self.r < 0:
            self.x, self.vx = float(self.r), abs(self.vx)
        elif self.x + self.r > w:
            self.x, self.vx = float(w - self.r), -abs(self.vx)
        if self.y - self.r < 0:
            self.y, self.vy = float(self.r), abs(self.vy)
        elif self.y + self.r > h:
            self.y, self.vy = float(h - self.r), -abs(self.vy)


class FakeTransport(Transport):
    name = "fake"

    def __init__(
        self,
        *,
        fps: float = 15.0,
        width: int = 320,
        height: int = 240,
        objects: int = 3,
        file: str | Path | None = None,
        seed: int = 0,
    ) -> None:
        self.fps = max(0.5, float(fps))
        self.width = int(width)
        self.height = int(height)
        self._file = Path(file) if file else None
        self._photo: np.ndarray | None = None
        self._rng = np.random.default_rng(seed)
        self._balls = [_Ball(self._rng, self.width, self.height, i) for i in range(int(objects))]
        self._inner = ManualTransport(
            [
                TopicInfo(IMAGE_TOPIC, "sensor_msgs/msg/Image", TopicKind.IMAGE),
                TopicInfo(GRAY_TOPIC, "sensor_msgs/msg/Image", TopicKind.IMAGE),
                TopicInfo(DETECTIONS_TOPIC, "vision_msgs/msg/Detection2DArray", TopicKind.BOXES),
                TopicInfo(TRACKS_TOPIC, "vision_msgs/msg/Detection2DArray", TopicKind.BOXES),
            ]
        )
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._seq = 0
        yy, xx = np.mgrid[0 : self.height, 0 : self.width]
        self._yy = yy.astype(np.float32)
        self._xx = xx.astype(np.float32)

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> FakeTransport:
        kwargs: dict[str, object] = {}
        for key, value in options.items():
            if key in ("fps",):
                kwargs[key] = float(value)
            elif key in ("width", "height", "objects", "seed"):
                kwargs[key] = int(value)
            elif key == "file":
                kwargs[key] = value
            else:
                raise ValueError(
                    f"unknown fake transport option '{key}' "
                    "(fps, width, height, objects, file, seed)"
                )
        return cls(**kwargs)  # type: ignore[arg-type]

    # -- Transport API -----------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        if self._file is not None:
            from PIL import Image

            img = Image.open(self._file).convert("RGB")
            self._photo = np.asarray(img, dtype=np.uint8)
            self.height, self.width = self._photo.shape[:2]
        self._stop.clear()
        self._inner.start()
        self._thread = threading.Thread(target=self._run, name="fake-transport", daemon=True)
        self._thread.start()
        log.info("fake scene %dx%d at %g fps", self.width, self.height, self.fps)

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._inner.stop()

    def list_topics(self) -> list[TopicInfo]:
        return self._inner.list_topics()

    def subscribe_image(self, topic, callback) -> Subscription:
        if topic not in (IMAGE_TOPIC, GRAY_TOPIC):
            raise LookupError(f"fake transport has no image topic {topic!r}")
        return self._inner.subscribe_image(topic, callback)

    def subscribe_boxes(self, topic, callback) -> Subscription:
        if topic not in (DETECTIONS_TOPIC, TRACKS_TOPIC):
            raise LookupError(f"fake transport has no box topic {topic!r}")
        return self._inner.subscribe_boxes(topic, callback)

    # -- scene -------------------------------------------------------------

    def _run(self) -> None:
        period = 1.0 / self.fps
        last = time.monotonic()
        while not self._stop.is_set():
            now = time.monotonic()
            dt = min(now - last, 0.25)
            last = now
            self.publish_once(now, dt)
            self._stop.wait(max(0.0, period - (time.monotonic() - now)))

    def publish_once(self, now: float | None = None, dt: float = 0.0) -> None:
        """Advance the scene and push one frame + detections to subscribers."""
        now = time.monotonic() if now is None else now
        self._seq += 1
        stamp = time.time()
        if self._photo is not None:
            pixels, boxes = self._photo_scene(now)
        else:
            pixels, boxes = self._synthetic_scene(now, dt)
        frame = Frame(pixels, stamp=stamp, frame_id="camera", encoding="rgb8")
        self._inner.push_frame(IMAGE_TOPIC, frame)
        if self._inner.subscriber_count(GRAY_TOPIC):
            gray = pixels.mean(axis=2).astype(np.uint8)
            self._inner.push_frame(
                GRAY_TOPIC, Frame(gray, stamp=stamp, frame_id="camera", encoding="mono8")
            )
        self._inner.push_boxes(DETECTIONS_TOPIC, Detections(boxes, stamp=stamp, frame_id="camera"))
        tracks = tuple(
            BoundingBox(b.x, b.y, b.w, b.h, label="", score=None, track_id=str(i + 1))
            for i, b in enumerate(boxes)
        )
        self._inner.push_boxes(TRACKS_TOPIC, Detections(tracks, stamp=stamp, frame_id="camera"))

    def _synthetic_scene(self, now: float, dt: float) -> tuple[np.ndarray, tuple[BoundingBox, ...]]:
        h, w = self.height, self.width
        t = now % 1000.0
        grad = self._yy / max(h - 1, 1)
        img = np.empty((h, w, 3), dtype=np.float32)
        img[..., 0] = 20 + 40 * grad
        img[..., 1] = 30 + 60 * grad
        img[..., 2] = 70 + 110 * grad
        stripes = ((self._xx + self._yy + t * 40.0) // 24.0) % 2.0
        img += stripes[..., None] * 14.0
        boxes: list[BoundingBox] = []
        for ball in self._balls:
            ball.step(dt, w, h)
            d2 = (self._xx - ball.x) ** 2 + (self._yy - ball.y) ** 2
            mask = d2 <= ball.r * ball.r
            shade = 1.0 - 0.45 * np.sqrt(np.clip(d2 / max(ball.r * ball.r, 1), 0, 1))
            color = np.array(ball.color, dtype=np.float32)
            img[mask] = color * shade[mask][:, None]
            jitter = float(self._rng.normal(0, 1.5))
            score = 0.55 + 0.45 * abs(math.sin(t * 0.7 + ball.r))
            boxes.append(
                BoundingBox(
                    ball.x - ball.r + jitter,
                    ball.y - ball.r + jitter,
                    2 * ball.r,
                    2 * ball.r,
                    label=ball.label,
                    score=round(score, 2),
                )
            )
        return np.clip(img, 0, 255).astype(np.uint8), tuple(boxes)

    def _photo_scene(self, now: float) -> tuple[np.ndarray, tuple[BoundingBox, ...]]:
        assert self._photo is not None
        h, w = self.height, self.width
        phase = (now * 0.15) % 1.0
        bw, bh = w * 0.25, h * 0.4
        x = phase * (w - bw)
        y = (0.5 + 0.3 * math.sin(now)) * (h - bh)
        boxes = (
            BoundingBox(x, y, bw, bh, label="scan", score=round(0.5 + phase / 2, 2)),
            BoundingBox(w * 0.1, h * 0.1, w * 0.3, h * 0.3, label="static", score=0.99),
        )
        return self._photo, boxes
