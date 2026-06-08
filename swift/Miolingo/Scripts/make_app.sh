#!/usr/bin/env bash
# Assemble a runnable, CODE-SIGNED Miolingo.app from the SwiftPM release build.
#
# Signing matters here for more than Gatekeeper: macOS TCC keys the
# Microphone and *Speech Recognition* permissions to the app's code signature.
# An UNSIGNED bundle gets a fresh, unstable identity each launch, so the
# Speech Recognition prompt may never appear and any grant won't persist —
# which is exactly the "(nothing recognised)" failure with similarity 0%.
#
# Signing identity (in order of preference, set MIOLINGO_SIGN_ID to choose):
#   * A self-signed certificate name (e.g. "Miolingo Dev")  ← BEST: stable
#     identity, TCC remembers the grant across every rebuild. Create once:
#       Keychain Access → Certificate Assistant → Create a Certificate…
#         Name: Miolingo Dev   Identity Type: Self Signed Root
#         Certificate Type: Code Signing
#     then run:  MIOLINGO_SIGN_ID="Miolingo Dev" ./Scripts/make_app.sh
#   * "-"  → ad-hoc signing (the default). Works and lets the Speech prompt
#     appear, but the identity can change between machines/builds so TCC may
#     re-prompt after a rebuild.
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIG=release
APP="Miolingo.app"
BIN_NAME="Miolingo"
BUNDLE_ID="co.fairflow.miolingo"
SIGN_ID="${MIOLINGO_SIGN_ID:--}"          # default: ad-hoc ("-")
ENTITLEMENTS="Scripts/Miolingo.entitlements"
# stamp the git short-hash as the build number, so "am I on the latest?" is
# answerable from the app's version (About box / Settings footer).
GITHASH="$(git rev-parse --short HEAD 2>/dev/null || echo 0)"

# compile the git hash INTO the binary (immune to plist/LaunchServices caching),
# then restore the placeholder so the worktree stays clean.
STAMP="Sources/${BIN_NAME}/BuildInfo.swift"
printf 'enum BuildInfo { static let stamp = "%s" }\n' "$GITHASH" > "$STAMP"

echo "▶ swift build -c $CONFIG  (build $GITHASH)"
swift build -c "$CONFIG"

git checkout -- "$STAMP" 2>/dev/null || true

BUILD_DIR="$(swift build -c "$CONFIG" --show-bin-path)"
echo "  bin path: $BUILD_DIR"

echo "▶ assembling $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$BUILD_DIR/$BIN_NAME" "$APP/Contents/MacOS/$BIN_NAME"

# SwiftPM resource bundle. It lives in Contents/Resources/ — the only place a
# code-signed .app can carry it (root or MacOS/ trip codesign: "unsealed
# contents" / "bundle format unrecognized"). The app reads it via
# BundledResource (which knows to look here), since the generated Bundle.module
# accessor only checks the app ROOT and the build machine's .build path.
if [ -d "$BUILD_DIR/${BIN_NAME}_${BIN_NAME}.bundle" ]; then
  cp -R "$BUILD_DIR/${BIN_NAME}_${BIN_NAME}.bundle" "$APP/Contents/Resources/"
fi

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>            <string>Miolingo</string>
  <key>CFBundleDisplayName</key>     <string>Miolingo</string>
  <key>CFBundleExecutable</key>      <string>$BIN_NAME</string>
  <key>CFBundleIdentifier</key>      <string>$BUNDLE_ID</string>
  <key>CFBundlePackageType</key>     <string>APPL</string>
  <key>CFBundleShortVersionString</key> <string>0.2.0</string>
  <key>CFBundleVersion</key>         <string>$GITHASH</string>
  <key>LSMinimumSystemVersion</key>  <string>15.0</string>
  <key>NSHighResolutionCapable</key> <true/>
  <key>NSMicrophoneUsageDescription</key>
    <string>Miolingo records your voice so it can score your pronunciation.</string>
  <key>NSSpeechRecognitionUsageDescription</key>
    <string>Miolingo transcribes your recording to compare it with the target pronunciation.</string>
</dict>
</plist>
PLIST

# --- code signing ------------------------------------------------------------
# The only Mach-O in the bundle is Contents/MacOS/Miolingo; the SwiftPM
# "resource bundle" is pure JSON (no Info.plist, no executable), so it is NOT a
# code bundle and must NOT be signed — hence no --deep (which would try to and
# fail with "bundle format unrecognized"). Signing the app bundle covers the
# executable and seals the resources into the bundle's code-resources.
echo "▶ codesign (identity: $SIGN_ID)"
codesign --force --options runtime \
  --entitlements "$ENTITLEMENTS" \
  --sign "$SIGN_ID" "$APP"

echo "▶ verifying signature"
codesign --verify --verbose "$APP" || true
codesign --display --entitlements - "$APP" 2>/dev/null | sed -n '1,40p' || true

echo "✔ built & signed $APP"
if [ "$SIGN_ID" = "-" ]; then
  echo "  identity: AD-HOC. Speech Recognition will prompt on first 'Check"
  echo "  pronunciation' — approve it. For a grant that survives rebuilds,"
  echo "  create a self-signed 'Code Signing' cert and re-run with"
  echo "  MIOLINGO_SIGN_ID=\"Miolingo Dev\" ./Scripts/make_app.sh"
fi
echo "  run with:  open ./$APP    (first launch: right-click → Open)"
