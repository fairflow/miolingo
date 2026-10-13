#!/bin/sh
# Make the Neolingo host start at login (a per-user launchd agent), and hand the running host over to it.
#   ./install_login_item.sh            install and start
#   ./install_login_item.sh remove     switch off and remove
# Run by Matthew himself: it adds a login item, which an assistant is not allowed to do for him.
# Afterwards:  clean restart (signs sessions out, saves settings):  launchctl kill TERM gui/$(id -u)/io.miolingo.neolingo
set -e
N=$(cd "$(dirname "$0")" && pwd)
L=io.miolingo.neolingo
P="$HOME/Library/LaunchAgents/$L.plist"
D="gui/$(id -u)"
if [ "$1" = "remove" ]; then
  launchctl bootout "$D/$L" 2>/dev/null || true
  rm -f "$P"; echo "removed: the host no longer starts at login (and is stopped)"; exit 0
fi
cat > "$P" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$L</string>
  <key>ProgramArguments</key>
  <array><string>$N/run.sh</string><string>--port</string><string>8810</string></array>
  <key>WorkingDirectory</key><string>$N</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>NEOLINGO_SLOTS</key><string>${NEOLINGO_SLOTS:-2}</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$N/var/host.log</string>
  <key>StandardErrorPath</key><string>$N/var/host.log</string>
</dict>
</plist>
PLIST
plutil -lint "$P"
launchctl bootout "$D/$L" 2>/dev/null || true
OLD=$(lsof -ti tcp:8810 -sTCP:LISTEN | head -1)
if [ -n "$OLD" ]; then kill -TERM "$OLD"; sleep 5; fi
launchctl bootstrap "$D" "$P"
printf "starting (the recognisers take about a minute) "
for i in $(seq 1 60); do
  if curl -s -m 2 http://127.0.0.1:8810/version >/dev/null; then echo; echo "up: http://127.0.0.1:8810/"; exit 0; fi
  printf "."; sleep 3
done
echo; echo "NOT up after 3 minutes: see $N/var/host.log"; exit 1
