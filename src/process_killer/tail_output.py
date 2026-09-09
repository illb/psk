"""Read macOS pipe state without inferring consumer liveness from PPID.

ABI: Darwin sys/proc_info.h; pipe EOF: sys/pipe.h. Non-Darwin and failed
queries return None, never permission to terminate.
"""
import ctypes as c
from functools import lru_cache
import sys
from typing import Optional, Tuple


class _BSDInfo(c.Structure):
    _fields_ = [
        (name, c.c_uint32) for name in (
            "flags", "status", "xstatus", "pid", "ppid", "uid", "gid",
            "ruid", "rgid", "svuid", "svgid", "reserved",
        )
    ] + [("comm", c.c_char * 16), ("name", c.c_char * 32)] + [
        (name, c.c_uint32) for name in ("nfiles", "pgid", "jobc", "tdev", "tpgid")
    ] + [("nice", c.c_int32), ("start_sec", c.c_uint64), ("start_usec", c.c_uint64)]


class _FileInfo(c.Structure):
    _fields_ = [("openflags", c.c_uint32), ("status", c.c_uint32),
                ("offset", c.c_int64), ("type", c.c_int32), ("guardflags", c.c_uint32)]


class _VInfoStat(c.Structure):
    _fields_ = [
        ("dev", c.c_uint32), ("mode", c.c_uint16), ("nlink", c.c_uint16),
        ("ino", c.c_uint64), ("uid", c.c_uint32), ("gid", c.c_uint32),
    ] + [(name, c.c_int64) for name in (
        "atime", "atimensec", "mtime", "mtimensec", "ctime", "ctimensec",
        "birthtime", "birthtimensec", "size", "blocks",
    )] + [("blksize", c.c_int32), ("flags", c.c_uint32), ("gen", c.c_uint32),
          ("rdev", c.c_uint32), ("qspare", c.c_int64 * 2)]


class _PipeInfo(c.Structure):
    _fields_ = [("stat", _VInfoStat), ("handle", c.c_uint64),
                ("peerhandle", c.c_uint64), ("status", c.c_int32),
                ("reserved", c.c_int32)]


class _PipeFDInfo(c.Structure):
    _fields_ = [("file", _FileInfo), ("pipe", _PipeInfo)]


_PROC_PIDTBSDINFO = 3
_PROC_PIDFDPIPEINFO = 6
_FWRITE = 2
_PIPE_EOF = 0x80


@lru_cache(maxsize=1)
def _libproc():
    if sys.platform != "darwin":
        return None
    try:
        lib = c.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        lib.proc_pidinfo.argtypes = [c.c_int, c.c_int, c.c_uint64, c.c_void_p, c.c_int]
        lib.proc_pidinfo.restype = c.c_int
        lib.proc_pidfdinfo.argtypes = [c.c_int, c.c_int, c.c_int, c.c_void_p, c.c_int]
        lib.proc_pidfdinfo.restype = c.c_int
        return lib
    except (OSError, AttributeError):
        return None


def disconnected_tail_identity(pid: int) -> Optional[Tuple[int, int, int]]:
    """Return (start seconds, microseconds, pipe handle) only for a dead stdout pipe."""
    lib = _libproc()
    if lib is None:
        return None
    before, after, fd = _BSDInfo(), _BSDInfo(), _PipeFDInfo()
    try:
        if lib.proc_pidinfo(pid, _PROC_PIDTBSDINFO, 0, c.byref(before), c.sizeof(before)) != c.sizeof(before):
            return None
        if before.pid != pid or before.ppid != 1 or before.comm != b"tail":
            return None
        # A successful PIPEINFO query also excludes files, terminals and /dev/null.
        if lib.proc_pidfdinfo(pid, 1, _PROC_PIDFDPIPEINFO, c.byref(fd), c.sizeof(fd)) != c.sizeof(fd):
            return None
        if not (fd.file.openflags & _FWRITE and fd.pipe.status & _PIPE_EOF):
            return None
        if fd.pipe.peerhandle != 0 or fd.pipe.handle == 0:
            return None
        if lib.proc_pidinfo(pid, _PROC_PIDTBSDINFO, 0, c.byref(after), c.sizeof(after)) != c.sizeof(after):
            return None
    except (OSError, ValueError, c.ArgumentError):
        return None
    if (after.pid, after.ppid, after.comm, after.start_sec, after.start_usec) != (
        before.pid, 1, b"tail", before.start_sec, before.start_usec,
    ):
        return None
    return before.start_sec, before.start_usec, fd.pipe.handle
