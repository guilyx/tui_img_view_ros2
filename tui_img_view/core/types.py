"""Plain data types shared by transports, the renderer and the UI.

Nothing in here depends on ROS or on any terminal library. A transport turns
its native messages into :class:`Frame` and :class:`Detections`; everything
downstream only ever sees these.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class TopicKind(Enum):
    """What a topic carries, as far as the viewer is concerned."""

    IMAGE = "image"
    BOXES = "boxes"


@dataclass(frozen=True)
class TopicInfo:
    """A subscribable source discovered by a transport."""

    name: str
    type: str
    kind: TopicKind

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.name} [{self.type}]"


@dataclass(frozen=True)
class BoundingBox:
    """An axis-aligned box in *source image pixel* coordinates.

    ``x``/``y`` is the top-left corner. Coordinates are floats so that
    transports can pass through sub-pixel values untouched.
    """

    x: float
    y: float
    w: float
    h: float
    label: str = ""
    score: float | None = None
    track_id: str | None = None

    @classmethod
    def from_center(
        cls,
        cx: float,
        cy: float,
        w: float,
        h: float,
        *,
        label: str = "",
        score: float | None = None,
        track_id: str | None = None,
    ) -> BoundingBox:
        """Build a box from its center and size (the vision_msgs convention)."""
        return cls(cx - w / 2.0, cy - h / 2.0, w, h, label=label, score=score, track_id=track_id)

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def caption(self) -> str:
        """Short human text for the overlay: ``#id label 0.87``."""
        parts: list[str] = []
        if self.track_id:
            parts.append(f"#{self.track_id}")
        if self.label:
            parts.append(self.label)
        if self.score is not None:
            parts.append(f"{self.score:.2f}")
        return " ".join(parts)


@dataclass
class Frame:
    """One decoded image as an ``HxWx3`` ``uint8`` RGB array."""

    pixels: np.ndarray
    stamp: float = 0.0
    frame_id: str = ""
    encoding: str = ""
    received_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        px = np.asarray(self.pixels)
        if px.ndim == 2:
            px = np.repeat(px[:, :, None], 3, axis=2)
        if px.ndim != 3 or px.shape[2] != 3:
            raise ValueError(f"Frame pixels must be HxWx3, got shape {px.shape}")
        if px.dtype != np.uint8:
            px = np.clip(px, 0, 255).astype(np.uint8)
        self.pixels = np.ascontiguousarray(px)

    @property
    def width(self) -> int:
        return int(self.pixels.shape[1])

    @property
    def height(self) -> int:
        return int(self.pixels.shape[0])


@dataclass
class Detections:
    """A set of boxes that belong to one image (or one moment in time)."""

    boxes: tuple[BoundingBox, ...] = ()
    stamp: float = 0.0
    frame_id: str = ""
    source: str = ""
    received_at: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.boxes = tuple(self.boxes)

    def __len__(self) -> int:
        return len(self.boxes)
