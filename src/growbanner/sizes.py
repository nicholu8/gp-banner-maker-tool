"""Output sizes. The default (1880x940) is built in; others are user-defined in config."""
from __future__ import annotations

from dataclasses import dataclass

from .layout import DEFAULT_CANVAS

MIN_SIDE, MAX_SIDE = 200, 8000


@dataclass(frozen=True)
class CanvasSize:
    name: str
    width: int
    height: int
    png: bool = True  # write a PNG for this size
    pdf: bool = True  # write a PDF (live text) for this size

    @property
    def file_count(self) -> int:
        return int(self.png) + int(self.pdf)

    @property
    def canvas(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def label(self) -> str:
        return f"{self.name} ({self.width}×{self.height})"

    @property
    def is_default(self) -> bool:
        return self.canvas == DEFAULT_CANVAS


DEFAULT_SIZE = CanvasSize("Standard", *DEFAULT_CANVAS)  # always exports both PNG and PDF
DEFAULT_EXTRA_SIZES = (CanvasSize("Square", 1080, 1080),)  # starting extra sizes for a fresh config


def valid_dimensions(width: int, height: int) -> bool:
    return MIN_SIDE <= width <= MAX_SIDE and MIN_SIDE <= height <= MAX_SIDE


def file_suffix(canvas: tuple[int, int]) -> str:
    """'' for the default size, '-1080x1080' otherwise (keeps default file names unchanged)."""
    return "" if canvas == DEFAULT_CANVAS else f"-{canvas[0]}x{canvas[1]}"
