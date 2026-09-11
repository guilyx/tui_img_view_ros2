"""The ``:`` command line. Pure Python so it is testable without Textual.

The dispatcher talks to the app through the small :class:`Controls` protocol,
so tests can drive it with a stub.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tui_img_view.core.session import ViewerSession
from tui_img_view.render.pipeline import Renderer
from tui_img_view.render.rasterize import MODE_ORDER, next_mode


class Controls(Protocol):
    session: ViewerSession
    renderer: Renderer

    def redraw(self) -> None: ...
    def set_fps(self, hz: float) -> None: ...
    def toggle_topics(self) -> None: ...
    def toggle_sidebar(self) -> None: ...
    def rescan(self) -> None: ...
    def clear_log(self) -> None: ...
    def quit(self) -> None: ...


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    message: str


HELP = (
    "mode [half|quadrant|braille|ascii]  image <topic>  next  prev  "
    "boxes [on|off|+<topic>|-<topic>|<topic>]  labels [on|off]  color [on|off]  "
    "pause [on|off]  stale <s>  fps <hz>  aspect <w/h>  rescan  topics  sidebar  clear  quit"
)

_ON = {"on", "1", "true", "yes", "show"}
_OFF = {"off", "0", "false", "no", "hide"}


def _flag(arg: str | None, current: bool) -> bool | None:
    if arg is None:
        return not current
    if arg.lower() in _ON:
        return True
    if arg.lower() in _OFF:
        return False
    return None


class CommandDispatcher:
    def __init__(self, controls: Controls) -> None:
        self.c = controls

    def run(self, line: str) -> CommandResult:
        line = line.strip().lstrip(":").strip()
        if not line:
            return CommandResult(True, "")
        name, _, rest = line.partition(" ")
        arg = rest.strip() or None
        handler = getattr(self, f"cmd_{name.lower()}", None)
        if handler is None:
            return CommandResult(False, f"unknown command '{name}'. Try: help")
        try:
            return handler(arg)
        except ValueError as exc:
            return CommandResult(False, str(exc))

    # -- commands ----------------------------------------------------------

    def cmd_help(self, arg: str | None) -> CommandResult:
        return CommandResult(True, HELP)

    def cmd_mode(self, arg: str | None) -> CommandResult:
        r = self.c.renderer
        if arg is None:
            r.mode = next_mode(r.mode)
        elif arg in MODE_ORDER:
            r.mode = arg
        else:
            return CommandResult(False, f"unknown mode '{arg}' ({', '.join(MODE_ORDER)})")
        self.c.redraw()
        return CommandResult(True, f"mode {r.mode}")

    def cmd_image(self, arg: str | None) -> CommandResult:
        if arg is None:
            return CommandResult(False, "usage: image <topic>")
        self.c.session.select_image(arg)
        return CommandResult(True, f"image {arg}")

    def cmd_next(self, arg: str | None) -> CommandResult:
        topic = self.c.session.next_image(1)
        return CommandResult(topic is not None, f"image {topic}" if topic else "no image topics")

    def cmd_prev(self, arg: str | None) -> CommandResult:
        topic = self.c.session.next_image(-1)
        return CommandResult(topic is not None, f"image {topic}" if topic else "no image topics")

    def cmd_boxes(self, arg: str | None) -> CommandResult:
        r, s = self.c.renderer, self.c.session
        if arg is None or arg.lower() in _ON | _OFF:
            value = _flag(arg, r.show_boxes)
            r.show_boxes = bool(value)
            self.c.redraw()
            return CommandResult(True, f"boxes {'on' if r.show_boxes else 'off'}")
        if arg.startswith("+"):
            s.add_box_topic(arg[1:])
            return CommandResult(True, f"boxes + {arg[1:]}")
        if arg.startswith("-"):
            s.remove_box_topic(arg[1:])
            return CommandResult(True, f"boxes - {arg[1:]}")
        enabled = s.toggle_box_topic(arg)
        return CommandResult(True, f"boxes {'+' if enabled else '-'} {arg}")

    def _toggle(self, arg: str | None, attr: str, label: str) -> CommandResult:
        r = self.c.renderer
        value = _flag(arg, getattr(r, attr))
        if value is None:
            return CommandResult(False, f"usage: {label} [on|off]")
        setattr(r, attr, value)
        self.c.redraw()
        return CommandResult(True, f"{label} {'on' if value else 'off'}")

    def cmd_labels(self, arg: str | None) -> CommandResult:
        return self._toggle(arg, "show_labels", "labels")

    def cmd_color(self, arg: str | None) -> CommandResult:
        return self._toggle(arg, "color", "color")

    cmd_colour = cmd_color

    def cmd_pause(self, arg: str | None) -> CommandResult:
        s = self.c.session
        value = _flag(arg, s.paused)
        if value is None:
            return CommandResult(False, "usage: pause [on|off]")
        s.set_paused(value)
        return CommandResult(True, "paused" if value else "resumed")

    def cmd_stale(self, arg: str | None) -> CommandResult:
        if arg is None:
            return CommandResult(True, f"stale {self.c.session.stale_after:g}s")
        self.c.session.stale_after = max(0.0, float(arg))
        return CommandResult(True, f"stale {self.c.session.stale_after:g}s")

    def cmd_fps(self, arg: str | None) -> CommandResult:
        if arg is None:
            return CommandResult(False, "usage: fps <hz>")
        hz = float(arg)
        if hz <= 0:
            raise ValueError("fps must be positive")
        self.c.set_fps(hz)
        return CommandResult(True, f"fps {hz:g}")

    def cmd_aspect(self, arg: str | None) -> CommandResult:
        if arg is None:
            return CommandResult(True, f"aspect {self.c.renderer.cell_aspect:g}")
        value = float(arg)
        if not 0.1 <= value <= 2.0:
            raise ValueError("aspect must be between 0.1 and 2.0")
        self.c.renderer.cell_aspect = value
        self.c.redraw()
        return CommandResult(True, f"aspect {value:g}")

    def cmd_rescan(self, arg: str | None) -> CommandResult:
        self.c.rescan()
        return CommandResult(True, "rescanned topics")

    def cmd_topics(self, arg: str | None) -> CommandResult:
        self.c.toggle_topics()
        return CommandResult(True, "toggled topic panel")

    def cmd_sidebar(self, arg: str | None) -> CommandResult:
        self.c.toggle_sidebar()
        return CommandResult(True, "toggled sidebar")

    def cmd_clear(self, arg: str | None) -> CommandResult:
        self.c.clear_log()
        return CommandResult(True, "")

    def cmd_quit(self, arg: str | None) -> CommandResult:
        self.c.quit()
        return CommandResult(True, "bye")

    cmd_q = cmd_quit
    cmd_exit = cmd_quit
