#!/usr/bin/env python3
"""
Category-based bulk process killer.

Powers the `psk kill` command: pick one or more process *categories*
(zombie, orphaned LSP, idle Gradle daemons, ...) and terminate the union in a
single pass. Works both interactively (checkbox multi-select) and
non-interactively (`-c zombie,lsp,gradle -y`) so it can be scripted.
"""
import os
import signal
import sys
import time
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .categories import CATEGORIES, CATEGORY_BY_KEY, KillCategory, category_keys
from .collector import ProcessCollector
from .models import ProcessInfo
from ..common.exceptions import CancelledError
from ..common.questionary_utils import select_checkbox, select_yes_no

console = Console()

_TERM_GRACE_SECONDS = 2.0


class CategoryKiller:
    """Collect processes, match them to categories, and terminate them."""

    def __init__(self):
        self.collector = ProcessCollector()

    # ---- public entry point -------------------------------------------------

    def run(
        self,
        category_keys_selected: Optional[List[str]] = None,
        assume_yes: bool = False,
        dry_run: bool = False,
        list_only: bool = False,
    ) -> None:
        console.print(Panel.fit(
            "[bold green]🧹 Process Killer — category kill[/bold green]",
            border_style="green",
        ))

        console.print("[blue]📊 Collecting process information...[/blue]")
        processes = self.collector.get_process_info()
        if not processes:
            console.print("[red]❌ Failed to retrieve process information.[/red]")
            return

        matches = self._match_all(processes)

        if list_only:
            self._print_category_summary(matches)
            return

        selected_keys = self._resolve_selection(category_keys_selected, matches)
        if not selected_keys:
            console.print("[yellow]No categories selected. Nothing to do.[/yellow]")
            return

        targets = self._collect_targets(selected_keys, matches)
        if not targets:
            console.print("[yellow]⚠️  No processes match the selected categories.[/yellow]")
            return

        self._print_targets(targets)

        if dry_run:
            console.print("\n[cyan]Dry run — nothing was terminated.[/cyan]")
            return

        if not self._confirm(len(targets), assume_yes):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

        self._execute(targets, assume_yes, quiet=False)

    def kill_categories(
        self,
        keys: List[str],
        *,
        assume_yes: bool = True,
        quiet: bool = False,
    ) -> dict:
        """Non-interactive collect → match → terminate for the given category
        keys. Returns a summary dict:

            {"targeted": int, "killed": int, "by_category": {key: int}}

        Used by the daemon and by any scripted caller. Never prompts.
        """
        processes = self.collector.get_process_info()
        if not processes:
            return {"targeted": 0, "killed": 0, "by_category": {}}
        valid = [k for k in keys if k in CATEGORY_BY_KEY]
        matches = self._match_all(processes)
        targets = self._collect_targets(valid, matches)
        if not targets:
            return {"targeted": 0, "killed": 0, "by_category": {k: 0 for k in valid}}
        if not quiet:
            self._print_targets(targets)
        return self._execute(targets, assume_yes, quiet=quiet)

    # ---- matching -----------------------------------------------------------

    def _match_all(self, processes: List[ProcessInfo]) -> Dict[str, List[ProcessInfo]]:
        """Return {category_key: [matching processes]} for every category."""
        excluded = self._self_and_ancestors()
        result: Dict[str, List[ProcessInfo]] = {c.key: [] for c in CATEGORIES}
        for proc in processes:
            if proc.pid in excluded:
                continue
            for category in CATEGORIES:
                if category.matcher(proc):
                    result[category.key].append(proc)
        return result

    def _collect_targets(
        self,
        selected_keys: List[str],
        matches: Dict[str, List[ProcessInfo]],
    ) -> List[Tuple[ProcessInfo, KillCategory]]:
        """Union of matched processes across selected categories, deduped by pid.

        The first selected category that matches a pid owns it (determines the
        kill strategy shown/used).
        """
        seen = set()
        targets: List[Tuple[ProcessInfo, KillCategory]] = []
        for key in selected_keys:
            category = CATEGORY_BY_KEY[key]
            for proc in matches.get(key, []):
                if proc.pid in seen:
                    continue
                seen.add(proc.pid)
                targets.append((proc, category))
        return targets

    # ---- selection ----------------------------------------------------------

    def _resolve_selection(
        self,
        category_keys_selected: Optional[List[str]],
        matches: Dict[str, List[ProcessInfo]],
    ) -> List[str]:
        if category_keys_selected:
            valid = []
            for key in category_keys_selected:
                if key in CATEGORY_BY_KEY:
                    valid.append(key)
                else:
                    console.print(f"[red]Unknown category: {key}[/red] "
                                  f"(available: {', '.join(category_keys())})")
            return valid

        # No categories given -> interactive multi-select (requires a TTY).
        if not sys.stdin.isatty():
            console.print("[red]No categories given and not a TTY.[/red] "
                          f"Use -c with: {', '.join(category_keys())}")
            return []

        choices = [
            (c.key, f"{c.label}  ({len(matches.get(c.key, []))})")
            for c in CATEGORIES
        ]
        try:
            return select_checkbox(
                title="Select process categories to terminate",
                choices=choices,
            )
        except (CancelledError, KeyboardInterrupt):
            return []

    # ---- display ------------------------------------------------------------

    def _print_category_summary(self, matches: Dict[str, List[ProcessInfo]]) -> None:
        table = Table(title="Kill categories", show_lines=False)
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Matches", justify="right", style="bold")
        table.add_column("Category")
        table.add_column("Description", style="dim")
        for category in CATEGORIES:
            count = len(matches.get(category.key, []))
            count_style = "green" if count else "dim"
            table.add_row(
                category.key,
                f"[{count_style}]{count}[/{count_style}]",
                category.label,
                category.description,
            )
        console.print(table)

    def _print_targets(self, targets: List[Tuple[ProcessInfo, KillCategory]]) -> None:
        table = Table(title=f"{len(targets)} process(es) to terminate")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("PID", justify="right")
        table.add_column("CPU%", justify="right")
        table.add_column("MEM%", justify="right")
        table.add_column("Up", justify="right", style="dim")
        table.add_column("Command")
        for proc, category in targets:
            command = proc.command or proc.name or "unknown"
            if len(command) > 80:
                command = command[:77] + "..."
            table.add_row(
                category.key,
                str(proc.pid),
                f"{proc.cpu:.1f}",
                f"{proc.mem:.1f}",
                proc.uptime,
                command,
            )
        console.print(table)

    def _confirm(self, count: int, assume_yes: bool) -> bool:
        if assume_yes:
            return True
        if not sys.stdin.isatty():
            console.print("[red]Refusing to kill without confirmation in a "
                          "non-interactive shell.[/red] Pass -y to proceed.")
            return False
        try:
            return bool(select_yes_no(
                f"Terminate these {count} process(es)?", default=True))
        except (CancelledError, KeyboardInterrupt):
            return False

    # ---- termination --------------------------------------------------------

    def _execute(
        self,
        targets: List[Tuple[ProcessInfo, KillCategory]],
        assume_yes: bool,
        quiet: bool = False,
    ) -> dict:
        terminate = [p for p, c in targets if c.strategy == "terminate"]
        reap = [p for p, c in targets if c.strategy == "reap_parent"]

        killed = 0
        if terminate:
            killed += self._terminate(terminate, assume_yes, quiet=quiet)
        if reap:
            killed += self._reap_parents(reap, quiet=quiet)

        by_category: dict = {}
        for _, category in targets:
            by_category[category.key] = by_category.get(category.key, 0) + 1
        return {"targeted": len(targets), "killed": killed, "by_category": by_category}

    def _terminate(self, procs: List[ProcessInfo], assume_yes: bool,
                   quiet: bool = False) -> int:
        if not quiet:
            console.print("\n[blue]Sending SIGTERM...[/blue]")
        sent = []
        for proc in procs:
            try:
                os.kill(proc.pid, signal.SIGTERM)
                sent.append(proc)
            except OSError as e:
                if not quiet:
                    console.print(f"[red]✗[/red] PID {proc.pid}: {e}")
        if not sent:
            return 0

        time.sleep(_TERM_GRACE_SECONDS)

        survivors = [p for p in sent if self._alive(p.pid)]
        terminated = len(sent) - len(survivors)
        if not quiet:
            console.print(f"[green]✓[/green] {terminated} terminated by SIGTERM.")

        if not survivors:
            return terminated

        if not quiet:
            console.print(f"[yellow]{len(survivors)} still alive:[/yellow] "
                          + ", ".join(str(p.pid) for p in survivors))
        if not self._confirm_force(assume_yes):
            if not quiet:
                console.print("[yellow]Left survivors running.[/yellow]")
            return terminated

        if not quiet:
            console.print("[blue]Sending SIGKILL...[/blue]")
        for proc in survivors:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except OSError as e:
                if not quiet:
                    console.print(f"[red]✗[/red] PID {proc.pid}: {e}")
        time.sleep(0.5)
        force_killed = sum(1 for p in survivors if not self._alive(p.pid))
        if not quiet:
            console.print(f"[green]✓[/green] {force_killed}/{len(survivors)} force-killed.")
        return terminated + force_killed

    def _reap_parents(self, zombies: List[ProcessInfo], quiet: bool = False) -> int:
        if not quiet:
            console.print("\n[blue]Nudging parents of zombie processes (SIGCHLD)...[/blue]")
        parents = set()
        for proc in zombies:
            try:
                parents.add(int(proc.ppid))
            except (ValueError, TypeError):
                continue
        parents.discard(0)
        parents.discard(1)  # launchd: nothing we can do
        for ppid in parents:
            try:
                os.kill(ppid, signal.SIGCHLD)
                if not quiet:
                    console.print(f"[green]✓[/green] SIGCHLD -> parent PID {ppid}")
            except OSError as e:
                if not quiet:
                    console.print(f"[red]✗[/red] parent PID {ppid}: {e}")
        if not quiet:
            console.print(
                f"[dim]{len(zombies)} zombie(s) flagged. Zombies clear once their "
                f"parent reaps them; if a parent is stuck, kill the parent instead.[/dim]"
            )
        return len(zombies)

    def _confirm_force(self, assume_yes: bool) -> bool:
        if assume_yes:
            return True
        if not sys.stdin.isatty():
            return False
        try:
            return bool(select_yes_no("Force kill survivors (SIGKILL)?", default=True))
        except (CancelledError, KeyboardInterrupt):
            return False

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    @staticmethod
    def _self_and_ancestors() -> set:
        """PIDs that must never be killed: this process and its ancestor chain."""
        excluded = set()
        try:
            import subprocess
            result = subprocess.run(['ps', '-axo', 'pid=,ppid='],
                                    capture_output=True, text=True, check=True)
            parent_of = {}
            for line in result.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 2:
                    parent_of[int(parts[0])] = int(parts[1])
            pid = os.getpid()
            for _ in range(64):  # guard against cycles
                if pid <= 0 or pid in excluded:
                    break
                excluded.add(pid)
                pid = parent_of.get(pid, 0)
        except Exception:
            excluded.add(os.getpid())
        return excluded
