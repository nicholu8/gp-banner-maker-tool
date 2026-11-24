# Build the app folder, the installer, and the zip. Run from anywhere:  powershell -File packaging\build.ps1
# Output: dist\GPBannerMaker\ (app), dist-installer\GP-Banner-Maker-Tool-Setup.exe, dist-installer\GP-Banner-Maker-Tool-Zip-<ver>.zip
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = (python -c "import growbanner; print(growbanner.__version__)").Trim()
Write-Host "Building GP Banner Maker Tool $version"

Get-Process GPBannerMaker -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -Recurse -Force dist, build, dist-installer -ErrorAction SilentlyContinue

python -m PyInstaller packaging/gp_banner_maker.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
              "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
              "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw "Inno Setup (ISCC.exe) not found. Install Inno Setup 6 first." }

& $iscc "/DAppVersion=$version" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

Compress-Archive -Path dist\GPBannerMaker -DestinationPath "dist-installer\GP-Banner-Maker-Tool-Zip-$version.zip"
Get-ChildItem dist-installer | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
