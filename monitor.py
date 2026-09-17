#!/usr/bin/env python3
"""
Linux Process Monitor - one-shot CLI entry point.

Usage:
    python monitor.py --once --sort cpu --top 10
    python monitor.py --once --sort memory --filter-name python
    python monitor.py --once --min-cpu 0.5 --user root

Without --once, this launches the interactive curses UI (see
monitor_curses.py). The one-shot mode never touches curses and never
requires a TTY, which is what makes it safe to script and test.
"""

from __future__ import annotations

import argparse
import sys

from core import (
    VALID_SORT_KEYS,
    get_sorted_filtered_snapshot,
    get_system_summary,
)


def format_bytes(n: int) -> str:
    """Human-readable byte count, e.g. 1234567 -> '1.18 GB'."""
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < step:
            return f"{n:.2f} {unit}"
        n /= step
    return f"{n:.2f} PB"


def render_summary(summary) -> str:
    lines = []
    lines.append(
        f"CPU: {summary.cpu_percent:5.1f}%   "
        f"Mem: {format_bytes(summary.memory_used)} / "
        f"{format_bytes(summary.memory_total)} "
        f"({summary.memory_percent:.1f}%)   "
        f"Processes: {summary.process_count}"
    )
    if summary.load_average is not None:
        la1, la5, la15 = summary.load_average
        lines.append(f"Load average: {la1:.2f} {la5:.2f} {la15:.2f}")
    else:
        lines.append("Load average: not available on this platform")
    return "\n".join(lines)


def render_table(processes) -> str:
    header = f"{'PID':>7}  {'USER':<12} {'CPU%':>6}  {'MEM%':>6}  {'STATUS':<10} {'NAME'}"
    rows = [header, "-" * len(header)]
    for p in processes:
        rows.append(
            f"{p.pid:>7}  {p.username[:12]:<12} {p.cpu_percent:6.1f}  "
            f"{p.memory_percent:6.1f}  {p.status[:10]:<10} {p.name}"
        )
    return "\n".join(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="monitor.py",
        description="Linux Process Monitor - a top-like process viewer built on psutil.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print a single snapshot and exit (no curses / TTY required).",
    )
    parser.add_argument(
        "--sort",
        choices=VALID_SORT_KEYS,
        default="cpu",
        help="Column to sort by (default: cpu).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Only show the top N processes after sorting/filtering.",
    )
    parser.add_argument(
        "--filter-name",
        dest="filter_name",
        default=None,
        help="Only show processes whose name contains this substring.",
    )
    parser.add_argument(
        "--user",
        dest="user",
        default=None,
        help="Only show processes owned by this username.",
    )
    parser.add_argument(
        "--min-cpu",
        dest="min_cpu",
        type=float,
        default=None,
        help="Only show processes with at least this CPU percent.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Refresh interval in seconds for interactive mode (default: 2.0).",
    )
    return parser


def run_once(args) -> None:
    summary = get_system_summary()
    processes = get_sorted_filtered_snapshot(
        sort_by=args.sort,
        name_contains=args.filter_name,
        username=args.user,
        min_cpu=args.min_cpu,
        top=args.top,
    )
    print(render_summary(summary))
    print()
    print(render_table(processes))


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.once:
        run_once(args)
        return 0

    # Interactive mode: hand off to the curses UI.
    try:
        from monitor_curses import run_curses_ui
    except ImportError as exc:  # pragma: no cover - defensive
        print(f"Could not load interactive UI: {exc}", file=sys.stderr)
        return 1

    return run_curses_ui(
        sort_by=args.sort,
        interval=args.interval,
        name_contains=args.filter_name,
        username=args.user,
        min_cpu=args.min_cpu,
    )


if __name__ == "__main__":
    sys.exit(main())
