from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("mcap_ros2", reason="bag transport needs mcap + mcap-ros2-support")

from tui_img_view.core.registry import load_transport  # noqa: E402
from tui_img_view.core.session import ViewerSession  # noqa: E402
from tui_img_view.core.types import TopicKind  # noqa: E402
from tui_img_view.transports.bag import McapTransport, resolve_bag_file  # noqa: E402

BAG_DIR = Path(__file__).resolve().parent.parent / "demo" / "bags" / "tui_demo"
IMAGE_TOPIC = "/camera/image/compressed"
BOX_TOPIC = "/detector/detections"


def test_resolve_bag_file_accepts_dir_or_file(tmp_path):
    assert resolve_bag_file(BAG_DIR).suffix == ".mcap"
    assert resolve_bag_file(BAG_DIR / "tui_demo_0.mcap").name == "tui_demo_0.mcap"
    with pytest.raises(FileNotFoundError):
        resolve_bag_file(tmp_path)
    with pytest.raises(FileNotFoundError):
        resolve_bag_file(tmp_path / "nope.mcap")


def test_from_options():
    t = McapTransport.from_options({"path": str(BAG_DIR), "rate": "2", "loop": "false"})
    assert t.rate == 2.0 and t.loop is False
    with pytest.raises(ValueError):
        McapTransport.from_options({})
    with pytest.raises(ValueError):
        McapTransport.from_options({"path": str(BAG_DIR), "bogus": "1"})
    assert load_transport("bag") is McapTransport


def test_bag_lists_topics_and_plays_real_frames():
    frames, dets = [], []
    t = McapTransport(BAG_DIR, rate=50.0, loop=False)
    with t:
        kinds = {ti.name: (ti.kind, ti.type) for ti in t.list_topics()}
        assert kinds[IMAGE_TOPIC] == (TopicKind.IMAGE, "sensor_msgs/msg/CompressedImage")
        assert kinds[BOX_TOPIC] == (TopicKind.BOXES, "vision_msgs/msg/Detection2DArray")
        t.subscribe_image(IMAGE_TOPIC, frames.append)
        t.subscribe_boxes(BOX_TOPIC, dets.append)
        deadline = time.monotonic() + 10
        while (len(frames) < 5 or len(dets) < 5) and time.monotonic() < deadline:
            time.sleep(0.02)
        with pytest.raises(LookupError):
            t.subscribe_image(BOX_TOPIC, frames.append)
    assert len(frames) >= 5 and len(dets) >= 5
    f = frames[0]
    assert (f.width, f.height) == (400, 300) and f.encoding == "compressed:jpeg"
    assert f.frame_id == "camera_optical_frame" and f.stamp > 1.6e9
    first = dets[0]
    assert first.source == BOX_TOPIC
    labels = {b.label for b in first.boxes}
    assert "person" in labels
    assert all(b.track_id and b.score is not None for b in first.boxes)
    assert t.last_error is None


def test_bag_through_session_snapshot():
    with ViewerSession(McapTransport(BAG_DIR, rate=50.0)) as s:
        s.refresh_topics()
        assert s.image_topics() == [IMAGE_TOPIC] and s.box_topics_available() == [BOX_TOPIC]
        s.select_image(IMAGE_TOPIC)
        s.set_box_topics([BOX_TOPIC])
        deadline = time.monotonic() + 10
        snap = s.snapshot()
        while (snap.frame is None or snap.box_count == 0) and time.monotonic() < deadline:
            time.sleep(0.02)
            snap = s.snapshot()
    assert snap.frame is not None and snap.box_count > 0
