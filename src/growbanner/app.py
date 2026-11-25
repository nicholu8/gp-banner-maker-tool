"""PySide6 desktop window. All drawing is delegated to render/pdf/export."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPainter, QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget,
)

import queue

from . import __version__, drive
from .config import Config, load_config, save_config
from .qtasks import Task
from .settings_dialog import SettingsDialog
from .sizes import CanvasSize
from .export import export_label, export_sizes
from .render import crop_to_canvas, draw_banner, build_layout, load_photo, render_png
from .schemes import match_scheme, new_rule
from .spec import BannerSpec
from .updates import UpdateInfo, check_for_update

PREVIEW_MAX_SIDE = 2400  # downscale early so the UI stays fast; export uses the full photo
PHOTO_FILTER = "Photos (*.jpg *.jpeg *.png *.heic *.heif *.webp *.bmp *.tif *.tiff)"


def pil_to_qimage(im: Image.Image) -> QImage:
    im = im.convert("RGB")
    return QImage(im.tobytes(), im.width, im.height, 3 * im.width, QImage.Format_RGB888).copy()


class UpdateChecker(QObject):
    """Runs the (optional) update check on a background thread; emits ``found`` on the UI thread."""

    found = Signal(str, str)  # version, url

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        info: UpdateInfo | None = check_for_update()
        if info:
            self.found.emit(info.version, info.url)


class Preview(QWidget):
    """2:1 preview; accepts dropped photos and vertical drag to move the crop band."""

    fileDropped = Signal(str)
    cropDragged = Signal(float)  # delta in crop_y units

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumSize(520, 260)
        self.image: QImage | None = None
        self.drag_enabled = False
        self.photo_aspect = 0.5  # photo height / width
        self.canvas_aspect = 2.0  # output width / height
        self._last_y: float | None = None

    def set_image(self, img: QImage | None):
        self.image = img
        self.update()

    def _target(self) -> QRectF:
        w, h = self.width(), self.height()
        a = self.canvas_aspect
        tw = min(w, h * a)
        return QRectF((w - tw) / 2, (h - tw / a) / 2, tw, tw / a)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#eeeeee"))
        r = self._target()
        if self.image:
            p.drawImage(r, self.image)
        else:
            p.setPen(QColor("#666666"))
            p.drawRect(r)
            p.drawText(r, Qt.AlignCenter, "Drop a photo here\nor click “Open photo…”")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.fileDropped.emit(u.toLocalFile())
                break

    def mousePressEvent(self, e):
        self._last_y = e.position().y() if self.drag_enabled else None

    def mouseMoveEvent(self, e):
        if self._last_y is None:
            return
        dy = e.position().y() - self._last_y
        self._last_y = e.position().y()
        band = 1 / self.canvas_aspect  # crop band height / photo width
        extra = (self.photo_aspect - band) / band * self._target().height()  # overflow, widget px
        if extra > 0:
            self.cropDragged.emit(-dy / extra)  # dragging the photo down reveals the top

    def mouseReleaseEvent(self, _):
        self._last_y = None


class CollisionDialog(QDialog):
    """Same-named file already in the Drive folder: Replace / Keep both / Skip."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("File already in Drive")
        self.choice = drive.Collision.SKIP
        lay = QVBoxLayout(self)
        msg = QLabel(f"“{name}” is already in the Drive folder.\nWhat should happen to the new file?")
        msg.setWordWrap(True)
        lay.addWidget(msg)
        self.rest = QCheckBox("Do this for the rest of this upload")
        lay.addWidget(self.rest)
        row = QHBoxLayout()
        for text, choice in (("Replace", drive.Collision.REPLACE), ("Keep both", drive.Collision.KEEP_BOTH),
                             ("Skip", drive.Collision.SKIP)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, c=choice: self._pick(c))
            row.addWidget(b)
        lay.addLayout(row)

    def _pick(self, choice):
        self.choice = choice
        self.accept()


class MainWindow(QWidget):
    collisionAsked = Signal(str)  # worker thread -> UI thread

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"GP Banner Maker Tool v{__version__}")
        self.cfg: Config = load_config()
        self.photo_path: Path | None = None
        self.full: Image.Image | None = None
        self.small: Image.Image | None = None
        self._crop_cache: tuple[tuple, Image.Image] | None = None
        self.last_export: list[Path] = []
        self._upload_task: Task | None = None
        self._answers: queue.Queue = queue.Queue()
        self._saved_msg = ""

        self.preview = Preview()
        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(0, 1000)
        self.slider.setValue(500)
        self.slider.setInvertedAppearance(True)
        self.slider.setToolTip("Which band of a tall photo is used (top → bottom)")

        self.title = QLineEdit()
        self.date = QLineEdit()
        self.time = QLineEdit()
        self.cost = QLineEdit()
        self.location = QComboBox()
        self.location.setEditable(True)
        self.location.addItems(self.cfg.presets)
        self.location.setCurrentText(self.cfg.last_location)
        self.size_combo = QComboBox()
        self.fill_sizes(self.cfg.last_size)
        self.add_loc_btn = QPushButton()
        self.add_loc_btn.setVisible(False)
        settings_btn = QPushButton("Settings…")
        self.update_label = QLabel()
        self.update_label.setOpenExternalLinks(True)
        self.update_label.setWordWrap(True)
        self.update_label.setStyleSheet("background:#fff3cd;color:#533f03;padding:6px;border-radius:4px")
        self.update_label.setVisible(False)
        self.nowrap = QCheckBox("Keep title on one line")
        self.swatch = QLabel()
        self.warnings = QLabel()
        self.warnings.setWordWrap(True)
        self.warnings.setStyleSheet("color:#9a5b00")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.set_status("")
        self.outdir = QLineEdit(self.cfg.output_dir)

        open_btn = QPushButton("Open photo…")
        browse = QPushButton("Browse…")
        self.export_btn = QPushButton()
        self.export_btn.setStyleSheet("font-weight:bold;padding:8px")
        self.folder_btn = QPushButton("Open folder")
        self.copy_btn = QPushButton("Copy PNG to clipboard")
        self.retry_btn = QPushButton("Retry upload to Drive")
        self.retry_btn.setVisible(False)

        form = QFormLayout()
        form.addRow("Preview size", self.size_combo)
        form.addRow("Title", self.title)
        form.addRow("Date", self.date)
        form.addRow("Time", self.time)
        form.addRow("Location", self.location)
        form.addRow("", self.swatch)
        form.addRow("", self.add_loc_btn)
        form.addRow("Cost", self.cost)
        form.addRow("", self.nowrap)
        out_row = QHBoxLayout()
        out_row.addWidget(self.outdir)
        out_row.addWidget(browse)

        side = QVBoxLayout()
        top = QHBoxLayout()
        top.addWidget(open_btn, 1)
        top.addWidget(settings_btn)
        side.addLayout(top)
        side.addWidget(self.update_label)
        side.addLayout(form)
        side.addWidget(self.warnings)
        side.addStretch()
        side.addWidget(QLabel("Output folder"))
        side.addLayout(out_row)
        side.addWidget(self.export_btn)
        row2 = QHBoxLayout()
        row2.addWidget(self.folder_btn)
        row2.addWidget(self.copy_btn)
        side.addLayout(row2)
        side.addWidget(self.retry_btn)
        side.addWidget(self.status)

        main = QHBoxLayout(self)
        main.addWidget(self.preview, 1)
        main.addWidget(self.slider)
        sw = QWidget()
        sw.setLayout(side)
        sw.setFixedWidth(340)
        main.addWidget(sw)

        open_btn.clicked.connect(self.choose_photo)
        browse.clicked.connect(self.choose_outdir)
        settings_btn.clicked.connect(self.open_settings)
        self.add_loc_btn.clicked.connect(self.add_location)
        self.size_combo.currentIndexChanged.connect(self.refresh)
        self.export_btn.clicked.connect(self.do_export)
        self.folder_btn.clicked.connect(self.open_folder)
        self.copy_btn.clicked.connect(self.copy_png)
        self.retry_btn.clicked.connect(self.start_upload)
        self.collisionAsked.connect(self.show_collision)
        self.preview.fileDropped.connect(self.load_photo_file)
        self.preview.cropDragged.connect(self.nudge_crop)
        self.slider.valueChanged.connect(self.refresh)
        for w in (self.title, self.date, self.time, self.cost):
            w.textChanged.connect(self.refresh)
        self.location.currentTextChanged.connect(self.refresh)
        self.nowrap.toggled.connect(self.refresh)
        self.refresh()
        self.update_export_label()
        self.updater = UpdateChecker()
        self.updater.found.connect(self.show_update)
        if self.cfg.check_updates:
            self.updater.start()

    def show_update(self, version: str, url: str):
        self.update_label.setText(
            f'Version {version} is available. <a href="{url}">Download it here</a>.')
        self.update_label.setVisible(True)

    def set_status(self, text: str, ok: bool = False):
        """Status line under the buttons; ``ok`` shows it as a green success banner."""
        self.status.setText(text)
        self.status.setStyleSheet(
            "background:#2e7d32;color:#fff;font-weight:bold;padding:8px;border-radius:4px"
            if ok else "padding:2px")
        self.status.setMinimumHeight(0)

    # ---- state ----
    def spec(self) -> BannerSpec:
        s = BannerSpec(
            title=self.title.text().strip(), date=self.date.text(), time=self.time.text(),
            location=self.location.currentText(), cost=self.cost.text(), photo_path=self.photo_path,
            crop_y=self.slider.value() / 1000, nowrap=self.nowrap.isChecked(),
            canvas=self.current_size().canvas,
        )
        s.scheme = match_scheme(s.location, self.cfg.locations, self.cfg.other)
        return s

    def current_size(self) -> CanvasSize:
        i = self.size_combo.currentIndex()
        sizes = self.cfg.all_sizes
        return sizes[i] if 0 <= i < len(sizes) else sizes[0]

    def fill_sizes(self, select: str):
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        for sz in self.cfg.all_sizes:
            self.size_combo.addItem(sz.label)
        self.size_combo.setCurrentIndex(
            next((i for i, sz in enumerate(self.cfg.all_sizes) if sz.name == select), 0))
        self.size_combo.blockSignals(False)

    def update_export_label(self):
        self.export_btn.setText(export_label(self.cfg.all_sizes))

    def fill_locations(self):
        text = self.location.currentText()
        self.location.blockSignals(True)
        self.location.clear()
        self.location.addItems(self.cfg.presets)
        self.location.setCurrentText(text)
        self.location.blockSignals(False)

    def open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.cfg = dlg.cfg
            if not self.cfg.check_updates:
                self.update_label.setVisible(False)
            self.fill_locations()
            self.fill_sizes(self.cfg.last_size)
            self.update_export_label()
            self._crop_cache = None
            self.save_settings()
            self.refresh()

    def add_location(self):
        name = self.location.currentText().strip()
        if name and not any(r.name.lower() == name.lower() for r in self.cfg.locations):
            self.cfg.locations.append(new_rule(name, self.cfg.other))
            self.fill_locations()
            self.save_settings()
            self.set_status(f"Added “{name}” (default color). Change it in Settings.")
            self.refresh()

    def choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open photo", "", PHOTO_FILTER)
        if path:
            self.load_photo_file(path)

    def load_photo_file(self, path: str):
        try:
            full = load_photo(path)
        except Exception as e:
            QMessageBox.warning(self, "Can't open photo", f"{Path(path).name}\n\n{e}")
            return
        self.photo_path, self.full = Path(path), full
        small = full.copy()
        small.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE))
        self.small = small
        self._crop_cache = None
        self.set_status(f"Loaded {Path(path).name} ({full.width}×{full.height})")
        self.refresh()

    def nudge_crop(self, delta: float):
        v = round(self.slider.value() + delta * 1000)
        self.slider.setValue(max(0, min(1000, v)))

    def choose_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.outdir.text())
        if d:
            self.outdir.setText(d)

    # ---- preview ----
    def refresh(self, *_):
        spec = self.spec()
        sch = spec.scheme
        txt = "#000" if sch.text.upper() == "#000000" else "#fff"
        self.swatch.setText(f"Banner color: {sch.name}")
        self.swatch.setStyleSheet(f"background:{sch.banner};color:{txt};padding:3px 6px")
        loc = spec.location.strip()
        listed = any(r.name.lower() == loc.lower() for r in self.cfg.locations)
        self.add_loc_btn.setVisible(bool(loc) and not listed)
        self.add_loc_btn.setText(f"Save “{loc}” to my locations")
        cw, ch = spec.canvas
        self.preview.canvas_aspect = cw / ch

        warn = []
        if self.small is None:
            self.preview.set_image(None)
            self.slider.setEnabled(False)
            self.preview.drag_enabled = False
        else:
            w, h = self.full.size
            tall = w * ch // cw < h
            self.slider.setEnabled(tall)
            self.preview.drag_enabled = tall
            self.preview.photo_aspect = h / w
            if not tall:
                warn.append("Photo is already the output shape or wider: the banner will cover part of it.")
            if w < cw:
                warn.append(f"Photo is narrower than {cw}px: it will look soft.")
            key = (spec.crop_y, spec.canvas)
            if self._crop_cache is None or self._crop_cache[0] != key:
                self._crop_cache = (key, crop_to_canvas(self.small, spec.crop_y, spec.canvas))
            img = draw_banner(self._crop_cache[1], build_layout(spec), sch)
            self.preview.set_image(pil_to_qimage(img))
        missing = [n for n, v in (("title", spec.title), ("date", spec.date.strip()), ("location", spec.location.strip())) if not v]
        if missing:
            warn.append("Missing: " + ", ".join(missing))
        self.warnings.setText("\n".join(warn))

    # ---- actions ----
    def do_export(self):
        if self.full is None:
            QMessageBox.information(self, "No photo", "Open or drop a photo first.")
            return
        try:
            results = export_sizes(self.spec(), self.cfg.all_sizes, self.outdir.text().strip(), self.full)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        files = [f for r in results for f in r.files]
        self.last_export = files
        self.last_title = self.spec().title
        self._saved_msg = (
            f"✔ Saved {files[0].name}" if len(files) == 1 else f"✔ Saved {len(files)} files, e.g. {files[0].name}")
        self.set_status(self._saved_msg, ok=True)
        self.retry_btn.setVisible(False)
        self.save_settings()
        if self.cfg.upload_to_drive:
            self.start_upload()

    # ---- google drive upload ----
    def start_upload(self):
        """Upload the last export's files. Local files are already saved; failures never lose them."""
        if self._upload_task is not None or not self.last_export:
            return
        files, folder_id = list(self.last_export), self.cfg.drive_folder_id
        event = getattr(self, "last_title", "")
        policy = drive.CollisionPolicy(self._ask_collision)

        def work():
            creds = drive.load_credentials()
            if creds is None:
                raise drive.DriveError("Google Drive is not connected. Reconnect in Settings.")
            if not folder_id:
                raise drive.DriveError("No GP Banners folder link is set. Add it in Settings.")
            return drive.DriveUploader(drive.build_service(creds), folder_id).upload(files, ask=policy, event=event)

        self.set_status(f"{self._saved_msg}\nUploading to Google Drive…")
        self.retry_btn.setVisible(False)
        self.export_btn.setEnabled(False)
        self._upload_task = Task(work)
        self._upload_task.done.connect(self.upload_done)
        self._upload_task.failed.connect(self.upload_failed)
        self._upload_task.start()

    def _ask_collision(self, name: str):
        """Runs on the worker thread: ask the UI thread and wait for the answer."""
        self.collisionAsked.emit(name)
        return self._answers.get()

    def show_collision(self, name: str):
        dlg = CollisionDialog(name, self)
        dlg.exec()
        self._answers.put((dlg.choice, dlg.rest.isChecked()))

    def upload_done(self, report):
        self._upload_task = None
        self.export_btn.setEnabled(True)
        self.set_status(f"{self._saved_msg}\n{report.summary()}", ok=True)

    def upload_failed(self, msg: str):
        self._upload_task = None
        self.export_btn.setEnabled(True)
        self.retry_btn.setVisible(True)
        self.set_status(f"{self._saved_msg}\nDrive upload failed: {msg}")

    def open_folder(self):
        d = Path(self.outdir.text().strip())
        if d.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))
        else:
            self.set_status("Output folder doesn't exist yet. Export once to create it.")

    def copy_png(self):
        if self.full is None:
            self.set_status("Open a photo first.")
            return
        QApplication.clipboard().setImage(pil_to_qimage(render_png(self.spec(), self.full)))
        self.set_status("✔ PNG copied to clipboard.", ok=True)

    def save_settings(self):
        self.cfg.last_location = self.location.currentText()
        self.cfg.last_size = self.current_size().name
        self.cfg.output_dir = self.outdir.text().strip() or self.cfg.output_dir
        try:
            save_config(self.cfg)
        except OSError:
            pass

    def closeEvent(self, e):
        self.save_settings()
        super().closeEvent(e)


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1180, 640)
    win.show()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        win.load_photo_file(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
