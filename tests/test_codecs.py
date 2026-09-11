from __future__ import annotations

import io
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from tui_img_view.transports.ros2.codecs import (
    UnsupportedEncoding,
    decode_compressed,
    decode_image,
    stamp_seconds,
)


def _header(sec=10, nanosec=500_000_000, frame_id="cam"):
    return SimpleNamespace(stamp=SimpleNamespace(sec=sec, nanosec=nanosec), frame_id=frame_id)


def _image(pixels: np.ndarray, encoding: str, step: int | None = None, bigendian=0, pad=0):
    h, w = pixels.shape[:2]
    rows = pixels.reshape(h, -1).view(np.uint8)
    if pad:
        rows = np.concatenate([rows, np.zeros((h, pad), dtype=np.uint8)], axis=1)
    return SimpleNamespace(
        header=_header(),
        height=h,
        width=w,
        encoding=encoding,
        is_bigendian=bigendian,
        step=step if step is not None else rows.shape[1],
        data=rows.tobytes(),
    )


def test_stamp_seconds():
    assert stamp_seconds(_header(3, 250_000_000)) == pytest.approx(3.25)
    assert stamp_seconds(None) == 0.0


def test_rgb8_roundtrip_with_padding():
    px = (np.random.default_rng(1).random((4, 6, 3)) * 255).astype(np.uint8)
    frame = decode_image(_image(px, "rgb8", pad=5))
    assert np.array_equal(frame.pixels, px)
    assert frame.stamp == pytest.approx(10.5)
    assert frame.frame_id == "cam" and frame.encoding == "rgb8"


def test_bgr8_and_bgra8_swap_channels():
    px = np.zeros((1, 1, 3), dtype=np.uint8)
    px[0, 0] = (10, 20, 30)  # B, G, R
    assert tuple(decode_image(_image(px, "bgr8")).pixels[0, 0]) == (30, 20, 10)
    px4 = np.zeros((1, 1, 4), dtype=np.uint8)
    px4[0, 0] = (10, 20, 30, 255)
    assert tuple(decode_image(_image(px4, "bgra8")).pixels[0, 0]) == (30, 20, 10)
    px4[0, 0] = (1, 2, 3, 4)
    assert tuple(decode_image(_image(px4, "rgba8")).pixels[0, 0]) == (1, 2, 3)


def test_mono8_and_mono16():
    gray = np.arange(12, dtype=np.uint8).reshape(3, 4)
    frame = decode_image(_image(gray, "mono8"))
    assert frame.pixels.shape == (3, 4, 3)
    assert np.array_equal(frame.pixels[..., 0], gray)
    depth = np.array([[0, 1000], [2000, 4000]], dtype="<u2")
    frame = decode_image(_image(depth, "16UC1"))
    assert tuple(frame.pixels[..., 0].ravel()) == (0, 63, 127, 255)
    big = depth.astype(">u2")
    frame_be = decode_image(_image(big, "mono16", bigendian=1))
    assert np.array_equal(frame_be.pixels, frame.pixels)


def test_32fc1_handles_nan():
    depth = np.array([[0.5, np.nan], [1.5, 2.5]], dtype="<f4")
    frame = decode_image(_image(depth, "32FC1"))
    assert tuple(frame.pixels[..., 0].ravel()) == (0, 0, 127, 255)


def test_yuv422_gray_roundtrip():
    # UYVY with U=V=128 → gray equal to Y.
    h, w = 2, 4
    y = np.array([[0, 64, 128, 255], [255, 128, 64, 0]], dtype=np.uint8)
    raw = np.zeros((h, w * 2), dtype=np.uint8)
    raw[:, 0::2] = 128
    raw[:, 1::2] = y
    msg = SimpleNamespace(
        header=_header(),
        height=h,
        width=w,
        encoding="yuv422",
        is_bigendian=0,
        step=w * 2,
        data=raw.tobytes(),
    )
    frame = decode_image(msg)
    assert np.array_equal(frame.pixels[..., 1], y)
    # YUYV layout too
    raw2 = np.zeros((h, w * 2), dtype=np.uint8)
    raw2[:, 0::2] = y
    raw2[:, 1::2] = 128
    msg.encoding = "yuv422_yuy2"
    msg.data = raw2.tobytes()
    assert np.array_equal(decode_image(msg).pixels[..., 0], y)


def test_bayer_half_res_demosaic():
    raw = np.zeros((4, 4), dtype=np.uint8)
    raw[0::2, 0::2] = 200  # R
    raw[0::2, 1::2] = 100  # G
    raw[1::2, 0::2] = 50  # G
    raw[1::2, 1::2] = 20  # B
    frame = decode_image(_image(raw, "bayer_rggb8"))
    assert frame.pixels.shape == (2, 2, 3)
    assert tuple(frame.pixels[0, 0]) == (200, 75, 20)


def test_unknown_encoding_and_short_buffer():
    px = np.zeros((2, 2, 3), dtype=np.uint8)
    with pytest.raises(UnsupportedEncoding):
        decode_image(_image(px, "weird42"))
    msg = _image(px, "rgb8")
    msg.data = msg.data[:5]
    with pytest.raises(ValueError):
        decode_image(msg)


def _png_bytes(px: np.ndarray, fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.fromarray(px).save(buf, format=fmt)
    return buf.getvalue()


def test_compressed_png_and_bgr_swap():
    px = np.zeros((3, 5, 3), dtype=np.uint8)
    px[..., 0] = 200
    px[..., 2] = 50
    msg = SimpleNamespace(header=_header(), format="png", data=_png_bytes(px))
    frame = decode_compressed(msg)
    assert np.array_equal(frame.pixels, px)
    assert frame.encoding == "compressed:png"
    msg.format = "bgr8; png compressed bgr8"
    assert np.array_equal(decode_compressed(msg).pixels, px[..., ::-1])
    msg.data = b"not an image"
    with pytest.raises(UnsupportedEncoding):
        decode_compressed(msg)


def test_compressed_jpeg_decodes():
    px = np.full((8, 8, 3), 128, dtype=np.uint8)
    msg = SimpleNamespace(header=_header(), format="jpeg", data=_png_bytes(px, "JPEG"))
    frame = decode_compressed(msg)
    assert frame.pixels.shape == (8, 8, 3)
    assert abs(int(frame.pixels.mean()) - 128) <= 2
