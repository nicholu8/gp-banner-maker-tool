"""Pillow rendering of the banner. No GUI imports."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from . import layout as L
from .fonts import load_font, weight_for
from .layout import BannerLayout, compute_layout
from .schemes import Scheme
from .spec import BannerSpec

try:  # HEIC/HEIF (iPhone) support
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass


def load_photo(path: str | Path) -> Image.Image:
    """Open any supported photo as upright RGB (EXIF applied, alpha flattened on white)."""
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P") or "transparency" in im.info:
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    return im.convert("RGB")  # also converts CMYK


def crop_to_canvas(
    im: Image.Image, crop_y: float = 0.5, canvas: tuple[int, int] = L.DEFAULT_CANVAS
) -> Image.Image:
    """Crop to the canvas aspect (band chosen by crop_y if the photo is taller, centered if
    wider), then resize to the canvas size. At 1880x940 this is the reference's 2:1 crop."""
    cw, ch = canvas
    w, h = im.size
    th = w * ch // cw
    if th <= h:
        top = int((h - th) * crop_y)
        im = im.crop((0, top, w, top + th))
    else:
        lw = h * cw // ch
        left = (w - lw) // 2
        im = im.crop((left, 0, left + lw, h))
    return im.resize((cw, ch), Image.LANCZOS)


def build_layout(spec: BannerSpec) -> BannerLayout:
    return compute_layout(spec.title, spec.date_time, spec.location_line, spec.nowrap, canvas=spec.canvas)


def _line_y(layout: BannerLayout, row: L.Row, top: int) -> tuple[int, int, int]:
    """Return (draw_y, ascent, descent) for a row, matching the reference's centering."""
    font = load_font(weight_for(row.bold), layout.size_of(row))
    asc, desc = font.getmetrics()
    return top + (layout.lh_of(row) - (asc + desc)) // 2, asc, desc


def baseline_y(layout: BannerLayout, row: L.Row, top: int) -> int:
    y, asc, _ = _line_y(layout, row, top)
    return y + asc


def draw_banner(base: Image.Image, layout: BannerLayout, scheme: Scheme) -> Image.Image:
    """Return a copy of the canvas-sized ``base`` with the banner drawn on it."""
    im = base.copy()
    bw, bh = layout.width, layout.height
    q = 4
    mask = Image.new("L", (bw * q, bh * q), 0)
    r = layout.radius * q
    ImageDraw.Draw(mask).rounded_rectangle((-r * 2, 0, bw * q - 1, bh * q + r * 2), radius=r, fill=255)
    mask = mask.resize((bw, bh), Image.LANCZOS)
    im.paste(Image.new("RGB", (bw, bh), scheme.banner), (0, layout.y0), mask)
    d = ImageDraw.Draw(im)
    for row, top in layout.row_tops():
        font = load_font(weight_for(row.bold), layout.size_of(row))
        y, _, _ = _line_y(layout, row, top)
        d.text((layout.text_x, y), row.text, font=font, fill=scheme.text)
    return im


def render_png(spec: BannerSpec, photo: Image.Image | None = None) -> Image.Image:
    """Full banner image at ``spec.canvas`` (default 1880x940). ``photo`` overrides loading ``spec.photo_path``."""
    if photo is None:
        photo = load_photo(spec.photo_path)
    base = crop_to_canvas(photo, spec.crop_y, spec.canvas)
    return draw_banner(base, build_layout(spec), spec.resolved_scheme())
