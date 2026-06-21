from __future__ import annotations

import argparse
import json
import time
import urllib.request


def post_json(base_url: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Mini-Drop continuous profiling session and repeated window tasks.")
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    parser.add_argument("--pid", type=int, default=1)
    parser.add_argument("--windows", type=int, default=3)
    parser.add_argument("--duration", type=int, default=5)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--collector", default="proc", choices=["proc", "perf", "ebpf", "synthetic"])
    args = parser.parse_args()
    session = post_json(
        args.server,
        "/api/continuous/sessions",
        {"pid": args.pid, "collector": args.collector, "interval": args.interval, "duration": args.duration},
    )["session"]
    print(f"session={session['id']} collector={session['collector']} interval={session['interval_sec']}s")
    created = []
    for idx in range(args.windows):
        payload = {
            "pid": args.pid,
            "duration": args.duration,
            "sample_rate": 1,
            "collector": args.collector,
            "session_id": session["id"],
        }
        result = post_json(args.server, "/api/tasks", payload)
        created.append(result["task"]["id"])
        print(f"window={idx + 1} task={result['task']['id']}")
        if idx != args.windows - 1:
            time.sleep(args.interval)
    print("created_tasks=" + ",".join(created))
    print(f"window_api=/api/continuous/window?session_id={session['id']}&from=<start_ts>&to=<end_ts>")


if __name__ == "__main__":
    main()
