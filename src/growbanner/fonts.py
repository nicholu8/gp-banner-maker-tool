"""Bundled Bitter fonts: path lookup (dev tree or PyInstaller bundle) and Pillow measuring."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TITLE_WEIGHT = 700  # Bitter Bold
INFO_WEIGHT = 600  # Bitter SemiBold


def resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "growbanner" / "resources"  # type: ignore[attr-defined]
    return Path(__file__).parent / "resources"


def font_path(weight: int) -> Path:
    return resource_dir() / "fonts" / f"Bitter-{weight}.ttf"


@lru_cache(maxsize=None)
def load_font(weight: int, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(weight)), size)


def weight_for(bold: bool) -> int:
    return TITLE_WEIGHT if bold else INFO_WEIGHT


_scratch = ImageDraw.Draw(Image.new("L", (1, 1)))


def pil_measure(text: str, size: int, bold: bool) -> float:
    """Pixel width of ``text`` at ``size`` px in the title (bold) or info face."""
    return _scratch.textlength(text, font=load_font(weight_for(bold), size))
