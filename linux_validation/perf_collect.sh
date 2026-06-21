#!/usr/bin/env bash
set -euo pipefail

PID="${1:-}"
DURATION="${2:-10}"
HZ="${3:-99}"
OUT_DIR="${4:-linux_validation/out}"

if [[ -z "$PID" ]]; then
  echo "usage: $0 <pid> [duration_sec] [hz] [out_dir]" >&2
  exit 2
fi

mkdir -p "$OUT_DIR"
echo "[mini-drop] collecting perf pid=$PID duration=$DURATION hz=$HZ"
perf record -F "$HZ" -g -p "$PID" -o "$OUT_DIR/perf.data" -- sleep "$DURATION"
perf script -i "$OUT_DIR/perf.data" > "$OUT_DIR/perf.script.txt"
echo "[mini-drop] wrote $OUT_DIR/perf.data and $OUT_DIR/perf.script.txt"

