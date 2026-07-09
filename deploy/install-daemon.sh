#!/bin/bash
#
# Install and load the psk cleanup daemon as a macOS LaunchAgent.
# Runs at login/boot and every --interval seconds thereafter.
#
# Follows the same pattern as com.illb.tsm-ai-notifier: invoke the project's
# venv entrypoint directly so the agent does not depend on uv/mise being on
# PATH under launchd.
#
set -euo pipefail

LABEL="com.illb.psk-daemon"
PSK_DIR="$HOME/kenny/asdp-kenny/kenny-work/psk"
PSK_BIN="$PSK_DIR/.venv/bin/psk"
LOG_DIR="$HOME/Library/Logs"
LOG="$LOG_DIR/psk-daemon.log"
AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST="$AGENTS_DIR/$LABEL.plist"

INTERVAL="${PSK_DAEMON_INTERVAL:-1800}"
CATEGORIES="${PSK_DAEMON_CATEGORIES:-zombie,lsp,gradle}"

if [ ! -x "$PSK_BIN" ]; then
    echo "Error: $PSK_BIN not found."
    echo "Run 'uv sync' in $PSK_DIR first to create the venv entrypoint."
    exit 1
fi

mkdir -p "$LOG_DIR" "$AGENTS_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <!-- Direct venv entrypoint avoids depending on uv/mise on PATH. -->
  <key>ProgramArguments</key>
  <array>
    <string>$PSK_BIN</string>
    <string>daemon</string>
    <string>--interval</string>
    <string>$INTERVAL</string>
    <string>--categories</string>
    <string>$CATEGORIES</string>
    <string>--log</string>
    <string>$LOG</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$PSK_DIR</string>

  <!-- PATH needs /usr/bin:/bin for the 'ps' calls the collector makes. -->
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>60</integer>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/psk-daemon.launchd.out</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/psk-daemon.launchd.err</string>
</dict>
</plist>
PLIST

# Reload (unload any previous instance first; ignore errors when not loaded).
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Installed and loaded: $LABEL"
echo "  interval:   ${INTERVAL}s"
echo "  categories: $CATEGORIES"
echo "  log:        $LOG"
launchctl list | grep "$LABEL" || true
