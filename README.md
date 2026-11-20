# GP Banner Maker Tool

Drop in an event photo, type the details, pick a location, and export a branded banner image:
`<slug>.png` (1880 x 940) and `<slug>.pdf` (live, editable text for Canva).

## Install (for users)
See [INSTALL.md](INSTALL.md): download the Setup.exe from the Releases page and double-click it.

## Run from source
```
pip install -e ".[dev]"
python -m growbanner            # GUI (optionally: python -m growbanner path\to\photo.jpg)
gp-banner-batch events.csv <OUTPUT_FOLDER>   # CSV batch; columns: photo,title,date,time,location,cost[,size]
pytest                          # tests (golden images from reference/banner_reference.py)
```
Default output folder is `Documents\GrowPGH Banners` (**placeholder, change it in the app**; it is remembered).

## Build the installer
Needs Inno Setup 6 (`winget install JRSoftware.InnoSetup --scope user`). Then:
```
powershell -File packaging\build.ps1
```
Produces `dist\GPBannerMaker\` (the app), `dist-installer\GP-Banner-Maker-Tool-Setup-<version>.exe` and a `.zip`.
The version comes from `src/growbanner/__version__` (the single place to change it).

## Release (GitHub Actions)
Bump `__version__`, commit, then `git tag v<version>` and `git push origin v<version>`. The workflow in
`.github/workflows/release.yml` runs the tests, builds the installer and zip, and publishes a GitHub Release.
Pushes and pull requests to `main` only run the tests.

## Update check
On startup the app makes one anonymous request to GitHub for the latest release tag and shows a note if a newer
one exists (never installs anything). It sends no user data and fails silently offline. Turn it off in
Settings > General. Code: `src/growbanner/updates.py`.

## Settings (in the app: "Settings…" button)
- **Locations:** every location is a row with a banner color, black/white text, and optional extra match words.
  Add or remove rows at will. A new location starts with the default color (maroon) and you can change it.
  Typing an unlisted location in the main window shows a "Save to my locations" button. Unlisted locations use the
  "not in this list" color (maroon by default).
- **Sizes:** 1880 x 940 ("Standard") is built in. Add other sizes (name, width, height): the photo is cropped to the
  new shape and the whole banner (text, padding, corner) scales to fit. Files for extra sizes are named
  `<slug>-<width>x<height>.png/.pdf`; the standard size keeps `<slug>.png/.pdf`.
- Stored in `%LOCALAPPDATA%\GP Banner Maker Tool\config.json` (written on save/export; you can also edit it by hand). Settings from the earlier `GrowBanner` folder are picked up automatically.
  CSV batch accepts an optional `size` column holding a size name from Settings.

## Notes
- **Canva:** import the PDF; text is live and uses Bitter. Canva only has Bitter regular/bold, so the lighter
  info lines may look lighter until set to bold.
- Other sizes scale the banner by min(width/1880, height/940); text still auto-shrinks/wraps to fit the width.
- Where the original project plan and the reference script differ, the script wins. Differences: banner height has a
  16 px trim the plan omits; the auto-shrink test measures info lines in the bold title face (a reference quirk,
  kept so output matches); the dropdown prints "Garden Resource Center" for GRC (plan only gave "GRC").
- Fonts: Bitter 600/700 static instances cut from Google's variable font (SIL OFL, see `resources/fonts/OFL.txt`).
- Golden PNGs in `tests/golden` come from the reference script on synthetic photos; regenerate only deliberately
  with `python tests/make_golden.py`.
