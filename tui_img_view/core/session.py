"""The viewer session: what is selected, and the latest data for it.

The session sits between a :class:`~tui_img_view.core.transport.Transport`
(pushing from arbitrary threads) and a UI (polling from its own loop). It has
no dependency on the terminal layer, so it can be driven from tests or from
other front-ends.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

from tui_img_view.core.transport import Subscription, Transport
from tui_img_view.core.types import Detections, Frame, TopicInfo, TopicKind

log = logging.getLogger(__name__)


class RateMeter:
    """Sliding-window event rate."""

    def __init__(self, window: float = 2.0) -> None:
        self._window = window
        self._ticks: deque[float] = deque()

    def tick(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._ticks.append(now)
        self._trim(now)

    def _trim(self, now: float) -> None:
        cutoff = now - self._window
        while self._ticks and self._ticks[0] < cutoff:
            self._ticks.popleft()

    def rate(self, now: float | None = None) -> float:
        now = time.monotonic() if now is None else now
        self._trim(now)
        if len(self._ticks) < 2:
            return 0.0
        span = self._ticks[-1] - self._ticks[0]
        return (len(self._ticks) - 1) / span if span > 0 else 0.0


@dataclass(frozen=True)
class Snapshot:
    """Immutable view of the session state for one UI refresh."""

    version: int
    frame: Frame | None
    detections: tuple[Detections, ...]
    image_topic: str | None
    box_topics: tuple[str, ...]
    fps: float
    paused: bool
    error: str | None = None
    topics: tuple[TopicInfo, ...] = field(default=())

    @property
    def box_count(self) -> int:
        return sum(len(d) for d in self.detections)


class ViewerSession:
    """Owns subscriptions and the most recent frame/detections.

    Thread-safe: transport callbacks may arrive from any thread while the UI
    calls :meth:`snapshot` from another.
    """

    def __init__(self, transport: Transport, *, stale_after: float = 2.0) -> None:
        self.transport = transport
        self.stale_after = stale_after
        self._lock = threading.Lock()
        self._version = 0
        self._frame: Frame | None = None
        self._detections: dict[str, Detections] = {}
        self._image_topic: str | None = None
        self._image_sub: Subscription | None = None
        self._box_subs: dict[str, Subscription] = {}
        self._fps = RateMeter()
        self._paused = False
        self._error: str | None = None
        self._topics: tuple[TopicInfo, ...] = ()
        self._started = False

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if not self._started:
            self.transport.start()
            self._started = True

    def stop(self) -> None:
        with self._lock:
            subs = list(self._box_subs.values())
            if self._image_sub is not None:
                subs.append(self._image_sub)
            self._image_sub = None
            self._box_subs.clear()
        for sub in subs:
            _safe_close(sub)
        if self._started:
            self.transport.stop()
            self._started = False

    def __enter__(self) -> ViewerSession:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- topics ------------------------------------------------------------

    def refresh_topics(self) -> tuple[TopicInfo, ...]:
        try:
            topics = tuple(sorted(self.transport.list_topics(), key=lambda t: t.name))
        except Exception as exc:  # noqa: BLE001 - surface, don't crash the UI
            self._set_error(f"list_topics failed: {exc}")
            return self._topics
        with self._lock:
            self._topics = topics
        return topics

    @property
    def topics(self) -> tuple[TopicInfo, ...]:
        return self._topics

    def image_topics(self) -> list[str]:
        return [t.name for t in self._topics if t.kind is TopicKind.IMAGE]

    def box_topics_available(self) -> list[str]:
        return [t.name for t in self._topics if t.kind is TopicKind.BOXES]

    # -- selection ---------------------------------------------------------

    @property
    def image_topic(self) -> str | None:
        return self._image_topic

    @property
    def box_topics(self) -> tuple[str, ...]:
        return tuple(self._box_subs)

    def select_image(self, topic: str | None) -> None:
        """Switch the displayed image topic (``None`` unsubscribes)."""
        with self._lock:
            if topic == self._image_topic and (topic is None or self._image_sub is not None):
                return
            old = self._image_sub
            self._image_sub = None
            self._image_topic = topic
            self._frame = None
            self._version += 1
        if old is not None:
            _safe_close(old)
        if topic is None:
            return
        try:
            sub = self.transport.subscribe_image(topic, self._on_frame)
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"subscribe {topic}: {exc}")
            return
        log.info("subscribed image %s", topic)
        with self._lock:
            if self._image_topic == topic:
                self._image_sub = sub
                sub = None
        if sub is not None:  # selection changed under us
            _safe_close(sub)

    def next_image(self, step: int = 1) -> str | None:
        """Cycle through the known image topics."""
        names = self.image_topics()
        if not names:
            return None
        if self._image_topic in names:
            idx = (names.index(self._image_topic) + step) % len(names)
        else:
            idx = 0
        self.select_image(names[idx])
        return names[idx]

    def set_box_topics(self, topics: Iterable[str]) -> None:
        wanted = set(topics)
        with self._lock:
            current = set(self._box_subs)
        for topic in current - wanted:
            self.remove_box_topic(topic)
        for topic in wanted - current:
            self.add_box_topic(topic)

    def add_box_topic(self, topic: str) -> None:
        with self._lock:
            if topic in self._box_subs:
                return
        try:
            sub = self.transport.subscribe_boxes(topic, self._make_box_callback(topic))
        except Exception as exc:  # noqa: BLE001
            self._set_error(f"subscribe {topic}: {exc}")
            return
        log.info("subscribed boxes %s", topic)
        with self._lock:
            self._box_subs[topic] = sub
            self._version += 1

    def remove_box_topic(self, topic: str) -> None:
        with self._lock:
            sub = self._box_subs.pop(topic, None)
            self._detections.pop(topic, None)
            self._version += 1
        if sub is not None:
            _safe_close(sub)
            log.info("unsubscribed boxes %s", topic)

    def toggle_box_topic(self, topic: str) -> bool:
        if topic in self._box_subs:
            self.remove_box_topic(topic)
            return False
        self.add_box_topic(topic)
        return True

    # -- playback ----------------------------------------------------------

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = paused
            self._version += 1

    def toggle_pause(self) -> bool:
        self.set_paused(not self._paused)
        return self._paused

    # -- data --------------------------------------------------------------

    def _on_frame(self, frame: Frame) -> None:
        with self._lock:
            self._fps.tick()
            if self._paused:
                return
            self._frame = frame
            self._version += 1

    def _make_box_callback(self, topic: str):
        def _on_detections(dets: Detections) -> None:
            if not dets.source:
                dets.source = topic
            with self._lock:
                if self._paused or topic not in self._box_subs:
                    return
                self._detections[topic] = dets
                self._version += 1

        return _on_detections

    def _set_error(self, message: str) -> None:
        log.warning("%s", message)
        with self._lock:
            self._error = message
            self._version += 1

    def clear_error(self) -> None:
        with self._lock:
            self._error = None

    def push_frame(self, frame: Frame) -> None:
        """Inject a frame directly (bypassing the transport). Handy for tests."""
        self._on_frame(frame)

    def snapshot(self) -> Snapshot:
        now = time.monotonic()
        with self._lock:
            live = tuple(
                d
                for topic, d in self._detections.items()
                if topic in self._box_subs and (now - d.received_at) <= self.stale_after
            )
            error = self._error or self.transport.last_error
            return Snapshot(
                version=self._version,
                frame=self._frame,
                detections=live,
                image_topic=self._image_topic,
                box_topics=tuple(self._box_subs),
                fps=self._fps.rate(now),
                paused=self._paused,
                error=error,
                topics=self._topics,
            )

    @property
    def version(self) -> int:
        return self._version


def _safe_close(sub: Subscription) -> None:
    # Never let teardown explode.
    with contextlib.suppress(Exception):
        sub.close()
