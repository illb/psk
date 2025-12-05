#!/usr/bin/env python3
"""
Process display and selection module
"""
import os
import unicodedata
from typing import List, Optional
from rich.console import Console

from .models import ProcessInfo
from .prompt_utils import select_multiple_custom

console = Console()


class ProcessDisplay:
    """Process display and selection class"""
    
    def __init__(self, exclude_list: Optional[List[str]] = None):
        """
        Initialize
        
        Args:
            exclude_list: Exclusion list (used in selection UI)
        """
        self.exclude_list = exclude_list or []
    
    def select_processes(self, processes: List[ProcessInfo], name_filter: Optional[str] = None, 
                        is_system_process_func=None, is_excluded_func=None, 
                        matches_name_filter_func=None):
        """
        Display UI for selecting processes
        
        Args:
            processes: Process list
            name_filter: Name filter
            is_system_process_func: Function to determine system process
            is_excluded_func: Function to determine excluded process
            matches_name_filter_func: Function to determine name filter match
        """
        if not processes:
            return

        # Get current process PID
        current_pid = os.getpid()
        
        # Filter system processes, exclusion list, name filter
        filtered_processes = []
        for proc in processes:
            # Exclude current process (psk itself)
            if proc.pid == current_pid:
                continue
            
            # Check system process
            if is_system_process_func and is_system_process_func(proc):
                continue

            # Check exclusion list (filter by shortened name)
            if is_excluded_func and is_excluded_func(proc):
                continue

            # Check name filter (filter by shortened name)
            if name_filter and matches_name_filter_func and not matches_name_filter_func(proc):
                continue

            filtered_processes.append(proc)

        if not filtered_processes:
            console.print("[yellow]No processes to display.[/yellow]")
            return

        # Multi-select with questionary checkbox
        choices = []
        for i, proc in enumerate(filtered_processes):
            # Process name field (fixed to exactly 50 characters)
            name = proc.name

            # Emoji flags
            emojis = []

            # Check if zombie process
            if 'Z' in proc.stat:
                emojis.append('🧟')

            # Memory 30% or more or CPU 100% or more
            if proc.mem >= 30.0 or proc.cpu >= 100.0:
                emojis.append('🔥')

            # Processes running for 7 days (168 hours) or more
            if proc.uptime and proc.uptime != '?':
                try:
                    # Check if uptime is in "123h45m" or "45m" format
                    if 'h' in proc.uptime:
                        hours = int(proc.uptime.split('h')[0])
                        if hours >= 168:  # 7 days = 168 hours
                            emojis.append('⏰')
                except (ValueError, IndexError):
                    pass

            # Add emojis all at once
            if emojis:
                name = f"{name} {' '.join(emojis)}"

            max_name_len = 50
            if len(name) > max_name_len:
                name = name[:max_name_len-3] + '...'
            # Calculate actual output length for padding (considering CJK characters, etc.)
            display_len = len(name)
            # Calculate East Asian character width (simple method)
            visual_len = sum(2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1 for c in name)
            padding = max_name_len - visual_len + (display_len - len(name))
            name_padded = name + ' ' * padding

            # Fix width of each field for column alignment
            label = f"{i+1:3d}. {name_padded} PID: {proc.pid:<7} CPU: {proc.cpu:>6.1f}% MEM: {proc.mem:>6.1f}%"
            choices.append((i, label))
        
        # Use select_multiple_custom (display status bar and current process info)
        selected_indices = select_multiple_custom(
            title="Select processes to terminate (multiple selection available)",
            choices=choices,
            process_data=filtered_processes,
            hide_system_processes=True,
            exclude_list=self.exclude_list
        )
        
        if selected_indices is None:
            return
        
        if not selected_indices:
            console.print("[yellow]No processes selected.[/yellow]")
            return
        
        # Deselect
        for proc in processes:
            proc.selected = False
        
        # Apply selected indices to original process list
        for idx in selected_indices:
            if 0 <= idx < len(filtered_processes):
                original_proc = filtered_processes[idx]
                # Find in original process list and mark as selected
                for proc in processes:
                    if proc.pid == original_proc.pid:
                        proc.selected = True
                        break
