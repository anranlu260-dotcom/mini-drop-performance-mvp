from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from agent import post_json, run_task
from mini_drop.store import Store
from server import make_handler


class E2ETest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "e2e.sqlite3")
        handler = make_handler(self.store, Path(__file__).resolve().parents[1] / "web")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()
        self.store.close()
        self.tmp.cleanup()

    def get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_normal_path_done_with_analysis(self) -> None:
        task = self.store.create_task(pid=999999, duration=1, sample_rate=2)
        self.store.heartbeat("a1", "host", "127.0.0.1", "test")
        claimed = self.store.claim_next_task("a1")
        run_task(self.base, claimed, allow_synthetic=True)
        detail = self.get_json(f"/api/tasks/{task['id']}")
        self.assertEqual(detail["task"]["status"], "DONE")
        self.assertIsNotNone(detail["analysis"])
        self.assertGreaterEqual(len(detail["transitions"]), 4)

    def test_invalid_pid_failure_path(self) -> None:
        task = self.store.create_task(pid=999999, duration=1, sample_rate=1)
        self.store.transition_task(task["id"], "RUNNING", "claimed", assigned_agent="a1")
        run_task(self.base, task, allow_synthetic=False)
        detail = self.get_json(f"/api/tasks/{task['id']}")
        self.assertEqual(detail["task"]["status"], "FAILED")
        self.assertIn("pid", detail["task"]["reason"])

    def test_perf_collector_failure_is_visible_on_task(self) -> None:
        task = self.store.create_task(pid=1, duration=1, sample_rate=1, collector="perf")
        self.store.transition_task(task["id"], "RUNNING", "claimed", assigned_agent="a1")
        with mock.patch("mini_drop.collectors.perf.shutil.which", return_value=None):
            run_task(self.base, task, allow_synthetic=True)
        detail = self.get_json(f"/api/tasks/{task['id']}")
        self.assertEqual(detail["task"]["status"], "FAILED")
        self.assertIn("perf unavailable", detail["task"]["reason"])

    def test_offline_audit_path(self) -> None:
        post_json(self.base, "/api/agent/heartbeat", {"agent_id": "a2", "hostname": "host", "ip": "127.0.0.1", "version": "test"})
        self.store.conn.execute("UPDATE agents SET last_heartbeat=? WHERE id='a2'", (time.time() - 60,))
        agents = self.get_json("/api/agents")
        self.assertEqual(agents["agents"][0]["online"], 0)
        self.assertTrue(any(a["kind"] == "AGENT_OFFLINE" for a in agents["audits"]))


if __name__ == "__main__":
    unittest.main()
