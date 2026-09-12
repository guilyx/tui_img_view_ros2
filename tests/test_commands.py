from __future__ import annotations

import logging

from tui_img_view.core.session import ViewerSession
from tui_img_view.core.types import TopicKind
from tui_img_view.render.pipeline import Renderer
from tui_img_view.transports.manual import ManualTransport
from tui_img_view.ui.commands import HELP, CommandDispatcher
from tui_img_view.ui.logbuffer import LogBuffer, attach


class StubControls:
    def __init__(self):
        t = ManualTransport()
        t.add_topic("/a", TopicKind.IMAGE)
        t.add_topic("/b", TopicKind.IMAGE)
        t.add_topic("/boxes", TopicKind.BOXES)
        self.session = ViewerSession(t)
        self.session.start()
        self.session.refresh_topics()
        self.renderer = Renderer()
        self.calls: list[str] = []

    def redraw(self):
        self.calls.append("redraw")

    def set_fps(self, hz):
        self.calls.append(f"fps={hz}")

    def toggle_topics(self):
        self.calls.append("topics")

    def toggle_sidebar(self):
        self.calls.append("sidebar")

    def rescan(self):
        self.calls.append("rescan")

    def clear_log(self):
        self.calls.append("clear")

    def quit(self):
        self.calls.append("quit")


def test_dispatcher_covers_every_command():
    c = StubControls()
    d = CommandDispatcher(c)
    assert d.run("").ok and d.run("   ").message == ""
    assert d.run("help").message == HELP
    assert not d.run("bogus").ok

    assert d.run(":mode ascii").message == "mode ascii" and c.renderer.mode == "ascii"
    assert d.run("mode").ok and c.renderer.mode == "half"  # cycles back around
    assert not d.run("mode nope").ok

    assert d.run("image /b").ok and c.session.image_topic == "/b"
    assert d.run("next").message == "image /a"
    assert d.run("prev").message == "image /b"
    assert not d.run("image").ok

    assert d.run("boxes off").ok and c.renderer.show_boxes is False
    assert d.run("boxes").ok and c.renderer.show_boxes is True
    assert d.run("boxes +/boxes").ok and c.session.box_topics == ("/boxes",)
    assert d.run("boxes -/boxes").ok and c.session.box_topics == ()
    assert d.run("boxes /boxes").message == "boxes + /boxes"
    assert d.run("boxes /boxes").message == "boxes - /boxes"

    assert d.run("labels off").ok and c.renderer.show_labels is False
    assert not d.run("labels maybe").ok
    assert d.run("colour").ok and c.renderer.color is False
    assert d.run("color on").ok and c.renderer.color is True
    assert d.run("pause").message == "paused" and c.session.paused
    assert d.run("pause off").message == "resumed"

    assert d.run("filter").message == "filters: none"
    assert d.run("filter blur").message == "filter blur on" and c.renderer.filters == ("blur",)
    assert d.run("filter +blur").ok and c.renderer.filters == ("blur",)
    assert d.run("filter +gray").ok and c.renderer.filters == ("blur", "gray")
    assert d.run("filter").message == "filters: blur+gray"
    assert d.run("filter -blur").message == "filter blur off" and c.renderer.filters == ("gray",)
    assert d.run("filter gray").message == "filter gray off" and c.renderer.filters == ()
    assert not d.run("filter nope").ok
    assert d.run("filter next").message == "filters: gray"
    assert d.run("filter off").message == "filters cleared" and c.renderer.filters == ()
    assert d.run("filters").message.startswith("filters: gray, invert")

    assert d.run("stale 3").message == "stale 3s" and c.session.stale_after == 3.0
    assert d.run("stale").message == "stale 3s"
    assert d.run("fps 5").ok and "fps=5.0" in c.calls
    assert not d.run("fps -1").ok and not d.run("fps").ok
    assert not d.run("fps abc").ok  # ValueError -> error result
    assert d.run("aspect 0.6").ok and c.renderer.cell_aspect == 0.6
    assert not d.run("aspect 9").ok

    for cmd, call in (
        ("rescan", "rescan"),
        ("topics", "topics"),
        ("sidebar", "sidebar"),
        ("clear", "clear"),
        ("quit", "quit"),
        ("q", "quit"),
        ("exit", "quit"),
    ):
        assert d.run(cmd).ok and c.calls[-1] == call
    assert "redraw" in c.calls
    c.session.stop()


def test_log_buffer_collects_logger_output():
    buf = LogBuffer(maxlen=3)
    attach(buf, "tui_img_view.test")
    logger = logging.getLogger("tui_img_view.test")
    logger.info("one %d", 1)
    logger.warning("two")
    buf.push("three", logging.ERROR)
    logger.info("four")  # pushes 'one' out (maxlen=3)
    lines = buf.drain()
    assert [level for _, level, _ in lines] == [logging.WARNING, logging.ERROR, logging.INFO]
    assert [msg for _, _, msg in lines] == ["two", "three", "four"]
    assert buf.drain() == []
    logging.getLogger("tui_img_view.test").removeHandler(buf)
