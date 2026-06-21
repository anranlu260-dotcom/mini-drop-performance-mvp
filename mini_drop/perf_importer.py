from __future__ import annotations

import re
import time
from typing import Any


HEADER_RE = re.compile(r"^\S+\s+(?P<pid>\d+)\s+(?P<ts>\d+(?:\.\d+)?):")


def parse_perf_script(text: str) -> list[dict[str, Any]]:
    """Convert a small perf script stack dump into analyzer samples.

    The parser intentionally accepts the common `perf script` text shape:
    an event header line followed by indented symbol frames and a blank line.
    It is not a full perf parser; it is a bridge from Linux validation output
    into the Mini-Drop analyzer evidence path.
    """
    samples: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    stack: list[str] = []

    def flush() -> None:
        nonlocal current, stack
        if current and stack:
            sample = dict(current)
            sample["stack"] = list(stack)
            sample["weight"] = 1.0
            sample["cpu_pct"] = 1.0
            sample["rss_mb"] = 0.0
            sample["io_read_kb"] = 0.0
            sample["io_write_kb"] = 0.0
            sample["source"] = "perf-script-import"
            samples.append(sample)
        current = None
        stack = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            flush()
            continue
        header = HEADER_RE.match(line)
        if header:
            flush()
            current = {
                "pid": int(header.group("pid")),
                "ts": float(header.group("ts")),
            }
            continue
        if current and raw_line[:1].isspace():
            symbol = _symbol_from_frame(line)
            if symbol:
                stack.append(symbol)

    flush()
    return samples


def _symbol_from_frame(line: str) -> str:
    parts = line.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return parts[1].split("+", 1)[0]


def load_perf_script(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        samples = parse_perf_script(fh.read())
    now = time.time()
    for idx, sample in enumerate(samples):
        sample.setdefault("ts", now + idx)
    return samples
