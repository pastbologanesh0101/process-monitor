"""
Unit tests for core.py - the testable (non-curses) part of Linux Process
Monitor.

These tests run against the real, current process list on the machine via
psutil. That is safe because we only ever read process data (pid, name,
cpu%, memory%, status, user) -- we never assert exact fixed values, only
structural/invariant properties that must hold on any machine (this dev
box, or an ubuntu-latest CI runner).
"""

from __future__ import annotations

import unittest

from core import (
    ProcessInfo,
    filter_processes,
    get_process_snapshot,
    get_sorted_filtered_snapshot,
    get_system_summary,
    sort_processes,
    top_n,
)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_returns_well_formed_records(self):
        processes = get_process_snapshot()
        self.assertGreater(len(processes), 0, "expected at least one process")

        for proc in processes[:25]:
            self.assertIsInstance(proc, ProcessInfo)
            self.assertIsInstance(proc.pid, int)
            self.assertGreaterEqual(proc.pid, 0)
            self.assertIsInstance(proc.name, str)
            self.assertIsInstance(proc.username, str)
            self.assertIsInstance(proc.cpu_percent, float)
            self.assertIsInstance(proc.memory_percent, float)
            self.assertIsInstance(proc.status, str)
            self.assertGreaterEqual(proc.cpu_percent, 0.0)
            self.assertGreaterEqual(proc.memory_percent, 0.0)

    def test_snapshot_pids_are_unique(self):
        processes = get_process_snapshot()
        pids = [p.pid for p in processes]
        self.assertEqual(len(pids), len(set(pids)))


class TestSort(unittest.TestCase):
    def setUp(self):
        self.processes = get_process_snapshot()

    def test_sort_by_cpu_is_descending(self):
        result = sort_processes(self.processes, sort_by="cpu")
        cpu_values = [p.cpu_percent for p in result]
        self.assertEqual(cpu_values, sorted(cpu_values, reverse=True))

    def test_sort_by_memory_is_descending(self):
        result = sort_processes(self.processes, sort_by="memory")
        mem_values = [p.memory_percent for p in result]
        self.assertEqual(mem_values, sorted(mem_values, reverse=True))

    def test_sort_by_pid_is_ascending(self):
        result = sort_processes(self.processes, sort_by="pid")
        pid_values = [p.pid for p in result]
        self.assertEqual(pid_values, sorted(pid_values))

    def test_sort_preserves_length_and_rejects_invalid_key(self):
        result = sort_processes(self.processes, sort_by="cpu")
        self.assertEqual(len(result), len(self.processes))
        with self.assertRaises(ValueError):
            sort_processes(self.processes, sort_by="bogus")


class TestFilter(unittest.TestCase):
    def setUp(self):
        self.processes = get_process_snapshot()

    def test_name_filter_narrows_results(self):
        # Every process name contains at least one character; filtering by
        # that character's process's own name (lowercased) must return a
        # subset that all contain the substring, and must not grow the set.
        sample = self.processes[0]
        needle = sample.name[:2] if len(sample.name) >= 2 else sample.name
        if not needle:
            self.skipTest("sample process has empty name")

        filtered = filter_processes(self.processes, name_contains=needle)
        self.assertLessEqual(len(filtered), len(self.processes))
        for proc in filtered:
            self.assertIn(needle.lower(), proc.name.lower())

    def test_name_filter_with_nonexistent_substring_returns_empty(self):
        filtered = filter_processes(
            self.processes, name_contains="zzzz_definitely_not_a_process_zzzz"
        )
        self.assertEqual(filtered, [])

    def test_min_cpu_filter_narrows_results(self):
        filtered = filter_processes(self.processes, min_cpu=10_000.0)
        self.assertEqual(filtered, [])

        filtered_all = filter_processes(self.processes, min_cpu=0.0)
        self.assertEqual(len(filtered_all), len(self.processes))
        for proc in filtered_all:
            self.assertGreaterEqual(proc.cpu_percent, 0.0)

    def test_username_filter_matches_exact_owner(self):
        if not self.processes:
            self.skipTest("no processes to test against")
        owner = self.processes[0].username
        filtered = filter_processes(self.processes, username=owner)
        self.assertGreaterEqual(len(filtered), 1)
        for proc in filtered:
            self.assertEqual(proc.username, owner)


class TestTopN(unittest.TestCase):
    def test_top_n_limits_results(self):
        processes = get_process_snapshot()
        limited = top_n(processes, 3)
        self.assertLessEqual(len(limited), 3)
        self.assertEqual(limited, processes[:3])

    def test_top_n_rejects_negative(self):
        processes = get_process_snapshot()
        with self.assertRaises(ValueError):
            top_n(processes, -1)

    def test_top_n_larger_than_list_returns_whole_list(self):
        processes = get_process_snapshot()
        limited = top_n(processes, len(processes) + 1000)
        self.assertEqual(len(limited), len(processes))


class TestSystemSummary(unittest.TestCase):
    def test_summary_fields_present_and_sane(self):
        summary = get_system_summary()
        self.assertGreaterEqual(summary.cpu_percent, 0.0)
        self.assertGreater(summary.memory_total, 0)
        self.assertGreaterEqual(summary.memory_used, 0)
        self.assertLessEqual(summary.memory_used, summary.memory_total)
        self.assertGreaterEqual(summary.memory_percent, 0.0)
        self.assertLessEqual(summary.memory_percent, 100.0)
        self.assertGreater(summary.process_count, 0)
        # load_average is either a 3-tuple of floats, or None on platforms
        # where psutil.getloadavg() is unsupported.
        if summary.load_average is not None:
            self.assertEqual(len(summary.load_average), 3)
            for val in summary.load_average:
                self.assertIsInstance(val, float)
                self.assertGreaterEqual(val, 0.0)


class TestCombinedHelper(unittest.TestCase):
    def test_get_sorted_filtered_snapshot_applies_top(self):
        result = get_sorted_filtered_snapshot(sort_by="cpu", top=5)
        self.assertLessEqual(len(result), 5)
        cpu_values = [p.cpu_percent for p in result]
        self.assertEqual(cpu_values, sorted(cpu_values, reverse=True))

    def test_get_sorted_filtered_snapshot_combines_filters(self):
        result = get_sorted_filtered_snapshot(sort_by="pid", min_cpu=0.0, top=10)
        self.assertLessEqual(len(result), 10)
        pid_values = [p.pid for p in result]
        self.assertEqual(pid_values, sorted(pid_values))


if __name__ == "__main__":
    unittest.main()
