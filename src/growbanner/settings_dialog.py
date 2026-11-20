"""Settings window: location colors and extra output sizes. Edits a copy of the Config."""
from __future__ import annotations

import copy

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from .config import Config
from .schemes import LocationRule, Scheme, new_rule
from .sizes import DEFAULT_SIZE, MAX_SIDE, MIN_SIDE, CanvasSize

BLACK, WHITE = "#000000", "#FFFFFF"


class ColorButton(QPushButton):
    def __init__(self, hex_color: str, parent=None):
        super().__init__(parent)
        self.color = hex_color.upper()
        self.clicked.connect(self.pick)
        self._paint()

    def _paint(self):
        c = QColor(self.color)
        fg = "#000" if c.lightness() > 140 else "#fff"
        self.setText(self.color)
        self.setStyleSheet(f"background:{self.color};color:{fg};padding:4px")

    def pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, "Banner color")
        if c.isValid():
            self.color = c.name().upper()
            self._paint()


def text_combo(hex_color: str) -> QComboBox:
    cb = QComboBox()
    cb.addItems(["White text", "Black text"])
    cb.setCurrentIndex(1 if hex_color.upper() == BLACK else 0)
    return cb


def text_hex(cb: QComboBox) -> str:
    return BLACK if cb.currentIndex() == 1 else WHITE


class SettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(640, 460)
        self.cfg = copy.deepcopy(cfg)  # the caller reads .cfg after accept()

        tabs = QTabWidget()
        tabs.addTab(self._locations_tab(), "Locations")
        tabs.addTab(self._sizes_tab(), "Sizes")
        tabs.addTab(self._general_tab(), "General")
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(buttons)

    # ---- general ----
    def _general_tab(self) -> QWidget:
        self.updates_box = QCheckBox("Check for new versions when the app starts")
        self.updates_box.setChecked(self.cfg.check_updates)
        note = QLabel(
            "This is the only time the app uses the internet. It asks GitHub whether a newer "
            "release exists and sends nothing about you, your photos or your events. "
            "It never installs anything by itself."
        )
        note.setWordWrap(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self.updates_box)
        lay.addWidget(note)
        lay.addStretch()
        return w

    # ---- locations ----
    def _locations_tab(self) -> QWidget:
        self.loc_table = QTableWidget(0, 4)
        self.loc_table.setHorizontalHeaderLabels(
            ["Location (printed on banner)", "Banner color", "Text", "Also match words"])
        self.loc_table.horizontalHeader().setStretchLastSection(True)
        self.loc_table.setColumnWidth(0, 210)
        self.loc_table.setColumnWidth(1, 110)
        self.loc_table.setColumnWidth(2, 100)
        for r in self.cfg.locations:
            self._add_loc_row(r)

        add = QPushButton("Add location")
        add.clicked.connect(lambda: self._add_loc_row(new_rule("", self.cfg.other), edit=True))
        rem = QPushButton("Remove selected")
        rem.clicked.connect(self._remove_loc_row)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()

        self.other_btn = ColorButton(self.cfg.other.banner)
        self.other_text = text_combo(self.cfg.other.text)
        other = QHBoxLayout()
        other.addWidget(QLabel("Locations not in this list use:"))
        other.addWidget(self.other_btn)
        other.addWidget(self.other_text)
        other.addStretch()

        hint = QLabel(
            "New locations start with the default color (maroon unless you change it below). "
            "“Also match words” is optional: comma-separated words that should also pick this "
            "row (e.g. GRC). Rows are checked top to bottom."
        )
        hint.setWordWrap(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(hint)
        lay.addWidget(self.loc_table)
        lay.addLayout(row)
        lay.addLayout(other)
        return w

    def _add_loc_row(self, rule: LocationRule, edit: bool = False):
        t = self.loc_table
        i = t.rowCount()
        t.insertRow(i)
        t.setItem(i, 0, QTableWidgetItem(rule.name))
        t.setCellWidget(i, 1, ColorButton(rule.banner))
        t.setCellWidget(i, 2, text_combo(rule.text))
        t.setItem(i, 3, QTableWidgetItem(", ".join(rule.keywords)))
        if edit:
            t.setCurrentCell(i, 0)
            t.editItem(t.item(i, 0))

    def _remove_loc_row(self):
        for i in sorted({ix.row() for ix in self.loc_table.selectedIndexes()}, reverse=True):
            self.loc_table.removeRow(i)

    def collect_locations(self) -> list[LocationRule]:
        t = self.loc_table
        out = []
        for i in range(t.rowCount()):
            name = t.item(i, 0).text().strip()
            kws = tuple(k.strip() for k in t.item(i, 3).text().split(",") if k.strip())
            out.append(LocationRule(name, kws, t.cellWidget(i, 1).color, text_hex(t.cellWidget(i, 2))))
        return out

    # ---- sizes ----
    def _sizes_tab(self) -> QWidget:
        self.size_table = QTableWidget(0, 3)
        self.size_table.setHorizontalHeaderLabels(["Name", "Width (px)", "Height (px)"])
        self.size_table.horizontalHeader().setStretchLastSection(True)
        self.size_table.setColumnWidth(0, 240)
        for s in self.cfg.sizes:
            self._add_size_row(s)
        add = QPushButton("Add size")
        add.clicked.connect(lambda: self._add_size_row(CanvasSize("", 1080, 1080), edit=True))
        rem = QPushButton("Remove selected")
        rem.clicked.connect(self._remove_size_row)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        hint = QLabel(
            f"{DEFAULT_SIZE.label} is the built-in default and can't be changed. Extra sizes crop "
            "the photo to the new shape and scale the banner (text, padding, corner) to fit. "
            "Files for extra sizes get the size added to their name, e.g. my-event-1080x1080.png."
        )
        hint.setWordWrap(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(hint)
        lay.addWidget(self.size_table)
        lay.addLayout(row)
        return w

    @staticmethod
    def _spin(v: int) -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(MIN_SIDE, MAX_SIDE)
        sb.setValue(v)
        return sb

    def _add_size_row(self, s: CanvasSize, edit: bool = False):
        t = self.size_table
        i = t.rowCount()
        t.insertRow(i)
        t.setItem(i, 0, QTableWidgetItem(s.name))
        t.setCellWidget(i, 1, self._spin(s.width))
        t.setCellWidget(i, 2, self._spin(s.height))
        if edit:
            t.setCurrentCell(i, 0)
            t.editItem(t.item(i, 0))

    def _remove_size_row(self):
        for i in sorted({ix.row() for ix in self.size_table.selectedIndexes()}, reverse=True):
            self.size_table.removeRow(i)

    def collect_sizes(self) -> list[CanvasSize]:
        t = self.size_table
        return [
            CanvasSize(t.item(i, 0).text().strip(), t.cellWidget(i, 1).value(), t.cellWidget(i, 2).value())
            for i in range(t.rowCount())
        ]

    # ---- save ----
    @staticmethod
    def validation_error(locs: list[LocationRule], sizes: list[CanvasSize]) -> str | None:
        names = [r.name.lower() for r in locs]
        if any(not n for n in names):
            return "Every location needs a name (or remove the empty row)."
        if len(set(names)) != len(names):
            return "Two locations have the same name."
        if any(not s.name for s in sizes):
            return "Every size needs a name (or remove the empty row)."
        snames = [s.name.lower() for s in sizes] + [DEFAULT_SIZE.name.lower()]
        if len(set(snames)) != len(snames):
            return f"Size names must be unique (“{DEFAULT_SIZE.name}” is used by the default size)."
        return None

    def _accept(self):
        locs, sizes = self.collect_locations(), self.collect_sizes()
        err = self.validation_error(locs, sizes)
        if err:
            QMessageBox.warning(self, "Check settings", err)
            return
        self.cfg.locations = locs
        self.cfg.sizes = sizes
        self.cfg.check_updates = self.updates_box.isChecked()
        self.cfg.other = Scheme("Other", self.other_btn.color, text_hex(self.other_text))
        self.accept()
