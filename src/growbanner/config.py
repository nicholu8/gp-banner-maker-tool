"""config.json in the user's app-data folder. Falls back to defaults on any problem."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_documents_dir

from .schemes import DEFAULT_RULES, OTHER, LocationRule, Scheme, new_rule
from .sizes import DEFAULT_EXTRA_SIZES, DEFAULT_SIZE, CanvasSize, valid_dimensions

APP_NAME = "GP Banner Maker Tool"
LEGACY_APP_NAME = "GrowBanner"  # pre-rename settings folder, read once if the new one is missing
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def config_path() -> Path:
    return Path(user_config_dir(APP_NAME, appauthor=False)) / "config.json"


def _legacy_config_path() -> Path:
    return Path(user_config_dir(LEGACY_APP_NAME, appauthor=False)) / "config.json"


def default_output_dir() -> str:
    # PLACEHOLDER default (confirm with the user): <Documents>/GrowPGH Banners
    return str(Path(user_documents_dir()) / "GrowPGH Banners")


@dataclass
class Config:
    locations: list[LocationRule] = field(default_factory=lambda: list(DEFAULT_RULES))
    other: Scheme = OTHER  # colors for locations that are not in the list
    sizes: list[CanvasSize] = field(default_factory=lambda: list(DEFAULT_EXTRA_SIZES))  # extra sizes; the default is built in
    last_location: str = ""
    last_size: str = DEFAULT_SIZE.name
    check_updates: bool = True
    output_dir: str = field(default_factory=default_output_dir)

    @property
    def presets(self) -> list[str]:
        return [r.name for r in self.locations]

    @property
    def all_sizes(self) -> list[CanvasSize]:
        return [DEFAULT_SIZE] + self.sizes

    def size_named(self, name: str) -> CanvasSize:
        return next((s for s in self.all_sizes if s.name == name), DEFAULT_SIZE)


def _hex(v: str) -> str:
    if not _HEX.match(v):
        raise ValueError(f"bad color {v!r}")
    return v.upper()


def _to_json(cfg: Config) -> dict:
    return {
        "locations": [
            {"name": r.name, "keywords": list(r.keywords), "banner": r.banner, "text": r.text}
            for r in cfg.locations
        ],
        "other": {"banner": cfg.other.banner, "text": cfg.other.text},
        "sizes": [
            {"name": s.name, "width": s.width, "height": s.height, "png": s.png, "pdf": s.pdf}
            for s in cfg.sizes
        ],
        "last_location": cfg.last_location,
        "last_size": cfg.last_size,
        "check_updates": cfg.check_updates,
        "output_dir": cfg.output_dir,
    }


def load_config(path: Path | None = None) -> Config:
    if path is None:
        path = config_path()
        if not path.exists() and _legacy_config_path().exists():
            path = _legacy_config_path()  # settings from before the rename
    cfg = Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return cfg
    except Exception:  # corrupt file: use defaults rather than crash
        return Config()
    try:
        if "other" in data:
            cfg.other = Scheme("Other", _hex(data["other"]["banner"]), _hex(data["other"]["text"]))
        locs = [
            LocationRule(d["name"], tuple(d.get("keywords", ())), _hex(d["banner"]), _hex(d["text"]))
            for d in data.get("locations", [])
            if str(d.get("name", "")).strip()
        ]
        # older configs kept plain presets separately; they become maroon rows
        known = {r.name.lower() for r in locs}
        locs += [new_rule(n, cfg.other) for n in data.get("extra_presets", []) if n.lower() not in known]
        if locs:
            cfg.locations = locs
        if "sizes" in data:  # a saved list (even an empty one) replaces the starting extras
            cfg.sizes = []
            for d in data["sizes"]:
                if not valid_dimensions(int(d["width"]), int(d["height"])):
                    continue
                png, pdf = bool(d.get("png", True)), bool(d.get("pdf", True))
                if not (png or pdf):  # at least one type must stay on
                    png = pdf = True
                cfg.sizes.append(CanvasSize(str(d["name"]), int(d["width"]), int(d["height"]), png, pdf))
        cfg.last_location = str(data.get("last_location", ""))
        cfg.last_size = str(data.get("last_size", cfg.last_size))
        cfg.check_updates = bool(data.get("check_updates", True))
        cfg.output_dir = str(data.get("output_dir") or cfg.output_dir)
    except Exception:
        return Config()
    return cfg


def save_config(cfg: Config, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_to_json(cfg), indent=2), encoding="utf-8")
