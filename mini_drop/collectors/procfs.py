from __future__ import annotations

import os
import time
from pathlib import Path

from .synthetic import synthetic_sample


def proc_exists(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def read_proc_sample(pid: int, prev: dict | None, interval: float) -> tuple[dict, dict]:
    stat_path = Path(f"/proc/{pid}/stat")
    status_path = Path(f"/proc/{pid}/status")
    io_path = Path(f"/proc/{pid}/io")
    if not stat_path.exists():
        raise ProcessLookupError(f"/proc/{pid} not found")

    stat = stat_path.read_text().split()
    utime = int(stat[13])
    stime = int(stat[14])
    ticks = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    total_time = (utime + stime) / ticks
    rss_mb = 0.0
    for line in status_path.read_text().splitlines():
        if line.startswith("VmRSS:"):
            rss_mb = float(line.split()[1]) / 1024
            break
    io_read = io_write = 0.0
    if io_path.exists():
        for line in io_path.read_text().splitlines():
            if line.startswith("read_bytes:"):
                io_read = float(line.split()[1]) / 1024
            elif line.startswith("write_bytes:"):
                io_write = float(line.split()[1]) / 1024

    if prev:
        cpu_pct = max(0.0, (total_time - prev["total_time"]) / max(interval, 0.001) * 100)
        io_read_kb = max(0.0, io_read - prev["io_read"])
        io_write_kb = max(0.0, io_write - prev["io_write"])
    else:
        cpu_pct = 0.0
        io_read_kb = 0.0
        io_write_kb = 0.0

    state = {"total_time": total_time, "io_read": io_read, "io_write": io_write}
    sample = {
        "ts": time.time(),
        "cpu_pct": round(cpu_pct, 2),
        "rss_mb": round(rss_mb, 2),
        "io_read_kb": round(io_read_kb, 2),
        "io_write_kb": round(io_write_kb, 2),
        "source": "procfs",
        "collector": "proc",
    }
    return sample, state


def collect_procfs(pid: int, duration: int, sample_rate: int, allow_synthetic: bool) -> list[dict]:
    interval = 1.0 / max(sample_rate, 1)
    count = max(1, min(duration * max(sample_rate, 1), 200))
    samples: list[dict] = []
    prev = None
    for idx in range(count):
        try:
            sample, prev = read_proc_sample(pid, prev, interval)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            if not allow_synthetic:
                raise ProcessLookupError(f"pid {pid} unavailable")
            sample = synthetic_sample(pid, idx)
        samples.append(sample)
        time.sleep(min(interval, 1.0))
    return samples
