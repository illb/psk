"""
Process information model
"""
from pydantic import BaseModel, Field


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
    command: str = Field(..., description="Full command")
    name: str = Field(..., description="Formatted process name")
    type: str = Field(..., description="Process type")
    selected: bool = Field(default=False, description="Selection status")
    
    class Config:
        """Pydantic configuration"""
        frozen = False  # Allow modification of selected field
