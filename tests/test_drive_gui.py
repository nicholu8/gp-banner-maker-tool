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


def _dialog(qapp, monkeypatch, tmp_path):
    from growbanner.settings_dialog import SettingsDialog
    monkeypatch.setenv("GP_GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GP_GOOGLE_CLIENT_SECRET", "sec")
    return SettingsDialog(Config(check_updates=False))


def _wait(qapp, dlg):
    end = time.time() + 5
    while time.time() < end and dlg._task is not None:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()


def test_copy_link_connect_shows_and_copies_link_without_opening_browser(qapp, tmp_path, monkeypatch):
    seen = {}

    def fake_connect(open_browser=True, message="", on_url=None):
        seen["open_browser"] = open_browser
        on_url("https://accounts.google.com/o/oauth2/auth?x=1&y=2")
        time.sleep(0.2)  # still "waiting for the user" so the link box is visible
        return None, "a@b.org"

    monkeypatch.setattr(drive, "connect", fake_connect)
    dlg = _dialog(qapp, monkeypatch, tmp_path)
    dlg.copy_connect_btn.click()
    end = time.time() + 2
    while time.time() < end and not dlg.link_edit.text():
        qapp.processEvents()
        time.sleep(0.01)
    assert seen["open_browser"] is False
    assert dlg.link_edit.text() == "https://accounts.google.com/o/oauth2/auth?x=1&y=2"
    assert QApplication.clipboard().text() == dlg.link_edit.text()
    assert "copied" in dlg.link_note.text().lower()
    _wait(qapp, dlg)
    assert dlg.cfg.drive_email == "a@b.org" and dlg.drive_box.isChecked()


def test_normal_connect_opens_browser_and_still_offers_the_link(qapp, tmp_path, monkeypatch):
    seen = {}

    def fake_connect(open_browser=True, message="", on_url=None):
        seen["open_browser"] = open_browser
        on_url("https://example.test/auth")
        time.sleep(0.2)
        return None, "a@b.org"

    monkeypatch.setattr(drive, "connect", fake_connect)
    dlg = _dialog(qapp, monkeypatch, tmp_path)
    dlg.drive_btn.click()
    end = time.time() + 2
    while time.time() < end and not dlg.link_edit.text():
        qapp.processEvents()
        time.sleep(0.01)
    assert seen["open_browser"] is True and dlg.link_edit.text() == "https://example.test/auth"
    assert "wrong browser" in dlg.link_note.text()
    _wait(qapp, dlg)


def test_connect_hands_the_url_to_the_callback(monkeypatch):
    """drive.connect passes an object whose format() reports the URL (the library calls it with url=...)."""
    import google_auth_oauthlib.flow as flow
    got = []

    class FakeFlow:
        redirect_uri = None

        @classmethod
        def from_client_config(cls, cfg, scopes):
            return cls()

        def run_local_server(self, **kw):
            assert kw["open_browser"] is False and kw["timeout_seconds"] == drive.SIGN_IN_TIMEOUT_S
            assert kw["authorization_prompt_message"].format(url="https://u") == ""
            raise drive.DriveError("stop here")

    monkeypatch.setattr(flow, "InstalledAppFlow", FakeFlow)
    monkeypatch.setenv("GP_GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GP_GOOGLE_CLIENT_SECRET", "sec")
    with pytest.raises(drive.DriveError, match="stop here"):
        drive.connect(open_browser=False, on_url=got.append)
    assert got == ["https://u"]
