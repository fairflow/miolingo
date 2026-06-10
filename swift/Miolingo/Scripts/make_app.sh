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
  <key>CFBundleShortVersionString</key> <string>0.6.0</string>
  <key>CFBundleVersion</key>         <string>$GITHASH</string>
  <key>LSMinimumSystemVersion</key>  <string>15.0</string>
  <key>NSHighResolutionCapable</key> <true/>
  <key>CFBundleHelpBookFolder</key>  <string>Miolingo.help</string>
  <key>CFBundleHelpBookName</key>    <string>Miolingo Help</string>
  <key>NSMicrophoneUsageDescription</key>
    <string>Miolingo records your voice so it can score your pronunciation.</string>
  <key>NSSpeechRecognitionUsageDescription</key>
    <string>Miolingo transcribes your recording to compare it with the target pronunciation.</string>
</dict>
</plist>
PLIST

# --- Help Book (macOS Help Viewer; the simpler companion to the in-app Help) ---
# Generate Miolingo.help from the same help.md via a light md→html pass. The
# AppleTitle meta MUST match CFBundleHelpBookName above. Built before signing so
# it is sealed into the bundle.
HELP_SRC="Sources/${BIN_NAME}/Resources/help.md"
if [ -f "$HELP_SRC" ]; then
  HB="$APP/Contents/Resources/Miolingo.help/Contents/Resources/en.lproj"
  mkdir -p "$HB"
  cat > "$APP/Contents/Resources/Miolingo.help/Contents/Info.plist" <<HBPLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key> <string>$BUNDLE_ID.help</string>
  <key>CFBundleName</key>       <string>Miolingo Help</string>
  <key>HPDBookAccessPath</key>  <string>index.html</string>
  <key>HPDBookIndexPath</key>   <string>index.html</string>
  <key>HPDBookTitle</key>       <string>Miolingo Help</string>
  <key>HPDBookType</key>        <string>3</string>
</dict></plist>
HBPLIST
  { echo '<!DOCTYPE html><html><head><meta charset="utf-8">'
    echo '<meta name="AppleTitle" content="Miolingo Help">'
    echo '<style>body{font-family:-apple-system,Helvetica,sans-serif;max-width:680px;margin:2em auto;padding:0 1.2em;line-height:1.5;color:#222}code,pre{background:#f3f3f3;border-radius:4px}code{padding:1px 4px}pre{padding:10px;overflow:auto}h1{font-size:1.7em}h2{margin-top:1.4em}</style>'
    echo '</head><body>'
    awk '
      /^```/   { if (c){print "</pre>";c=0} else {print "<pre>";c=1}; next }
      c        { gsub(/&/,"\\&amp;"); gsub(/</,"\\&lt;"); print; next }
      /^### /  { sub(/^### /,""); print "<h3>" $0 "</h3>"; next }
      /^## /   { sub(/^## /,"");  print "<h2>" $0 "</h2>"; next }
      /^# /    { sub(/^# /,"");   print "<h1>" $0 "</h1>"; next }
      /^---/   { print "<hr>"; next }
      /^- /    { sub(/^- /,""); print "<li>" $0 "</li>"; next }
      /^$/     { print ""; next }
      { print "<p>" $0 "</p>" }
    ' "$HELP_SRC"
    echo '</body></html>'
  } > "$HB/index.html"
  echo "▶ Help Book → $APP/Contents/Resources/Miolingo.help"
fi

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
