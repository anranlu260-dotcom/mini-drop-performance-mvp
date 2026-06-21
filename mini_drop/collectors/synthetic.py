from __future__ import annotations

import math
import time


def synthetic_sample(pid: int, idx: int, source: str = "synthetic-demo") -> dict:
    return {
        "ts": time.time(),
        "cpu_pct": round(20 + 30 * abs(math.sin(idx / 2)), 2),
        "rss_mb": round(64 + 8 * idx + 4 * math.cos(idx), 2),
        "io_read_kb": round(4 * idx, 2),
        "io_write_kb": round(2 * idx, 2),
        "source": source,
        "note": f"/proc/{pid} unavailable; emitted deterministic demo sample",
    }


def collect_synthetic(pid: int, duration: int, sample_rate: int, source: str = "synthetic-demo") -> list[dict]:
    count = max(1, min(duration * max(sample_rate, 1), 200))
    return [synthetic_sample(pid, idx, source=source) for idx in range(count)]
