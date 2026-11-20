import json

import numpy as np
import pytest
from PIL import Image

from growbanner import layout as L
from growbanner.config import Config, load_config, save_config
from growbanner.export import export_banner
from growbanner.render import crop_to_canvas, render_png
from growbanner.schemes import OTHER, LocationRule, match_scheme, new_rule
from growbanner.sizes import CanvasSize, file_suffix, valid_dimensions
from growbanner.spec import BannerSpec
from scenarios import SCENARIOS, make_photo


def photo():
    return make_photo("braddock_landscape", SCENARIOS["braddock_landscape"][0])


def test_new_location_defaults_to_maroon_and_is_editable():
    rules = [new_rule("Hazelwood")]
    assert match_scheme("Hazelwood", rules).banner == OTHER.banner
    edited = [LocationRule("Hazelwood", (), "#112233", "#000000")]
    s = match_scheme("hazelwood farm day", edited)
    assert (s.banner, s.text) == ("#112233", "#000000")


def test_unlisted_location_uses_configured_default():
    other = type(OTHER)("Other", "#123456", "#FFFFFF")
    assert match_scheme("Nowhere", [], other).banner == "#123456"


def test_config_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    cfg = Config()
    cfg.locations.append(LocationRule("Hazelwood", ("hazelwood",), "#112233", "#000000"))
    cfg.sizes = [CanvasSize("Square", 1080, 1080)]
    cfg.last_size = "Square"
    save_config(cfg, p)
    back = load_config(p)
    assert back.locations[-1].banner == "#112233"
    assert [s.name for s in back.all_sizes] == ["Standard", "Square"]
    assert back.last_size == "Square"


def test_old_config_extra_presets_become_maroon_rows(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"locations": [], "extra_presets": ["Old Place"]}))
    cfg = load_config(p)
    assert any(r.name == "Old Place" and r.banner == OTHER.banner for r in cfg.locations)


@pytest.mark.parametrize("bad", ["not json", json.dumps({"locations": [{"name": "X", "banner": "red", "text": "#000000"}]})])
def test_bad_config_falls_back_to_defaults(tmp_path, bad):
    p = tmp_path / "c.json"
    p.write_text(bad)
    assert load_config(p).presets == Config().presets


def test_size_validation_and_suffix():
    assert valid_dimensions(1080, 1080) and not valid_dimensions(10, 1080)
    assert file_suffix((1880, 940)) == "" and file_suffix((1080, 1350)) == "-1080x1350"


@pytest.mark.parametrize("canvas", [(1080, 1080), (1080, 1920), (1200, 628), (3760, 1880)])
def test_other_sizes_render_at_size_and_banner_fits(canvas):
    spec = BannerSpec(title="Spring Seedling Sale and Plant Giveaway", date="May 3", time="6pm",
                      location="Braddock", cost="Free", photo_path=photo(), canvas=canvas)
    im = render_png(spec)
    assert im.size == canvas
    lay = L.compute_layout(spec.title, spec.date_time, spec.location_line, False, canvas=canvas)
    assert lay.width <= canvas[0] and lay.height < canvas[1] * 0.6
    assert lay.y0 + lay.height == canvas[1]


def test_double_size_scales_banner_exactly():
    a = L.compute_layout("Hello World", "May 3 | 6pm", "Braddock | Free")
    b = L.compute_layout("Hello World", "May 3 | 6pm", "Braddock | Free", canvas=(3760, 1880))
    assert b.title_size == 2 * a.title_size and abs(b.width - 2 * a.width) <= 4


def test_crop_matches_requested_aspect_for_tall_and_wide_sources():
    for size in [(1800, 1200), (1200, 1800)]:
        for canvas in [(1080, 1080), (1920, 1080), (1880, 940)]:
            assert crop_to_canvas(Image.new("RGB", size), 0.5, canvas).size == canvas


def test_default_size_files_keep_plain_names(tmp_path):
    spec = BannerSpec(title="Plant Sale", location="Braddock", photo_path=photo())
    assert export_banner(spec, tmp_path).png.name == "plant-sale.png"
    spec.canvas = (1080, 1080)
    assert export_banner(spec, tmp_path).png.name == "plant-sale-1080x1080.png"


def test_settings_dialog_edits_locations_and_sizes():
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from growbanner.settings_dialog import SettingsDialog
    app = QApplication.instance() or QApplication([])
    dlg = SettingsDialog(Config())
    n = dlg.loc_table.rowCount()
    dlg._add_loc_row(new_rule("Hazelwood"))
    dlg.loc_table.cellWidget(0, 1).color = "#010203"
    dlg._add_size_row(CanvasSize("Square", 1080, 1080))
    locs, sizes = dlg.collect_locations(), dlg.collect_sizes()
    assert len(locs) == n + 1 and locs[0].banner == "#010203" and locs[-1].banner == OTHER.banner
    assert sizes == [CanvasSize("Square", 1080, 1080)]
    assert dlg.validation_error(locs, sizes) is None
    assert dlg.validation_error(locs + [new_rule("hazelwood")], sizes)  # duplicate name
    assert dlg.validation_error(locs, [CanvasSize("standard", 500, 500)])  # clashes with default
    dlg._accept()
    assert dlg.cfg.sizes == sizes and dlg.cfg.locations[0].banner == "#010203"
