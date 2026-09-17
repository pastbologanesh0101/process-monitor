# Linux Process Monitor

A `top`-like process monitor CLI written in Python, built on top of
[`psutil`](https://github.com/giampaolo/psutil) so it works cross-platform
(Linux, macOS, Windows) even though it's designed with Linux servers in
mind. Ships with both a live, curses-based interactive UI and a
non-interactive one-shot mode you can script or pipe.

## Features

- **Process snapshots** — pid, name, owning user, CPU%, memory%, and status
  for every process you have permission to see.
- **Sorting** by CPU%, memory%, or PID.
- **Filtering** by process name substring, exact username, and/or a minimum
  CPU% threshold.
- **Top-N limiting** to only show the busiest N processes.
- **System summary** — overall CPU%, memory used/total, load average (when
  the platform supports it), and total process count.
- **Interactive curses UI** (`monitor_curses.py`) — a live-refreshing table
  with keybindings to change the sort column or quit.
- **One-shot CLI mode** (`--once`) — prints a single snapshot and exits, no
  terminal/TTY required, so it's safe to script and unit test.

The core logic (`core.py`) has zero curses/TTY dependency, which is what
makes it independently testable. The curses rendering (`monitor_curses.py`)
is kept intentionally thin — it just draws whatever `core.py` computes.

## Installation

```bash
git clone https://github.com/pastbologanesh0101/process-monitor.git
cd process-monitor
pip install -r requirements.txt
```

Requires Python 3.11+ and `psutil`.

## Usage

### Interactive mode (requires a real terminal)

```bash
python monitor.py
```

Launches the live, auto-refreshing curses UI. Keybindings:

| Key       | Action            |
|-----------|-------------------|
| `c`       | Sort by CPU%      |
| `m`       | Sort by memory%   |
| `p`       | Sort by PID       |
| `q` / Esc | Quit              |

Optional flags: `--interval 1.5` to change the refresh rate (seconds),
plus any of the filter flags below.

### One-shot mode (no TTY needed — great for scripts/cron/CI)

```bash
python monitor.py --once --sort cpu --top 10
```

Other flags:

```bash
python monitor.py --once --sort memory --filter-name python
python monitor.py --once --sort cpu --user root --min-cpu 0.5
```

| Flag             | Meaning                                              |
|-------------------|-------------------------------------------------------|
| `--once`          | Print one snapshot and exit                          |
| `--sort`          | `cpu`, `memory`, or `pid` (default: `cpu`)           |
| `--top N`         | Only show the top N processes                        |
| `--filter-name X` | Only processes whose name contains substring `X`      |
| `--user X`        | Only processes owned by user `X`                      |
| `--min-cpu X`     | Only processes with CPU% >= `X`                       |
| `--interval N`    | Refresh interval in seconds (interactive mode only)   |

### Example one-shot output

```
$ python monitor.py --once --sort cpu --top 10
CPU:   0.0%   Mem: 6.67 GB / 16.00 GB (72.3%)   Processes: 816
Load average: 2.10 2.18 2.03

    PID  USER           CPU%    MEM%  STATUS     NAME
-----------------------------------------------------
  68716  vishwanathan   22.0     4.0  running    Google Chrome Helper (Renderer)
   1477  vishwanathan   20.1     1.2  running    Google Chrome Helper
  68750  vishwanathan    6.5     0.1  running    Python
  16917  vishwanathan    1.3     0.7  running    Terminal
  68533  vishwanathan    0.5     4.6  running    Google Chrome Helper (Renderer)
  64805  vishwanathan    0.3     2.2  running    WhatsApp
   1014  vishwanathan    0.2     0.1  running    cloudd
   1411  vishwanathan    0.2     3.7  running    Google Chrome
   1605  vishwanathan    0.2     0.6  running    Raycast
  31572  vishwanathan    0.2     1.2  running    2.1.273
```

(Captured on macOS during development — on Linux you'd see kernel threads,
systemd units, etc. instead, but the shape of the output is identical.)

## Project layout

```
core.py            # Snapshot/sort/filter/summary logic (fully unit tested)
monitor.py         # One-shot CLI + entry point for the interactive UI
monitor_curses.py  # Thin curses rendering layer (requires a real TTY)
test_core.py       # Unit tests for core.py
requirements.txt
LICENSE
```

## Running the tests

```bash
pip install -r requirements.txt
python -m unittest discover -v
```

Tests read the real, live process list via `psutil` (safe — read-only) and
assert structural invariants (well-formed records, correct sort order,
correct filtering, sane summary numbers) rather than exact fixed values, so
they pass consistently across machines and CI runners.

Continuous integration runs the same test suite on `ubuntu-latest` against
Python 3.11 and 3.12 via `.github/workflows/tests.yml`.

## Why psutil instead of parsing `/proc`?

`psutil` gives the same API on Linux, macOS, and Windows, which means this
project can be developed and unit tested on any machine while still being
a genuinely useful Linux process monitor in production — and it's what
lets CI run correctly on `ubuntu-latest` without any platform-specific
branches in the core logic.

## License

MIT — see [LICENSE](LICENSE).
