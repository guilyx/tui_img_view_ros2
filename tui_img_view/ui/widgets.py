"""Sidebar and status bar widgets."""

from __future__ import annotations

import logging
import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, OptionList, RichLog, SelectionList, Static
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection


class TopicPanel(Vertical):
    """Image topics (pick one) and box topics (toggle any)."""

    DEFAULT_CSS = """
    TopicPanel {
        width: 36;
        height: 1fr;
        border-right: tall $primary;
        background: $surface;
    }
    TopicPanel.hidden { display: none; }
    TopicPanel Label { padding: 0 1; color: $text-muted; text-style: bold; }
    TopicPanel OptionList, TopicPanel SelectionList {
        height: 1fr; border: none; background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Image topics  (Enter = view)")
        yield OptionList(id="image-topics")
        yield Label("Box topics  (Space = toggle)")
        yield SelectionList[str](id="box-topics")

    def set_image_topics(self, names: list[str], selected: str | None) -> None:
        lst = self.query_one("#image-topics", OptionList)
        current = [lst.get_option_at_index(i).id for i in range(lst.option_count)]
        if current != names:
            highlighted = lst.highlighted
            lst.clear_options()
            lst.add_options([Option(_mark(n, n == selected), id=n) for n in names])
            if names:
                lst.highlighted = min(highlighted or 0, len(names) - 1)
            return
        for i, name in enumerate(names):
            lst.replace_option_prompt_at_index(i, _mark(name, name == selected))

    def set_box_topics(self, names: list[str], enabled: set[str]) -> None:
        lst = self.query_one("#box-topics", SelectionList)
        current = [lst.get_option_at_index(i).value for i in range(lst.option_count)]
        if current == names:
            return
        highlighted = lst.highlighted
        lst.clear_options()
        lst.add_options([Selection(n, n, n in enabled) for n in names])
        if names:
            lst.highlighted = min(highlighted or 0, len(names) - 1)


def _mark(name: str, selected: bool) -> str:
    return f"[b]▶ {name}[/b]" if selected else f"  {name}"


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    StatusBar.error { background: $error; }
    """


class CommandInput(Input):
    """The ``:`` line. Escape hands focus back to the image."""

    BINDINGS = [Binding("escape", "back_to_image", "Back to image", show=False)]

    def action_back_to_image(self) -> None:
        self.screen.query_one("#image").focus()


class CommandPanel(Vertical):
    """Action buttons plus a ``:`` command line."""

    DEFAULT_CSS = """
    CommandPanel { height: auto; padding: 0 1; }
    CommandPanel Label { padding: 0; }
    CommandPanel .buttons {
        layout: grid;
        grid-size: 3;
        grid-gutter: 0 1;
        height: auto;
        margin-bottom: 1;
    }
    CommandPanel Button { width: 100%; }
    CommandPanel Input { border: tall $primary; }
    """

    ACTIONS: tuple[tuple[str, str], ...] = (
        ("mode", "Mode"),
        ("boxes", "Boxes"),
        ("labels", "Labels"),
        ("color", "Colour"),
        ("pause", "Pause"),
        ("next", "Next img"),
        ("rescan", "Rescan"),
        ("topics", "Topics"),
        ("quit", "Quit"),
    )

    def compose(self) -> ComposeResult:
        yield Label("Commands  (: to type)")
        with Horizontal(classes="buttons"):
            for action, text in self.ACTIONS:
                yield Button(text, id=f"cmd-{action}", compact=True)
        yield CommandInput(placeholder=":mode ascii · :boxes +/topic · :help", id="command-input")


class LogPanel(RichLog):
    """Timestamped event log fed from the ``tui_img_view`` logger."""

    DEFAULT_CSS = """
    LogPanel { height: 1fr; border-top: tall $primary; padding: 0 1; }
    """

    LEVEL_STYLE = {
        logging.DEBUG: "dim",
        logging.INFO: "",
        logging.WARNING: "yellow",
        logging.ERROR: "bold red",
        logging.CRITICAL: "bold red",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(
            highlight=False, markup=False, wrap=True, min_width=10, max_lines=500, **kwargs
        )
        self.entries = 0

    def add(self, when: float, level: int, message: str) -> None:
        stamp = time.strftime("%H:%M:%S", time.localtime(when))
        style = self.LEVEL_STYLE.get(level, "")
        text = Text(f"{stamp} ", style="dim")
        text.append(message, style=style)
        self.write(text)
        self.entries += 1


class SidePanel(Vertical):
    """Right-hand column: command panel on top, log below."""

    DEFAULT_CSS = """
    SidePanel {
        width: 44;
        height: 1fr;
        border-left: tall $primary;
        background: $surface;
    }
    SidePanel.hidden { display: none; }
    """

    def compose(self) -> ComposeResult:
        yield CommandPanel(id="commands")
        yield LogPanel(id="log")
