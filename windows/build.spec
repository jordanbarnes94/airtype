# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AirType
Run with: pyinstaller build.spec

To build a named variant, set AIRTYPE_VARIANT_NAME before running:
    set AIRTYPE_VARIANT_NAME=AirType-5ms && python -m PyInstaller build.spec
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

variant_name = os.environ.get("AIRTYPE_VARIANT_NAME", "AirType")

# Collect CustomTkinter data files (themes, etc.)
ctk_datas = collect_data_files('customtkinter')

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=ctk_datas + [
        ('airtype.ico', '.'),
        ('airtype_tray.png', '.'),
        ('config.json', '.'),
    ],
    hiddenimports=[
        'pystray._win32',
        'PIL._tkinter_finder',
        'pyperclip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name=variant_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='airtype.ico',
)
