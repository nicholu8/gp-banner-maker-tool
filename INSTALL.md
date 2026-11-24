# Installing GP Banner Maker Tool (Windows)

For a step-by-step guide aimed at first-time users (making a banner, Google Drive setup, troubleshooting), see **[ABOUT.md](ABOUT.md)**.

1. Download the installer: **[GP-Banner-Maker-Tool-Setup.exe](https://github.com/nicholu8/gp-banner-maker-tool/releases/latest/download/GP-Banner-Maker-Tool-Setup.exe)**
   (this link always gives the newest version; older versions and notes are on the
   [Releases page](https://github.com/nicholu8/gp-banner-maker-tool/releases)).
2. Double-click the downloaded file.
3. Windows may show a blue **"Windows protected your PC"** screen. This is normal for small free apps that
   are not code-signed. Click **More info**, then **Run anyway**.
4. Click **Next** through the installer. It installs just for you and does not ask for an administrator password.
   Leave "Create a desktop shortcut" ticked if you want an icon on your desktop.
5. Click **Finish**. The app opens. Next time, use the desktop icon or the Start menu.

## Using it
Drop a photo on the window (or **Open photo…**), fill in the title, date, time, location and cost, and click
**Export**. The button says what it will write (for example "Export 4 files"). Every export writes all the sizes
listed in Settings (the standard 1880x940 and a 1080x1080 square to start), each as PNG, PDF or both. A green
message confirms the files were saved. Use **Settings…** to change location colors, add or remove banner sizes and
choose PNG/PDF per size.

## Saving to Google Drive (optional, Grow Pittsburgh staff)
1. **Settings… > Google Drive > Connect Google Drive**. Your browser opens; sign in with your Grow Pittsburgh
   Google account and click **Allow**. If your default browser is not the one signed in to that account, copy the
   sign-in link shown in the Settings window (**Copy link**) and paste it into the right browser, or click
   **Connect without opening a browser (copy link)** to skip the automatic window.
2. Paste the link to the **GP Banners** folder in the Shared Drive.
3. Leave **Upload to Drive after export** ticked. Each export is saved on your computer first, then copied to
   `GP Banners / <year>`. If a file with the same name is already there you choose Replace, Keep both or Skip.
   If the upload fails (for example offline), the files are still saved and a **Retry upload** button appears.
Nothing is sent to Google until you connect. **Disconnect** in the same tab removes the saved sign-in.

## Updating
When a new version is out, the app shows a yellow "Version X is available" note. Click its link, download the new
installer and run it; it replaces the old version and keeps your settings. (You can turn the check off in
**Settings… > General**.)

## Uninstalling
Windows **Settings > Apps > Installed apps > GP Banner Maker Tool > Uninstall**. Your saved settings and exported
banners are not deleted.

## Can't run installers?
Download the `.zip` (named `GP-Banner-Maker-Tool-Zip-<version>.zip`) from the [Releases page](https://github.com/nicholu8/gp-banner-maker-tool/releases/latest), unzip it anywhere, and double-click `GPBannerMaker.exe` inside the
folder. Keep the folder together; the exe needs the files next to it.
