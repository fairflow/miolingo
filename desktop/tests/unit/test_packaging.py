"""Structural + pure-logic tests for the macOS packaging tooling.

The actual PyInstaller build / signing must run on a Mac (and this sandbox can't
execute it), so these tests cover what IS checkable headlessly: the artifacts
exist, the build-step planner is correct, and the build module imports without
side effects.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

PACKAGING = Path(__file__).resolve().parents[1].parent / "packaging"


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "miolingo_build_macos", PACKAGING / "build_macos.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaging_files_exist() -> None:
    for name in (
        "build_macos.py",
        "miolingo.spec",
        "entitlements.plist",
        "fetch_piper_voices.py",
        "generate_voice_samples.py",
        "SIGNING.md",
    ):
        assert (PACKAGING / name).exists(), f"missing packaging/{name}"


def test_build_module_imports() -> None:
    module = _load_build_module()
    assert hasattr(module, "build_steps")
    assert hasattr(module, "main")


def test_build_steps_unsigned() -> None:
    module = _load_build_module()
    assert module.build_steps(sign=False, fetch_voices=False) == ["pyinstaller", "make_dmg"]


def test_build_steps_with_voices() -> None:
    module = _load_build_module()
    steps = module.build_steps(sign=False, fetch_voices=True)
    assert steps[0] == "fetch_voices"


def test_build_steps_signed() -> None:
    module = _load_build_module()
    steps = module.build_steps(sign=True, fetch_voices=False)
    assert steps[-3:] == ["codesign", "notarize", "staple"]


def test_entitlements_has_microphone() -> None:
    text = (PACKAGING / "entitlements.plist").read_text(encoding="utf-8")
    assert "com.apple.security.device.audio-input" in text


def test_spec_excludes_streamlit() -> None:
    text = (PACKAGING / "miolingo.spec").read_text(encoding="utf-8")
    assert "streamlit" in text  # in the excludes list
    assert "Miolingo.app" in text
