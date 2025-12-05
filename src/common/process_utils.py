"""
Common process utility functions
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..process_killer.models import ProcessInfo
else:
    # Runtime import to avoid circular dependency
    try:
        from ..process_killer.models import ProcessInfo
    except ImportError:
        ProcessInfo = None  # type: ignore

# System users that indicate system processes
SYSTEM_USERS = {'root', 'daemon', '_', 'nobody', 'www', 'mail', 'sshd', 'postfix'}

# System process names (Mac-specific)
SYSTEM_PROCESS_NAMES = {
    'kernel_task', 'launchd', 'WindowServer', 'loginwindow',
    'UserEventAgent', 'syspolicyd', 'trustd', 'kextd',
    'fseventsd', 'mds', 'mdworker', 'mdworker_shared',
    'cloudd', 'com.apple', 'com.apple.WebKit', 'VTDecoderXPCService',
    'hidd', 'distnoted', 'coreaudiod', 'bluetoothd', 'airportd',
    'configd', 'networksetupd', 'networkd', 'powerd', 'thermalmonitord',
    'diskarbitrationd', 'fsck', 'fsck_hfs', 'fsck_apfs', 'mount',
    'kextstat', 'kextload', 'kextunload'
}

# System paths that indicate system processes
SYSTEM_PATHS = ('/system/', '/usr/libexec/')


def is_system_process(proc: 'ProcessInfo') -> bool:
    """
    Determine if process is a system process
    
    Args:
        proc: Process information model
    
    Returns:
        Whether process is a system process
    """
    # PID 1 is always a system process
    if proc.pid == 1:
        return True
    
    # Check system users
    if proc.user in SYSTEM_USERS:
        return True
    
    process_name = proc.name.lower()
    command = proc.command.lower()
    
    # Check if process name contains system process names
    if any(sys_name in process_name for sys_name in SYSTEM_PROCESS_NAMES):
        return True
    
    # Check if command starts from system path
    if any(command.startswith(path) for path in SYSTEM_PATHS):
        return True
    
    # If PPID is 1 (child of launchd)
    if proc.ppid == '1':
        # But some user processes may also have PPID 1, so
        # additional filtering needed
        if proc.user not in SYSTEM_USERS and not any(sys_name in process_name for sys_name in SYSTEM_PROCESS_NAMES):
            return False
    
    return False
