"""Optional Google Drive upload. No GUI imports.

The second network feature (after the update check). Opt-in: nothing is contacted until the
user clicks "Connect Google Drive" in Settings. Only the exported PNG/PDF files are sent, to
one folder in a Shared Drive. The sign-in uses OAuth 2.0 (Desktop app); the refresh token is
kept in Windows Credential Manager through ``keyring``, never in config.json.

Google libraries are imported lazily so the rest of the app starts (and tests run) without them.
"""
from __future__ import annotations

import enum
import mimetypes
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
KEYRING_SERVICE = "GP Banner Maker Tool"
KEYRING_USER = "google-drive-refresh-token"
FOLDER_MIME = "application/vnd.google-apps.folder"
_ID = re.compile(r"[A-Za-z0-9_-]{10,}")
_MIME = {".png": "image/png", ".pdf": "application/pdf"}


class DriveError(Exception):
    """A problem worth showing to the user as-is."""


class Collision(enum.Enum):
    REPLACE = "replace"
    KEEP_BOTH = "keep both"
    SKIP = "skip"


# ---------------------------------------------------------------- client id / secret
def client_config() -> dict | None:
    """OAuth client from env vars (GP_GOOGLE_CLIENT_ID/SECRET) or the build-time file; None if absent."""
    cid, secret = os.environ.get("GP_GOOGLE_CLIENT_ID"), os.environ.get("GP_GOOGLE_CLIENT_SECRET")
    if not (cid and secret):
        try:
            from . import _google_client as g  # gitignored; written by CI from secrets

            cid, secret = g.CLIENT_ID, g.CLIENT_SECRET
        except Exception:
            return None
    if not cid or not secret or "PLACEHOLDER" in cid + secret:
        return None
    return {"installed": {
        "client_id": cid, "client_secret": secret, "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": TOKEN_URI, "redirect_uris": ["http://localhost"],
    }}


def available() -> bool:
    """True if this build has a Google client configured (otherwise hide the Drive settings)."""
    return client_config() is not None


# ---------------------------------------------------------------- folder link
def parse_folder_id(text: str) -> str | None:
    """Folder ID from a Drive folder link (or a bare ID); None if it does not look like one."""
    t = text.strip()
    for pat in (r"/folders/([A-Za-z0-9_-]+)", r"[?&]id=([A-Za-z0-9_-]+)"):
        m = re.search(pat, t)
        if m:
            return m.group(1) if _ID.fullmatch(m.group(1)) else None
    return t if _ID.fullmatch(t) else None


# ---------------------------------------------------------------- token storage + sign in
def _keyring():
    try:
        import keyring

        return keyring
    except Exception as e:  # pragma: no cover
        raise DriveError(f"Windows Credential Manager is not available: {e}") from e


def saved_token() -> str | None:
    try:
        return _keyring().get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        return None


def forget_token() -> None:
    try:
        _keyring().delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass


def build_service(creds):
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=creds, cache_discovery=False)


class _UrlCallback:
    """Stands in for the library's prompt message: its ``format`` hands the sign-in URL to ``on_url``."""

    def __init__(self, on_url: Callable[[str], None]):
        self._on_url = on_url

    def format(self, url: str) -> str:
        self._on_url(url)
        return ""


SIGN_IN_TIMEOUT_S = 300


def connect(
    open_browser: bool = True, message: str = "", on_url: Callable[[str], None] | None = None,
) -> tuple[object, str]:
    """Browser sign-in. Saves the refresh token. Returns (credentials, signed-in email). Blocks.

    ``on_url(url)`` receives the sign-in link so the UI can show or copy it (for people whose
    default browser is not the one signed in to their Google account). ``open_browser=False``
    skips opening any browser. Gives up after 5 minutes."""
    cfg = client_config()
    if cfg is None:
        raise DriveError("This build has no Google client configured.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
    creds = flow.run_local_server(
        port=0, prompt="consent", open_browser=open_browser, timeout_seconds=SIGN_IN_TIMEOUT_S,
        authorization_prompt_message=_UrlCallback(on_url) if on_url else message,
        success_message="You can close this tab and return to GP Banner Maker Tool.",
    )
    if not creds.refresh_token:
        raise DriveError("Google did not return a refresh token. Try connecting again.")
    _keyring().set_password(KEYRING_SERVICE, KEYRING_USER, creds.refresh_token)
    return creds, signed_in_email(build_service(creds))


def load_credentials():
    """Credentials from the saved refresh token (refreshed silently), or None if not connected."""
    token, cfg = saved_token(), client_config()
    if not token or cfg is None:
        return None
    from google.oauth2.credentials import Credentials

    c = cfg["installed"]
    return Credentials(None, refresh_token=token, token_uri=TOKEN_URI,
                       client_id=c["client_id"], client_secret=c["client_secret"], scopes=SCOPES)


def signed_in_email(service) -> str:
    return service.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]


def folder_name(service, folder_id: str) -> str:
    """Name of the folder if it exists and is reachable; raises DriveError otherwise."""
    try:
        f = service.files().get(fileId=folder_id, fields="name,mimeType", supportsAllDrives=True).execute()
    except Exception as e:
        raise DriveError("Can't open that folder. Check the link and that you have access to the Shared Drive.") from e
    if f.get("mimeType") != FOLDER_MIME:
        raise DriveError("That link is not a folder.")
    return f["name"]


def friendly_error(e: Exception) -> str:
    """A short message a non-technical user can act on."""
    if isinstance(e, DriveError):
        return str(e)
    name = type(e).__name__
    if name == "RefreshError":
        return "Your Google sign-in expired or was revoked. Reconnect in Settings."
    if name == "WSGITimeoutError":
        return "Sign-in timed out. Click Connect and finish signing in within 5 minutes."
    if name == "HttpError":
        status = getattr(getattr(e, "resp", None), "status", "")
        reason = e._get_reason() if hasattr(e, "_get_reason") else str(e)
        if status in (401, 403):
            return f"Google denied access ({reason}). Check that you can edit the GP Banners folder."
        return f"Google Drive returned an error ({status}): {reason}"
    if isinstance(e, (OSError, TimeoutError)) or name in ("TransportError", "ServerNotFoundError"):
        return "Couldn't reach Google. Check your internet connection and try again."
    return f"{name}: {e}"


# ---------------------------------------------------------------- upload
class CollisionPolicy:
    """Wraps a prompt ``(name) -> (Collision, apply_to_rest)`` so "do this for the rest" sticks."""

    def __init__(self, prompt: Callable[[str], tuple[Collision, bool]]):
        self._prompt = prompt
        self.remembered: Collision | None = None

    def __call__(self, name: str) -> Collision:
        if self.remembered is not None:
            return self.remembered
        choice, rest = self._prompt(name)
        if rest:
            self.remembered = choice
        return choice


def _q(name: str) -> str:
    return name.replace("\\", "\\\\").replace("'", "\\'")


@dataclass
class UploadReport:
    uploaded: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    folder: str = ""

    @property
    def count(self) -> int:
        return len(self.uploaded) + len(self.replaced)

    def summary(self) -> str:
        bits = [f"Uploaded {self.count} file{'s' if self.count != 1 else ''} to Drive ({self.folder})"]
        if self.replaced:
            bits.append(f"{len(self.replaced)} replaced")
        if self.skipped:
            bits.append(f"{len(self.skipped)} skipped")
        return ", ".join(bits)


class DriveUploader:
    def __init__(self, service, root_folder_id: str):
        self.svc = service
        self.root = root_folder_id

    def _list(self, q: str) -> list[dict]:
        resp = self.svc.files().list(
            q=q, fields="files(id,name)", pageSize=100, supportsAllDrives=True,
            includeItemsFromAllDrives=True, corpora="allDrives",
        ).execute()
        return resp.get("files", [])

    def year_folder(self, year: int) -> str:
        """ID of ``<root>/<year>``, created if missing."""
        name = str(year)
        found = self._list(
            f"'{self.root}' in parents and name = '{name}' and mimeType = '{FOLDER_MIME}' and trashed = false")
        if found:
            return found[0]["id"]
        made = self.svc.files().create(
            body={"name": name, "mimeType": FOLDER_MIME, "parents": [self.root]},
            fields="id", supportsAllDrives=True,
        ).execute()
        return made["id"]

    def find_file(self, folder_id: str, name: str) -> str | None:
        found = self._list(
            f"'{folder_id}' in parents and name = '{_q(name)}' and mimeType != '{FOLDER_MIME}' and trashed = false")
        return found[0]["id"] if found else None

    def _free_name(self, folder_id: str, name: str) -> str:
        stem, suffix = Path(name).stem, Path(name).suffix
        n = 2
        while self.find_file(folder_id, f"{stem}-{n}{suffix}"):
            n += 1
        return f"{stem}-{n}{suffix}"

    def _media(self, path: Path):
        from googleapiclient.http import MediaFileUpload

        mime = _MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return MediaFileUpload(str(path), mimetype=mime, resumable=False)

    def upload(
        self, files: Sequence[Path], ask: Callable[[str], Collision] = lambda _name: Collision.KEEP_BOTH,
        year: int | None = None,
    ) -> UploadReport:
        """Upload into ``<root>/<year>/``. ``ask(name)`` is called only when a same-named file exists."""
        year = year or datetime.now().year
        report = UploadReport(folder=f"{year}")
        folder = self.year_folder(year)
        for path in map(Path, files):
            name, existing = path.name, self.find_file(folder, path.name)
            if existing:
                choice = ask(name)
                if choice is Collision.SKIP:
                    report.skipped.append(name)
                    continue
                if choice is Collision.REPLACE:
                    self.svc.files().update(
                        fileId=existing, media_body=self._media(path), supportsAllDrives=True).execute()
                    report.replaced.append(name)
                    continue
                name = self._free_name(folder, name)
            self.svc.files().create(
                body={"name": name, "parents": [folder]}, media_body=self._media(path),
                fields="id", supportsAllDrives=True,
            ).execute()
            report.uploaded.append(name)
        return report
