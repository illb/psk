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
psk kill -c zombie,lsp,gradle -y     # safe set, no prompt
psk kill -c codex,claude             # orphaned/stale only — review, then confirm
```

Termination is SIGTERM first, then SIGKILL for survivors. The running process
and its ancestors are always excluded, so `psk` can never kill itself or the
session invoking it.

## Categories

| Key      | Targets                                                              | Safety |
|----------|---------------------------------------------------------------------|--------|
| `zombie` | Defunct (stat `Z`) processes; parent is nudged (SIGCHLD) to reap them | safe |
| `lsp`    | Orphaned language servers (PPID 1): leaked serena/pyright/ts/kotlin  | safe |
| `gradle` | Idle Gradle build / Kotlin compile daemons (CPU < 1%); respawn on next build | safe |
| `codex`  | OpenAI Codex CLI processes that are orphaned (PPID 1) or ≥ 3 days old | orphan/stale only |
| `claude` | Claude Code CLI processes that are orphaned (PPID 1) or ≥ 3 days old  | orphan/stale only |

`codex` / `claude` never match a recent, actively-driven session — only leaks
and long-stale processes.

## Cleanup daemon

A LaunchAgent (`com.illb.psk-daemon`) runs the safe set (`zombie,lsp,gradle`)
every 30 minutes and at login/boot.

```bash
launchctl list | grep com.illb.psk-daemon          # is it loaded? (status 0 = ok)
tail -n 20 ~/Library/Logs/psk-daemon.log           # recent cleanup cycles

# install / start (idempotent) and stop / remove:
~/kenny/asdp-kenny/kenny-work/psk/deploy/install-daemon.sh
~/kenny/asdp-kenny/kenny-work/psk/deploy/uninstall-daemon.sh
```

The daemon deliberately does NOT auto-run `codex` / `claude` — those are
manual-only, to avoid ever killing an active AI session.

## Rules

- Always preview with `--list` / `--dry-run` before terminating.
- The safe set (`zombie`, `lsp`, `gradle`) is low-risk and may be run with `-y`.
- For `codex` / `claude`, show the dry-run, explain what will be killed, and get
  user approval before terminating — do not pass `-y` blindly.
- Summarize the result (how many terminated per category) concisely.
