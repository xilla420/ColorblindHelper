# -*- mode: python ; coding: utf-8 -*-
# Build:  python -m PyInstaller --noconfirm ColorblindHelper.spec
# Windows -> dist/ColorblindHelper.exe (single file)
# macOS   -> dist/ColorblindHelper.app
import re
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
VERSION = re.search(r'__version__ = "([^"]+)"',
                    (ROOT / "colorblind_helper" / "__init__.py").read_text()).group(1)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_WIN:
    hidden = ["pynput.keyboard._win32", "pynput.mouse._win32"]
elif IS_MAC:
    hidden = ["pynput.keyboard._darwin", "pynput.mouse._darwin"]
else:
    hidden = ["pynput.keyboard._xorg", "pynput.mouse._xorg"]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    hiddenimports=hidden,
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.QtWebEngineCore", "PySide6.QtMultimedia", "PySide6.QtPdf",
              "PySide6.QtOpenGL", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if IS_WIN:
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo,
                                                     StringStruct, StringTable, VarFileInfo,
                                                     VarStruct, VSVersionInfo)
    nums = tuple(int(x) for x in (VERSION.split(".") + ["0", "0", "0"])[:4])
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "xilla420"),
            StringStruct("FileDescription", "Colorblind Helper"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "ColorblindHelper"),
            StringStruct("OriginalFilename", "ColorblindHelper.exe"),
            StringStruct("ProductName", "Colorblind Helper"),
            StringStruct("ProductVersion", VERSION),
        ])]), VarFileInfo([VarStruct("Translation", [1033, 1200])])],
    )
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
              name="ColorblindHelper", console=False, upx=False,
              icon=str(ROOT / "assets" / "icon.ico"), version=version_info)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ColorblindHelper",
              console=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="ColorblindHelper", upx=False)
    if IS_MAC:
        app = BUNDLE(
            coll,
            name="ColorblindHelper.app",
            icon=str(ROOT / "assets" / "icon.png"),
            bundle_identifier="io.github.xilla420.colorblindhelper",
            version=VERSION,
            info_plist={
                "CFBundleDisplayName": "Colorblind Helper",
                "CFBundleShortVersionString": VERSION,
                "LSUIElement": True,  # menu-bar app: no Dock icon
                "NSHighResolutionCapable": True,
            },
        )
