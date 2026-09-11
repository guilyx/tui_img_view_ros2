"""A cell grid: the renderer's output, the UI's input."""

from __future__ import annotations

from collections.abc import Iterator

RGB = tuple[int, int, int]
#: (character, foreground, background). ``None`` means "terminal default".
Cell = tuple[str, RGB | None, RGB | None]
BLANK: Cell = (" ", None, None)


class Canvas:
    __slots__ = ("width", "height", "cells")

    def __init__(self, width: int, height: int, cells: list[list[Cell]] | None = None) -> None:
        self.width = max(0, int(width))
        self.height = max(0, int(height))
        if cells is None:
            cells = [[BLANK] * self.width for _ in range(self.height)]
        self.cells = cells

    def get(self, x: int, y: int) -> Cell:
        return self.cells[y][x]

    def put(self, x: int, y: int, cell: Cell) -> None:
        """Set a cell; silently ignores out-of-range coordinates."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = cell

    def blit(self, other: Canvas, x0: int, y0: int) -> None:
        """Copy ``other`` onto this canvas with its top-left at ``(x0, y0)``."""
        for oy, row in enumerate(other.cells):
            y = y0 + oy
            if not 0 <= y < self.height:
                continue
            xs = max(0, -x0)
            xe = min(other.width, self.width - x0)
            if xe <= xs:
                continue
            self.cells[y][x0 + xs : x0 + xe] = row[xs:xe]

    def rows(self) -> Iterator[list[Cell]]:
        return iter(self.cells)

    def to_text(self) -> str:
        """Characters only (no colour). Useful for tests and debugging."""
        return "\n".join("".join(c[0] for c in row) for row in self.cells)
