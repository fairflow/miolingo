# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Miolingo macOS desktop app.

Bundles: the Python runtime, PySide6/Qt, the app package, the bundled
``language_materials/`` content, and the Piper voices in
``miolingo_desktop/resources/piper_voices/`` (fetched via
``packaging/fetch_piper_voices.py`` before building). ffmpeg should be placed in
``packaging/bin/`` before building so it is bundled too.

The Whisper ``medium`` model (~1.5 GB) is intentionally NOT bundled — it is
downloaded on first run and cached under ``~/.cache/whisper`` (SPEC §8). A small
``base`` model may be pre-cached by the build if present.

Build via ``python packaging/build_macos.py`` (which invokes PyInstaller with
this spec). Run directly with: ``pyinstaller packaging/miolingo.spec``.
"""

import os
from pathlib import Path

# Spec files are exec'd by PyInstaller; __file__ isn't defined, so derive paths
# from the current working directory (build_macos.py cd's into desktop/).
DESKTOP_DIR = Path(os.getcwd())
PKG_DIR = DESKTOP_DIR / "miolingo_desktop"
REPO_ROOT = DESKTOP_DIR.parent

datas = []

# Bundle the language materials (read at runtime via MIOLINGO_MATERIALS_DIR).
materials_dir = REPO_ROOT / "language_materials"
if materials_dir.is_dir():
    datas.append((str(materials_dir), "language_materials"))

# Bundle Piper voices if they've been fetched.
voices_dir = PKG_DIR / "resources" / "piper_voices"
if voices_dir.is_dir() and any(voices_dir.iterdir()):
    datas.append((str(voices_dir), "miolingo_desktop/resources/piper_voices"))

# Bundle a pre-cached small Whisper model if present (medium downloads on first run).
whisper_cache = DESKTOP_DIR / "packaging" / "whisper_models"
if whisper_cache.is_dir() and any(whisper_cache.iterdir()):
    datas.append((str(whisper_cache), "whisper_models"))

binaries = []
# Bundle ffmpeg if dropped into packaging/bin/.
ffmpeg = DESKTOP_DIR / "packaging" / "bin" / "ffmpeg"
if ffmpeg.exists():
    binaries.append((str(ffmpeg), "."))

hiddenimports = [
    "miolingo_desktop",
    "sounddevice",
    "soundfile",
]

a = Analysis(
    [str(PKG_DIR / "main.py")],
    pathex=[str(DESKTOP_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["streamlit", "tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Miolingo",
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,  # universal2 if the Python build supports it
    codesign_identity=os.environ.get("MIOLINGO_CODESIGN_IDENTITY"),
    entitlements_file=str(DESKTOP_DIR / "packaging" / "entitlements.plist"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Miolingo",
)

app = BUNDLE(
    coll,
    name="Miolingo.app",
    icon=None,
    bundle_identifier="co.fairflow.miolingo",
    info_plist={
        "NSMicrophoneUsageDescription": "Miolingo records your voice to score pronunciation.",
        "LSMinimumSystemVersion": "12.0",
        "CFBundleShortVersionString": "0.1.0",
    },
)
