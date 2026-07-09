"""
Process Killer CLI
"""
import sys
import typer
from typing import Optional
from rich.console import Console

from ..common.cli_utils import initialize_cli
from ..process_killer import ProcessKiller, CategoryKiller
from ..process_killer.daemon import (
    run_daemon,
    DEFAULT_INTERVAL_SECONDS,
    DEFAULT_LOG_PATH,
    DEFAULT_CATEGORIES,
)

app = typer.Typer(
    name="psk",
    help="Process management tool",
    no_args_is_help=True,
)

console = Console()


def run_process_killer(
    by: Optional[str] = None,
    excludes: Optional[str] = None,
    name: Optional[str] = None
):
    """Process killer execution logic"""
    exclude_list = []
    if excludes:
        exclude_list = [exclude_name.strip() for exclude_name in excludes.split(',')]

    killer = ProcessKiller(exclude_list=exclude_list, name_filter=name)
    killer.run(sort_by=by)


@app.command()
def version():
    """Show version information"""
    console.print("[blue]Process Killer CLI v1.0.0[/blue]")


@app.command()
def kill(
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Comma-separated categories to kill (e.g. 'zombie,lsp,gradle'). "
             "Omit for an interactive multi-select.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts (required for non-interactive use).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be killed without terminating anything.",
    ),
    list_categories: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available categories with current match counts, then exit.",
    ),
):
    """
    Bulk-kill processes by category (multi-select).

    Categories:
    - zombie: Defunct (Z) processes — parent nudged to reap them
    - lsp:    Orphaned language servers (PPID 1) — leaked serena/pyright/ts/kotlin LSPs
    - gradle: Idle Gradle/Kotlin build daemons (CPU < 1%)

    Examples:
      psk kill                      # interactive: check categories, confirm
      psk kill --list               # show categories and match counts
      psk kill -c lsp,gradle        # non-interactive, still confirms
      psk kill -c lsp,zombie -y     # non-interactive, no prompt
      psk kill -c gradle --dry-run  # preview only
    """
    keys = None
    if category:
        keys = [k.strip() for k in category.split(",") if k.strip()]

    CategoryKiller().run(
        category_keys_selected=keys,
        assume_yes=yes,
        dry_run=dry_run,
        list_only=list_categories,
    )


@app.command()
def run(
    by: Optional[str] = typer.Option(
        None,
        "--by",
        "-b",
        help="Process sorting method: general, memory, cpu, uptime, zombie"
    ),
    excludes: Optional[str] = typer.Option(
        "Google Chrome,KakaoTalk,Slack,KakaoWork,Okta,Cursor",
        "--excludes",
        "-e",
        help="Process names to exclude (comma-separated, e.g., 'Cursor,Google Chrome')"
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Filter by specific process name (e.g., 'Chrome', 'node')"
    )
):
    """
    Run process killer

    Sorting methods:
    - general: General (CPU + Memory)
    - memory: Memory usage
    - cpu: CPU usage
    - uptime: Uptime (oldest first)
    - zombie: Zombie processes

    Exclusion filter:
    - excludes: Process names to exclude (comma-separated)
      Example: --excludes "Cursor,Google Chrome"

    Name filter:
    - name: Filter by specific process name
      Example: --name "Chrome" or --name "node"

    Search:
    - Press '/' key after execution to search in real-time
    """
    run_process_killer(by=by, excludes=excludes, name=name)


@app.command()
def daemon(
    interval: int = typer.Option(
        DEFAULT_INTERVAL_SECONDS,
        "--interval",
        "-i",
        help="Seconds between cleanup cycles (default 1800 = 30 min).",
    ),
    categories: str = typer.Option(
        ",".join(DEFAULT_CATEGORIES),
        "--categories",
        "-c",
        help="Comma-separated categories to auto-kill each cycle.",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Run a single cleanup cycle and exit (for testing / cron).",
    ),
    log: str = typer.Option(
        DEFAULT_LOG_PATH,
        "--log",
        help="Log file path (use '' to disable file logging).",
    ),
):
    """
    Run the periodic cleanup daemon.

    Each cycle silently terminates the given categories (default: zombie, lsp,
    gradle) and appends a summary line to the log. Intended to be supervised by
    launchd (see deploy/install-daemon.sh) but runnable standalone.

    Note: `codex`/`claude` are intentionally NOT part of the default set — they
    are manual-only via `psk kill` to avoid killing active sessions.
    """
    keys = [k.strip() for k in categories.split(",") if k.strip()]
    run_daemon(
        categories=keys,
        interval_seconds=interval,
        once=once,
        log_path=(log or None),
    )


# Subcommands that must never be rewritten to the default `run` command.
KNOWN_COMMANDS = {"run", "kill", "daemon", "version"}


def main():
    """Main function"""
    initialize_cli()
    args = sys.argv[1:]
    if {"--help", "-h"} & set(args):
        # Global help only when no subcommand precedes the flag.
        if not args or args[0] not in KNOWN_COMMANDS:
            sys.argv[:] = [sys.argv[0], "--help"]
    elif not args or args[0] not in KNOWN_COMMANDS:
        # No subcommand given (bare `psk` or only options) -> default to `run`.
        sys.argv[1:1] = ["run"]
    app()


if __name__ == "__main__":
    main()
