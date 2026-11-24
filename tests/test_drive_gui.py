"""Export -> Drive upload wiring in the main window (fake uploader, offscreen Qt)."""
import os
import time

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("googleapiclient")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from growbanner import config, drive
from growbanner.config import Config, save_config
from scenarios import SCENARIOS, make_photo


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeUploader:
    instances = []
    fail = None

    def __init__(self, service, folder_id):
        self.folder_id, self.uploads = folder_id, []
        FakeUploader.instances.append(self)

    def upload(self, files, ask=None, year=None):
        if FakeUploader.fail:
            raise FakeUploader.fail
        self.uploads.append([f.name for f in files])
        rep = drive.UploadReport(folder="2026")
        rep.uploaded = [f.name for f in files]
        return rep


def make_window(qapp, tmp_path, monkeypatch, *, upload, email="a@b.org", token=True):
    cfg_file = tmp_path / "c.json"
    monkeypatch.setattr(config, "config_path", lambda: cfg_file)
    save_config(Config(check_updates=False, output_dir=str(tmp_path / "out"), drive_email=email,
                       drive_folder_id="FOLDERID123456", upload_to_drive=upload), cfg_file)
    monkeypatch.setattr(drive, "load_credentials", lambda: object() if token else None)
    monkeypatch.setattr(drive, "build_service", lambda creds: object())
    monkeypatch.setattr(drive, "DriveUploader", FakeUploader)
    FakeUploader.instances.clear()
    FakeUploader.fail = None
    from growbanner.app import MainWindow
    win = MainWindow()
    win.load_photo_file(str(make_photo("braddock_landscape", SCENARIOS["braddock_landscape"][0])))
    win.title.setText("Plant Sale")
    win.location.setCurrentText("Braddock")
    return win


def wait_upload(qapp, win):
    end = time.time() + 10
    while time.time() < end and (win._upload_task is not None):
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()
    assert win._upload_task is None, "upload did not finish"


def test_nothing_uploaded_when_box_unchecked(qapp, tmp_path, monkeypatch):
    win = make_window(qapp, tmp_path, monkeypatch, upload=False)
    win.do_export()
    assert win._upload_task is None and FakeUploader.instances == []
    assert len(list((tmp_path / "out").iterdir())) == 4  # Standard + Square, PNG + PDF


def test_export_then_upload_sends_every_saved_file(qapp, tmp_path, monkeypatch):
    win = make_window(qapp, tmp_path, monkeypatch, upload=True)
    win.do_export()
    wait_upload(qapp, win)
    (up,) = FakeUploader.instances
    assert up.folder_id == "FOLDERID123456"
    assert sorted(up.uploads[0]) == sorted(p.name for p in (tmp_path / "out").iterdir())
    assert "Uploaded 4 files" in win.status.text() and not win.retry_btn.isVisibleTo(win)


def test_failure_keeps_local_files_and_offers_retry(qapp, tmp_path, monkeypatch):
    win = make_window(qapp, tmp_path, monkeypatch, upload=True)
    FakeUploader.fail = OSError("offline")
    win.do_export()
    wait_upload(qapp, win)
    assert len(list((tmp_path / "out").iterdir())) == 4
    assert win.retry_btn.isVisibleTo(win) and "upload failed" in win.status.text()
    assert "internet" in win.status.text() and win.export_btn.isEnabled()
    FakeUploader.fail = None
    win.retry_btn.click()
    wait_upload(qapp, win)
    assert len(FakeUploader.instances[-1].uploads[0]) == 4  # the same last export
    assert not win.retry_btn.isVisibleTo(win)


def test_lost_sign_in_gives_reconnect_message(qapp, tmp_path, monkeypatch):
    win = make_window(qapp, tmp_path, monkeypatch, upload=True, token=False)
    win.do_export()
    wait_upload(qapp, win)
    assert "Reconnect in Settings" in win.status.text() and win.retry_btn.isVisibleTo(win)
    assert FakeUploader.instances == []


def test_friendly_errors():
    assert "internet" in drive.friendly_error(ConnectionError("x"))
    assert drive.friendly_error(drive.DriveError("plain")) == "plain"
