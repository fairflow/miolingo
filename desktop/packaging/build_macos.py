#!/usr/bin/env python3
"""Build the Miolingo macOS app bundle and .dmg.

Single-command build (run on macOS):

    python packaging/build_macos.py            # unsigned .app + .dmg
    python packaging/build_macos.py --sign     # sign + notarize (needs Apple ID)

Steps:
1. (optional) ensure Piper voices are fetched into resources/piper_voices/.
2. run PyInstaller against packaging/miolingo.spec -> dist/Miolingo.app.
3. build dist/Miolingo.dmg from the .app.
4. (optional, --sign) codesign with a Developer ID + notarize + staple.

Signing is gated on an Apple Developer ID. If absent, an UNSIGNED bundle is
produced and the exact signing steps are in packaging/SIGNING.md. Required env
for --sign: MIOLINGO_CODESIGN_IDENTITY, plus notarytool credentials
(MIOLINGO_NOTARY_PROFILE or AC_USERNAME/AC_PASSWORD/AC_TEAM_ID).

This script is build tooling — it shells out to pyinstaller/hdiutil/codesign and
must run on a Mac. The pure planning helpers (``build_steps``) are unit-tested.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parent.parent
SPEC = DESKTOP_DIR / "packaging" / "miolingo.spec"
DIST = DESKTOP_DIR / "dist"
APP = DIST / "Miolingo.app"
DMG = DIST / "Miolingo.dmg"


def run(cmd: list[str], **kwargs: object) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, **kwargs)  # type: ignore[arg-type]


def build_steps(*, sign: bool, fetch_voices: bool) -> list[str]:
    """Return the ordered list of step names for this build (pure; testable)."""
    steps = []
    if fetch_voices:
        steps.append("fetch_voices")
    steps += ["pyinstaller", "make_dmg"]
    if sign:
        steps += ["codesign", "notarize", "staple"]
    return steps


def fetch_voices() -> None:
    run([sys.executable, str(DESKTOP_DIR / "packaging" / "fetch_piper_voices.py")])


def run_pyinstaller() -> None:
    if shutil.which("pyinstaller") is None:
        raise SystemExit("pyinstaller not found — pip install pyinstaller")
    if DIST.exists():
        shutil.rmtree(DIST)
    run(["pyinstaller", "--noconfirm", str(SPEC)], cwd=str(DESKTOP_DIR))
    if not APP.exists():
        raise SystemExit(f"expected {APP} after PyInstaller build")


def make_dmg() -> None:
    if DMG.exists():
        DMG.unlink()
    run([
        "hdiutil", "create", "-volname", "Miolingo", "-srcfolder", str(APP),
        "-ov", "-format", "UDZO", str(DMG),
    ])


def codesign(identity: str) -> None:
    run([
        "codesign", "--deep", "--force", "--options", "runtime", "--timestamp",
        "--entitlements", str(DESKTOP_DIR / "packaging" / "entitlements.plist"),
        "--sign", identity, str(APP),
    ])


def notarize(profile: str) -> None:
    run([
        "xcrun", "notarytool", "submit", str(DMG),
        "--keychain-profile", profile, "--wait",
    ])


def staple() -> None:
    run(["xcrun", "stapler", "staple", str(APP)])


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(description="Build the Miolingo macOS app + .dmg")
    parser.add_argument("--sign", action="store_true", help="sign + notarize")
    parser.add_argument("--fetch-voices", action="store_true", help="fetch Piper voices first")
    args = parser.parse_args(argv)

    if sys.platform != "darwin":
        print("WARNING: macOS build should run on macOS; continuing anyway.", file=sys.stderr)

    for step in build_steps(sign=args.sign, fetch_voices=args.fetch_voices):
        if step == "fetch_voices":
            fetch_voices()
        elif step == "pyinstaller":
            run_pyinstaller()
        elif step == "make_dmg":
            make_dmg()
        elif step == "codesign":
            identity = os.environ.get("MIOLINGO_CODESIGN_IDENTITY")
            if not identity:
                print("No MIOLINGO_CODESIGN_IDENTITY — leaving the bundle UNSIGNED. "
                      "See packaging/SIGNING.md.", file=sys.stderr)
                break
            codesign(identity)
        elif step == "notarize":
            profile = os.environ.get("MIOLINGO_NOTARY_PROFILE")
            if not profile:
                print("No MIOLINGO_NOTARY_PROFILE — skipping notarization.", file=sys.stderr)
                break
            notarize(profile)
        elif step == "staple":
            staple()

    print(f"Done. Bundle: {APP}  DMG: {DMG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
