# Process Killer

A clean CLI tool for process management

## Features

- Various sorting options (CPU, memory, uptime, etc.)
- Process search functionality
- Clean interface using rich
- Fast dependency management via uv
- Safe process termination (SIGTERM → SIGKILL)

## Screenshot

![Process Killer Screenshot](docs/psk-screenshot-01.png)

## Installation and Usage

```bash
# Install dependencies
uv sync

# Run method 1: Using script (recommended)
./psk

# Run method 2: Direct execution
uv run psk run

# Show help
./psk --help
```

## Usage

1. Select sorting method
   - General (CPU + Memory)
   - Memory usage
   - CPU usage
   - Uptime (oldest first)
   - Zombie processes
   - Process search

2. Select processes to terminate by number (comma-separated or range, e.g., 1,3,5 or 1-5)
3. Confirm and terminate processes

## Bulk kill by category (`psk kill`)

Terminate whole classes of processes at once instead of picking them one by
one. Run `psk kill` with no arguments for an interactive checkbox multi-select,
or pass categories directly for scripted, non-interactive use.

Categories:

- `zombie` — defunct (stat `Z`) processes; their parent is nudged (SIGCHLD) to reap them
- `lsp` — orphaned language servers (PPID 1): leaked serena / pyright / typescript / kotlin LSPs
- `orphan-tail` — PPID 1인 `tail -f` / `tail -F` 중 stdout 파이프의 소비자 연결 종료를 커널에서 확인한 프로세스
- `gradle` — idle Gradle / Kotlin daemon JVMs (CPU < 1%); manual cleanup only, because active builds can briefly look idle
- `codex` — OpenAI Codex CLI processes that are orphaned (PPID 1) or ≥ 3 days old
- `claude` — Claude Code CLI processes that are orphaned (PPID 1) or ≥ 3 days old

`codex` / `claude` never match a recent, actively-driven session — only leaks
and long-stale processes.

```bash
psk kill                      # interactive: check categories, confirm
psk kill --list               # show categories and current match counts
psk kill -c lsp,gradle        # non-interactive, still confirms
psk kill -c lsp,zombie -y     # non-interactive, no prompt
psk kill -c gradle --dry-run  # preview only, kill nothing
psk kill -c codex,claude      # orphaned/stale only — review, then confirm
psk stale-ai                  # same codex/claude stale scan, with reasons
psk stale-ai --dry-run        # preview clearly stale AI processes only
```

Termination is SIGTERM first, then SIGKILL for survivors. The running process
and its ancestors are always excluded, so `kill` can never terminate itself.

`psk stale-ai` is the preferred command for Codex/Claude cleanup. It only
matches processes with known Codex/Claude command markers that are orphaned
(`PPID 1`) or at least 3 days old, prints the reason for each match, and asks
before termination unless `--yes` is explicitly passed.

## Cleanup daemon (`psk daemon`)

Run a periodic background cleanup so leaks never accumulate. Installed as a
macOS LaunchAgent (`com.illb.psk-daemon`), it runs the safe set
(`zombie,lsp,orphan-tail`) every 30 minutes and at login/boot. `gradle`, `codex`, and
`claude` are intentionally excluded from daemon termination by default. The
daemon may report clearly stale AI candidates in the log, but cleanup stays
manual via `psk stale-ai` so the user can confirm first.

```bash
# install + load (runs at boot thereafter), and stop + remove:
./deploy/install-daemon.sh
./deploy/uninstall-daemon.sh

# status and recent cycles:
launchctl list | grep com.illb.psk-daemon
tail -n 20 ~/Library/Logs/psk-daemon.log

# run standalone (no launchd):
psk daemon --once                          # one cycle, then exit
psk daemon --interval 1800 -c zombie,lsp,orphan-tail
psk kill -c orphan-tail --dry-run          # 연결이 끊긴 stdout 파이프 검증 결과
psk kill -c gradle --dry-run               # inspect idle Gradle/Kotlin daemon candidates manually
psk daemon --no-check-stale-ai             # disable codex/claude stale reporting
```

`orphan-tail`은 PPID 1만으로 종료하지 않는다. macOS `libproc`로 실제 프로세스명과
부모 PID를 확인하고 stdout이 쓰기 파이프이며 peer가 없고 EOF인 경우에만 자동 정리한다.
소비자가 남은 파이프, 파일, 터미널, `/dev/null`, 조회 실패 및 미지원 OS는 보호한다.
SIGTERM/SIGKILL 직전에도 시작 시각과 파이프 식별자, 연결 상태를 다시 확인한다.
옵션 파서는 `--` 또는 첫 파일명 이후를 해석하지 않으며, 지원하지 않는 옵션은 후보에서 제외한다.

Configure via env before install: `PSK_DAEMON_INTERVAL` (seconds),
`PSK_DAEMON_CATEGORIES` (comma-separated).

## Global skill

This project ships its own skill in `skill/SKILL.md`. Install it to let both
Claude Code and Codex drive `psk` via the `/psk` skill — it symlinks `skill/`
into `~/.claude/skills/psk` and `~/.codex/skills/psk`:

```bash
./deploy/install-skill.sh      # register for Claude + Codex
./deploy/uninstall-skill.sh    # remove
```

The skill is self-contained here (not part of any other skills repo), so
updating `skill/SKILL.md` updates the installed skill immediately.
