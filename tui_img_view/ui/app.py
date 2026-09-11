"""The Textual application."""

from __future__ import annotations

import time

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, OptionList, SelectionList

from tui_img_view.core.session import Snapshot, ViewerSession
from tui_img_view.render.pipeline import Renderer
from tui_img_view.render.rasterize import next_mode
from tui_img_view.ui.image_view import ImageView
from tui_img_view.ui.widgets import StatusBar, TopicPanel


class ViewerApp(App[None]):
    TITLE = "tui-img-view"
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "toggle_topics", "Topics"),
        Binding("n", "next_image", "Next image"),
        Binding("m", "cycle_mode", "Mode"),
        Binding("b", "toggle_boxes", "Boxes"),
        Binding("l", "toggle_labels", "Labels"),
        Binding("c", "toggle_color", "Colour"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("r", "refresh_topics", "Rescan"),
    ]

    def __init__(
        self,
        session: ViewerSession,
        *,
        renderer: Renderer | None = None,
        refresh_hz: float = 20.0,
        topic_scan_s: float = 2.0,
        show_topics: bool = True,
    ) -> None:
        super().__init__()
        self.session = session
        self.renderer = renderer or Renderer()
        self.refresh_hz = max(1.0, refresh_hz)
        self.topic_scan_s = max(0.2, topic_scan_s)
        self._show_topics = show_topics
        self._last_version = -1
        self._last_render_ms = 0.0

    # -- layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield StatusBar("starting…", id="status")
        with Horizontal(id="body"):
            yield TopicPanel(id="topics", classes="" if self._show_topics else "hidden")
            yield ImageView(self.renderer, id="image")
        yield Footer()

    def on_mount(self) -> None:
        self.session.start()
        self.action_refresh_topics()
        self.set_interval(1.0 / self.refresh_hz, self._tick, name="frame-tick")
        self.set_interval(self.topic_scan_s, self.action_refresh_topics, name="topic-scan")
        self.query_one(ImageView).focus()

    async def action_quit(self) -> None:
        self.session.stop()
        self.exit()

    # -- periodic ----------------------------------------------------------

    def _tick(self) -> None:
        snap = self.session.snapshot()
        if snap.version != self._last_version:
            self._last_version = snap.version
            t0 = time.perf_counter()
            self.query_one(ImageView).set_content(snap.frame, snap.detections)
            self._last_render_ms = (time.perf_counter() - t0) * 1000.0
        self._update_status(snap)

    def _update_status(self, snap: Snapshot) -> None:
        bar = self.query_one(StatusBar)
        parts: list[str] = []
        parts.append(f"[b]{snap.image_topic or '(no image topic)'}[/b]")
        if snap.frame is not None:
            enc = f" {snap.frame.encoding}" if snap.frame.encoding else ""
            parts.append(f"{snap.frame.width}x{snap.frame.height}{enc}")
            latency = _latency(snap.frame.stamp)
            if latency is not None:
                parts.append(f"lat {latency * 1000:.0f}ms")
        parts.append(f"{snap.fps:4.1f} fps")
        parts.append(f"mode:{self.renderer.mode}")
        boxes = "off" if not self.renderer.show_boxes else str(self.renderer.last_box_count)
        parts.append(f"boxes:{boxes}/{len(snap.box_topics)}t")
        if not self.renderer.color:
            parts.append("gray")
        if snap.paused:
            parts.append("[b]PAUSED[/b]")
        parts.append(f"draw {self._last_render_ms:.0f}ms")
        if snap.error:
            parts.append(f"⚠ {snap.error}")
        bar.set_class(bool(snap.error), "error")
        bar.update("  ".join(parts))

    # -- actions -----------------------------------------------------------

    def action_refresh_topics(self) -> None:
        self.session.refresh_topics()
        panel = self.query_one(TopicPanel)
        panel.set_image_topics(self.session.image_topics(), self.session.image_topic)
        panel.set_box_topics(self.session.box_topics_available(), set(self.session.box_topics))
        if self.session.image_topic is None and self.session.image_topics():
            self.session.select_image(self.session.image_topics()[0])
            panel.set_image_topics(self.session.image_topics(), self.session.image_topic)

    def action_toggle_topics(self) -> None:
        panel = self.query_one(TopicPanel)
        panel.toggle_class("hidden")
        if panel.has_class("hidden"):
            self.query_one(ImageView).focus()
        else:
            self.query_one("#image-topics", OptionList).focus()

    def action_next_image(self) -> None:
        self.session.next_image()
        panel = self.query_one(TopicPanel)
        panel.set_image_topics(self.session.image_topics(), self.session.image_topic)

    def action_cycle_mode(self) -> None:
        self.renderer.mode = next_mode(self.renderer.mode)
        self._redraw()

    def action_toggle_boxes(self) -> None:
        self.renderer.show_boxes = not self.renderer.show_boxes
        self._redraw()

    def action_toggle_labels(self) -> None:
        self.renderer.show_labels = not self.renderer.show_labels
        self._redraw()

    def action_toggle_color(self) -> None:
        self.renderer.color = not self.renderer.color
        self._redraw()

    def action_toggle_pause(self) -> None:
        self.session.toggle_pause()

    def _redraw(self) -> None:
        self._last_version = -1
        self._tick()

    # -- sidebar events ----------------------------------------------------

    @on(OptionList.OptionSelected, "#image-topics")
    def _image_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self.session.select_image(event.option_id)
            self.query_one(TopicPanel).set_image_topics(
                self.session.image_topics(), self.session.image_topic
            )

    @on(SelectionList.SelectedChanged, "#box-topics")
    def _boxes_changed(self, event: SelectionList.SelectedChanged) -> None:
        self.session.set_box_topics(event.selection_list.selected)


def _latency(stamp: float) -> float | None:
    """Wall-clock latency when the stamp looks like wall time; ``None`` otherwise."""
    if stamp <= 0:
        return None
    lat = time.time() - stamp
    if -1.0 <= lat <= 120.0:
        return max(0.0, lat)
    return None
