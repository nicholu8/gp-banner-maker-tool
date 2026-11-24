"""Drive upload logic against a fake Drive service (no network, no Google sign-in)."""
import itertools
import json
import re

import pytest

pytest.importorskip("googleapiclient")

from growbanner import drive
from growbanner.config import Config, load_config, save_config
from growbanner.drive import Collision, CollisionPolicy, DriveUploader, parse_folder_id

ROOT = "ROOTFOLDERID1234"


class _Call:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class FakeDrive:
    """Just enough of drive.v3 files(): list / create / update / get, with the queries drive.py builds."""

    def __init__(self):
        self.files_by_id = {ROOT: {"name": "GP Banners", "parents": [], "mime": drive.FOLDER_MIME, "data": None}}
        self.ids = itertools.count(1)
        self.calls = []

    def files(self):
        return self

    def _add(self, name, parents, mime, data=None):
        fid = f"id{next(self.ids):012d}"
        self.files_by_id[fid] = {"name": name, "parents": parents, "mime": mime, "data": data}
        return fid

    def list(self, q, **kw):
        assert kw.get("supportsAllDrives") and kw.get("includeItemsFromAllDrives")
        parent = re.search(r"'([^']+)' in parents", q).group(1)
        name = re.search(r"name = '((?:[^'\\]|\\.)*)'", q).group(1).replace("\\'", "'").replace("\\\\", "\\")
        want_folder = "mimeType = '" in q
        out = [
            {"id": i, "name": f["name"]} for i, f in self.files_by_id.items()
            if parent in f["parents"] and f["name"] == name and (f["mime"] == drive.FOLDER_MIME) == want_folder
        ]
        return _Call(lambda: {"files": out})

    def create(self, body, media_body=None, **kw):
        assert kw.get("supportsAllDrives")
        self.calls.append(("create", body["name"]))
        data = media_body.getbytes(0, media_body.size()) if media_body else None
        mime = body.get("mimeType") or (media_body.mimetype() if media_body else "")
        return _Call(lambda: {"id": self._add(body["name"], body["parents"], mime, data)})

    def update(self, fileId, media_body, **kw):
        assert kw.get("supportsAllDrives")
        self.calls.append(("update", self.files_by_id[fileId]["name"]))

        def run():
            self.files_by_id[fileId]["data"] = media_body.getbytes(0, media_body.size())
            return {"id": fileId}

        return _Call(run)

    def get(self, fileId, **kw):
        def run():
            if fileId not in self.files_by_id:
                raise RuntimeError("404")
            f = self.files_by_id[fileId]
            return {"name": f["name"], "mimeType": f["mime"]}

        return _Call(run)

    def names_in(self, folder_id):
        return sorted(f["name"] for f in self.files_by_id.values() if folder_id in f["parents"])


def make_files(tmp_path, *names):
    out = []
    for n in names:
        p = tmp_path / n
        p.write_bytes(n.encode())
        out.append(p)
    return out


# ---- link parsing
@pytest.mark.parametrize("text,expected", [
    ("https://drive.google.com/drive/folders/1A0EaYziH8BefESjvs8UBtubq69mBqsiJ?usp=drive_link", "1A0EaYziH8BefESjvs8UBtubq69mBqsiJ"),
    ("https://drive.google.com/drive/u/1/folders/1A0EaYziH8BefESjvs8UBtubq69mBqsiJ", "1A0EaYziH8BefESjvs8UBtubq69mBqsiJ"),
    ("https://drive.google.com/open?id=1A0EaYziH8BefESjvs8UBtubq69mBqsiJ", "1A0EaYziH8BefESjvs8UBtubq69mBqsiJ"),
    ("  1A0EaYziH8BefESjvs8UBtubq69mBqsiJ  ", "1A0EaYziH8BefESjvs8UBtubq69mBqsiJ"),
    ("", None), ("not a link", None), ("https://example.com/folders/", None),
])
def test_parse_folder_id(text, expected):
    assert parse_folder_id(text) == expected


# ---- year folder
def test_year_folder_created_once_then_reused():
    fake = FakeDrive()
    up = DriveUploader(fake, ROOT)
    a = up.year_folder(2026)
    assert fake.files_by_id[a]["name"] == "2026" and fake.files_by_id[a]["parents"] == [ROOT]
    assert up.year_folder(2026) == a
    assert up.year_folder(2027) != a
    assert fake.names_in(ROOT) == ["2026", "2027"]


def test_upload_goes_into_year_folder_with_mime_types(tmp_path):
    fake = FakeDrive()
    files = make_files(tmp_path, "plant-sale.png", "plant-sale.pdf")
    rep = DriveUploader(fake, ROOT).upload(files, year=2026)
    year = DriveUploader(fake, ROOT).year_folder(2026)
    assert fake.names_in(year) == ["plant-sale.pdf", "plant-sale.png"]
    mimes = {f["name"]: f["mime"] for f in fake.files_by_id.values() if year in f["parents"]}
    assert mimes == {"plant-sale.png": "image/png", "plant-sale.pdf": "application/pdf"}
    assert rep.count == 2 and "Uploaded 2 files" in rep.summary()


def test_year_defaults_to_current_year(tmp_path):
    from datetime import datetime
    fake = FakeDrive()
    DriveUploader(fake, ROOT).upload(make_files(tmp_path, "a.png"))
    assert str(datetime.now().year) in fake.names_in(ROOT)


# ---- collisions
def seeded(tmp_path):
    fake = FakeDrive()
    up = DriveUploader(fake, ROOT)
    up.upload(make_files(tmp_path, "plant-sale.png"), year=2026)
    fake.calls.clear()
    (tmp_path / "plant-sale.png").write_bytes(b"new version")
    return fake, up


def test_no_prompt_when_no_collision(tmp_path):
    fake = FakeDrive()
    asked = []
    DriveUploader(fake, ROOT).upload(make_files(tmp_path, "a.png"), ask=lambda n: asked.append(n), year=2026)
    assert asked == []


def test_collision_replace_updates_in_place(tmp_path):
    fake, up = seeded(tmp_path)
    rep = up.upload([tmp_path / "plant-sale.png"], ask=lambda n: Collision.REPLACE, year=2026)
    year = up.year_folder(2026)
    assert fake.names_in(year) == ["plant-sale.png"]
    assert [f["data"] for f in fake.files_by_id.values() if year in f["parents"]] == [b"new version"]
    assert rep.replaced == ["plant-sale.png"] and fake.calls == [("update", "plant-sale.png")]


def test_collision_keep_both_uses_next_free_suffix(tmp_path):
    fake, up = seeded(tmp_path)
    up.upload([tmp_path / "plant-sale.png"], ask=lambda n: Collision.KEEP_BOTH, year=2026)
    up.upload([tmp_path / "plant-sale.png"], ask=lambda n: Collision.KEEP_BOTH, year=2026)
    assert fake.names_in(up.year_folder(2026)) == ["plant-sale-2.png", "plant-sale-3.png", "plant-sale.png"]


def test_collision_skip_uploads_nothing(tmp_path):
    fake, up = seeded(tmp_path)
    rep = up.upload([tmp_path / "plant-sale.png"], ask=lambda n: Collision.SKIP, year=2026)
    assert fake.calls == [] and rep.skipped == ["plant-sale.png"] and rep.count == 0


def test_do_this_for_the_rest_asks_once(tmp_path):
    fake = FakeDrive()
    up = DriveUploader(fake, ROOT)
    files = make_files(tmp_path, "a.png", "a.pdf", "b.png")
    up.upload(files, year=2026)
    fake.calls.clear()
    prompts = []

    def prompt(name):
        prompts.append(name)
        return Collision.SKIP, True

    rep = up.upload(files, ask=CollisionPolicy(prompt), year=2026)
    assert prompts == ["a.png"] and len(rep.skipped) == 3 and fake.calls == []


def test_policy_without_rest_asks_each_time():
    answers = iter([(Collision.REPLACE, False), (Collision.SKIP, False)])
    pol = CollisionPolicy(lambda n: next(answers))
    assert (pol("a"), pol("b")) == (Collision.REPLACE, Collision.SKIP)


def test_apostrophe_in_name_is_escaped(tmp_path):
    fake = FakeDrive()
    up = DriveUploader(fake, ROOT)
    f = make_files(tmp_path, "farmer's-market.png")
    up.upload(f, year=2026)
    asked = []
    up.upload(f, ask=lambda n: asked.append(n) or Collision.SKIP, year=2026)
    assert asked == ["farmer's-market.png"]


# ---- folder check
def test_folder_name_checks_existence_and_type():
    fake = FakeDrive()
    assert drive.folder_name(fake, ROOT) == "GP Banners"
    with pytest.raises(drive.DriveError):
        drive.folder_name(fake, "missing-folder-id")
    fid = fake._add("x.png", [ROOT], "image/png")
    with pytest.raises(drive.DriveError, match="not a folder"):
        drive.folder_name(fake, fid)


# ---- config + credentials
def test_drive_settings_roundtrip_and_token_never_in_config(tmp_path):
    p = tmp_path / "c.json"
    cfg = Config(drive_email="a@b.org", drive_folder_id=ROOT, upload_to_drive=True)
    save_config(cfg, p)
    text = p.read_text()
    assert "token" not in text.lower() and "secret" not in text.lower()
    back = load_config(p)
    assert (back.drive_email, back.drive_folder_id, back.upload_to_drive) == ("a@b.org", ROOT, True)


def test_upload_flag_needs_a_connected_account(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"upload_to_drive": True, "drive_email": ""}))
    assert load_config(p).upload_to_drive is False


def test_defaults_are_off():
    c = Config()
    assert not c.upload_to_drive and not c.drive_email and not c.drive_folder_id


def test_client_config_from_env(monkeypatch):
    monkeypatch.setenv("GP_GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GP_GOOGLE_CLIENT_SECRET", "sec")
    c = drive.client_config()["installed"]
    assert (c["client_id"], c["client_secret"]) == ("cid", "sec")


def test_no_credentials_when_not_connected(monkeypatch):
    monkeypatch.setattr(drive, "saved_token", lambda: None)
    assert drive.load_credentials() is None
