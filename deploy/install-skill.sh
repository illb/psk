#!/bin/bash
#
# Register the psk skill globally so both Claude Code and Codex can invoke it
# via `/psk`. Symlinks this project's `skill/` directory into the standard
# skill locations — the same mechanism the asdp-scripts skills use, but owned
# by and installed from the psk project itself.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PSK_DIR="$(dirname "$SCRIPT_DIR")"
SKILL_SRC="$PSK_DIR/skill"

TARGETS=(
    "$HOME/.claude/skills"
    "$HOME/.codex/skills"
)

if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
    echo "Error: $SKILL_SRC/SKILL.md not found." >&2
    exit 1
fi

for dir in "${TARGETS[@]}"; do
    mkdir -p "$dir"
    ln -sfn "$SKILL_SRC" "$dir/psk"
    echo "Registered: $dir/psk -> $SKILL_SRC"
done

echo "Done. Claude and Codex can now use the /psk skill."
