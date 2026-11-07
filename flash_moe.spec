# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ["chat.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        # I modelli GGUF e mmproj restano accanto all'exe, non inclusi qui
        # per dimensioni. Se vuoi includerli, decommenta:
        # ("*.gguf", "."),
        # ("*.mmproj", "."),
    ],
    hiddenimports=collect_submodules("flash_moe") + [
        "gguf",
        "openvino",
        "tokenizers",
        "PIL",
        "numpy",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="flash-moe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
