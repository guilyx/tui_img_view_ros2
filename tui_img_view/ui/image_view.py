"""Widget that paints a :class:`~tui_img_view.render.canvas.Canvas` line by line."""

from __future__ import annotations

from rich.color import Color
from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

from tui_img_view.core.types import Detections, Frame
from tui_img_view.render.canvas import RGB, Canvas
from tui_img_view.render.pipeline import Renderer


class ImageView(Widget):
    """Renders the latest frame + detections to fit its own size."""

    can_focus = True

    DEFAULT_CSS = """
    ImageView {
        width: 1fr;
        height: 1fr;
        background: $background;
    }
    ImageView:focus { border: none; }
    """

    def __init__(self, renderer: Renderer | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.renderer = renderer or Renderer()
        self._frame: Frame | None = None
        self._detections: tuple[Detections, ...] = ()
        self._strips: list[Strip] = []
        self._strip_width = 0
        self._style_cache: dict[tuple[RGB | None, RGB | None], Style] = {}
        self._base_style: Style | None = None
        self.canvas: Canvas | None = None

    # -- data --------------------------------------------------------------

    def set_content(self, frame: Frame | None, detections: tuple[Detections, ...] = ()) -> None:
        self._frame = frame
        self._detections = detections
        self.rebuild()

    def rebuild(self) -> None:
        """Re-rasterise for the current size and repaint."""
        width, height = self.size.width, self.size.height
        if width <= 0 or height <= 0:
            self._strips = []
            self.canvas = None
            return
        canvas = self.renderer.render(self._frame, self._detections, width, height)
        self.canvas = canvas
        base = self.rich_style
        if base != self._base_style:
            self._base_style = base
            self._style_cache.clear()
        elif len(self._style_cache) > 60_000:
            self._style_cache.clear()
        cache = self._style_cache
        strips: list[Strip] = []
        for row in canvas.rows():
            segments: list[Segment] = []
            for ch, fg, bg in row:
                key = (fg, bg)
                style = cache.get(key)
                if style is None:
                    style = base + Style.from_color(
                        Color.from_rgb(*fg) if fg is not None else None,
                        Color.from_rgb(*bg) if bg is not None else None,
                    )
                    cache[key] = style
                segments.append(Segment(ch, style))
            strips.append(Strip(segments, width))
        self._strips = strips
        self._strip_width = width
        self.refresh()

    # -- Textual hooks -----------------------------------------------------

    def on_resize(self) -> None:
        self.rebuild()

    def render_line(self, y: int) -> Strip:
        if y < len(self._strips) and self._strip_width == self.size.width:
            return self._strips[y]
        return Strip.blank(self.size.width, self.rich_style)
