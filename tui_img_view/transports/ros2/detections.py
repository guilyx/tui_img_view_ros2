"""Convert detection messages into :class:`~tui_img_view.core.types.Detections`.

Adapters are keyed by ROS type string and duck-typed on the message. Plug in
your own message type in one of these ways:

* Python: decorate a function with :func:`register_detection_adapter`.
* CLI, code: ``--adapter my_pkg.adapters`` imports a module that does the above.
* CLI, no code: ``--box-type "pkg/msg/Type:items=...,x=...,y=...,w=...,h=..."``
  or ``--box-types file.toml`` describe where the fields live
  (see :class:`BoxFieldMap`).
* Packaging: expose a ``tui_img_view.detection_adapters`` entry point.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Plugging in custom message types
# ---------------------------------------------------------------------------

ADAPTER_ENTRY_POINT_GROUP = "tui_img_view.detection_adapters"


def load_adapter_plugins(modules: Iterable[str]) -> list[str]:
    """Import ``module`` or ``module:callable`` entries so they can register adapters.

    A bare module is imported for its side effects (decorators run). With a
    ``:callable`` suffix the callable is invoked with no arguments after import.
    Returns the list of adapter type names registered by the plugins.
    """
    before = set(DETECTION_ADAPTERS)
    for entry in modules:
        module_name, _, attr = entry.partition(":")
        module = importlib.import_module(module_name)
        if attr:
            getattr(module, attr)()
    return sorted(set(DETECTION_ADAPTERS) - before)


def load_entry_point_adapters() -> list[str]:
    """Import every ``tui_img_view.detection_adapters`` entry point (each registers itself)."""
    try:
        eps = metadata.entry_points(group=ADAPTER_ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - Python < 3.10 API
        eps = metadata.entry_points().get(ADAPTER_ENTRY_POINT_GROUP, [])
    before = set(DETECTION_ADAPTERS)
    for ep in eps:
        loaded = ep.load()
        if callable(loaded) and not isinstance(loaded, type):
            loaded()
    return sorted(set(DETECTION_ADAPTERS) - before)


_INDEX_RE = re.compile(r"\[(-?\d+)\]")


def resolve_path(obj: Any, path: str) -> Any:
    """Follow a dotted attribute path with optional indexes: ``results[0].hypothesis.score``."""
    if not path or path == ".":
        return obj
    for segment in path.split("."):
        name = segment.split("[", 1)[0]
        if name:
            obj = getattr(obj, name)
        for index in _INDEX_RE.findall(segment):
            obj = obj[int(index)]
    return obj


@dataclass(frozen=True)
class BoxFieldMap:
    """Declarative adapter: where in a message to find each box field.

    ``items`` is the path to the sequence of detections (empty means the
    message itself is one detection). The other paths are relative to one
    item. ``origin`` is ``topleft`` or ``center`` for what ``x``/``y`` mean.
    """

    type_name: str
    x: str
    y: str
    w: str
    h: str
    items: str = ""
    label: str | None = None
    score: str | None = None
    id: str | None = None
    origin: str = "topleft"

    def __post_init__(self) -> None:
        if self.origin not in ("topleft", "center"):
            raise ValueError(f"origin must be 'topleft' or 'center', got {self.origin!r}")

    def __call__(self, msg: Any) -> Detections:
        stamp, frame_id = _header_fields(msg)
        items = resolve_path(msg, self.items) if self.items else (msg,)
        boxes = []
        for item in items:
            x, y = float(resolve_path(item, self.x)), float(resolve_path(item, self.y))
            w, h = float(resolve_path(item, self.w)), float(resolve_path(item, self.h))
            label = str(resolve_path(item, self.label)) if self.label else ""
            score = float(resolve_path(item, self.score)) if self.score else None
            track_id = str(resolve_path(item, self.id)) if self.id else ""
            kwargs = {"label": label, "score": score, "track_id": track_id or None}
            if self.origin == "center":
                boxes.append(BoundingBox.from_center(x, y, w, h, **kwargs))
            else:
                boxes.append(BoundingBox(x, y, w, h, **kwargs))
        return Detections(tuple(boxes), stamp=stamp, frame_id=frame_id)

    def register(self) -> BoxFieldMap:
        DETECTION_ADAPTERS[self.type_name] = self
        return self


_SPEC_KEYS = {"items", "x", "y", "w", "h", "label", "score", "id", "origin"}


def parse_box_type_spec(spec: str) -> BoxFieldMap:
    """Parse ``pkg/msg/Type:items=objects,x=bbox.x,y=bbox.y,w=bbox.w,h=bbox.h[,...]``.

    Optional keys: ``label``, ``score``, ``id``, ``origin=topleft|center``.
    """
    type_name, sep, rest = spec.partition(":")
    type_name = type_name.strip()
    if not sep or not type_name or type_name.count("/") != 2:
        raise ValueError(
            f"bad box type spec {spec!r}: expected 'pkg/msg/Type:key=path,...' "
            f"(keys: {', '.join(sorted(_SPEC_KEYS))})"
        )
    fields: dict[str, str] = {}
    for part in rest.split(","):
        part = part.strip()
        if not part:
            continue
        key, eq, value = part.partition("=")
        key = key.strip()
        if not eq or key not in _SPEC_KEYS:
            raise ValueError(f"bad box type spec {spec!r}: unknown or malformed field {part!r}")
        fields[key] = value.strip()
    missing = [k for k in ("x", "y", "w", "h") if k not in fields]
    if missing:
        raise ValueError(f"bad box type spec {spec!r}: missing {', '.join(missing)}")
    return BoxFieldMap(type_name=type_name, **fields)


def load_box_types_file(path: str | Path) -> list[BoxFieldMap]:
    """Load ``[[box_types]]`` tables from a TOML file (spec keys plus ``type``)."""
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "reading a TOML box-types file needs Python 3.11+ or `pip install tomli`"
            ) from exc
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    maps: list[BoxFieldMap] = []
    for entry in data.get("box_types", []):
        entry = dict(entry)
        type_name = entry.pop("type", None)
        if not type_name:
            raise ValueError(f"{path}: every [[box_types]] table needs a 'type'")
        unknown = set(entry) - _SPEC_KEYS
        if unknown:
            raise ValueError(f"{path}: unknown keys for {type_name}: {', '.join(sorted(unknown))}")
        maps.append(BoxFieldMap(type_name=str(type_name), **{k: str(v) for k, v in entry.items()}))
    return maps
