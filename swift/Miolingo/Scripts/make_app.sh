#!/usr/bin/env bash
# Assemble a runnable (unsigned) Miolingo.app from the SwiftPM release build.
# Signing/notarisation is deliberately deferred (PORTING.md decision 8).
set -euo pipefail
cd "$(dirname "$0")/.."

CONFIG=release
APP="Miolingo.app"
BIN_NAME="Miolingo"
BUNDLE_ID="co.fairflow.miolingo"

echo "▶ swift build -c $CONFIG"
swift build -c "$CONFIG"

BUILD_DIR="$(swift build -c "$CONFIG" --show-bin-path)"
echo "  bin path: $BUILD_DIR"

echo "▶ assembling $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$BUILD_DIR/$BIN_NAME" "$APP/Contents/MacOS/$BIN_NAME"

# SwiftPM resource bundle (Bundle.module) must sit next to the executable.
if [ -d "$BUILD_DIR/${BIN_NAME}_${BIN_NAME}.bundle" ]; then
  cp -R "$BUILD_DIR/${BIN_NAME}_${BIN_NAME}.bundle" "$APP/Contents/MacOS/"
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
  <key>CFBundleShortVersionString</key> <string>0.1.0</string>
  <key>CFBundleVersion</key>         <string>1</string>
  <key>LSMinimumSystemVersion</key>  <string>14.0</string>
  <key>NSHighResolutionCapable</key> <true/>
  <key>NSMicrophoneUsageDescription</key>
    <string>Miolingo records your voice so it can score your pronunciation.</string>
  <key>NSSpeechRecognitionUsageDescription</key>
    <string>Miolingo transcribes your recording to compare it with the target pronunciation.</string>
</dict>
</plist>
PLIST

echo "✔ built $APP"
echo "  run with:  open ./$APP    (first launch: right-click → Open, it is unsigned)"
