#!/usr/bin/env python3
"""
Process information collection module
"""
import subprocess
import os
import re
from typing import List
from datetime import datetime, timedelta
from rich.console import Console

from .models import ProcessInfo

console = Console()


class ProcessCollector:
    """Process information collection and formatting class"""
    
    def get_process_info(self) -> List[ProcessInfo]:
        """Collect process information from system and return as ProcessInfo list"""
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')[1:]  # Remove header
            
            processes = []
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    user, pid, cpu, mem, vsz, rss, tty, stat, start, time_str, command = parts
                    
                    # Data normalization: ensure no None values (convert to empty string)
                    command = (str(command) if command is not None else '') or ''
                    start = (str(start) if start is not None else '') or ''
                    user = (str(user) if user is not None else '') or ''
                    stat = (str(stat) if stat is not None else '') or ''
                    
                    # Extract and format process name
                    process_name = self.format_process_name(command) or ''
                    if not process_name:
                        process_name = 'unknown'
                    
                    # Extract process type (e.g., java, python, etc.)
                    process_type = 'unknown'
                    if command:
                        try:
                            first_part = command.split()[0]
                            if first_part:
                                process_type = os.path.basename(first_part).split('.')[0] or 'unknown'
                        except (IndexError, AttributeError):
                            pass
                    
                    # Get PPID
                    ppid_result = subprocess.run(['ps', '-o', 'ppid=', '-p', pid], 
                                               capture_output=True, text=True)
                    ppid = ppid_result.stdout.strip() if ppid_result.returncode == 0 else ''
                    if not ppid:
                        ppid = '?'
                    
                    # Calculate uptime (return '?' if start is empty string)
                    uptime = ''
                    if start:
                        uptime = self.calculate_uptime(start) or ''
                    if not uptime:
                        uptime = '?'
                    
                    # Create ProcessInfo with Pydantic model (ensure all fields are non-None)
                    process_info = ProcessInfo(
                        user=user or 'unknown',
                        pid=int(pid),
                        ppid=ppid or '?',
                        cpu=float(cpu) if cpu else 0.0,
                        mem=float(mem) if mem else 0.0,
                        stat=stat or '?',
                        start=start or '?',
                        uptime=uptime or '?',
                        command=command or '',
                        name=process_name or 'unknown',
                        type=process_type or 'unknown',
                        selected=False
                    )
                    processes.append(process_info)
            
            return processes
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to retrieve process information: {e}[/red]")
            return []

    def format_process_name(self, command: str) -> str:
        """
        Format process name
        
        Rules:
        - /Applications/AppName.app/Contents/MacOS/AppName → Applications / AppName.app (when same)
        - /Applications/AppName.app/Contents/MacOS/ExecName → Applications / AppName / ExecName (when different)
        - /opt/homebrew/bin/python → homebrew / python
        - /usr/bin/command → usr / command
        - Others: parent directory / executable name
        
        Args:
            command: Full command
        
        Returns:
            Formatted process name
        """
        # Handle empty command
        if not command:
            return 'unknown'

        # Mac Application path handling: /Applications/AppName.app/... (including all sub-paths)
        # Check before split() (path may contain spaces)
        if '/Applications/' in command and '.app/' in command:
            # Extract AppName (using regex)
            try:
                # Find app name right after /Applications/ (before first /)
                match = re.search(r'/Applications/([^/]+)\.app/', command)

                if match:
                    app_name = match.group(1)  # Name without .app (e.g., "Google Chrome")

                    # Find the last .app/Contents/MacOS/ pattern
                    last_exec_path = None
                    for m in re.finditer(r'\.app/Contents/MacOS/', command):
                        start_pos = m.end()
                        remaining = command[start_pos:]
                        # Extract until option (-- or -) or end of line
                        option_match = re.search(r'(\s--|\s-[a-z]|$)', remaining)
                        if option_match:
                            last_exec_path = remaining[:option_match.start()].strip()
                        else:
                            last_exec_path = remaining.strip()

                    if last_exec_path:
                        # Last MacOS executable name
                        exec_name = os.path.basename(last_exec_path)
                        # If AppName and ExecName differ, use Applications / AppName / ExecName format
                        if app_name != exec_name:
                            return f"Applications / {app_name} / {exec_name}"
                        # If same, use Applications / AppName format
                        else:
                            return f"Applications / {app_name}"
                    else:
                        # If Contents/MacOS doesn't exist, just return app name
                        return f"Applications / {app_name}"
                else:
                    # Regex match failed - proceed to default handling
                    pass
            except (IndexError, AttributeError):
                # Parsing failed - proceed to default handling
                pass

        # First part of command (executable file path)
        command_parts = command.split()
        if not command_parts:
            return 'unknown'
        first_part = command_parts[0]
        
        # Homebrew path handling: /opt/homebrew/... (including all sub-paths)
        if first_part.startswith('/opt/homebrew/'):
            basename = os.path.basename(first_part)
            return f"homebrew / {basename}"
        
        # /usr/bin, /usr/sbin, /bin, /sbin handling
        if first_part.startswith('/usr/bin/') or first_part.startswith('/usr/sbin/'):
            basename = os.path.basename(first_part)
            return f"usr / {basename}"
        
        if first_part.startswith('/bin/') or first_part.startswith('/sbin/'):
            basename = os.path.basename(first_part)
            return f"bin / {basename}"
        
        # /usr/local/bin handling
        if first_part.startswith('/usr/local/bin/'):
            basename = os.path.basename(first_part)
            return f"local / {basename}"
        
        # General path: parent directory / executable name
        dirname = os.path.dirname(first_part)
        basename = os.path.basename(first_part)
        
        # Root path or empty path (executed without path)
        # e.g., node, npm, python, etc.
        if not dirname or dirname == '/':
            # If no path, display as (no path) / executable name
            return f"(no path) / {basename}"
        
        # Extract only parent directory name
        parent_dir = os.path.basename(dirname)
        
        # Maximum length limit (50 characters)
        result = f"{parent_dir} / {basename}"
        max_length = 50
        if len(result) > max_length:
            # Preserve basename first, abbreviate parent_dir
            if len(basename) + 5 > max_length:  # " / " + basename exceeds max_length
                return basename[:max_length-3] + '...'
            available = max_length - len(basename) - 3  # Exclude " / "
            return f"{parent_dir[:available]} / {basename}"
        
        return result
    
    def calculate_uptime(self, start_time: str) -> str:
        """Calculate uptime from process start time"""
        try:
            # Handle None or empty string start_time
            if not start_time:
                return '?'
            
            # Convert to string if not string
            if not isinstance(start_time, str):
                start_time = str(start_time)
                if not start_time:
                    return '?'
            
            now = datetime.now()
            if ':' in start_time:
                # Process started today (HH:MM format)
                try:
                    parts = start_time.split(':')
                    if len(parts) < 2:
                        return start_time
                    start_hour, start_min = map(int, parts[:2])
                except (ValueError, AttributeError, IndexError, TypeError):
                    return start_time
                start_dt = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                if start_dt > now:
                    start_dt -= timedelta(days=1)
            else:
                # Process started on a date
                if len(start_time) == 5:  # MMdd format
                    month = int(start_time[:2])
                    day = int(start_time[2:])
                    start_dt = now.replace(month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
                else:
                    return start_time
            
            uptime = now - start_dt
            hours = int(uptime.total_seconds() // 3600)
            minutes = int((uptime.total_seconds() % 3600) // 60)
            
            if hours > 0:
                return f"{hours}h{minutes}m"
            else:
                return f"{minutes}m"
        except:
            return start_time
