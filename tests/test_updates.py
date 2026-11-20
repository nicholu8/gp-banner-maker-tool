import io
import json

import pytest

from growbanner import updates
from growbanner.config import load_config, save_config


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(payload):
    seen = {}

    def opener(req, timeout=None):
        seen["req"], seen["timeout"] = req, timeout
        return FakeResp(json.dumps(payload).encode())

    opener.seen = seen
    return opener


@pytest.mark.parametrize("tag,cur,expected", [
    ("v1.0.1", "1.0.0", True), ("1.1", "1.0.9", True), ("v2.0.0", "1.9.9", True),
    ("v1.0.0", "1.0.0", False), ("v1.0", "1.0.0", False), ("v0.9.0", "1.0.0", False),
    ("nightly", "1.0.0", False), ("v1.0.0-beta", "1.0.0", False),
])
def test_newer_than(tag, cur, expected):
    assert updates.newer_than(tag, cur) is expected


def test_newer_release_found_and_request_sends_nothing_personal():
    op = opener_for({"tag_name": "v1.2.0", "html_url": f"https://github.com/{updates.REPO}/releases/tag/v1.2.0"})
    info = updates.check_for_update("1.0.0", opener=op)
    assert info == updates.UpdateInfo("1.2.0", f"https://github.com/{updates.REPO}/releases/tag/v1.2.0")
    req = op.seen["req"]
    assert req.full_url == updates.API_URL and req.data is None  # plain GET, no body
    assert set(req.headers) <= {"User-agent", "Accept"} and op.seen["timeout"] == updates.TIMEOUT_S


def test_no_update_when_current():
    assert updates.check_for_update("1.2.0", opener=opener_for({"tag_name": "v1.2.0"})) is None


def test_foreign_link_is_replaced_with_releases_page():
    info = updates.check_for_update("1.0.0", opener=opener_for({"tag_name": "v9.0.0", "html_url": "https://evil.example/x"}))
    assert info.url == updates.RELEASES_URL


@pytest.mark.parametrize("failure", [OSError("offline"), ValueError("bad"), TimeoutError()])
def test_errors_are_silent(failure):
    def boom(req, timeout=None):
        raise failure
    assert updates.check_for_update("1.0.0", opener=boom) is None


def test_garbage_json_is_silent():
    assert updates.check_for_update("1.0.0", opener=lambda r, timeout=None: FakeResp(b"<html>")) is None


def test_update_setting_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    cfg = load_config(p)
    assert cfg.check_updates is True
    cfg.check_updates = False
    save_config(cfg, p)
    assert load_config(p).check_updates is False
