# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

v1.0.0 is released (repo `nicholu8/gp-banner-maker-tool`, GitHub Actions builds the installer on a `v*` tag). v1.1.0 (in progress/released: check git tags) adds per-size PNG/PDF checkboxes, a default 1080x1080 size, export of all sizes at once, opt-in Google Drive upload (`drive.py`), and a versionless installer name (`GP-Banner-Maker-Tool-Setup.exe`) for a permanent download link. `reference/banner_reference.py` stays untouched. Product name is GP Banner Maker Tool; the Python package stays `growbanner`. The user has confirmed the PDF imports into Canva with editable text, and that HEIC photos work. See `README.md`. `PROJECT_PLAN.md`, `INSTALLER_PLAN.md`, `DRIVE_PLAN.md` and `PROJECT_NOTES.md` are local planning docs that are gitignored; they may be absent in a fresh clone.

## Commands

```
pip install -e ".[dev]"                  # editable install + dev tools
python -m growbanner [photo]             # run the GUI
pytest                                   # all tests
pytest tests/test_render.py::test_pdf_has_live_text_and_matches_png   # single test
python tests/make_golden.py              # regenerate goldens from the reference (deliberate only)
powershell -File packaging\build.ps1     # PyInstaller app + Inno Setup installer + zip (needs Inno Setup 6)
```
Offscreen GUI check: `QT_QPA_PLATFORM=offscreen` (text shows as boxes there; that is only the missing platform fonts).

## What the app is

A Windows-first desktop app that takes an event photo plus Title/Date/Time/Location/Cost and produces a Grow Pittsburgh branded image: photo cropped to 2:1 with a colored info banner in the lower-left. Every export writes the same base name as:
- PNG, 1880 x 940
- PDF with **live, editable text** (for Canva import). No SVG (Canva imports it as a flat graphic).

## Architecture

`src/growbanner/` with `layout.py` (measurement, wrap, shrink — no drawing), `render.py` (`render_png(spec) -> PIL.Image`), `pdf.py` (ReportLab), `schemes.py` (location → colors, tolerant matching), `sizes.py` (output sizes; layout scales from the 1880x940 default via `layout.scale_for`), `settings_dialog.py`, `config.py` (`config.json` in platformdirs app-data), `app.py` (PySide6). `render`/`layout`/`pdf` must not import any GUI code so they are testable headless and reusable for batch/CLI.

The reference script's PDF path (python-pptx → LibreOffice `soffice`) is to be **replaced** by ReportLab with bundled Bitter TTFs. Known reference gaps to fix: no EXIF transpose (use `ImageOps.exif_transpose`), hardcoded `/home/claude/fonts/...` paths (bundle fonts; resolve via `sys._MEIPASS` when frozen), `soffice` subprocess, and `--yoff` crop guessing (replace with preview + slider).

## Look is fixed by the reference script

Where `PROJECT_PLAN.md` and `reference/banner_reference.py` disagree, **the script wins** (note differences in the README). One known difference: the script's banner height is `pad_top + pad_bot + lines*title_lh + 2*info_lh - 8*S` (S=2, so −16 px), which the plan's geometry table omits. Other script details: the script works at 2x of a 940x470 template (1880x940); the info font is `title_size*29/34`; wrapping splits the title at the word boundary that minimizes the longer line; shrink loop steps down by S until it fits or reaches the minimum.

Brand colors (banner / text): Braddock `#8DC63F`/black, Shiloh `#FFC20E`/black, Garden Dreams `#F7941D`/black, GRC `#003510`/white, everything else (Virtual, Community Forge, GP Office, …) maroon `#981B1E`/white. Do not offer a white banner. Typeface is Bitter (title Bold 700, info lines SemiBold 600), full latin TTFs bundled with the app.

## Standing rules (from PROJECT_PLAN.md §10)

- Do not change colors, fonts, banner geometry, or banner position unless asked.
- No network calls, telemetry, or LLM/API calls, with TWO exceptions: (1) the opt-out update check in `updates.py` (anonymous GET of the latest GitHub release tag, no user data, silent on failure, never auto-installs); (2) the opt-in Google Drive upload in `drive.py` (nothing contacted until the user clicks Connect in Settings; sends only the exported PNG/PDF files to the one `GP Banners` Shared Drive folder; refresh token only in Windows Credential Manager via `keyring`, never in `config.json`).
- The Google OAuth client ID/secret never go in source. Locally: gitignored `src/growbanner/_google_client.py` or env vars `GP_GOOGLE_CLIENT_ID`/`GP_GOOGLE_CLIENT_SECRET`; CI writes the file from repo secrets `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`. Without a client the Drive tab is hidden.
- Use `pathlib` and `platformdirs`; no hardcoded absolute paths.
- Any value the user must supply (paths, username, repo name, output folder such as `Documents\GrowPGH Banners`) must be marked clearly as a placeholder; don't assume defaults.
- Run the test suite and visually inspect a rendered banner (and the rasterized PDF) before declaring any phase done. Golden PNGs come from `banner_reference.py`; regenerate them only with the user's approval.
- Commit in small steps; never force-push.
