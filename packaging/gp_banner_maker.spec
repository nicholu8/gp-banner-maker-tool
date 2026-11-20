# Build from the repo root:  pyinstaller packaging/growbanner.spec --noconfirm
from pathlib import Path

root = Path(SPECPATH).parent
fonts = root / "src" / "growbanner" / "resources" / "fonts"

a = Analysis(
    [str(root / "packaging" / "run_growbanner.py")],
    pathex=[str(root / "src")],
    datas=[(str(fonts), "growbanner/resources/fonts")],
    hiddenimports=["pillow_heif"],
    excludes=["tkinter", "numpy", "yaml", "PySide6.QtNetwork", "PySide6.QtPdf", "PySide6.QtSvg", "PySide6.QtOpenGL", "PySide6.QtVirtualKeyboard", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts"],
)
# Drop Qt pieces a QtWidgets-only app never loads (software OpenGL, QML/Quick, PDF, translations).
_DROP = ("opengl32sw", "qt6quick", "qt6qml", "qt6pdf", "qt6virtualkeyboard", "qt6network",
         "qt6opengl", "qt6svg", "numpy", "translations")
def _keep(entry):
    name = entry[0].replace("\\", "/").lower()
    return not any(d in name for d in _DROP)
a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GPBannerMaker", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="GPBannerMaker")
