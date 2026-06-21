from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from agent import get_json, loop, proc_exists, synthetic_sample
from mini_drop.analyzer import build_analysis
from mini_drop.store import Store
from server import make_handler


class ApiAndAgentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "api.sqlite3")
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

    def post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_http_create_task_and_static_index(self) -> None:
        created = self.post("/api/tasks", {"pid": 1, "duration": 2, "sample_rate": 1, "collector": "proc"})
        self.assertEqual(created["task"]["status"], "PENDING")
        with urllib.request.urlopen(self.base + "/", timeout=10) as resp:
            html = resp.read().decode("utf-8")
        self.assertIn("Mini-Drop", html)

    def test_http_bad_request_and_not_found(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as bad:
            self.post("/api/tasks", {"pid": 1, "duration": 0, "sample_rate": 1})
        self.assertEqual(bad.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(self.base + "/api/tasks/nope", timeout=10)
        self.assertEqual(missing.exception.code, 404)

    def test_continuous_session_api_and_window(self) -> None:
        created = self.post("/api/continuous/sessions", {"pid": 1, "collector": "proc", "interval": 5, "duration": 2})
        session = created["session"]
        task = self.post(
            "/api/tasks",
            {"pid": 1, "duration": 2, "sample_rate": 1, "collector": "proc", "session_id": session["id"]},
        )["task"]
        with urllib.request.urlopen(
            self.base + f"/api/continuous/window?session_id={session['id']}&from={task['created_at'] - 1}&to={task['created_at'] + 1}",
            timeout=10,
        ) as resp:
            window = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(window["tasks"][0]["id"], task["id"])
        with urllib.request.urlopen(self.base + "/api/continuous/sessions", timeout=10) as resp:
            sessions = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(sessions["sessions"][0]["id"], session["id"])

    def test_agent_loop_once_registers_without_task(self) -> None:
        loop(self.base, "loop-agent", once=True, allow_synthetic=True)
        agents = get_json(self.base, "/api/agents")
        self.assertEqual(agents["agents"][0]["id"], "loop-agent")

    def test_agent_helpers_and_analyzer_branches(self) -> None:
        self.assertIsInstance(proc_exists(1), bool)
        sample = synthetic_sample(999999, 3)
        self.assertEqual(sample["source"], "synthetic-demo")
        analysis = build_analysis(
            {"id": "t1", "pid": 1, "collector": "proc"},
            [
                {"ts": 1, "cpu_pct": 95, "rss_mb": 2048},
                {"ts": 2, "cpu_pct": 30, "rss_mb": 512},
                {"ts": 3, "cpu_pct": 10, "rss_mb": 128},
                {"ts": 4, "cpu_pct": 5, "rss_mb": 64},
            ],
        )
        self.assertIn("CPU", " ".join(analysis["diagnosis"]))
        self.assertGreaterEqual(len(analysis["hotspots"]), 1)

    def test_analyzer_uses_perf_script_stack_samples(self) -> None:
        analysis = build_analysis(
            {"id": "t-perf", "pid": 4321, "collector": "perf-script-import"},
            [
                {
                    "ts": 1,
                    "cpu_pct": 1,
                    "rss_mb": 10,
                    "source": "perf-script-import",
                    "stack": ["python", "handle_request", "hot_loop"],
                },
                {
                    "ts": 2,
                    "cpu_pct": 1,
                    "rss_mb": 10,
                    "source": "perf-script-import",
                    "stack": ["python", "handle_request", "hot_loop"],
                },
                {
                    "ts": 3,
                    "cpu_pct": 1,
                    "rss_mb": 10,
                    "source": "perf-script-import",
                    "stack": ["python", "flush_metrics"],
                },
            ],
        )
        self.assertEqual(analysis["summary"]["source_mode"], "perf-script-import")
        root_children = analysis["flamegraph"]["children"]
        self.assertEqual(root_children[0]["name"], "python")
        request_node = root_children[0]["children"][0]
        self.assertEqual(request_node["name"], "handle_request")
        self.assertEqual(request_node["children"][0]["name"], "hot_loop")
        self.assertEqual(analysis["hotspots"][0]["name"], "python;handle_request;hot_loop")


if __name__ == "__main__":
    unittest.main()
