#!/bin/bash
# psk skill 전역 설치 — skills/ 를 ~/.claude/skills, ~/.codex/skills 로 symlink.
# flavor 중립 단일 skills/ 를 claude·codex 양쪽에 건다(한 SKILL.md 가 둘 다 커버).
# 자기 source(skills/)를 가리키는 link 만 다룬다 — 다른 도구 link 는 불변.
#   --list      설치 계획만 출력 (dry-run)
#   --uninstall 이 repo 가 설치한 skill symlink 제거

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_DIR/skills"
DRY=0
RM=0
for a in "$@"; do
    case "$a" in
        --list) DRY=1 ;;
        --uninstall) RM=1 ;;
        *) echo "unknown option: $a" >&2; exit 2 ;;
    esac
done

for flavor in claude codex; do
    DEST="$HOME/.$flavor/skills"
    echo "=== $flavor: $SRC -> $DEST ==="
    mkdir -p "$DEST"
    # 1) 우리가 만든 link 중 source 에 없는 것 제거 (--uninstall 이면 전부)
    for link in "$DEST"/*; do
        [ -L "$link" ] || continue
        case "$(readlink "$link")" in "$SRC"/*) ;; *) continue ;; esac
        name="$(basename "$link")"
        if [ "$RM" = 1 ] || [ ! -f "$SRC/$name/SKILL.md" ]; then
            echo "제거: $flavor:$name"
            [ "$DRY" = 1 ] || rm "$link"
        fi
    done
    [ "$RM" = 1 ] && continue
    # 2) 설치/갱신
    for d in "$SRC"/*/; do
        [ -f "${d}SKILL.md" ] || continue
        name="$(basename "$d")"
        link="$DEST/$name"
        target="${d%/}"
        if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
            continue
        fi
        echo "설치: $flavor:$name -> $target"
        [ "$DRY" = 1 ] || { rm -f "$link"; ln -s "$target" "$link"; }
    done
done
