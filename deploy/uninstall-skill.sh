#!/bin/bash
#
# Remove the globally-registered psk skill symlinks.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PSK_DIR="$(dirname "$SCRIPT_DIR")"
SKILL_SRC="$PSK_DIR/skill"

for link in "$HOME/.claude/skills/psk" "$HOME/.codex/skills/psk"; do
    # Only remove if it's a symlink pointing at this project's skill dir.
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$SKILL_SRC" ]; then
        rm -f "$link"
        echo "Removed: $link"
    elif [ -e "$link" ]; then
        echo "Skipped: $link (not a psk-project symlink)"
    fi
done
