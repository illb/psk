"""
Process information model
"""
from pydantic import BaseModel, Field
from typing import Optional, Tuple


class ProcessInfo(BaseModel):
    """Process information model"""
    user: str = Field(..., description="Username")
    pid: int = Field(..., description="Process ID")
    ppid: str = Field(..., description="Parent Process ID")
    cpu: float = Field(..., description="CPU usage (%)")
    mem: float = Field(..., description="Memory usage (%)")
    stat: str = Field(..., description="Process status")
    start: str = Field(..., description="Start time")
    uptime: str = Field(..., description="Uptime")
    etime_seconds: int = Field(default=0, description="Elapsed running time in seconds")
    cpu_time_seconds: float = Field(default=0.0, description="Cumulative CPU time in seconds")
    live_children: int = Field(default=0, description="Number of non-zombie child processes")
    idle_seconds: Optional[int] = Field(
        default=None, description="Seconds without build-level CPU use, observed across cycles")
    command: str = Field(..., description="Full command")
    name: str = Field(..., description="Formatted process name")
    type: str = Field(..., description="Process type")
    selected: bool = Field(default=False, description="Selection status")
    tail_identity: Optional[Tuple[int, int, int]] = Field(
        default=None, description="Verified tail start time and disconnected stdout pipe identity")
    
    class Config:
        """Pydantic configuration"""
        frozen = False  # Allow modification of selected field
