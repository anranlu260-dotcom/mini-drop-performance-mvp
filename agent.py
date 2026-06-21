from __future__ import annotations

import argparse
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from mini_drop.collectors import CollectorUnavailable, collect_samples
from mini_drop.collectors.procfs import proc_exists, read_proc_sample
from mini_drop.collectors.synthetic import synthetic_sample


VERSION = "mini-drop-agent/0.1"


def post_json(base_url: str, path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(base_url: str, path: str, query: dict | None = None) -> dict:
    url = base_url + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_task(base_url: str, task: dict, allow_synthetic: bool) -> None:
    task_id = task["id"]
    try:
        samples = collect_samples(task, allow_synthetic=allow_synthetic)
    except (CollectorUnavailable, FileNotFoundError, ProcessLookupError, PermissionError, RuntimeError) as exc:
        post_json(base_url, f"/api/tasks/{task_id}/complete", {"success": False, "reason": str(exc)})
        return

    for sample in samples:
        sample.setdefault("collector", task.get("collector", "proc"))

    batch = []
    for sample in samples:
        batch.append(sample)
        if len(batch) >= 5:
            post_json(base_url, f"/api/tasks/{task_id}/samples", {"samples": batch})
            batch.clear()

    if batch:
        post_json(base_url, f"/api/tasks/{task_id}/samples", {"samples": batch})
    post_json(base_url, f"/api/tasks/{task_id}/complete", {"success": True, "reason": "agent completed sampling and analyzer generated result"})


def loop(base_url: str, agent_id: str, once: bool, allow_synthetic: bool) -> None:
    hostname = socket.gethostname()
    ip = "127.0.0.1"
    while True:
        try:
            post_json(
                base_url,
                "/api/agent/heartbeat",
                {"agent_id": agent_id, "hostname": hostname, "ip": ip, "version": VERSION},
            )
            payload = get_json(base_url, "/api/agent/next", {"agent_id": agent_id})
            task = payload.get("task")
            if task:
                run_task(base_url, task, allow_synthetic=allow_synthetic)
                if once:
                    return
        except urllib.error.URLError as exc:
            print(json.dumps({"level": "error", "message": f"server unavailable: {exc}"}, ensure_ascii=False))
        if once:
            return
        time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=os.environ.get("MINI_DROP_SERVER", "http://127.0.0.1:8080"))
    parser.add_argument("--agent-id", default=os.environ.get("MINI_DROP_AGENT_ID", "agent-local"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--allow-synthetic", action="store_true", default=os.environ.get("MINI_DROP_ALLOW_SYNTHETIC", "1") == "1")
    args = parser.parse_args()
    loop(args.server.rstrip("/"), args.agent_id, args.once, args.allow_synthetic)


if __name__ == "__main__":
    main()
