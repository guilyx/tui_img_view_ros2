"""Sidebar and status bar widgets."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, OptionList, SelectionList, Static
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
