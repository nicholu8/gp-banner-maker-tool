# GP Banner Maker Tool

Drop in an event photo, type the details, pick a location, and export a branded banner image:
`<slug>.png` (1880 x 940) and `<slug>.pdf` (live, editable text for Canva), plus any extra sizes from Settings
(a 1080 x 1080 square to start), each as PNG, PDF or both. Optionally copies the files to a Google Drive folder.

## Install (for users)
See [INSTALL.md](INSTALL.md). Permanent download link: https://github.com/nicholu8/gp-banner-maker-tool/releases/latest/download/GP-Banner-Maker-Tool-Setup.exe

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
Produces `dist\GPBannerMaker\` (the app), `dist-installer\GP-Banner-Maker-Tool-Setup.exe` (versionless on purpose, so the
`releases/latest/download/` link never changes) and `GP-Banner-Maker-Tool-Zip-<version>.zip` (named to sort after the installer on the
release page). Google Drive upload needs a client ID/secret baked in at build time: see "Google Drive upload" below.
The version comes from `src/growbanner/__version__` (the single place to change it).

## Release (GitHub Actions)
Bump `__version__`, commit, then `git tag v<version>` and `git push origin v<version>`. The workflow in
`.github/workflows/release.yml` runs the tests, builds the installer and zip, and publishes a GitHub Release.
Pushes and pull requests to `main` only run the tests.

## Google Drive upload (optional)
Settings > Google Drive: **Connect Google Drive** (browser sign-in, OAuth Desktop client, Internal to the Grow Pittsburgh
Workspace), paste the **GP Banners** folder link, tick **Upload to Drive after export**. Exports are saved locally first, then
copied to `GP Banners / <year>` (year folder created if missing; Shared Drive supported). A same-named file prompts
Replace / Keep both / Skip; failures keep the local files and show **Retry upload**. Only the exported PNG/PDF files are sent,
and only after you connect. The refresh token lives in Windows Credential Manager (`keyring`), never in `config.json`.
Code: `src/growbanner/drive.py` (no GUI imports), wired in `app.py` and `settings_dialog.py`.

**Client ID/secret (build time, never in source):** a Google Cloud "Desktop app" OAuth client, scope
`https://www.googleapis.com/auth/drive`. Locally put them in the gitignored `src/growbanner/_google_client.py`
(`CLIENT_ID = ...`, `CLIENT_SECRET = ...`) or set env vars `GP_GOOGLE_CLIENT_ID` / `GP_GOOGLE_CLIENT_SECRET`. CI writes that file from
the repository secrets `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` before the build (tag builds fail without them). Without a
client the Drive tab is hidden and the app works as before. (A Desktop client secret is not confidential the way a server secret is;
Google expects installed apps to ship it. Access is still limited to your Workspace by the Internal consent screen.)

## Update check
The app's other network call is the update check: on startup it makes one anonymous request to GitHub for the latest release tag and shows a note if a newer
one exists (never installs anything). It sends no user data and fails silently offline. Turn it off in
Settings > General. Code: `src/growbanner/updates.py`.

## Settings (in the app: "Settings…" button)
- **Locations:** every location is a row with a banner color, black/white text, and optional extra match words.
  Add or remove rows at will. A new location starts with the default color (maroon) and you can change it.
  Typing an unlisted location in the main window shows a "Save to my locations" button. Unlisted locations use the
  "not in this list" color (maroon by default).
- **Sizes:** each size has PNG and PDF checkboxes (at least one stays on); every export writes all listed sizes. 1880 x 940 ("Standard") is built in and always exports both. A fresh install also lists a 1080 x 1080 "Square" (edit or remove it). Add other sizes (name, width, height): the photo is cropped to the
  new shape and the whole banner (text, padding, corner) scales to fit. Files for extra sizes are named
  `<slug>-<width>x<height>.png/.pdf`; the standard size keeps `<slug>.png/.pdf`.
- Stored in `%LOCALAPPDATA%\GP Banner Maker Tool\config.json` (written on save/export; you can also edit it by hand). Settings from the earlier `GrowBanner` folder are picked up automatically.
  CSV batch exports every size in Settings, or only the one named in an optional `size` column.

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
