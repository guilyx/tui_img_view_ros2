"""tui_img_view: a terminal image + bounding-box viewer with pluggable transports.

The core (``tui_img_view.core``, ``tui_img_view.render``) knows nothing about
ROS. Transports (``tui_img_view.transports``) adapt a message source to the
small :class:`~tui_img_view.core.transport.Transport` interface.
"""

from __future__ import annotations

from tui_img_view.core.transport import Subscription, Transport, TransportUnavailable
from tui_img_view.core.types import BoundingBox, Detections, Frame, TopicInfo, TopicKind

__version__ = "0.1.0"

__all__ = [
    "BoundingBox",
    "Detections",
    "Frame",
    "Subscription",
    "TopicInfo",
    "TopicKind",
    "Transport",
    "TransportUnavailable",
    "__version__",
]
