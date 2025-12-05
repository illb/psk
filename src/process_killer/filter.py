#!/usr/bin/env python3
"""
Process filtering module
"""
from typing import Optional, List

from .models import ProcessInfo
from ..common.process_utils import is_system_process as check_system_process


class ProcessFilter:
    """Process filtering class"""
    
    def __init__(self, exclude_list: Optional[List[str]] = None, name_filter: Optional[str] = None):
        """
        Initialize
        
        Args:
            exclude_list: List of process names to exclude
            name_filter: Name filter keyword
        """
        self.exclude_list = exclude_list or []
        self.name_filter = name_filter
    
    def is_excluded(self, proc: ProcessInfo) -> bool:
        """
        Check if process is in exclusion list

        Args:
            proc: Process information model

        Returns:
            Whether process is in exclusion list
        """
        if not self.exclude_list:
            return False

        # Check if exclusion list keywords are included in shortened name (proc.name)
        proc_name_lower = proc.name.lower()
        for exclude_keyword in self.exclude_list:
            exclude_keyword_lower = exclude_keyword.lower()
            if exclude_keyword_lower in proc_name_lower:
                return True

        return False

    def matches_name_filter(self, proc: ProcessInfo) -> bool:
        """
        Check if process matches name filter

        Args:
            proc: Process information model

        Returns:
            Whether process matches name filter
        """
        if not self.name_filter:
            return True

        # Check if filter keyword is included in shortened name (proc.name)
        proc_name_lower = proc.name.lower()
        filter_lower = self.name_filter.lower()
        return filter_lower in proc_name_lower

    def is_system_process(self, proc: ProcessInfo) -> bool:
        """
        Check if process is a system process

        Args:
            proc: Process information model

        Returns:
            Whether process is a system process
        """
        return check_system_process(proc)
