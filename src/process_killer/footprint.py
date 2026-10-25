#!/usr/bin/env python3
"""macOS phys_footprint per process (Activity Monitor "Memory", includes compressed pages)."""
import ctypes
import functools
from typing import Optional

_RUSAGE_INFO_V2 = 2
_PHYS_FOOTPRINT_SLOT = 9  # uint64 index of ri_phys_footprint in rusage_info_v2


@functools.lru_cache(maxsize=1)
def _libproc():
    try:
        lib = ctypes.CDLL("/usr/lib/libproc.dylib")
        lib.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        return lib
    except (OSError, AttributeError):
        return None


def footprint_kb(pid: int) -> Optional[int]:
    lib = _libproc()
    if lib is None:
        return None
    buf = (ctypes.c_uint64 * 32)()
    if lib.proc_pid_rusage(pid, _RUSAGE_INFO_V2, buf) != 0:
        return None
    return buf[_PHYS_FOOTPRINT_SLOT] // 1024
