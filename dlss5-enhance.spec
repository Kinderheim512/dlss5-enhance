# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: one file, console subsystem, GUI hides the console itself."""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("tkinterdnd2") + [("dlss5-enhance.ico", ".")]
binaries = collect_dynamic_libs("tkinterdnd2")

a = Analysis(
    ["dlss5_entry.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=["websocket", "tkinterdnd2"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy",
        "PIL",
        "matplotlib",
        "scipy",
        "pandas",
        "PyQt5",
        "PySide2",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DLSS5-Enhance",
    icon="dlss5-enhance.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
