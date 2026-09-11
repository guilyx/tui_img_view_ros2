from __future__ import annotations

import time

import numpy as np
import pytest

from tui_img_view.core.registry import available_transports, load_transport
from tui_img_view.core.session import RateMeter, ViewerSession
from tui_img_view.core.transport import TransportUnavailable
from tui_img_view.core.types import BoundingBox, Detections, Frame, TopicKind
from tui_img_view.transports.fake import DETECTIONS_TOPIC, IMAGE_TOPIC, TRACKS_TOPIC, FakeTransport
from tui_img_view.transports.manual import ManualTransport


def _frame(v=1):
    return Frame(np.full((4, 4, 3), v, dtype=np.uint8))


def test_rate_meter():
    m = RateMeter(window=2.0)
    for i in range(5):
        m.tick(now=100.0 + i * 0.1)
    assert m.rate(now=100.4) == pytest.approx(10.0)
    assert m.rate(now=200.0) == 0.0


def test_session_selection_and_snapshot():
    t = ManualTransport()
    t.add_topic("/img", TopicKind.IMAGE)
    t.add_topic("/img2", TopicKind.IMAGE)
    t.add_topic("/boxes", TopicKind.BOXES)
    with ViewerSession(t, stale_after=0.5) as s:
        assert t.started
        s.refresh_topics()
        assert s.image_topics() == ["/img", "/img2"] and s.box_topics_available() == ["/boxes"]
        assert s.snapshot().frame is None
        s.select_image("/img")
        v0 = s.version
        assert t.push_frame("/img", _frame(1)) == 1
        snap = s.snapshot()
        assert snap.frame is not None and snap.version > v0 and snap.image_topic == "/img"
        # frames on other topics are ignored
        assert t.push_frame("/img2", _frame(2)) == 0
        # switching drops the old frame and closes the old subscription
        assert s.next_image() == "/img2"
        assert t.subscriber_count("/img") == 0
        assert s.snapshot().frame is None
        # boxes
        s.set_box_topics(["/boxes"])
        t.push_boxes("/boxes", Detections((BoundingBox(0, 0, 1, 1),)))
        assert s.snapshot().box_count == 1
        assert s.snapshot().detections[0].source == "/boxes"
        time.sleep(0.6)
        assert s.snapshot().box_count == 0  # stale
        assert s.toggle_box_topic("/boxes") is False
        assert t.subscriber_count("/boxes") == 0
        # pause
        s.select_image("/img")
        t.push_frame("/img", _frame(3))
        s.set_paused(True)
        t.push_frame("/img", _frame(4))
        assert s.snapshot().frame.pixels[0, 0, 0] == 3 and s.snapshot().paused
        s.toggle_pause()
        t.push_frame("/img", _frame(5))
        assert s.snapshot().frame.pixels[0, 0, 0] == 5
    assert not t.started
    assert t.subscriber_count("/img") == 0


def test_session_surfaces_subscribe_errors():
    with ViewerSession(FakeTransport()) as s:
        s.select_image("/nope")
        snap = s.snapshot()
        assert snap.error and "/nope" in snap.error
        s.add_box_topic("/nope")
        assert s.box_topics == ()


def test_fake_transport_streams_frames_and_boxes():
    frames, dets = [], []
    t = FakeTransport(fps=60, width=64, height=48)
    with t:
        names = {ti.name for ti in t.list_topics()}
        assert {IMAGE_TOPIC, DETECTIONS_TOPIC, TRACKS_TOPIC} <= names
        s1 = t.subscribe_image(IMAGE_TOPIC, frames.append)
        s2 = t.subscribe_boxes(DETECTIONS_TOPIC, dets.append)
        deadline = time.monotonic() + 3
        while (len(frames) < 3 or not dets) and time.monotonic() < deadline:
            time.sleep(0.02)
        s1.close()
        s2.close()
    assert len(frames) >= 3
    assert frames[0].width == 64 and frames[0].height == 48
    assert len(dets[0]) == 3 and all(b.label for b in dets[0].boxes)
    assert all(0 <= b.x <= 64 for b in dets[0].boxes)


def test_fake_transport_from_file(tmp_path):
    from PIL import Image

    path = tmp_path / "photo.png"
    Image.fromarray(np.full((10, 20, 3), 90, dtype=np.uint8)).save(path)
    t = FakeTransport.from_options({"file": str(path), "fps": "30"})
    got = []
    with t:
        t.subscribe_image(IMAGE_TOPIC, got.append)
        t.publish_once()
    assert got and got[-1].width == 20 and got[-1].pixels[0, 0, 0] == 90
    with pytest.raises(ValueError):
        FakeTransport.from_options({"bogus": "1"})


def test_registry():
    assert {"fake", "ros2"} <= set(available_transports())
    assert load_transport("fake") is FakeTransport
    with pytest.raises(KeyError):
        load_transport("does-not-exist")
    try:
        import rclpy  # noqa: F401
    except ImportError:
        with pytest.raises(TransportUnavailable):
            load_transport("ros2")()
