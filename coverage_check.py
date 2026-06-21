from __future__ import annotations

import sys
import trace
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGETS = [
    ROOT / "mini_drop" / "store.py",
    ROOT / "mini_drop" / "analyzer.py",
    ROOT / "mini_drop" / "perf_importer.py",
    ROOT / "mini_drop" / "collectors" / "__init__.py",
    ROOT / "mini_drop" / "collectors" / "procfs.py",
    ROOT / "mini_drop" / "collectors" / "synthetic.py",
    ROOT / "mini_drop" / "collectors" / "perf.py",
    ROOT / "mini_drop" / "collectors" / "ebpf.py",
]


def main() -> None:
    tracer = trace.Trace(count=True, trace=False, ignoredirs=[sys.prefix, sys.exec_prefix])
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))

    def run_suite() -> None:
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            raise SystemExit(1)

    tracer.runfunc(run_suite)

    results = tracer.results()
    counts = results.counts
    total_lines = 0
    hit_lines = 0
    for path in TARGETS:
        executable = [
            idx
            for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if line.strip() and not line.strip().startswith("#")
        ]
        hits = {lineno for (filename, lineno), count in counts.items() if Path(filename).resolve() == path.resolve() and count > 0}
        total_lines += len(executable)
        hit_lines += len(set(executable) & hits)
    pct = hit_lines / max(total_lines, 1) * 100
    print(f"mini_drop_core_coverage={pct:.1f}% ({hit_lines}/{total_lines} executable lines)")
    if pct < 50:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
