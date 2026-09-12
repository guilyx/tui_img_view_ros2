"""The Textual application."""

from __future__ import annotations

import logging
import time

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Input, OptionList, SelectionList

from tui_img_view.core.session import Snapshot, ViewerSession
from tui_img_view.render.pipeline import Renderer
from tui_img_view.render.rasterize import next_mode
from tui_img_view.ui.commands import CommandDispatcher
from tui_img_view.ui.image_view import ImageView
from tui_img_view.ui.logbuffer import LogBuffer, attach
from tui_img_view.ui.widgets import CommandPanel, LogPanel, SidePanel, StatusBar, TopicPanel

log = logging.getLogger("tui_img_view.ui")


class ViewerApp(App[None]):
    TITLE = "tui-img-view"
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "toggle_topics", "Topics"),
        Binding("s", "toggle_sidebar", "Sidebar"),
        Binding("colon", "focus_command", "Command", key_display=":"),
        Binding("n", "next_image", "Next image"),
        Binding("m", "cycle_mode", "Mode"),
        Binding("b", "toggle_boxes", "Boxes"),
        Binding("l", "toggle_labels", "Labels"),
        Binding("c", "toggle_color", "Colour"),
        Binding("f", "cycle_filter", "Filter"),
        Binding("p", "toggle_pause", "Pause"),
        Binding("r", "refresh_topics", "Rescan"),
        Binding("escape", "focus_image", "Back to image", show=False),
    ]

    def __init__(
        self,
        session: ViewerSession,
        *,
        renderer: Renderer | None = None,
        refresh_hz: float = 20.0,
        topic_scan_s: float = 2.0,
        show_topics: bool = True,
        show_sidebar: bool = True,
    ) -> None:
        super().__init__()
        self.session = session
        self.renderer = renderer or Renderer()
        self.refresh_hz = max(1.0, refresh_hz)
        self.topic_scan_s = max(0.2, topic_scan_s)
        self._show_topics = show_topics
        self._show_sidebar = show_sidebar
        self._last_version = -1
        self._last_render_ms = 0.0
        self._last_error: str | None = None
        self._frame_timer = None
        self.logs = LogBuffer()
        attach(self.logs)
        self.commands = CommandDispatcher(self)

    # -- layout ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield StatusBar("starting…", id="status")
        with Horizontal(id="body"):
            yield TopicPanel(id="topics", classes="" if self._show_topics else "hidden")
            yield ImageView(self.renderer, id="image")
            yield SidePanel(id="sidebar", classes="" if self._show_sidebar else "hidden")
        yield Footer()

    def on_mount(self) -> None:
        log.info("transport '%s' starting", self.session.transport.name)
        self.session.start()
        self.action_refresh_topics()
        self._frame_timer = self.set_interval(1.0 / self.refresh_hz, self._tick, name="frame-tick")
        self.set_interval(self.topic_scan_s, self._scan_topics, name="topic-scan")
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
        if snap.error != self._last_error:
            self._last_error = snap.error
            if snap.error:
                log.error("%s", snap.error)
        self._drain_logs()
        self._update_status(snap)

    def _drain_logs(self) -> None:
        lines = self.logs.drain()
        if not lines:
            return
        panel = self.query_one(LogPanel)
        for when, level, message in lines:
            panel.add(when, level, message)

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
        if self.renderer.filters:
            parts.append("flt:" + "+".join(self.renderer.filters))
        if snap.paused:
            parts.append("[b]PAUSED[/b]")
        parts.append(f"draw {self._last_render_ms:.0f}ms")
        if snap.error:
            parts.append(f"⚠ {snap.error}")
        bar.set_class(bool(snap.error), "error")
        bar.update("  ".join(parts))

    def _scan_topics(self) -> None:
        before = set(t.name for t in self.session.topics)
        self.session.refresh_topics()
        after = set(t.name for t in self.session.topics)
        for name in sorted(after - before):
            log.info("topic appeared: %s", name)
        for name in sorted(before - after):
            log.info("topic gone: %s", name)
        self._sync_topic_panel()
        if self.session.image_topic is None and self.session.image_topics():
            self.session.select_image(self.session.image_topics()[0])
            self._sync_topic_panel()

    def _sync_topic_panel(self) -> None:
        panel = self.query_one(TopicPanel)
        panel.set_image_topics(self.session.image_topics(), self.session.image_topic)
        panel.set_box_topics(self.session.box_topics_available(), set(self.session.box_topics))

    # -- Controls protocol (used by the command dispatcher) ----------------

    def redraw(self) -> None:
        self._last_version = -1
        self.query_one(CommandPanel).set_active_filters(self.renderer.filters)
        self._tick()

    def set_fps(self, hz: float) -> None:
        self.refresh_hz = max(1.0, hz)
        if self._frame_timer is not None:
            self._frame_timer.stop()
        self._frame_timer = self.set_interval(1.0 / self.refresh_hz, self._tick, name="frame-tick")

    def toggle_topics(self) -> None:
        self.action_toggle_topics()

    def toggle_sidebar(self) -> None:
        self.action_toggle_sidebar()

    def rescan(self) -> None:
        self.action_refresh_topics()

    def clear_log(self) -> None:
        self.query_one(LogPanel).clear()

    def quit(self) -> None:
        self.session.stop()
        self.exit()

    # -- actions -----------------------------------------------------------

    def action_refresh_topics(self) -> None:
        self._scan_topics()
        log.info(
            "found %d image and %d box topics",
            len(self.session.image_topics()),
            len(self.session.box_topics_available()),
        )

    def action_toggle_topics(self) -> None:
        panel = self.query_one(TopicPanel)
        panel.toggle_class("hidden")
        if panel.has_class("hidden"):
            self.query_one(ImageView).focus()
        else:
            self.query_one("#image-topics", OptionList).focus()

    def action_toggle_sidebar(self) -> None:
        self.query_one(SidePanel).toggle_class("hidden")
        self.query_one(ImageView).focus()

    def action_focus_command(self) -> None:
        sidebar = self.query_one(SidePanel)
        if sidebar.has_class("hidden"):
            sidebar.remove_class("hidden")
        self.query_one("#command-input", Input).focus()

    def action_focus_image(self) -> None:
        self.query_one(ImageView).focus()

    def action_next_image(self) -> None:
        topic = self.session.next_image()
        log.info("image topic: %s", topic)
        self._sync_topic_panel()

    def action_cycle_mode(self) -> None:
        self.renderer.mode = next_mode(self.renderer.mode)
        log.info("mode: %s", self.renderer.mode)
        self.redraw()

    def action_toggle_boxes(self) -> None:
        self.renderer.show_boxes = not self.renderer.show_boxes
        log.info("boxes %s", "on" if self.renderer.show_boxes else "off")
        self.redraw()

    def action_toggle_labels(self) -> None:
        self.renderer.show_labels = not self.renderer.show_labels
        log.info("labels %s", "on" if self.renderer.show_labels else "off")
        self.redraw()

    def action_toggle_color(self) -> None:
        self.renderer.color = not self.renderer.color
        log.info("colour %s", "on" if self.renderer.color else "off")
        self.redraw()

    def action_cycle_filter(self) -> None:
        active = self.renderer.cycle_filter()
        log.info("filters: %s", "+".join(active) or "none")
        self.redraw()

    def action_toggle_pause(self) -> None:
        paused = self.session.toggle_pause()
        log.info("paused" if paused else "resumed")

    # -- events ------------------------------------------------------------

    @on(OptionList.OptionSelected, "#image-topics")
    def _image_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self.session.select_image(event.option_id)
            log.info("image topic: %s", event.option_id)
            self._sync_topic_panel()

    @on(SelectionList.SelectedChanged, "#box-topics")
    def _boxes_changed(self, event: SelectionList.SelectedChanged) -> None:
        self.session.set_box_topics(event.selection_list.selected)

    @on(Button.Pressed)
    def _button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("flt-"):
            self.run_command(f"filter {button_id[4:]}")
        elif button_id.startswith("cmd-"):
            self.run_command(button_id[4:])
        else:
            return
        if button_id != "cmd-topics":
            self.query_one(ImageView).focus()

    @on(Input.Submitted, "#command-input")
    def _command_submitted(self, event: Input.Submitted) -> None:
        self.run_command(event.value)
        event.input.value = ""

    def run_command(self, line: str) -> None:
        """Run a ``:`` command and log its outcome."""
        result = self.commands.run(line)
        if result.message:
            log.log(logging.INFO if result.ok else logging.WARNING, "%s", result.message)
        self._drain_logs()


def _latency(stamp: float) -> float | None:
    """Wall-clock latency when the stamp looks like wall time; ``None`` otherwise."""
    if stamp <= 0:
        return None
    lat = time.time() - stamp
    if -1.0 <= lat <= 120.0:
        return max(0.0, lat)
    return None
