"""CSV batch mode: columns photo,title,date,time,location,cost (optional: size). No GUI imports."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .config import load_config
from .export import export_sizes
from .schemes import match_scheme
from .spec import BannerSpec


def run_batch(csv_path: Path, out_dir: Path) -> list[str]:
    cfg = load_config()
    summary = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            try:
                photo = Path(row["photo"])
                if not photo.is_absolute():
                    photo = csv_path.parent / photo
                spec = BannerSpec(
                    title=row.get("title", ""), date=row.get("date", ""), time=row.get("time", ""),
                    location=row.get("location", ""), cost=row.get("cost", ""), photo_path=photo,
                )
                spec.scheme = match_scheme(spec.location, cfg.locations, cfg.other)
                # optional column: one size name from Settings; otherwise every size in Settings
                sizes = [cfg.size_named(row["size"])] if row.get("size") else cfg.all_sizes
                results = export_sizes(spec, sizes, out_dir)
                names = ", ".join(f.name for r in results for f in r.files)
                summary.append(f"row {i}: {names}  [{spec.scheme.name} {spec.scheme.banner}]")
            except Exception as e:
                summary.append(f"row {i}: FAILED ({e})")
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Generate banners from a CSV.")
    p.add_argument("csv", type=Path)
    p.add_argument("out_dir", type=Path, help="output folder (placeholder: choose your own)")
    a = p.parse_args()
    print("\n".join(run_batch(a.csv, a.out_dir)))


if __name__ == "__main__":
    main()
