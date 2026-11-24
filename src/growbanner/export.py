"""Write the PNG and/or PDF files for a banner. No GUI imports."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from PIL import Image

from .pdf import render_pdf
from .render import load_photo, render_png
from .sizes import CanvasSize, file_suffix
from .spec import BannerSpec


@dataclass(frozen=True)
class ExportResult:
    png: Path | None = None
    pdf: Path | None = None

    @property
    def files(self) -> list[Path]:
        return [p for p in (self.png, self.pdf) if p is not None]


def slugify(title: str, max_len: int = 60) -> str:
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:max_len].strip("-")
    return s or "banner"


def unique_stem(out_dir: Path, slug: str) -> str:
    stem, n = slug, 1
    while (out_dir / f"{stem}.png").exists() or (out_dir / f"{stem}.pdf").exists():
        n += 1
        stem = f"{slug}-{n}"
    return stem


def export_label(sizes: Sequence[CanvasSize]) -> str:
    """Text for the Export button: 'Export PNG', 'Export PDF', 'Export PNG + PDF', or 'Export 5 files'."""
    if len(sizes) == 1:
        s = sizes[0]
        kinds = [k for k, on in (("PNG", s.png), ("PDF", s.pdf)) if on]
        return "Export " + " + ".join(kinds) if kinds else "Export"
    n = sum(s.file_count for s in sizes)
    return f"Export {n} file" + ("" if n == 1 else "s")


def export_banner(
    spec: BannerSpec, out_dir: str | Path, photo: Image.Image | None = None,
    png: bool = True, pdf: bool = True,
) -> ExportResult:
    """Write one size (``spec.canvas``). ``png``/``pdf`` choose which file types to write."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if photo is None:
        photo = load_photo(spec.photo_path)
    stem = unique_stem(out_dir, slugify(spec.title) + file_suffix(spec.canvas))
    png_path = out_dir / f"{stem}.png" if png else None
    pdf_path = out_dir / f"{stem}.pdf" if pdf else None
    if png_path:
        render_png(spec, photo).save(png_path)
    if pdf_path:
        render_pdf(spec, pdf_path, photo)
    return ExportResult(png_path, pdf_path)


def export_sizes(
    spec: BannerSpec, sizes: Sequence[CanvasSize], out_dir: str | Path,
    photo: Image.Image | None = None,
) -> list[ExportResult]:
    """Write every size in ``sizes``, each with only its checked file types."""
    if photo is None:
        photo = load_photo(spec.photo_path)
    return [
        export_banner(replace(spec, canvas=s.canvas), out_dir, photo, png=s.png, pdf=s.pdf)
        for s in sizes if s.file_count
    ]
