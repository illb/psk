#!/usr/bin/env python3
"""
Process Killer main module
"""
import traceback
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel

from .collector import ProcessCollector
from .sorter import ProcessSorter
from .filter import ProcessFilter
from .killer import ProcessTerminator
from .display import ProcessDisplay
from ..common.questionary_utils import select_single
from ..common.exceptions import CancelledError

console = Console()


class ProcessKiller:
    """Process Killer main controller class"""
    
    def __init__(self, exclude_list: Optional[List[str]] = None, name_filter: Optional[str] = None):
        """
        Initialize
        
        Args:
            exclude_list: List of process names to exclude
            name_filter: Name filter keyword
        """
        self.exclude_list = exclude_list or []
        self.name_filter = name_filter
        
        # Initialize each module
        self.collector = ProcessCollector()
        self.sorter = ProcessSorter()
        self.filter = ProcessFilter(exclude_list=exclude_list, name_filter=name_filter)
        self.terminator = ProcessTerminator()
        self.display = ProcessDisplay(exclude_list=exclude_list)
        
        # Get sort options
        self.sort_options = self.sorter.get_sort_options()

    def show_menu(self):
        """Display menu and get selection"""
        choices = []
        for key, (name, _) in self.sort_options.items():
            choices.append((key, name))
        choices.append(("exit", "Exit"))
        
        try:
            selected = select_single(
                title="Select process sorting method",
                choices=choices
            )
            return selected if selected else "exit"
        except CancelledError:
            # User cancelled, return exit
            return "exit"

    def run(self, sort_by: Optional[str] = None):
        """Main execution logic"""
        console.print(Panel.fit("[bold green]🚀 Starting Process Killer[/bold green]", border_style="green"))
        
        # If --by option is provided, execute once and exit
        if sort_by:
            if sort_by not in self.sort_options:
                console.print(f"[red]❌ Invalid sorting method: {sort_by}[/red]")
                console.print(f"[yellow]Available options: {', '.join(self.sort_options.keys())}[/yellow]")
                return
            
            try:
                self._execute_sort_option(sort_by)
            except KeyboardInterrupt:
                console.print("\n\n[bold green]👋 Exiting program.[/bold green]")
            except CancelledError:
                console.print("\n\n[bold green]👋 Exiting program.[/bold green]")
            except Exception as e:
                console.print(f"[red]❌ An error occurred: {e}[/red]")
                console.print("[red]Stack trace:[/red]")
                console.print(traceback.format_exc())
            return
        
        # If --by option is not provided, show menu and repeat execution
        while True:
            try:
                choice = self.show_menu()
                
                if choice == "exit" or choice is None:
                    console.print("[bold green]👋 Exiting program.[/bold green]")
                    break
                
                if choice in self.sort_options:
                    self._execute_sort_option(choice)
                
            except KeyboardInterrupt:
                console.print("\n\n[bold green]👋 Exiting program.[/bold green]")
                break
            except CancelledError:
                console.print("\n\n[bold green]👋 Exiting program.[/bold green]")
                break
            except Exception as e:
                console.print(f"[red]❌ An error occurred: {e}[/red]")
                console.print("[red]Stack trace:[/red]")
                console.print(traceback.format_exc())
    
    def _execute_sort_option(self, choice: str):
        """Execute sort option"""
        console.print("[blue]📊 Collecting process information...[/blue]")
        all_processes = self.collector.get_process_info()
        
        if not all_processes:
            console.print("[red]❌ Failed to retrieve process information.[/red]")
            return
        
        # Apply selected sorting method
        _, sort_func = self.sort_options[choice]
        sorted_processes = sort_func(all_processes)
        
        if not sorted_processes:
            console.print("[yellow]⚠️  No processes match the criteria.[/yellow]")
            return

        # Select processes
        self.display.select_processes(
            sorted_processes,
            name_filter=self.name_filter,
            is_system_process_func=self.filter.is_system_process,
            is_excluded_func=self.filter.is_excluded,
            matches_name_filter_func=self.filter.matches_name_filter
        )
        
        # Terminate selected processes
        self.terminator.kill_selected_processes(sorted_processes)
