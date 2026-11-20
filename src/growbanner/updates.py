"""Optional update check against the public GitHub Releases API. No GUI imports.

The ONLY network call in the app. It sends no user data (no photos, text, or ids):
one anonymous GET for the latest release tag. Any failure (offline, blocked, 404,
bad JSON) is silent. Turn it off with ``check_updates`` in config / Settings.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

from . import __version__

REPO = "nicholu8/gp-banner-maker-tool"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"
TIMEOUT_S = 5


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str


def parse_version(tag: str) -> tuple[int, ...] | None:
    m = re.fullmatch(r"v?(\d+(?:\.\d+)*)", tag.strip())
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def newer_than(tag: str, current: str = __version__) -> bool:
    a, b = parse_version(tag), parse_version(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def check_for_update(current: str = __version__, opener=urllib.request.urlopen) -> UpdateInfo | None:
    """Return UpdateInfo if a newer release exists, else None (also on any error)."""
    try:
        req = urllib.request.Request(
            API_URL,
            headers={"User-Agent": "GP-Banner-Maker-Tool", "Accept": "application/vnd.github+json"},
        )
        with opener(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data["tag_name"])
        if not newer_than(tag, current):
            return None
        url = str(data.get("html_url", ""))
        if not url.startswith(f"https://github.com/{REPO}/"):
            url = RELEASES_URL  # never open a link the response made up
        return UpdateInfo(tag.lstrip("v"), url)
    except Exception:
        return None
