"""Serialise a :class:`Canvas` as 24-bit ANSI text (for snapshots, piping, tests)."""

from __future__ import annotations

from tui_img_view.render.canvas import RGB, Canvas

RESET = "\x1b[0m"


def _sgr(fg: RGB | None, bg: RGB | None) -> str:
    parts: list[str] = []
    parts.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}" if fg else "39")
    parts.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}" if bg else "49")
    return f"\x1b[{';'.join(parts)}m"


def canvas_to_ansi(canvas: Canvas, *, color: bool = True) -> str:
    lines: list[str] = []
    for row in canvas.rows():
        out: list[str] = []
        current: tuple[RGB | None, RGB | None] = (None, None)
        for ch, fg, bg in row:
            if color and (fg, bg) != current:
                out.append(_sgr(fg, bg))
                current = (fg, bg)
            out.append(ch)
        if color and current != (None, None):
            out.append(RESET)
        lines.append("".join(out))
    return "\n".join(lines)
