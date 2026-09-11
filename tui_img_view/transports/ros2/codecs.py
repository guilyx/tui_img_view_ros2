"""Decode ``sensor_msgs/Image`` and ``sensor_msgs/CompressedImage`` without cv_bridge.

Functions here are duck-typed: anything with the message's attributes works,
so they are testable without a ROS installation.
"""

from __future__ import annotations

import io
from typing import Any

import numpy as np
from PIL import Image as PilImage

from tui_img_view.core.types import Frame


class UnsupportedEncoding(ValueError):
    pass


def stamp_seconds(header: Any) -> float:
    try:
        stamp = header.stamp
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9
    except AttributeError:
        return 0.0


def _frame_id(header: Any) -> str:
    return str(getattr(header, "frame_id", "") or "")


# encoding -> (channels, dtype, channel order into RGB or None for special handling)
_SIMPLE: dict[str, tuple[int, str, tuple[int, ...] | None]] = {
    "rgb8": (3, "u1", (0, 1, 2)),
    "bgr8": (3, "u1", (2, 1, 0)),
    "rgba8": (4, "u1", (0, 1, 2)),
    "bgra8": (4, "u1", (2, 1, 0)),
    "8UC3": (3, "u1", (2, 1, 0)),  # OpenCV default channel order
    "8UC4": (4, "u1", (2, 1, 0)),
    "mono8": (1, "u1", None),
    "8UC1": (1, "u1", None),
    "8SC1": (1, "i1", None),
    "mono16": (1, "u2", None),
    "16UC1": (1, "u2", None),
    "16SC1": (1, "i2", None),
    "32FC1": (1, "f4", None),
    "64FC1": (1, "f8", None),
    "rgb16": (3, "u2", (0, 1, 2)),
    "bgr16": (3, "u2", (2, 1, 0)),
    "rgba16": (4, "u2", (0, 1, 2)),
    "bgra16": (4, "u2", (2, 1, 0)),
    "16UC3": (3, "u2", (2, 1, 0)),
}

_BAYER = {
    "bayer_rggb8": ("r", "g", "g", "b"),
    "bayer_bggr8": ("b", "g", "g", "r"),
    "bayer_gbrg8": ("g", "b", "r", "g"),
    "bayer_grbg8": ("g", "r", "b", "g"),
}


def _normalize_to_u8(plane: np.ndarray) -> np.ndarray:
    """Scale a single-channel non-uint8 plane to 0..255 using its finite min/max."""
    data = plane.astype(np.float32)
    finite = np.isfinite(data)
    if not finite.any():
        return np.zeros(plane.shape, dtype=np.uint8)
    valid = data[finite]
    lo = float(valid.min())
    hi = float(valid.max())
    if hi <= lo:
        return np.where(finite, 255 if hi > 0 else 0, 0).astype(np.uint8)
    out = (np.where(finite, data, lo) - lo) * (255.0 / (hi - lo))
    return np.clip(out, 0, 255).astype(np.uint8)


def _buffer(msg: Any) -> np.ndarray:
    data = msg.data
    if isinstance(data, np.ndarray):
        return data.view(np.uint8).ravel()
    return np.frombuffer(
        bytes(data) if not isinstance(data, (bytes, bytearray, memoryview)) else data,
        dtype=np.uint8,
    )


def decode_image(msg: Any) -> Frame:
    """``sensor_msgs/msg/Image`` (duck-typed) → RGB :class:`Frame`."""
    height, width = int(msg.height), int(msg.width)
    encoding = str(msg.encoding)
    step = int(msg.step)
    endian = ">" if int(getattr(msg, "is_bigendian", 0)) else "<"
    buf = _buffer(msg)

    if height <= 0 or width <= 0:
        raise ValueError(f"empty image {width}x{height}")

    if encoding in _BAYER:
        rgb = _debayer_half(buf, width, height, step, _BAYER[encoding])
    elif encoding in ("yuv422", "uyvy", "yuv422_yuy2", "yuyv"):
        rgb = _yuv422_to_rgb(buf, width, height, step, yuyv=encoding in ("yuv422_yuy2", "yuyv"))
    elif encoding in _SIMPLE:
        channels, kind, order = _SIMPLE[encoding]
        dtype = np.dtype(kind if kind in ("u1", "i1") else endian + kind)
        row_bytes = width * channels * dtype.itemsize
        if step < row_bytes:
            step = row_bytes
        needed = step * height
        if buf.size < needed:
            raise ValueError(f"image buffer too small: {buf.size} < {needed} bytes")
        rows = buf[:needed].reshape(height, step)[:, :row_bytes]
        arr = np.ascontiguousarray(rows).view(dtype).reshape(height, width, channels)
        if channels == 1:
            plane = arr[..., 0]
            gray = plane if dtype == np.uint8 else _normalize_to_u8(plane)
            rgb = np.repeat(gray[..., None], 3, axis=2)
        else:
            assert order is not None
            rgb = arr[..., list(order)]
            if dtype.itemsize == 2:
                rgb = (rgb.astype(np.uint32) >> 8).astype(np.uint8)
    else:
        raise UnsupportedEncoding(f"unsupported image encoding {encoding!r}")

    return Frame(
        np.ascontiguousarray(rgb, dtype=np.uint8),
        stamp=stamp_seconds(getattr(msg, "header", None)),
        frame_id=_frame_id(getattr(msg, "header", None)),
        encoding=encoding,
    )


def _rows(buf: np.ndarray, width: int, height: int, step: int, bytes_per_px: int) -> np.ndarray:
    row_bytes = width * bytes_per_px
    step = max(step, row_bytes)
    needed = step * height
    if buf.size < needed:
        raise ValueError(f"image buffer too small: {buf.size} < {needed} bytes")
    return buf[:needed].reshape(height, step)[:, :row_bytes]


def _debayer_half(buf, width, height, step, pattern) -> np.ndarray:
    """Cheap half-resolution demosaic: one output pixel per 2x2 Bayer quad."""
    raw = _rows(buf, width, height, step, 1).astype(np.float32)
    h2, w2 = height // 2, width // 2
    raw = raw[: h2 * 2, : w2 * 2]
    quads = {
        pattern[0]: raw[0::2, 0::2],
        pattern[1]: raw[0::2, 1::2],
        pattern[2]: raw[1::2, 0::2],
        pattern[3]: raw[1::2, 1::2],
    }
    # Two greens in every pattern: average them.
    greens = [raw[(i // 2) :: 2, (i % 2) :: 2] for i, c in enumerate(pattern) if c == "g"]
    g = sum(greens) / len(greens)
    rgb = np.stack([quads["r"], g, quads["b"]], axis=2)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def _yuv422_to_rgb(buf, width, height, step, *, yuyv: bool) -> np.ndarray:
    raw = _rows(buf, width, height, step, 2).astype(np.float32)
    pairs = raw.reshape(height, width // 2, 4)
    if yuyv:  # Y0 U Y1 V
        y = pairs[..., (0, 2)]
        u = pairs[..., 1]
        v = pairs[..., 3]
    else:  # U Y0 V Y1
        y = pairs[..., (1, 3)]
        u = pairs[..., 0]
        v = pairs[..., 2]
    y = y.reshape(height, width)
    u = np.repeat(u, 2, axis=1) - 128.0
    v = np.repeat(v, 2, axis=1) - 128.0
    r = y + 1.402 * v
    g = y - 0.344136 * u - 0.714136 * v
    b = y + 1.772 * u
    return np.clip(np.stack([r, g, b], axis=2), 0, 255).astype(np.uint8)


def decode_compressed(msg: Any) -> Frame:
    """``sensor_msgs/msg/CompressedImage`` (duck-typed) → RGB :class:`Frame`."""
    fmt = str(getattr(msg, "format", "") or "").lower()
    raw = bytes(msg.data)
    try:
        img = PilImage.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise UnsupportedEncoding(
            f"cannot decode compressed image (format={fmt!r}): {exc}"
        ) from exc
    channel_swap = "compressed bgr" in fmt or "compressed bgra" in fmt
    if img.mode in ("I;16", "I;16B", "I;16L", "I", "F"):
        pixels = _normalize_to_u8(np.asarray(img))
        pixels = np.repeat(pixels[..., None], 3, axis=2)
    else:
        pixels = np.asarray(img.convert("RGB"), dtype=np.uint8)
        if channel_swap:
            pixels = pixels[..., ::-1]
    return Frame(
        np.ascontiguousarray(pixels),
        stamp=stamp_seconds(getattr(msg, "header", None)),
        frame_id=_frame_id(getattr(msg, "header", None)),
        encoding=f"compressed:{fmt}" if fmt else "compressed",
    )
