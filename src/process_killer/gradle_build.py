"""Reads a Gradle daemon's own log to find the build it is running now."""
import glob
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

_BUILD_START = "Daemon is about to start building"
# Tooling API builds (IDE sync) print no BUILD line, so the daemon's own finish line also ends a build.
_BUILD_END = re.compile(r"^BUILD (SUCCESSFUL|FAILED) in |\] The daemon has finished executing the build\.")
_EXHAUSTED = re.compile(r"^The Daemon will expire after the build after running out of JVM (heap space|Metaspace)")
_TIMESTAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+[+-]\d{4}) ")
_READ_LIMIT = 64 * 1024 * 1024
WORKER_SAMPLE_SECONDS = 10.0
WORKER_ACTIVE_CPU_SECONDS = 1.0

# Children that belong to the build itself; any other child (bootRun / JavaExec app, dev server) is protected.
_BUILD_CHILD_MARKERS = (
    "gradleworkermain",
    "gradle test executor",
    "org.jetbrains.kotlin.daemon.kotlincompiledaemon",
)


@dataclass(frozen=True)
class Build:
    started: float
    exhausted: Optional[str] = None


def daemon_log(pid: int) -> Optional[Path]:
    """The daemon keeps its log open, which also finds logs under a non-default Gradle user home."""
    name = f"daemon-{pid}.out.log"
    try:
        out = subprocess.run(["lsof", "-a", "-p", str(pid), "-Fn"], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    for line in out.splitlines():
        if line.startswith("n") and line.endswith("/" + name):
            return Path(line[1:])
    found = glob.glob(os.path.expanduser(f"~/.gradle/daemon/*/{name}"))
    return Path(found[0]) if found else None


def current_build(log: Path) -> Optional[Build]:
    """The build started last and not yet reported finished, or None."""
    try:
        f = log.open("rb")
    except OSError:
        return None
    build: Optional[Build] = None
    with f:
        size = os.fstat(f.fileno()).st_size
        if size > _READ_LIMIT:
            f.seek(size - _READ_LIMIT)
            f.readline()
        for raw in f:
            line = raw.decode("utf-8", "replace")
            if _BUILD_START in line:
                started = _timestamp(line)
                build = Build(started) if started is not None else None
            elif build is None:
                continue
            elif _BUILD_END.search(line):
                build = None
            else:
                exhausted = _EXHAUSTED.match(line)
                if exhausted:
                    build = Build(build.started, exhausted.group(1))
    return build


def _children(pid: int) -> Optional[List[Tuple[float, str]]]:
    """(cumulative CPU seconds, command) of each child, or None when ps fails."""
    try:
        out = subprocess.run(["ps", "-axo", "ppid=,time=,command="], capture_output=True, text=True,
                             timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    children = []
    for line in out.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3 and fields[0] == str(pid):
            children.append((_cpu_seconds(fields[1]), fields[2]))
    return children


def _is_build_worker(command: str) -> bool:
    lowered = command.lower()
    return any(marker in lowered for marker in _BUILD_CHILD_MARKERS)


def app_children(pid: int) -> List[str]:
    """Commands of the daemon's children that are not part of the build (a running app or server)."""
    children = _children(pid)
    if children is None:
        return ["<ps failed>"]
    return [command for _, command in children if not _is_build_worker(command)]


def _worker_cpu(pid: int) -> Optional[float]:
    children = _children(pid)
    if children is None:
        return None
    return sum(cpu for cpu, command in children if _is_build_worker(command))


def workers_busy(pid: int, window: float = WORKER_SAMPLE_SECONDS) -> bool:
    """Whether the build's worker JVMs (tests, worker daemons) keep using CPU over the window."""
    before = _worker_cpu(pid)
    if before is None:
        return True
    time.sleep(window)
    after = _worker_cpu(pid)
    return after is None or after - before >= WORKER_ACTIVE_CPU_SECONDS


def _cpu_seconds(value: str) -> float:
    total = 0.0
    for part in value.split(":"):
        try:
            total = total * 60 + float(part)
        except ValueError:
            return 0.0
    return total


def _timestamp(line: str) -> Optional[float]:
    match = _TIMESTAMP.match(line)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S.%f%z").timestamp()
    except ValueError:
        return None
