from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .schemes import Scheme, match_scheme


@dataclass
class BannerSpec:
    title: str = ""
    date: str = ""
    time: str = ""
    location: str = ""
    cost: str = ""
    photo_path: Path | None = None
    crop_y: float = 0.5  # 0 = top band, 1 = bottom band (tall photos only)
    nowrap: bool = False
    scheme: Scheme | None = None  # None -> matched from ``location``
    canvas: tuple[int, int] = (1880, 940)  # output size in px; (1880, 940) is the default

    @property
    def date_time(self) -> str:
        return " | ".join(p for p in (self.date.strip(), self.time.strip()) if p)

    @property
    def location_line(self) -> str:
        loc, cost = self.location.strip(), self.cost.strip()
        return f"{loc} | {cost}" if loc and cost else (loc or cost)

    def resolved_scheme(self) -> Scheme:
        return self.scheme or match_scheme(self.location)
