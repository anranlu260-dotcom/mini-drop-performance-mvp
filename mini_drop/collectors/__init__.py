from __future__ import annotations

from typing import Any

from .ebpf import BpftraceCollector
from .perf import PerfCollector
from .procfs import collect_procfs, proc_exists, read_proc_sample
from .synthetic import collect_synthetic, synthetic_sample


class CollectorUnavailable(RuntimeError):
    pass


def collect_samples(task: dict[str, Any], allow_synthetic: bool) -> list[dict[str, Any]]:
    collector = str(task.get("collector", "proc"))
    pid = int(task["pid"])
    duration = int(task["duration"])
    sample_rate = int(task["sample_rate"])

    if collector in {"proc", "procfs", "continuous-demo"}:
        return collect_procfs(pid, duration, sample_rate, allow_synthetic=allow_synthetic)
    if collector in {"synthetic", "synthetic-ebpf", "synthetic-pyspy"}:
        return collect_synthetic(pid, duration, sample_rate, source=collector)
    if collector == "perf":
        return PerfCollector().collect(pid, duration, sample_rate)
    if collector == "ebpf":
        return BpftraceCollector().collect(pid, duration, sample_rate)
    raise CollectorUnavailable(f"collector {collector} unsupported")
