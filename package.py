from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "陆安然+Mini-Drop最终提交.zip"
SKIP_SUFFIXES = {".sqlite3", ".sqlite3-shm", ".sqlite3-wal", ".pyc"}
SKIP_DIRS = {"__pycache__", ".pycache"}


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    with ZipFile(OUT, "w", ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            if path.is_dir():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in SKIP_SUFFIXES:
                continue
            zf.write(path, path.relative_to(ROOT.parent).as_posix())
    print(OUT)


if __name__ == "__main__":
    main()
