---
description: "Kill leaked/stale processes by category (zombies, orphaned LSPs, idle Gradle daemons, orphaned/stale codex & claude) and manage the psk cleanup daemon"
argument-hint: "[list | kill -c <cats> | daemon status] ..."
allowed-tools: Bash, Read
---

Use the `psk` CLI to find and terminate whole classes of leaked or stale
processes, and to inspect the background cleanup daemon. `psk` is a global
command; call it directly.

## Preview before killing (always do this first)

```bash
psk kill --list                      # categories + how many processes each matches
psk kill -c <categories> --dry-run   # show exactly what would be killed
```

## Kill

```bash
psk kill                             # interactive checkbox multi-select + confirm
psk kill -c zombie,lsp -y            # always-safe set, no prompt
psk kill -c codex,claude             # orphaned/stale only — review, then confirm
psk stale-ai                         # codex/claude stale scan with reasons + confirm
```

Termination is SIGTERM first, then SIGKILL for survivors. The running process
and its ancestors are always excluded, so `psk` can never kill itself or the
session invoking it.

## Categories

| Key      | Targets                                                              | Safety |
|----------|---------------------------------------------------------------------|--------|
| `zombie` | Defunct (stat `Z`) processes; parent is nudged (SIGCHLD) to reap them | safe |
| `lsp`    | Orphaned language servers (PPID 1): leaked serena/pyright/ts/kotlin  | safe |
| `orphan-tail` | PPID 1 follow-mode tail, 커널에서 stdout 파이프 peer 없음 + EOF 확인 | verified auto |
| `gradle` | Idle Gradle / Kotlin daemon JVMs (CPU < 1%)                  | manual |
| `codex`  | OpenAI Codex CLI processes that are orphaned (PPID 1) or ≥ 3 days old | orphan/stale only |
| `claude` | Claude Code CLI processes that are orphaned (PPID 1) or ≥ 3 days old  | orphan/stale only |

`codex` / `claude` never match a recent, actively-driven session — only leaks
and long-stale processes.

Use `psk stale-ai` for Codex/Claude cleanup when the user asks to clean stale
AI workers. It only targets known Codex/Claude command markers that are
orphaned (`PPID 1`) or at least 3 days old, prints a reason for each candidate,
and asks before terminating unless the user explicitly approved `--yes`.

## Cleanup daemon

A LaunchAgent (`com.illb.psk-daemon`) runs the verified cleanup set (`zombie,lsp,orphan-tail`)
every 30 minutes and at login/boot. `gradle` is manual-only by default because
active builds can briefly look idle while tasks hand off between daemon JVMs.

```bash
launchctl list | grep com.illb.psk-daemon          # is it loaded? (status 0 = ok)
tail -n 20 ~/Library/Logs/psk-daemon.log           # recent cleanup cycles

# install / start (idempotent) and stop / remove:
~/kenny/asdp-kenny/kenny-work/psk/deploy/install-daemon.sh
~/kenny/asdp-kenny/kenny-work/psk/deploy/uninstall-daemon.sh
```

The daemon deliberately does NOT auto-terminate `codex` / `claude`. It may log
clearly stale AI candidates and the review command (`psk stale-ai`), but
termination stays manual so the user can confirm first.

## Rules

- Always preview with `--list` / `--dry-run` before terminating.
- The always-safe set (`zombie`, `lsp`) is low-risk and may be run with `-y`.
- For `gradle`, preview with `psk kill -c gradle --dry-run` and avoid daemon
  auto-kill unless the candidates are clearly idle.
- `orphan-tail`은 `psk kill -c orphan-tail --dry-run`으로 먼저 확인한다.
  PPID 1만으로 종료하지 않고 macOS 커널의 stdout 파이프 peer 없음 + EOF를 확인한다.
  연결된 소비자, 파일, 터미널, `/dev/null`, 조회 실패는 보호하며 SIGTERM/SIGKILL 직전 재검증한다.
- For `codex` / `claude`, show the dry-run, explain what will be killed, and get
  user approval before terminating — do not pass `-y` blindly.
- Prefer `psk stale-ai --dry-run` before asking the user to approve stale
  Codex/Claude cleanup.
- Summarize the result (how many terminated per category) concisely.
