"""Play a ROS 2 bag (MCAP storage) straight into the viewer, no ROS needed.

Uses the ``mcap`` and ``mcap-ros2-support`` packages to read CDR messages and
decode them into plain attribute objects, which the same codecs and detection
adapters as the live ROS 2 transport then consume.

Options (``-o``): ``path`` (an ``.mcap`` file or a rosbag2 directory, required),
``rate`` (playback speed multiplier, default 1), ``loop`` (default true).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from tui_img_view.core.transport import (
    DetectionsCallback,
    FrameCallback,
    Subscription,
    Transport,
    TransportUnavailable,
)
from tui_img_view.core.types import Detections, Frame, TopicInfo, TopicKind
from tui_img_view.transports.manual import ManualTransport
from tui_img_view.transports.ros2.codecs import decode_compressed, decode_image
from tui_img_view.transports.ros2.detections import DETECTION_ADAPTERS
from tui_img_view.transports.ros2.transport import IMAGE_TYPES

log = logging.getLogger(__name__)


def resolve_bag_file(path: str | Path) -> Path:
    """Accept an ``.mcap`` file or a rosbag2 directory containing one."""
    p = Path(path).expanduser()
    if p.is_dir():
        candidates = sorted(p.glob("*.mcap"))
        if not candidates:
            raise FileNotFoundError(f"no .mcap file in {p}")
        return candidates[0]
    if not p.is_file():
        raise FileNotFoundError(f"bag not found: {p}")
    return p


class McapTransport(Transport):
    name = "bag"

    def __init__(self, path: str | Path, *, rate: float = 1.0, loop: bool = True) -> None:
        try:
            from mcap.reader import make_reader  # noqa: F401
            from mcap_ros2.decoder import DecoderFactory  # noqa: F401
        except ImportError as exc:
            raise TransportUnavailable(
                "the bag transport needs `pip install mcap mcap-ros2-support` "
                "(or `pip install tui_img_view[bag]`)"
            ) from exc
        self.path = resolve_bag_file(path)
        self.rate = max(0.01, float(rate))
        self.loop = bool(loop)
        self._inner = ManualTransport()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._fh: Any = None
        self._reader: Any = None
        self._decoders: dict[int, Callable[[bytes], Any]] = {}
        self._topic_types: dict[str, str] = {}
        self.loops_completed = 0

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> McapTransport:
        opts = dict(options)
        path = opts.pop("path", None)
        if not path:
            raise ValueError("bag transport needs -o path=<file.mcap or rosbag2 dir>")
        kwargs: dict[str, Any] = {}
        if "rate" in opts:
            kwargs["rate"] = float(opts.pop("rate"))
        if "loop" in opts:
            kwargs["loop"] = opts.pop("loop").lower() in ("1", "true", "yes", "on")
        if opts:
            raise ValueError(f"unknown bag transport option(s): {', '.join(sorted(opts))}")
        return cls(path, **kwargs)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        from mcap.reader import make_reader
        from mcap_ros2.decoder import DecoderFactory

        self._fh = open(self.path, "rb")  # noqa: SIM115 - lives for the whole playback
        self._reader = make_reader(self._fh)
        self._factory = DecoderFactory()
        summary = self._reader.get_summary()
        if summary is None:
            raise ValueError(f"{self.path} has no summary section; re-index the bag")
        for channel in summary.channels.values():
            schema = summary.schemas.get(channel.schema_id)
            if schema is None:
                continue
            kind = None
            if schema.name in IMAGE_TYPES:
                kind = TopicKind.IMAGE
            elif schema.name in DETECTION_ADAPTERS:
                kind = TopicKind.BOXES
            if kind is not None:
                self._inner.add_topic(channel.topic, kind, schema.name)
                self._topic_types[channel.topic] = schema.name
        stats = summary.statistics
        if stats is not None:
            span = (stats.message_end_time - stats.message_start_time) / 1e9
            log.info(
                "bag %s: %d messages, %.1fs, rate x%g%s",
                self.path.name,
                stats.message_count,
                span,
                self.rate,
                ", loop" if self.loop else "",
            )
        self._stop.clear()
        self._inner.start()
        self._thread = threading.Thread(target=self._run, name="bag-playback", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._inner.stop()
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._reader = None

    # -- Transport API -----------------------------------------------------

    def list_topics(self) -> list[TopicInfo]:
        return self._inner.list_topics()

    def subscribe_image(self, topic: str, callback: FrameCallback) -> Subscription:
        if self._topic_types.get(topic) not in IMAGE_TYPES:
            raise LookupError(f"{topic} is not an image topic in {self.path.name}")
        return self._inner.subscribe_image(topic, callback)

    def subscribe_boxes(self, topic: str, callback: DetectionsCallback) -> Subscription:
        if self._topic_types.get(topic) not in DETECTION_ADAPTERS:
            raise LookupError(f"{topic} is not a detection topic in {self.path.name}")
        return self._inner.subscribe_boxes(topic, callback)

    # -- playback ----------------------------------------------------------

    def _decode(self, schema: Any, data: bytes) -> Any:
        decoder = self._decoders.get(schema.id)
        if decoder is None:
            decoder = self._factory.decoder_for("cdr", schema)
            if decoder is None:
                raise ValueError(f"no decoder for schema {schema.name}")
            self._decoders[schema.id] = decoder
        return decoder(data)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._play_once()
            if not self.loop:
                log.info("bag finished")
                break
            self.loops_completed += 1
            log.info("bag loop %d", self.loops_completed)

    def _play_once(self) -> None:
        first_log: int | None = None
        wall_start = time.monotonic()
        for schema, channel, message in self._reader.iter_messages():
            if self._stop.is_set():
                return
            if first_log is None:
                first_log = message.log_time
            target = wall_start + (message.log_time - first_log) / 1e9 / self.rate
            delay = target - time.monotonic()
            if delay > 0 and self._stop.wait(delay):
                return
            topic = channel.topic
            if not self._inner.subscriber_count(topic):
                continue
            try:
                self._dispatch(topic, schema, message.data)
            except Exception as exc:  # noqa: BLE001 - keep playing, report in status bar
                self.last_error = f"{topic}: {exc}"

    def _dispatch(self, topic: str, schema: Any, data: bytes) -> None:
        type_name = schema.name
        decoded = self._decode(schema, data)
        if type_name == "sensor_msgs/msg/CompressedImage":
            frame: Frame = decode_compressed(decoded)
            self._inner.push_frame(topic, frame)
        elif type_name == "sensor_msgs/msg/Image":
            self._inner.push_frame(topic, decode_image(decoded))
        else:
            dets: Detections = DETECTION_ADAPTERS[type_name](decoded)
            dets.source = topic
            self._inner.push_boxes(topic, dets)
