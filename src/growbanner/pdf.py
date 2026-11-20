"""PDF export with live (selectable/editable) text, via ReportLab. No GUI imports."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .fonts import font_path
from .render import baseline_y, build_layout, crop_to_canvas, load_photo
from .spec import BannerSpec

PAGE_W_IN = 13.333  # same as the reference slide
BOLD, SEMIBOLD = "Bitter-Bold", "Bitter-SemiBold"
_registered = False


def _register_fonts() -> None:
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont(BOLD, str(font_path(700))))
        pdfmetrics.registerFont(TTFont(SEMIBOLD, str(font_path(600))))
        _registered = True


def render_pdf(spec: BannerSpec, out_path: str | Path, photo: Image.Image | None = None) -> Path:
    _register_fonts()
    if photo is None:
        photo = load_photo(spec.photo_path)
    base = crop_to_canvas(photo, spec.crop_y, spec.canvas)
    layout = build_layout(spec)
    scheme = spec.resolved_scheme()

    cw, ch = layout.canvas_w, layout.canvas_h
    # Long side is 13.333 in (same as the reference slide at the default size).
    pw = PAGE_W_IN * 72 * min(1.0, cw / ch)
    k = pw / cw  # canvas px -> points
    ph = ch * k
    c = canvas.Canvas(str(out_path), pagesize=(pw, ph))
    c.setTitle(spec.title or "Grow Pittsburgh banner")

    buf = io.BytesIO()
    base.save(buf, "JPEG", quality=92)
    buf.seek(0)
    c.drawImage(ImageReader(buf), 0, 0, pw, ph)

    # banner: bottom-left anchored, rounded top-right corner only
    bw, bh = layout.width * k, layout.height * k
    r = min(layout.radius * k, bw, bh)
    kappa = 0.5522847498 * r
    p = c.beginPath()
    p.moveTo(0, 0)
    p.lineTo(bw, 0)
    p.lineTo(bw, bh - r)
    p.curveTo(bw, bh - r + kappa, bw - r + kappa, bh, bw - r, bh)
    p.lineTo(0, bh)
    p.close()
    c.setFillColor(HexColor(scheme.banner))
    c.setStrokeColor(HexColor(scheme.banner))
    c.drawPath(p, fill=1, stroke=0)

    c.setFillColor(HexColor(scheme.text))
    for row, top in layout.row_tops():
        c.setFont(BOLD if row.bold else SEMIBOLD, layout.size_of(row) * k)
        c.drawString(layout.text_x * k, ph - baseline_y(layout, row, top) * k, row.text)

    c.showPage()
    c.save()
    return Path(out_path)
