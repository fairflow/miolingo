# Signing & Notarizing the Miolingo macOS build

The build (`python packaging/build_macos.py`) produces an **unsigned**
`Miolingo.app` + `Miolingo.dmg` by default. To distribute without Gatekeeper
warnings you must sign with an Apple **Developer ID Application** certificate and
notarize. This is gated on an Apple Developer account (see `QUESTIONS.md`).

## Prerequisites

- Apple Developer Program membership.
- A **Developer ID Application** certificate in your login keychain
  (Xcode → Settings → Accounts → Manage Certificates, or download from the
  developer portal).
- `xcrun notarytool` (ships with Xcode command-line tools).

## One-time: store notarization credentials

```bash
xcrun notarytool store-credentials MIOLINGO_NOTARY \
  --apple-id "you@example.com" \
  --team-id "YOURTEAMID" \
  --password "app-specific-password"   # from appleid.apple.com
```

## Build, sign, notarize, staple

```bash
export MIOLINGO_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export MIOLINGO_NOTARY_PROFILE="MIOLINGO_NOTARY"

python packaging/fetch_piper_voices.py          # bundle voices
python packaging/build_macos.py --sign --fetch-voices
```

`build_macos.py --sign` runs, in order:
1. `pyinstaller packaging/miolingo.spec` → `dist/Miolingo.app`
2. `hdiutil create … Miolingo.dmg`
3. `codesign --deep --options runtime --timestamp --entitlements packaging/entitlements.plist --sign "$MIOLINGO_CODESIGN_IDENTITY" Miolingo.app`
4. `xcrun notarytool submit Miolingo.dmg --keychain-profile "$MIOLINGO_NOTARY_PROFILE" --wait`
5. `xcrun stapler staple Miolingo.app`

If `MIOLINGO_CODESIGN_IDENTITY` is unset, the script stops after step 2 and
leaves an **unsigned** bundle (still runnable locally; users must right-click →
Open the first time).

## Hardened runtime entitlements

`packaging/entitlements.plist` grants:
- `com.apple.security.device.audio-input` — microphone (recording).
- `com.apple.security.cs.allow-jit` / `allow-unsigned-executable-memory` /
  `disable-library-validation` — required by the bundled Python/torch runtime.

## Verifying

```bash
codesign --verify --deep --strict --verbose=2 dist/Miolingo.app
spctl --assess --type execute --verbose dist/Miolingo.app
xcrun stapler validate dist/Miolingo.app
```

## Notes / open items

- `target_arch` in the spec is left `None` (universal2 if the building Python
  supports it). Build on Apple Silicon for arm64; use a universal2 Python for a
  fat binary.
- The Whisper `medium` model is **not** bundled; it downloads on first run and
  caches in `~/.cache/whisper`. After that, the app works fully offline.
- ffmpeg: drop a static `ffmpeg` binary in `packaging/bin/ffmpeg` before
  building and the spec bundles it.
