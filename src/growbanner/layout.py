"""Banner measurements, title wrapping and auto-shrink. No drawing, no GUI.

Numbers follow reference/banner_reference.py (S=2 on a 940x470 template).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .fonts import pil_measure

S = 2
BASE_W, BASE_H = 940 * S, 470 * S  # 1880 x 940: the default size every other size scales from
CANVAS_W, CANVAS_H = BASE_W, BASE_H
DEFAULT_CANVAS = (BASE_W, BASE_H)
TITLE_SIZE = 34 * S
MIN_TITLE_SIZE = 20 * S
INFO_RATIO = 29 / 34
LINE_HEIGHT = 1.5
PAD_TOP = 18 * S
PAD_BOTTOM = 14 * S
HEIGHT_TRIM = 8 * S  # reference subtracts this from the banner height
TEXT_X = 20 * S
RIGHT_PAD = 62 * S
RADIUS = 26 * S
FIT_MARGIN = 82 * S

Measure = Callable[[str, int, bool], float]  # (text, px size, bold) -> width


def scale_for(canvas: tuple[int, int]) -> float:
    """Banner scale factor: 1.0 for the default size, proportional for others."""
    return min(canvas[0] / BASE_W, canvas[1] / BASE_H)


@dataclass(frozen=True)
class Row:
    text: str
    bold: bool  # True = title face, False = info face


@dataclass(frozen=True)
class BannerLayout:
    rows: tuple[Row, ...]
    title_size: int
    info_size: int
    title_lh: int
    info_lh: int
    width: int
    height: int
    canvas_w: int = BASE_W
    canvas_h: int = BASE_H
    pad_top: int = PAD_TOP
    text_x: int = TEXT_X
    radius: int = RADIUS

    @property
    def y0(self) -> int:
        return self.canvas_h - self.height

    def size_of(self, row: Row) -> int:
        return self.title_size if row.bold else self.info_size

    def lh_of(self, row: Row) -> int:
        return self.title_lh if row.bold else self.info_lh

    def row_tops(self) -> list[tuple[Row, int]]:
        """Each row with the y of its line box top (canvas coordinates)."""
        y = self.y0 + self.pad_top
        out = []
        for row in self.rows:
            out.append((row, y))
            y += self.lh_of(row)
        return out


def _wrap(title: str, size: int, limit: float, nowrap: bool, measure: Measure) -> list[str]:
    if nowrap or measure(title, size, True) <= limit:
        return [title]
    words = title.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        m = max(measure(a, size, True), measure(b, size, True))
        if best is None or m < best[0]:
            best = (m, [a, b])
    return best[1] if best else [title]


def compute_layout(
    title: str,
    date_time: str,
    location_line: str,
    nowrap: bool = False,
    measure: Measure = pil_measure,
    canvas: tuple[int, int] = DEFAULT_CANVAS,
) -> BannerLayout:
    cw, ch = canvas
    k = scale_for(canvas)

    def sc(v: int) -> int:  # scale a base-size pixel value (identity at the default size)
        return max(1, round(v * k))

    maxw = int(cw * (0.97 if nowrap else 0.86))
    limit = maxw - sc(FIT_MARGIN)
    info = [t for t in (date_time, location_line) if t]
    min_size, step = sc(MIN_TITLE_SIZE), sc(S)
    pad_top, pad_bot = sc(PAD_TOP), sc(PAD_BOTTOM)
    text_x, right_pad = sc(TEXT_X), sc(RIGHT_PAD)

    size = sc(TITLE_SIZE)
    lines = _wrap(title, size, limit, nowrap, measure)

    def widest() -> float:
        info_size = int(size * INFO_RATIO)
        return max(
            [measure(t, size, True) for t in lines] + [measure(t, info_size, False) for t in info]
        )

    def fit_width() -> float:
        # Quirk kept from the reference: the shrink test measures the info lines
        # in the (wider) bold title face, not the info face.
        return max(measure(t, size, True) for t in lines + info)

    while fit_width() > limit and size > min_size:
        size = max(size - step, min_size)
        lines = _wrap(title, size, limit, nowrap, measure)

    info_size = int(size * INFO_RATIO)
    rows = tuple([Row(t, True) for t in lines] + [Row(t, False) for t in info])
    title_lh = int(size * LINE_HEIGHT)
    info_lh = int(size * INFO_RATIO * LINE_HEIGHT)
    height = pad_top + pad_bot + len(lines) * title_lh + len(info) * info_lh - sc(HEIGHT_TRIM)
    width = min(int(widest() + text_x + right_pad), cw)
    return BannerLayout(
        rows, size, info_size, title_lh, info_lh, width, height,
        cw, ch, pad_top, text_x, min(sc(RADIUS), width, height),
    )
