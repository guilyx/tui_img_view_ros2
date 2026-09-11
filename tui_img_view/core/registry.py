"""Lookup of transports by name.

Built-in transports are imported lazily so that importing the package never
pulls in ``rclpy``. Third-party packages can add transports through the
``tui_img_view.transports`` entry-point group::

    [options.entry_points]
    tui_img_view.transports =
        zmq = my_pkg.zmq_transport:ZmqTransport
"""

from __future__ import annotations

from importlib import import_module, metadata

from tui_img_view.core.transport import Transport

ENTRY_POINT_GROUP = "tui_img_view.transports"

_BUILTIN: dict[str, str] = {
    "fake": "tui_img_view.transports.fake:FakeTransport",
    "ros2": "tui_img_view.transports.ros2:Ros2Transport",
    "bag": "tui_img_view.transports.bag:McapTransport",
}

_REGISTERED: dict[str, type[Transport]] = {}


def register_transport(cls: type[Transport]) -> type[Transport]:
    """Register a transport class under its ``name``. Usable as a decorator."""
    _REGISTERED[cls.name] = cls
    return cls


def _entry_points() -> dict[str, metadata.EntryPoint]:
    try:
        eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - Python < 3.10 API
        eps = metadata.entry_points().get(ENTRY_POINT_GROUP, [])
    return {ep.name: ep for ep in eps}


def available_transports() -> list[str]:
    names = set(_BUILTIN) | set(_REGISTERED) | set(_entry_points())
    return sorted(names)


def _load_path(path: str) -> type[Transport]:
    module_name, _, attr = path.partition(":")
    module = import_module(module_name)
    return getattr(module, attr)


def load_transport(name: str) -> type[Transport]:
    """Return the transport class registered under ``name``.

    Raises :class:`KeyError` for unknown names and
    :class:`~tui_img_view.core.transport.TransportUnavailable` when the
    transport exists but its dependencies are missing.
    """
    if name in _REGISTERED:
        return _REGISTERED[name]
    if name in _BUILTIN:
        return _load_path(_BUILTIN[name])
    eps = _entry_points()
    if name in eps:
        return eps[name].load()
    raise KeyError(f"unknown transport '{name}'. Available: {', '.join(available_transports())}")
