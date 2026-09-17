"""
Core process-monitoring logic for Linux Process Monitor.

This module is deliberately free of any curses/TTY dependency so that it can
be unit tested in any environment (CI, headless machines, etc). It uses
psutil, which is cross-platform (Linux, macOS, Windows), so behavior is
consistent between a macOS dev machine and an ubuntu-latest CI runner.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

import psutil


@dataclass
class ProcessInfo:
    """A single process snapshot record."""

    pid: int
    name: str
    username: str
    cpu_percent: float
    memory_percent: float
    status: str

    def as_tuple(self):
        return (
            self.pid,
            self.name,
            self.username,
            self.cpu_percent,
            self.memory_percent,
            self.status,
        )


@dataclass
class SystemSummary:
    """A snapshot of overall system resource usage."""

    cpu_percent: float
    memory_used: int
    memory_total: int
    memory_percent: float
    load_average: Optional[tuple]
    process_count: int


VALID_SORT_KEYS = ("cpu", "memory", "pid")


def _safe_cpu_percent(proc: psutil.Process) -> float:
    try:
        return proc.cpu_percent(interval=None)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return 0.0


def _safe_memory_percent(proc: psutil.Process) -> float:
    try:
        return proc.memory_percent()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return 0.0


def get_process_snapshot(cpu_interval: float = 0.1) -> List[ProcessInfo]:
    """Return a list of ProcessInfo records for every currently running
    process that we have permission to inspect.

    psutil.Process.cpu_percent() returns a meaningless 0.0 the very first
    time it's called for a given process (it needs a time delta to measure
    against). To get a useful reading in a single call to this function, we
    "prime" every process's internal cpu-time counter, sleep for a short
    interval, then read the real cpu_percent() for each one. Set
    cpu_interval=0 to skip the sleep (e.g. in fast unit tests where only the
    shape of the data matters, not the exact CPU value).

    Processes that disappear or are inaccessible mid-iteration (a normal
    race condition on any live system) are silently skipped rather than
    raising, since a monitor should never crash because a process exited.
    """
    procs = list(psutil.process_iter(attrs=["pid", "name", "username", "status"]))

    # Priming pass: starts each process's internal CPU-time measurement
    # window. The return value here is intentionally discarded.
    for proc in procs:
        _safe_cpu_percent(proc)

    if cpu_interval > 0:
        time.sleep(cpu_interval)

    records: List[ProcessInfo] = []
    for proc in procs:
        try:
            info = proc.info
            records.append(
                ProcessInfo(
                    pid=info.get("pid", -1),
                    name=info.get("name") or "",
                    username=info.get("username") or "",
                    cpu_percent=_safe_cpu_percent(proc),
                    memory_percent=_safe_memory_percent(proc),
                    status=info.get("status") or "",
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return records


def sort_processes(
    processes: List[ProcessInfo], sort_by: str = "cpu"
) -> List[ProcessInfo]:
    """Return a new list of processes sorted descending by the given key.

    sort_by must be one of "cpu", "memory", or "pid". For "pid" the sort is
    ascending (lowest pid first), which matches the usual expectation for
    process listings; cpu/memory sorts are descending (highest usage first).
    """
    if sort_by not in VALID_SORT_KEYS:
        raise ValueError(
            f"Invalid sort_by={sort_by!r}; must be one of {VALID_SORT_KEYS}"
        )

    if sort_by == "cpu":
        return sorted(processes, key=lambda p: p.cpu_percent, reverse=True)
    if sort_by == "memory":
        return sorted(processes, key=lambda p: p.memory_percent, reverse=True)
    # pid
    return sorted(processes, key=lambda p: p.pid)


def filter_processes(
    processes: List[ProcessInfo],
    name_contains: Optional[str] = None,
    username: Optional[str] = None,
    min_cpu: Optional[float] = None,
) -> List[ProcessInfo]:
    """Filter a list of processes by optional criteria.

    - name_contains: case-insensitive substring match against process name.
    - username: exact match against the process owner.
    - min_cpu: keep only processes whose cpu_percent >= min_cpu.
    """
    result = processes

    if name_contains:
        needle = name_contains.lower()
        result = [p for p in result if needle in p.name.lower()]

    if username:
        result = [p for p in result if p.username == username]

    if min_cpu is not None:
        result = [p for p in result if p.cpu_percent >= min_cpu]

    return result


def top_n(processes: List[ProcessInfo], n: int) -> List[ProcessInfo]:
    """Return the first n processes (use after sorting)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    return processes[:n]


def get_system_summary() -> SystemSummary:
    """Return a SystemSummary describing overall CPU/memory/load state.

    load_average is populated via psutil.getloadavg() when available
    (Linux/macOS). On platforms where it is unsupported (e.g. Windows),
    psutil raises/omits it, in which case we fall back to None so callers
    can display a "not available on this platform" message instead of
    crashing.
    """
    cpu_percent = psutil.cpu_percent(interval=None)
    vmem = psutil.virtual_memory()
    process_count = len(psutil.pids())

    load_average = None
    try:
        load_average = psutil.getloadavg()
    except (AttributeError, OSError):
        load_average = None

    return SystemSummary(
        cpu_percent=cpu_percent,
        memory_used=vmem.used,
        memory_total=vmem.total,
        memory_percent=vmem.percent,
        load_average=load_average,
        process_count=process_count,
    )


def get_sorted_filtered_snapshot(
    sort_by: str = "cpu",
    name_contains: Optional[str] = None,
    username: Optional[str] = None,
    min_cpu: Optional[float] = None,
    top: Optional[int] = None,
) -> List[ProcessInfo]:
    """Convenience helper combining snapshot + filter + sort + top-N."""
    processes = get_process_snapshot()
    processes = filter_processes(
        processes, name_contains=name_contains, username=username, min_cpu=min_cpu
    )
    processes = sort_processes(processes, sort_by=sort_by)
    if top is not None:
        processes = top_n(processes, top)
    return processes
