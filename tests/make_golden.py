"""Regenerate golden PNGs from reference/banner_reference.py (PNG half only).

Run only deliberately, with the user's approval of any visual change:
    python tests/make_golden.py
The reference file itself is not modified: we exec the part before its PDF step
and point its hardcoded font path at the bundled fonts.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scenarios import GOLDEN, SCENARIOS, make_photo  # noqa: E402

ROOT = Path(__file__).parent.parent
FONTS = ROOT / "src" / "growbanner" / "resources" / "fonts"


def load_reference():
    src = (ROOT / "reference" / "banner_reference.py").read_text()
    ns: dict = {"__name__": "reference"}
    exec(src[: src.index("# ---- PDF twin")], ns)  # defines build() up to the PNG save
    ns["F"] = str(FONTS / "Bitter-%d.ttf")
    return ns["build"]


def main() -> None:
    GOLDEN.mkdir(exist_ok=True)
    build = load_reference()
    for name, (size, args) in SCENARIOS.items():
        photo = make_photo(name, size)
        build(str(photo), str(GOLDEN / f"{name}.png"), **args)
        print("wrote", name)


if __name__ == "__main__":
    main()
