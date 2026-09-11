"""A transport you feed by hand. Useful for tests and for embedding the viewer."""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Mapping

from tui_img_view.core.transport import (
    CallbackSubscription,
    DetectionsCallback,
    FrameCallback,
    Subscription,
    Transport,
)
from tui_img_view.core.types import Detections, Frame, TopicInfo, TopicKind


class ManualTransport(Transport):
    name = "manual"

    def __init__(self, topics: list[TopicInfo] | None = None) -> None:
        self._topics: list[TopicInfo] = list(topics or [])
        self._image_cbs: dict[str, list[FrameCallback]] = defaultdict(list)
        self._box_cbs: dict[str, list[DetectionsCallback]] = defaultdict(list)
        self._lock = threading.Lock()
        self.started = False

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> ManualTransport:
        return cls()

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def add_topic(self, name: str, kind: TopicKind, type_: str = "manual") -> None:
        with self._lock:
            self._topics = [t for t in self._topics if t.name != name]
            self._topics.append(TopicInfo(name, type_, kind))

    def list_topics(self) -> list[TopicInfo]:
        with self._lock:
            return list(self._topics)

    def subscribe_image(self, topic: str, callback: FrameCallback) -> Subscription:
        with self._lock:
            self._image_cbs[topic].append(callback)

        def _close() -> None:
            with self._lock:
                if callback in self._image_cbs[topic]:
                    self._image_cbs[topic].remove(callback)

        return CallbackSubscription(_close)

    def subscribe_boxes(self, topic: str, callback: DetectionsCallback) -> Subscription:
        with self._lock:
            self._box_cbs[topic].append(callback)

        def _close() -> None:
            with self._lock:
                if callback in self._box_cbs[topic]:
                    self._box_cbs[topic].remove(callback)

        return CallbackSubscription(_close)

    # -- producer side -----------------------------------------------------

    def push_frame(self, topic: str, frame: Frame) -> int:
        with self._lock:
            cbs = list(self._image_cbs.get(topic, ()))
        for cb in cbs:
            cb(frame)
        return len(cbs)

    def push_boxes(self, topic: str, dets: Detections) -> int:
        with self._lock:
            cbs = list(self._box_cbs.get(topic, ()))
        for cb in cbs:
            cb(dets)
        return len(cbs)

    def subscriber_count(self, topic: str) -> int:
        with self._lock:
            return len(self._image_cbs.get(topic, ())) + len(self._box_cbs.get(topic, ()))
