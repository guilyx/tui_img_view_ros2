"""ROS 2 transport built on rclpy.

Spins a node in a background thread. Image topics are decoded with
:mod:`tui_img_view.transports.ros2.codecs`; box topics through the adapters in
:mod:`tui_img_view.transports.ros2.detections`.

Options (``--transport-opt``): ``node_name``, ``qos`` (``sensor`` | ``reliable``),
``depth`` (history depth, default 1).
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from typing import Any

from tui_img_view.core.transport import (
    CallbackSubscription,
    DetectionsCallback,
    FrameCallback,
    Subscription,
    Transport,
    TransportUnavailable,
)
from tui_img_view.core.types import TopicInfo, TopicKind
from tui_img_view.transports.ros2.codecs import decode_compressed, decode_image
from tui_img_view.transports.ros2.detections import DETECTION_ADAPTERS

IMAGE_TYPES = ("sensor_msgs/msg/Image", "sensor_msgs/msg/CompressedImage")
log = logging.getLogger(__name__)


class Ros2Transport(Transport):
    name = "ros2"

    def __init__(
        self,
        *,
        node_name: str = "tui_img_view",
        qos: str = "sensor",
        depth: int = 1,
        args: list[str] | None = None,
    ) -> None:
        try:
            import rclpy  # noqa: F401
            from rosidl_runtime_py.utilities import get_message  # noqa: F401
        except ImportError as exc:
            raise TransportUnavailable(
                "rclpy is not importable. Source your ROS 2 workspace "
                "(e.g. `source /opt/ros/<distro>/setup.bash`) and retry."
            ) from exc
        if qos not in ("sensor", "reliable"):
            raise ValueError("qos must be 'sensor' or 'reliable'")
        self._node_name = node_name
        self._qos_kind = qos
        self._depth = max(1, int(depth))
        self._args = args
        self._node: Any = None
        self._executor: Any = None
        self._thread: threading.Thread | None = None
        self._we_initialised = False
        self._lock = threading.Lock()
        self._type_cache: dict[str, str] = {}

    @classmethod
    def from_options(cls, options: Mapping[str, str]) -> Ros2Transport:
        kwargs: dict[str, Any] = {}
        for key, value in options.items():
            if key == "node_name" or key == "qos":
                kwargs[key] = value
            elif key == "depth":
                kwargs[key] = int(value)
            else:
                raise ValueError(f"unknown ros2 transport option '{key}' (node_name, qos, depth)")
        return cls(**kwargs)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._node is not None:
            return
        import rclpy
        from rclpy.executors import SingleThreadedExecutor

        if not rclpy.ok():
            rclpy.init(args=self._args)
            self._we_initialised = True
        self._node = rclpy.create_node(self._node_name)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._thread = threading.Thread(target=self._spin, name="ros2-spin", daemon=True)
        self._thread.start()
        log.info(
            "node /%s spinning (qos=%s, depth=%d)", self._node_name, self._qos_kind, self._depth
        )

    def _spin(self) -> None:
        try:
            self._executor.spin()
        except Exception as exc:  # noqa: BLE001 - executor died; surface it
            self.last_error = f"executor stopped: {exc}"

    def stop(self) -> None:
        import rclpy

        executor, self._executor = self._executor, None
        node, self._node = self._node, None
        thread, self._thread = self._thread, None
        if executor is not None:
            executor.shutdown(timeout_sec=1.0)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if node is not None:
            node.destroy_node()
        if self._we_initialised and rclpy.ok():
            rclpy.shutdown()
            self._we_initialised = False

    # -- discovery ---------------------------------------------------------

    def _require_node(self) -> Any:
        if self._node is None:
            raise RuntimeError("Ros2Transport is not started")
        return self._node

    def list_topics(self) -> list[TopicInfo]:
        node = self._require_node()
        found: list[TopicInfo] = []
        for name, types in node.get_topic_names_and_types():
            for type_name in types:
                if type_name in IMAGE_TYPES:
                    found.append(TopicInfo(name, type_name, TopicKind.IMAGE))
                    self._type_cache[name] = type_name
                    break
                if type_name in DETECTION_ADAPTERS:
                    found.append(TopicInfo(name, type_name, TopicKind.BOXES))
                    self._type_cache[name] = type_name
                    break
        return found

    def _resolve_type(self, topic: str, fallback: str) -> str:
        node = self._require_node()
        for name, types in node.get_topic_names_and_types():
            if name == topic and types:
                for type_name in types:
                    if type_name in IMAGE_TYPES or type_name in DETECTION_ADAPTERS:
                        self._type_cache[name] = type_name
                        return type_name
                return types[0]
        return self._type_cache.get(topic, fallback)

    def _qos(self) -> Any:
        from rclpy.qos import (
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
            qos_profile_sensor_data,
        )

        if self._qos_kind == "sensor":
            return QoSProfile(
                reliability=qos_profile_sensor_data.reliability,
                durability=qos_profile_sensor_data.durability,
                history=HistoryPolicy.KEEP_LAST,
                depth=self._depth,
            )
        return QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=self._depth,
        )

    # -- subscriptions -----------------------------------------------------

    def _subscribe(self, topic: str, type_name: str, handler) -> Subscription:
        from rosidl_runtime_py.utilities import get_message

        node = self._require_node()
        msg_cls = get_message(type_name)

        def _on_msg(msg: Any) -> None:
            try:
                handler(msg)
            except Exception as exc:  # noqa: BLE001 - keep spinning, report in status bar
                if self.last_error != f"{topic}: {exc}":
                    log.error("%s: %s", topic, exc)
                self.last_error = f"{topic}: {exc}"

        with self._lock:
            sub = node.create_subscription(msg_cls, topic, _on_msg, self._qos())
        log.info("subscribed %s [%s]", topic, type_name)

        def _close() -> None:
            with self._lock:
                if self._node is not None:
                    self._node.destroy_subscription(sub)

        return CallbackSubscription(_close)

    def subscribe_image(self, topic: str, callback: FrameCallback) -> Subscription:
        fallback = (
            "sensor_msgs/msg/CompressedImage"
            if topic.endswith("/compressed")
            else "sensor_msgs/msg/Image"
        )
        type_name = self._resolve_type(topic, fallback)
        if type_name == "sensor_msgs/msg/CompressedImage":
            decode = decode_compressed
        elif type_name == "sensor_msgs/msg/Image":
            decode = decode_image
        else:
            raise LookupError(f"{topic} has type {type_name}, which is not an image type")
        return self._subscribe(topic, type_name, lambda msg: callback(decode(msg)))

    def subscribe_boxes(self, topic: str, callback: DetectionsCallback) -> Subscription:
        type_name = self._resolve_type(topic, "vision_msgs/msg/Detection2DArray")
        adapter = DETECTION_ADAPTERS.get(type_name)
        if adapter is None:
            raise LookupError(
                f"{topic} has type {type_name}; supported: {', '.join(sorted(DETECTION_ADAPTERS))}"
            )

        def _handle(msg: Any) -> None:
            dets = adapter(msg)
            dets.source = topic
            callback(dets)

        return self._subscribe(topic, type_name, _handle)
