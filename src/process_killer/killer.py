#!/usr/bin/env python3
"""
Process termination module
"""
import os
import signal
import time
from typing import List
from rich.console import Console

from .models import ProcessInfo
from ..common.questionary_utils import select_yes_no
from ..common.exceptions import CancelledError

console = Console()


class ProcessTerminator:
    """Process termination class"""
    
    def kill_selected_processes(self, processes: List[ProcessInfo]):
        """Terminate selected processes"""
        selected = [p for p in processes if p.selected]
        if not selected:
            console.print("[yellow]No processes selected.[/yellow]")
            return

        console.print(f"\n[bold yellow]Terminate {len(selected)} process(es)?[/bold yellow]")
        for proc in selected:
            # Display full command (use command instead of name)
            command = proc.command or proc.name or 'unknown'
            console.print(f"  • {command} (PID: {proc.pid})")

        try:
            if not select_yes_no("Continue?", default=True):
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled.[/yellow]")
            return
        except CancelledError:
            console.print("\n[yellow]Operation cancelled.[/yellow]")
            return

        console.print("\n[blue]Sending termination signals...[/blue]")

        # Step 1: Send SIGTERM
        signal_sent = []
        immediate_failed = []

        for proc in selected:
            try:
                os.kill(proc.pid, signal.SIGTERM)
                signal_sent.append(proc)
                command = proc.command or proc.name or 'unknown'
                console.print(f"[green]✓[/green] {command} (PID: {proc.pid}) termination signal sent")
            except OSError as e:
                command = proc.command or proc.name or 'unknown'
                console.print(f"[red]✗[/red] {command} (PID: {proc.pid}) signal send failed: {e}")
                immediate_failed.append(proc)

        if not signal_sent:
            return

        # Step 2: Verify termination (wait up to 3 seconds)
        console.print("\n[blue]Verifying process termination...[/blue]")
        time.sleep(2)  # Give processes time to terminate normally

        still_running = []
        for proc in signal_sent:
            try:
                # Check if process still exists (send signal 0)
                os.kill(proc.pid, 0)
                still_running.append(proc)
            except OSError:
                # Process terminated
                command = proc.command or proc.name or 'unknown'
                console.print(f"[green]✓[/green] {command} (PID: {proc.pid}) terminated normally")

        # Step 3: Force terminate processes still running
        if still_running:
            console.print(f"\n[bold yellow]{len(still_running)} process(es) still running:[/bold yellow]")
            for proc in still_running:
                command = proc.command or proc.name or 'unknown'
                console.print(f"  • {command} (PID: {proc.pid})")

            try:
                if select_yes_no("Attempt force termination (SIGKILL)?", default=True):
                    for proc in still_running:
                        try:
                            os.kill(proc.pid, signal.SIGKILL)
                            command = proc.command or proc.name or 'unknown'
                            console.print(f"[green]✓[/green] {command} (PID: {proc.pid}) force termination signal sent")
                            time.sleep(0.1)
                        except OSError as e:
                            command = proc.command or proc.name or 'unknown'
                            console.print(f"[red]✗[/red] {command} (PID: {proc.pid}) force termination failed: {e}")

                    # Verify after force termination
                    time.sleep(1)
                    console.print("\n[blue]Verifying force termination results...[/blue]")
                    for proc in still_running:
                        try:
                            os.kill(proc.pid, 0)
                            command = proc.command or proc.name or 'unknown'
                            console.print(f"[red]✗[/red] {command} (PID: {proc.pid}) still running")
                        except OSError:
                            command = proc.command or proc.name or 'unknown'
                            console.print(f"[green]✓[/green] {command} (PID: {proc.pid}) force terminated")
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled.[/yellow]")
            except CancelledError:
                console.print("\n[yellow]Operation cancelled.[/yellow]")
