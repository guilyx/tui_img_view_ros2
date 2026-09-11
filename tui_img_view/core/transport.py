"""The transport interface.

A transport is the *only* thing that knows where frames come from. Implement
:class:`Transport` to plug in a new source (ROS 2, ZeroMQ, a video file, a
websocket, ...). Callbacks may be invoked from any thread; the viewer session
handles synchronisation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import ClassVar, Protocol

from tui_img_view.core.types import Detections, Frame, TopicInfo

FrameCallback = Callable[[Frame], None]
DetectionsCallback = Callable[[Detections], None]


class TransportUnavailable(RuntimeError):
    """Raised when a transport cannot run in this environment (missing deps, ...)."""


class Subscription(Protocol):
    """Handle returned by ``subscribe_*``; ``close()`` stops the callbacks."""

    def close(self) -> None: ...


class CallbackSubscription:
    """Minimal :class:`Subscription` that runs a closure once on close."""

    __slots__ = ("_on_close", "_closed")

    def __init__(self, on_close: Callable[[], None]) -> None:
        self._on_close = on_close
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._on_close()


class Transport(ABC):
    """Abstract message source.

    Lifecycle: construct → :meth:`start` → subscribe/list → :meth:`stop`.
    Implementations must be safe to ``stop()`` more than once.
    """

    #: Short identifier used on the command line (``--transport NAME``).
    name: ClassVar[str] = "abstract"

    #: Most recent error message produced by a decoder/callback, for the status bar.
    last_error: str | None = None

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Transport:
        """Build a transport from ``key=value`` CLI options. Override to accept options."""
        if options:
            unknown = ", ".join(sorted(options))
            raise ValueError(f"transport '{cls.name}' accepts no options (got: {unknown})")
        return cls()

    @abstractmethod
    def start(self) -> None:
        """Connect / spin up background threads."""

    @abstractmethod
    def stop(self) -> None:
        """Tear everything down. Idempotent."""

    @abstractmethod
    def list_topics(self) -> list[TopicInfo]:
        """Return currently visible image and box topics."""

    @abstractmethod
    def subscribe_image(self, topic: str, callback: FrameCallback) -> Subscription:
        """Deliver every decoded image published on ``topic`` to ``callback``."""

    @abstractmethod
    def subscribe_boxes(self, topic: str, callback: DetectionsCallback) -> Subscription:
        """Deliver every detection set published on ``topic`` to ``callback``."""

    def __enter__(self) -> Transport:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
