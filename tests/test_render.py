import numpy as np
import pytest
from PIL import Image

from growbanner.export import export_banner
from growbanner.render import load_photo, render_png
from growbanner.schemes import match_scheme
from growbanner.spec import BannerSpec
from scenarios import GOLDEN, SCENARIOS, make_photo


def spec_for(name):
    size, a = SCENARIOS[name]
    return BannerSpec(
        title=a["title"], date=a["dt"].split(" | ")[0], time=" | ".join(a["dt"].split(" | ")[1:]),
        location=a["loc"], cost=a["cost"] or "", photo_path=make_photo(name, size),
        crop_y=a["yoff"], nowrap=a["nowrap"], scheme=match_scheme(a["loc"]),
    )


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_matches_reference_golden(name):
    out = render_png(spec_for(name))
    gold = Image.open(GOLDEN / f"{name}.png").convert("RGB")
    assert out.size == gold.size == (1880, 940)
    diff = np.abs(np.asarray(out, dtype=float) - np.asarray(gold, dtype=float)).mean()
    assert diff < 1.0, f"mean diff {diff}"


def test_exif_rotation_is_applied(tmp_path):
    im = Image.new("RGB", (400, 200), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW on display
    p = tmp_path / "rot.jpg"
    im.save(p, exif=exif)
    assert load_photo(p).size == (200, 400)


def test_transparent_png_flattens_to_white(tmp_path):
    p = tmp_path / "t.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(p)
    assert load_photo(p).getpixel((5, 5)) == (255, 255, 255)


def test_export_writes_pair_and_avoids_collisions(tmp_path):
    spec = spec_for("braddock_landscape")
    first = export_banner(spec, tmp_path)
    second = export_banner(spec, tmp_path)
    assert first.png.name == "spring-seedling-sale.png" and first.pdf.exists()
    assert second.png.name == "spring-seedling-sale-2.png" and second.pdf.exists()


def test_pdf_has_live_text_and_matches_png(tmp_path):
    fitz = pytest.importorskip("fitz")
    spec = spec_for("braddock_landscape")
    res = export_banner(spec, tmp_path)
    page = fitz.open(res.pdf)[0]
    text = page.get_text()
    assert "Spring Seedling Sale" in text and "Braddock | Free" in text
    fonts = [f[3] for f in page.get_fonts()]
    assert any("Bitter" in f for f in fonts), fonts
    pix = page.get_pixmap(dpi=140)
    pdf_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).resize((1880, 940))
    png = Image.open(res.png).convert("RGB")
    diff = np.abs(np.asarray(pdf_img, dtype=float) - np.asarray(png, dtype=float)).mean()
    assert diff < 6.0, f"pdf vs png mean diff {diff}"
