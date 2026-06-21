from __future__ import annotations

import argparse
import json
import os
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    parser.add_argument("--pid", type=int, default=os.getpid())
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--sample-rate", type=int, default=1)
    args = parser.parse_args()
    payload = {
        "pid": args.pid,
        "duration": args.duration,
        "sample_rate": args.sample_rate,
        "collector": "proc",
    }
    req = urllib.request.Request(
        args.server.rstrip("/") + "/api/tasks",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(resp.read().decode("utf-8"))


if __name__ == "__main__":
    main()
