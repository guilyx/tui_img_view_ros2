from __future__ import annotations

import asyncio

from textual.widgets import OptionList, SelectionList

from tui_img_view.core.session import ViewerSession
from tui_img_view.transports.fake import DETECTIONS_TOPIC, GRAY_TOPIC, FakeTransport
from tui_img_view.ui.app import ViewerApp
from tui_img_view.ui.image_view import ImageView
from tui_img_view.ui.widgets import StatusBar


async def _wait_for(predicate, timeout=3.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while not predicate():
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.05)


async def test_app_renders_and_reacts_to_keys():
    session = ViewerSession(FakeTransport(fps=30, width=64, height=48))
    app = ViewerApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        view = app.query_one(ImageView)
        await _wait_for(lambda: view.canvas is not None and "▀" in view.canvas.to_text())
        assert session.image_topic == "/camera/image_raw"
        assert app.query_one(StatusBar).content.startswith("[b]/camera/image_raw")

        # Toggle a box topic through the sidebar.
        boxes = app.query_one("#box-topics", SelectionList)
        boxes.focus()
        await pilot.pause()
        await pilot.press("space")
        await _wait_for(lambda: DETECTIONS_TOPIC in session.box_topics)
        await _wait_for(lambda: app.renderer.last_box_count > 0)
        assert "┌" in view.canvas.to_text()

        # Pick another image topic.
        images = app.query_one("#image-topics", OptionList)
        images.focus()
        await pilot.pause()
        await pilot.press("down", "enter")
        await _wait_for(lambda: session.image_topic == GRAY_TOPIC)

        await pilot.press("m")
        assert app.renderer.mode == "quadrant"
        await pilot.press("b")
        assert app.renderer.show_boxes is False
        await pilot.press("c")
        assert app.renderer.color is False
        await pilot.press("p")
        assert session.paused is True
        await pilot.press("t")
        assert app.query_one("#topics").has_class("hidden")
        await pilot.press("q")
    assert session.transport._thread is None
