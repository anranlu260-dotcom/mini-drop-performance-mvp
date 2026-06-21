from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from mini_drop.perf_importer import parse_perf_script


class PerfCollector:
    def __init__(self, perf_path: str | None = None, runner=None):
        self.perf_path = perf_path
        self.runner = runner or self._run

    def collect(self, pid: int, duration: int, sample_rate: int) -> list[dict]:
        perf = self.perf_path or shutil.which("perf")
        if not perf:
            from . import CollectorUnavailable

            raise CollectorUnavailable("perf unavailable: install linux-tools/perf and run on Linux")
        with tempfile.TemporaryDirectory(prefix="mini-drop-perf-") as tmp:
            out = Path(tmp) / "perf.data"
            self.runner([perf, "record", "-F", str(sample_rate), "-g", "-p", str(pid), "-o", str(out), "--", "sleep", str(duration)])
            script = self.runner([perf, "script", "-i", str(out)])
        samples = parse_perf_script(script)
        for sample in samples:
            sample["collector"] = "perf"
        if not samples:
            from . import CollectorUnavailable

            raise CollectorUnavailable("perf produced no stack samples")
        return samples

    @staticmethod
    def _run(cmd: list[str], cwd: str | None = None) -> str:
        result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "command failed").strip())
        return result.stdout
