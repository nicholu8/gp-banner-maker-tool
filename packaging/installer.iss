; Inno Setup script for GP Banner Maker Tool.
; Build:  ISCC.exe /DAppVersion=1.0.0 packaging\installer.iss   (see packaging\build.ps1)
; Expects the PyInstaller output in dist\GPBannerMaker\.

#define AppName "GP Banner Maker Tool"
#define AppExe "GPBannerMaker.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Fixed ID: lets a newer installer upgrade an older install in place. Never change it.
AppId={{6F2B1D7E-3C58-4E0A-9B8D-4A7C1E52D9F3}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=nicholu8
AppPublisherURL=https://github.com/nicholu8/gp-banner-maker-tool
AppSupportURL=https://github.com/nicholu8/gp-banner-maker-tool/issues
AppUpdatesURL=https://github.com/nicholu8/gp-banner-maker-tool/releases
; Per-user install: no admin prompt (goes under %LOCALAPPDATA%\Programs).
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist-installer
OutputBaseFilename=GP-Banner-Maker-Tool-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
RestartApplications=no
LicenseFile=..\LICENSE
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} installer

[Tasks]
; Checked by default (no "unchecked" flag).
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\GPBannerMaker\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\src\growbanner\resources\fonts\OFL.txt"; DestDir: "{app}"; DestName: "Bitter-OFL.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; Uninstall removes the app only. The user's settings (%LOCALAPPDATA%\GP Banner Maker Tool)
; and exported banners are left alone.
