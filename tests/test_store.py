from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from mini_drop.store import Store


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.sqlite3")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_state_transition_persists_reason(self) -> None:
        task = self.store.create_task(pid=1, duration=5, sample_rate=1)
        self.store.transition_task(task["id"], "RUNNING", "claimed by unit-test", assigned_agent="a1")
        transitions = self.store.list_transitions(task["id"])
        self.assertEqual([t["to_state"] for t in transitions], ["PENDING", "RUNNING"])
        self.assertEqual(transitions[-1]["reason"], "claimed by unit-test")

    def test_heartbeat_offline_and_recovered_audit(self) -> None:
        self.store.heartbeat("a1", "host", "127.0.0.1", "test")
        self.store.conn.execute("UPDATE agents SET last_heartbeat=? WHERE id='a1'", (time.time() - 60,))
        offline = self.store.mark_offline_agents(timeout_sec=30)
        self.assertEqual(len(offline), 1)
        self.store.heartbeat("a1", "host", "127.0.0.1", "test")
        audits = self.store.list_audits()
        kinds = [a["kind"] for a in audits]
        self.assertIn("AGENT_OFFLINE", kinds)
        self.assertIn("AGENT_RECOVERED", kinds)

    def test_complete_task_generates_analysis(self) -> None:
        task = self.store.create_task(pid=1, duration=1, sample_rate=1)
        self.store.transition_task(task["id"], "RUNNING", "claimed", assigned_agent="a1")
        self.store.add_sample(task["id"], {"ts": time.time(), "cpu_pct": 42, "rss_mb": 120})
        done = self.store.complete_task(task["id"], True, "done")
        self.assertEqual(done["status"], "DONE")
        analysis = self.store.get_analysis(task["id"])
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis["summary"]["sample_count"], 1)

    def test_continuous_session_window_lists_tasks_in_time_range(self) -> None:
        session = self.store.create_continuous_session(pid=1, collector="proc", interval=5, duration=2)
        first = self.store.create_task(pid=1, duration=2, sample_rate=1, collector="proc", session_id=session["id"])
        time.sleep(0.01)
        second = self.store.create_task(pid=1, duration=2, sample_rate=1, collector="proc", session_id=session["id"])
        tasks = self.store.list_continuous_window(session["id"], first["created_at"] - 1, first["created_at"] + 0.005)
        self.assertEqual([task["id"] for task in tasks], [first["id"]])
        all_tasks = self.store.list_continuous_window(session["id"], first["created_at"] - 1, second["created_at"] + 1)
        self.assertEqual([task["id"] for task in all_tasks], [second["id"], first["id"]])
        stopped = self.store.stop_continuous_session(session["id"])
        self.assertEqual(stopped["status"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
