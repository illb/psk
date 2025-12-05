#!/usr/bin/env python3
"""
Process sorting module
"""
from typing import List, Dict, Tuple, Callable

from .models import ProcessInfo


class ProcessSorter:
    """Process sorting class"""
    
    def __init__(self):
        """Initialize sort options"""
        self.sort_options: Dict[str, Tuple[str, Callable]] = {
            'general': ('General (CPU + Memory)', self.sort_general),
            'memory': ('Memory usage', self.sort_memory),
            'cpu': ('CPU usage', self.sort_cpu),
            'uptime': ('Uptime (oldest first)', self.sort_uptime),
            'zombie': ('Zombie processes', self.sort_zombie)
        }
    
    def get_sort_options(self) -> Dict[str, Tuple[str, Callable]]:
        """Return sort options dictionary"""
        return self.sort_options
    
    def sort_general(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """Sort by sum of CPU and memory usage"""
        return sorted(processes, key=lambda x: (x.cpu + x.mem), reverse=True)

    def sort_memory(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """Sort by memory usage"""
        return sorted(processes, key=lambda x: x.mem, reverse=True)

    def sort_cpu(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """Sort by CPU usage"""
        return sorted(processes, key=lambda x: x.cpu, reverse=True)

    def sort_uptime(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """Sort by uptime (oldest first)"""
        return sorted(processes, key=lambda x: x.start)

    def sort_zombie(self, processes: List[ProcessInfo]) -> List[ProcessInfo]:
        """Show zombie processes first"""
        zombies = [p for p in processes if 'Z' in p.stat]
        others = [p for p in processes if 'Z' not in p.stat]
        return zombies + others
