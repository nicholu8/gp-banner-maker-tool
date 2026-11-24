import json
import os

import pytest

from growbanner.config import Config, load_config, save_config
from growbanner.export import export_banner, export_label, export_sizes
from growbanner.sizes import DEFAULT_SIZE, CanvasSize
from growbanner.spec import BannerSpec
from scenarios import SCENARIOS, make_photo


def photo():
    return make_photo("braddock_landscape", SCENARIOS["braddock_landscape"][0])


def spec():
    return BannerSpec(title="Plant Sale", date="May 3", location="Braddock", photo_path=photo())


def test_fresh_config_has_square_extra_with_both_types():
    cfg = Config()
    assert [(s.name, s.width, s.height, s.png, s.pdf) for s in cfg.sizes] == [("Square", 1080, 1080, True, True)]


def test_old_config_without_type_flags_loads_as_both(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"sizes": [{"name": "Tall", "width": 1080, "height": 1920}]}))
    (s,) = load_config(p).sizes
    assert s.png and s.pdf


def test_old_config_with_empty_sizes_stays_empty(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"sizes": []}))
    assert load_config(p).sizes == []


def test_type_flags_roundtrip_and_never_both_off(tmp_path):
    p = tmp_path / "c.json"
    cfg = Config()
    cfg.sizes = [CanvasSize("A", 1080, 1080, png=True, pdf=False), CanvasSize("B", 1080, 1350, png=False, pdf=True)]
    save_config(cfg, p)
    a, b = load_config(p).sizes
    assert (a.png, a.pdf, b.png, b.pdf) == (True, False, False, True)
    data = json.loads(p.read_text())
    data["sizes"][0].update(png=False, pdf=False)
    p.write_text(json.dumps(data))
    assert load_config(p).sizes[0].png and load_config(p).sizes[0].pdf


def test_export_writes_only_selected_types(tmp_path):
    r = export_banner(spec(), tmp_path, png=True, pdf=False)
    assert r.png.exists() and r.pdf is None
    r = export_banner(spec(), tmp_path, png=False, pdf=True)
    assert r.pdf.exists() and r.png is None
    assert sorted(f.suffix for f in tmp_path.iterdir()) == [".pdf", ".png"]


def test_export_sizes_honours_each_size(tmp_path):
    sizes = [DEFAULT_SIZE, CanvasSize("Square", 1080, 1080, png=True, pdf=False)]
    results = export_sizes(spec(), sizes, tmp_path)
    assert sorted(f.name for r in results for f in r.files) == [
        "plant-sale-1080x1080.png", "plant-sale.pdf", "plant-sale.png"]


def test_export_label():
    assert export_label([DEFAULT_SIZE]) == "Export PNG + PDF"
    assert export_label([CanvasSize("x", 1880, 940, png=True, pdf=False)]) == "Export PNG"
    assert export_label([CanvasSize("x", 1880, 940, png=False, pdf=True)]) == "Export PDF"
    assert export_label([DEFAULT_SIZE, CanvasSize("S", 1080, 1080, png=True, pdf=False)]) == "Export 3 files"
    assert export_label([DEFAULT_SIZE, CanvasSize("S", 1080, 1080), CanvasSize("T", 1080, 1350, png=False)]) == "Export 5 files"


def test_settings_dialog_keeps_at_least_one_type():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QCheckBox
    from growbanner.settings_dialog import SettingsDialog
    QApplication.instance() or QApplication([])
    dlg = SettingsDialog(Config())
    png = dlg.size_table.cellWidget(0, 3).findChild(QCheckBox)
    pdf = dlg.size_table.cellWidget(0, 4).findChild(QCheckBox)
    png.setChecked(False)
    assert not png.isChecked() and pdf.isChecked()
    pdf.setChecked(False)  # last one: blocked
    assert pdf.isChecked()
    assert dlg.collect_sizes()[0].png is False and dlg.collect_sizes()[0].pdf is True
    assert SettingsDialog.validation_error([], [CanvasSize("x", 500, 500, False, False)])
