# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

APP_DIR = Path(SPECPATH) / "webview2-app"
REPO_DIR = Path(SPECPATH)

a = Analysis(
    [str(APP_DIR / "main.py")],
    pathex=[str(APP_DIR)],
    binaries=[],
    datas=[
        (str(APP_DIR / "ui"), "ui"),
        (str(REPO_DIR / "config.json"), "."),
    ],
    hiddenimports=[
        "webview",
        "webview.platforms.edgechromium",
        "clr",
        "pyautogui",
        "pygetwindow",
        "pyscreeze",
        "pymsgbox",
        "pytweening",
        "pyrect",
        "mouseinfo",
        "pyperclip",
        "tkinter",
        "tkinter.filedialog",
        "queue",
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
    name="ClaudeOllamaLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(REPO_DIR / "comment.ico"),
)
