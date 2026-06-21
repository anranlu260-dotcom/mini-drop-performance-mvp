from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path


class BpftraceCollector:
    def __init__(self, bpftrace_path: str | None = None, runner=None, script_path: Path | None = None):
        self.bpftrace_path = bpftrace_path
        self.runner = runner or self._run
        self.script_path = script_path or Path(__file__).resolve().parents[2] / "linux_validation" / "bpftrace_io_latency.bt"

    def collect(self, pid: int, duration: int, sample_rate: int) -> list[dict]:
        bpftrace = self.bpftrace_path or shutil.which("bpftrace")
        if not bpftrace:
            from . import CollectorUnavailable

            raise CollectorUnavailable("bpftrace unavailable: install bpftrace and run with eBPF permissions")
        if not self.script_path.exists():
            from . import CollectorUnavailable

            raise CollectorUnavailable(f"bpftrace script not found: {self.script_path}")
        output = self.runner([bpftrace, str(self.script_path)], timeout=max(duration, 1))
        return [
            {
                "ts": time.time(),
                "cpu_pct": 0.0,
                "rss_mb": 0.0,
                "io_read_kb": 0.0,
                "io_write_kb": 0.0,
                "source": "ebpf-bpftrace",
                "collector": "ebpf",
                "pid": pid,
                "sample_rate": sample_rate,
                "raw_output": output[-4000:],
                "note": "bpftrace output captured; use saved terminal log for full eBPF evidence",
            }
        ]

    @staticmethod
    def _run(cmd: list[str], timeout: int) -> str:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
        return (result.stdout + "\n" + result.stderr).strip()
