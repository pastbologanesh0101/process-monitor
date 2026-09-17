"""
Curses-based live-refreshing UI for Linux Process Monitor.

This module is intentionally thin: all real logic (snapshotting, sorting,
filtering) lives in core.py, which is fully unit tested without any TTY
dependency. This file only knows how to render that data with curses and
handle keybindings. Because it requires a real terminal, it is not covered
by automated tests -- exercise it manually with:

    python monitor.py

Keybindings:
    c        sort by CPU%
    m        sort by memory%
    p        sort by PID
    q or Esc quit
"""

from __future__ import annotations

import curses
import time
from typing import Optional

from core import get_sorted_filtered_snapshot, get_system_summary

SORT_KEYS_BY_CHAR = {
    ord("c"): "cpu",
    ord("m"): "memory",
    ord("p"): "pid",
}


def _format_bytes(n: int) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < step:
            return f"{n:.1f}{unit}"
        n /= step
    return f"{n:.1f}PB"


def _draw(stdscr, sort_by: str, name_contains, username, min_cpu) -> None:
    height, width = stdscr.getmaxyx()
    stdscr.erase()

    summary = get_system_summary()
    load_str = (
        "N/A"
        if summary.load_average is None
        else " ".join(f"{x:.2f}" for x in summary.load_average)
    )
    header_line1 = (
        f"CPU {summary.cpu_percent:5.1f}%  "
        f"Mem {_format_bytes(summary.memory_used)}/{_format_bytes(summary.memory_total)} "
        f"({summary.memory_percent:.1f}%)  "
        f"Load {load_str}  "
        f"Procs {summary.process_count}  "
        f"Sort:{sort_by}  [c/m/p sort, q quit]"
    )
    stdscr.addnstr(0, 0, header_line1, max(width - 1, 0))

    col_header = f"{'PID':>7}  {'USER':<12} {'CPU%':>6}  {'MEM%':>6}  {'STATUS':<10} {'NAME'}"
    stdscr.addnstr(2, 0, col_header, max(width - 1, 0))

    processes = get_sorted_filtered_snapshot(
        sort_by=sort_by,
        name_contains=name_contains,
        username=username,
        min_cpu=min_cpu,
    )

    max_rows = max(height - 4, 0)
    for row_idx, proc in enumerate(processes[:max_rows]):
        line = (
            f"{proc.pid:>7}  {proc.username[:12]:<12} {proc.cpu_percent:6.1f}  "
            f"{proc.memory_percent:6.1f}  {proc.status[:10]:<10} {proc.name}"
        )
        stdscr.addnstr(3 + row_idx, 0, line, max(width - 1, 0))

    stdscr.refresh()


def run_curses_ui(
    sort_by: str = "cpu",
    interval: float = 2.0,
    name_contains: Optional[str] = None,
    username: Optional[str] = None,
    min_cpu: Optional[float] = None,
) -> int:
    """Entry point used by monitor.py to launch the interactive UI."""

    def _main(stdscr):
        nonlocal sort_by
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(int(interval * 1000))

        while True:
            _draw(stdscr, sort_by, name_contains, username, min_cpu)
            ch = stdscr.getch()
            if ch in (ord("q"), 27):  # q or Esc
                break
            if ch in SORT_KEYS_BY_CHAR:
                sort_by = SORT_KEYS_BY_CHAR[ch]

    curses.wrapper(_main)
    return 0


if __name__ == "__main__":
    run_curses_ui()
