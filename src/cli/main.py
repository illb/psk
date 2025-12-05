"""
Process Killer CLI
"""
import typer
from typing import Optional
from rich.console import Console

from ..process_killer import ProcessKiller

app = typer.Typer(
    name="psk",
    help="Process management tool",
    no_args_is_help=False
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


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    by: Optional[str] = typer.Option(
        None,
        "--by",
        "-b",
        help="Process sorting method: general, memory, cpu, uptime, zombie"
    ),
    excludes: Optional[str] = typer.Option(
        None,
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
    Process management tool
    
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
    if ctx.invoked_subcommand is None:
        run_process_killer(by=by, excludes=excludes, name=name)


@app.command()
def version():
    """Show version information"""
    console.print("[blue]Process Killer CLI v1.0.0[/blue]")


@app.command()
def run(
    by: Optional[str] = typer.Option(
        None,
        "--by",
        "-b",
        help="Process sorting method: general, memory, cpu, uptime, zombie"
    ),
    excludes: Optional[str] = typer.Option(
        None,
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


def main():
    """Main function"""
    app()


if __name__ == "__main__":
    main()
