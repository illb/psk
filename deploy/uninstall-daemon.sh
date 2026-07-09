#!/bin/bash
#
# Stop and remove the psk cleanup daemon LaunchAgent.
#
set -euo pipefail

LABEL="com.illb.psk-daemon"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ -f "$PLIST" ]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed $LABEL"
else
    launchctl remove "$LABEL" 2>/dev/null || true
    echo "$LABEL was not installed (no plist at $PLIST)"
fi
