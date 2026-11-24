"""Settings window: location colors and extra output sizes. Edits a copy of the Config."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from . import drive
from .config import Config
from .schemes import LocationRule, Scheme, new_rule
from .qtasks import Task
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
    linkReady = Signal(str)  # sign-in link, from the worker thread to the UI thread

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(640, 460)
        self.cfg = copy.deepcopy(cfg)  # the caller reads .cfg after accept()

        tabs = QTabWidget()
        tabs.addTab(self._locations_tab(), "Locations")
        tabs.addTab(self._sizes_tab(), "Sizes")
        tabs.addTab(self._general_tab(), "General")
        self._orig_email = cfg.drive_email
        self._disconnect_pending = False
        self._connected_here = False
        self._task: Task | None = None
        self._auto_copy = False
        if drive.available():
            tabs.addTab(self._drive_tab(), "Google Drive")
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
            "This check asks GitHub whether a newer release exists and sends nothing about you, "
            "your photos or your events. It never installs anything by itself. The only other "
            "time the app uses the internet is the optional Google Drive upload (see that tab)."
        )
        note.setWordWrap(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(self.updates_box)
        lay.addWidget(note)
        lay.addStretch()
        return w

    # ---- google drive ----
    def _drive_tab(self) -> QWidget:
        self.drive_status = QLabel()
        self.drive_btn = QPushButton()
        self.drive_btn.clicked.connect(lambda: self._drive_toggle(True))
        self.copy_connect_btn = QPushButton("Connect without opening a browser (copy link)")
        self.copy_connect_btn.setToolTip(
            "Use this if your default browser is not the one signed in to your Grow Pittsburgh Google account.")
        self.copy_connect_btn.clicked.connect(lambda: self._drive_toggle(False))
        self.link_edit = QLineEdit()
        self.link_edit.setReadOnly(True)
        self.link_copy = QPushButton("Copy link")
        self.link_copy.clicked.connect(self._copy_link)
        self.link_note = QLabel()
        self.link_note.setWordWrap(True)
        self.link_box = QWidget()
        lb = QVBoxLayout(self.link_box)
        lb.setContentsMargins(0, 0, 0, 0)
        lb.addWidget(self.link_note)
        lrow = QHBoxLayout()
        lrow.addWidget(self.link_edit, 1)
        lrow.addWidget(self.link_copy)
        lb.addLayout(lrow)
        self.link_box.setVisible(False)
        self.linkReady.connect(self._show_link)
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Paste the link to the GP Banners folder")
        if self.cfg.drive_folder_id:
            self.folder_edit.setText(f"https://drive.google.com/drive/folders/{self.cfg.drive_folder_id}")
        self.folder_edit.editingFinished.connect(self._check_folder)
        self.folder_note = QLabel()
        self.folder_note.setWordWrap(True)
        self.drive_box = QCheckBox("Upload to Drive after export")
        self.drive_box.setChecked(self.cfg.upload_to_drive)
        note = QLabel(
            "Optional. After you click Connect, the app can copy each exported PNG and PDF into "
            "GP Banners / <year> in your Shared Drive. Only the exported files are sent. The "
            "files are always saved on this computer first, and nothing is uploaded until you "
            "connect. Your sign-in is kept in Windows Credential Manager, not in the settings file."
        )
        note.setWordWrap(True)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(note)
        row = QHBoxLayout()
        row.addWidget(self.drive_status, 1)
        row.addWidget(self.drive_btn)
        lay.addLayout(row)
        lay.addWidget(self.copy_connect_btn)
        lay.addWidget(self.link_box)
        lay.addWidget(QLabel("GP Banners folder link"))
        lay.addWidget(self.folder_edit)
        lay.addWidget(self.folder_note)
        lay.addWidget(self.drive_box)
        lay.addStretch()
        self._paint_drive()
        return w

    def _paint_drive(self):
        on = bool(self.cfg.drive_email)
        self.drive_status.setText(f"Connected as {self.cfg.drive_email}" if on else "Not connected")
        self.drive_btn.setText("Disconnect" if on else "Connect Google Drive")
        self.drive_btn.setEnabled(self._task is None)
        self.copy_connect_btn.setVisible(not on)
        self.copy_connect_btn.setEnabled(self._task is None)
        self.drive_box.setEnabled(on)
        self.folder_edit.setEnabled(on)
        if not on:
            self.drive_box.setChecked(False)

    def _drive_toggle(self, open_browser: bool = True):
        if self.cfg.drive_email:  # disconnect (the saved sign-in is erased when Save is clicked)
            self.cfg.drive_email = ""
            self._disconnect_pending = True
            self._paint_drive()
            return
        self.drive_status.setText("Finish signing in in your browser…")
        self._auto_copy = not open_browser
        self.link_box.setVisible(False)
        self._run(lambda: drive.connect(open_browser=open_browser, on_url=self.linkReady.emit), self._connected)

    def _show_link(self, url: str):
        self.link_edit.setText(url)
        self.link_copy.setText("Copy link")
        if self._auto_copy:
            self._copy_link()
            self.link_note.setText(
                "The sign-in link is copied. Paste it into the browser where you are signed in to your "
                "Grow Pittsburgh Google account, then click Allow. Keep this window open.")
        else:
            self.link_note.setText(
                "A browser window should open. If it is the wrong browser, copy this link and paste it "
                "into the browser where you are signed in to your Grow Pittsburgh Google account.")
        self.link_box.setVisible(True)

    def _copy_link(self):
        QGuiApplication.clipboard().setText(self.link_edit.text())
        self.link_copy.setText("Copied")

    def _run(self, fn, ok):
        self._task = Task(fn)
        self._task.done.connect(ok)
        self._task.failed.connect(self._task_failed)
        self.drive_btn.setEnabled(False)
        self._task.start()

    def _task_failed(self, msg: str):
        self._task = None
        self.link_box.setVisible(False)
        self._paint_drive()
        self.folder_note.setText("")
        QMessageBox.warning(self, "Google Drive", msg)

    def _connected(self, result):
        self._task = None
        _creds, email = result
        self.link_box.setVisible(False)
        self.cfg.drive_email = email
        self._connected_here = True
        self._disconnect_pending = False
        self._paint_drive()
        self.drive_box.setChecked(True)  # connecting turns uploads on
        self._check_folder()

    def _check_folder(self):
        text = self.folder_edit.text().strip()
        if not text or not self.cfg.drive_email or self._task is not None:
            self.folder_note.setText("")
            return
        fid = drive.parse_folder_id(text)
        if fid is None:
            self.folder_note.setText("That does not look like a Google Drive folder link.")
            return
        self.folder_note.setText("Checking the folder…")

        def check():
            creds = drive.load_credentials()
            if creds is None:
                raise drive.DriveError("Not connected to Google Drive.")
            return drive.folder_name(drive.build_service(creds), fid)

        self._run(check, self._folder_ok)

    def _folder_ok(self, name: str):
        self._task = None
        self._paint_drive()
        self.folder_note.setText(f"✔ Found folder “{name}”.")

    def reject(self):
        if self._connected_here and not self._orig_email:
            drive.forget_token()  # undo a sign-in that was never saved
        super().reject()

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
        self.size_table = QTableWidget(0, 5)
        self.size_table.setHorizontalHeaderLabels(["Name", "Width (px)", "Height (px)", "PNG", "PDF"])
        self.size_table.horizontalHeader().setStretchLastSection(True)
        self.size_table.setColumnWidth(0, 200)
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
            "Files for extra sizes get the size added to their name, e.g. my-event-1080x1080.png. "
            "Every export writes all sizes below, each with only the file types ticked. "
            "At least one of PNG / PDF must stay ticked."
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
        png, pdf = QCheckBox(), QCheckBox()
        png.setChecked(s.png)
        pdf.setChecked(s.pdf)
        png.toggled.connect(lambda on, me=png, other=pdf: self._keep_one(on, me, other))
        pdf.toggled.connect(lambda on, me=pdf, other=png: self._keep_one(on, me, other))
        for col, box in ((3, png), (4, pdf)):
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setAlignment(Qt.AlignCenter)
            hl.addWidget(box)
            t.setCellWidget(i, col, holder)
        if edit:
            t.setCurrentCell(i, 0)
            t.editItem(t.item(i, 0))

    @staticmethod
    def _keep_one(on: bool, me: QCheckBox, other: QCheckBox):
        """Block unticking the last file type of a size."""
        if not on and not other.isChecked():
            me.setChecked(True)

    def _remove_size_row(self):
        for i in sorted({ix.row() for ix in self.size_table.selectedIndexes()}, reverse=True):
            self.size_table.removeRow(i)

    def collect_sizes(self) -> list[CanvasSize]:
        t = self.size_table
        def box(i: int, col: int) -> bool:
            return t.cellWidget(i, col).findChild(QCheckBox).isChecked()

        return [
            CanvasSize(t.item(i, 0).text().strip(), t.cellWidget(i, 1).value(),
                       t.cellWidget(i, 2).value(), box(i, 3), box(i, 4))
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
        if any(not (s.png or s.pdf) for s in sizes):
            return "Every size needs PNG or PDF ticked (or remove the row)."
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
        if drive.available() and self.cfg.drive_email:
            link = self.folder_edit.text().strip()
            fid = drive.parse_folder_id(link) if link else ""
            if fid is None:
                QMessageBox.warning(
                    self, "Check settings", "The GP Banners folder link does not look like a Google Drive folder link.")
                return
            if self.drive_box.isChecked() and not fid:
                QMessageBox.warning(
                    self, "Check settings",
                    "Paste the GP Banners folder link, or untick Upload to Drive after export.")
                return
            self.cfg.drive_folder_id = fid
            self.cfg.upload_to_drive = self.drive_box.isChecked()
        else:
            self.cfg.upload_to_drive = False
        if self._disconnect_pending:
            drive.forget_token()
        self.cfg.locations = locs
        self.cfg.sizes = sizes
        self.cfg.check_updates = self.updates_box.isChecked()
        self.cfg.other = Scheme("Other", self.other_btn.color, text_hex(self.other_text))
        self.accept()
