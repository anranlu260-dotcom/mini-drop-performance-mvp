from __future__ import annotations

import shutil
import tempfile
import unittest
import time
from pathlib import Path
from unittest import mock

from mini_drop.collectors import CollectorUnavailable, collect_samples
from mini_drop.collectors.ebpf import BpftraceCollector
from mini_drop.collectors.perf import PerfCollector
from mini_drop.collectors.procfs import collect_procfs, proc_exists
from mini_drop.collectors.synthetic import collect_synthetic


class CollectorTest(unittest.TestCase):
    def test_perf_collector_fails_with_clear_reason_when_perf_missing(self) -> None:
        with mock.patch.object(shutil, "which", return_value=None):
            with self.assertRaises(CollectorUnavailable) as ctx:
                collect_samples({"pid": 1234, "duration": 1, "sample_rate": 1, "collector": "perf"}, allow_synthetic=False)
        self.assertIn("perf unavailable", str(ctx.exception))

    def test_perf_collector_parses_perf_script_from_runner(self) -> None:
        def fake_run(cmd: list[str], cwd: str | None = None) -> str:
            if cmd[:2] == ["perf", "record"]:
                return "recorded"
            if cmd[:2] == ["perf", "script"]:
                return (
                    "python 1234 111.111: cycles:\n"
                    "        7fffaaa runtime_eval\n"
                    "        7fffbbb handle_request\n"
                    "        7fffccc hot_loop\n\n"
                )
            raise AssertionError(cmd)

        collector = PerfCollector(perf_path="perf", runner=fake_run)
        samples = collector.collect(pid=1234, duration=1, sample_rate=99)
        self.assertEqual(samples[0]["source"], "perf-script-import")
        self.assertEqual(samples[0]["stack"], ["runtime_eval", "handle_request", "hot_loop"])
        self.assertEqual(samples[0]["collector"], "perf")

    def test_perf_collector_reports_empty_perf_script(self) -> None:
        def fake_run(cmd: list[str], cwd: str | None = None) -> str:
            return ""

        collector = PerfCollector(perf_path="perf", runner=fake_run)
        with self.assertRaises(CollectorUnavailable) as ctx:
            collector.collect(pid=1234, duration=1, sample_rate=99)
        self.assertIn("no stack samples", str(ctx.exception))

    def test_ebpf_collector_fails_with_clear_reason_when_bpftrace_missing(self) -> None:
        with mock.patch.object(shutil, "which", return_value=None):
            with self.assertRaises(CollectorUnavailable) as ctx:
                collect_samples({"pid": 1, "duration": 1, "sample_rate": 1, "collector": "ebpf"}, allow_synthetic=False)
        self.assertIn("bpftrace unavailable", str(ctx.exception))

    def test_ebpf_collector_captures_runner_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "probe.bt"
            script.write_text("BEGIN { printf(\"ok\") }\n", encoding="utf-8")
            collector = BpftraceCollector(bpftrace_path="bpftrace", script_path=script, runner=lambda cmd, timeout: "latency histogram")
            samples = collector.collect(pid=55, duration=1, sample_rate=1)
        self.assertEqual(samples[0]["source"], "ebpf-bpftrace")
        self.assertIn("latency", samples[0]["raw_output"])
        self.assertEqual(samples[0]["collector"], "ebpf")

    def test_synthetic_and_procfs_fallback_collectors(self) -> None:
        samples = collect_synthetic(pid=999999, duration=1, sample_rate=3, source="synthetic-test")
        self.assertEqual(len(samples), 3)
        self.assertEqual(samples[0]["source"], "synthetic-test")
        self.assertIsInstance(proc_exists(1), bool)
        start = time.time()
        fallback = collect_procfs(pid=999999, duration=1, sample_rate=1, allow_synthetic=True)
        self.assertGreaterEqual(fallback[0]["ts"], start)
        self.assertEqual(fallback[0]["source"], "synthetic-demo")

    def test_unknown_collector_fails_clearly(self) -> None:
        with self.assertRaises(CollectorUnavailable) as ctx:
            collect_samples({"pid": 1, "duration": 1, "sample_rate": 1, "collector": "unknown"}, allow_synthetic=True)
        self.assertIn("unsupported", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
