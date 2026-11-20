"""Write the PNG + PDF pair for a banner. No GUI imports."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .pdf import render_pdf
from .render import load_photo, render_png
from .sizes import file_suffix
from .spec import BannerSpec


@dataclass(frozen=True)
class ExportResult:
    png: Path
    pdf: Path


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


def export_banner(spec: BannerSpec, out_dir: str | Path, photo: Image.Image | None = None) -> ExportResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if photo is None:
        photo = load_photo(spec.photo_path)
    stem = unique_stem(out_dir, slugify(spec.title) + file_suffix(spec.canvas))
    png, pdf = out_dir / f"{stem}.png", out_dir / f"{stem}.pdf"
    render_png(spec, photo).save(png)
    render_pdf(spec, pdf, photo)
    return ExportResult(png, pdf)
