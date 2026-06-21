from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from .analyzer import dumps_analysis


TASK_STATES = {"PENDING", "RUNNING", "UPLOADING", "DONE", "FAILED"}
TERMINAL_STATES = {"DONE", "FAILED"}


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.init_schema()

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL,
                ip TEXT NOT NULL,
                version TEXT NOT NULL,
                online INTEGER NOT NULL DEFAULT 1,
                last_heartbeat REAL NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                pid INTEGER NOT NULL,
                duration INTEGER NOT NULL,
                sample_rate INTEGER NOT NULL,
                collector TEXT NOT NULL,
                session_id TEXT,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                assigned_agent TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS state_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                agent_id TEXT,
                task_id TEXT,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                ts REAL NOT NULL,
                cpu_pct REAL NOT NULL,
                rss_mb REAL NOT NULL,
                io_read_kb REAL NOT NULL DEFAULT 0,
                io_write_kb REAL NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analysis_results (
                task_id TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS continuous_sessions (
                id TEXT PRIMARY KEY,
                pid INTEGER NOT NULL,
                collector TEXT NOT NULL,
                interval_sec INTEGER NOT NULL,
                duration_sec INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """
        )
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "session_id" not in columns:
            self.conn.execute("ALTER TABLE tasks ADD COLUMN session_id TEXT")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def create_task(
        self,
        pid: int,
        duration: int,
        sample_rate: int,
        collector: str = "proc",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        if duration <= 0 or duration > 300:
            raise ValueError("duration must be between 1 and 300 seconds")
        if sample_rate <= 0 or sample_rate > 50:
            raise ValueError("sample_rate must be between 1 and 50 Hz")
        task_id = "task-" + uuid.uuid4().hex[:10]
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO tasks(id, pid, duration, sample_rate, collector, session_id, status, reason, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 'created from web/api', ?, ?)
            """,
            (task_id, pid, duration, sample_rate, collector, session_id, now, now),
        )
        self.conn.execute(
            "INSERT INTO state_transitions(task_id, from_state, to_state, reason, created_at) VALUES (?, NULL, 'PENDING', ?, ?)",
            (task_id, "created from web/api", now),
        )
        self.conn.commit()
        return self.get_task(task_id)

    def create_continuous_session(self, pid: int, collector: str, interval: int, duration: int) -> dict[str, Any]:
        if interval <= 0 or interval > 3600:
            raise ValueError("interval must be between 1 and 3600 seconds")
        if duration <= 0 or duration > 300:
            raise ValueError("duration must be between 1 and 300 seconds")
        session_id = "cont-" + uuid.uuid4().hex[:10]
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO continuous_sessions(id, pid, collector, interval_sec, duration_sec, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (session_id, pid, collector, interval, duration, now, now),
        )
        self.conn.commit()
        return self.get_continuous_session(session_id)

    def get_continuous_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM continuous_sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def list_continuous_sessions(self) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute("SELECT * FROM continuous_sessions ORDER BY created_at DESC").fetchall()
        ]

    def stop_continuous_session(self, session_id: str) -> dict[str, Any]:
        now = time.time()
        self.conn.execute(
            "UPDATE continuous_sessions SET status='STOPPED', updated_at=? WHERE id=?",
            (now, session_id),
        )
        self.conn.commit()
        session = self.get_continuous_session(session_id)
        if not session:
            raise KeyError(session_id)
        return session

    def list_continuous_window(self, session_id: str, start_ts: float, end_ts: float) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT * FROM tasks
                WHERE session_id=? AND created_at >= ? AND created_at <= ?
                ORDER BY created_at DESC
                """,
                (session_id, start_ts, end_ts),
            ).fetchall()
        ]

    def transition_task(self, task_id: str, to_state: str, reason: str, assigned_agent: str | None = None) -> dict[str, Any]:
        if to_state not in TASK_STATES:
            raise ValueError(f"invalid task state: {to_state}")
        task = self.get_task(task_id)
        if not task:
            raise KeyError(task_id)
        if task["status"] in TERMINAL_STATES and task["status"] != to_state:
            raise ValueError(f"terminal task cannot transition from {task['status']} to {to_state}")
        now = time.time()
        self.conn.execute(
            "UPDATE tasks SET status=?, reason=?, assigned_agent=COALESCE(?, assigned_agent), updated_at=? WHERE id=?",
            (to_state, reason, assigned_agent, now, task_id),
        )
        self.conn.execute(
            "INSERT INTO state_transitions(task_id, from_state, to_state, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, task["status"], to_state, reason, now),
        )
        self.conn.commit()
        return self.get_task(task_id)

    def heartbeat(self, agent_id: str, hostname: str, ip: str, version: str) -> dict[str, Any]:
        now = time.time()
        row = self.conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO agents(id, hostname, ip, version, online, last_heartbeat, created_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (agent_id, hostname, ip, version, now, now),
            )
            self.add_audit("AGENT_REGISTERED", f"agent {agent_id} registered", agent_id=agent_id)
        else:
            was_offline = int(row["online"]) == 0
            self.conn.execute(
                "UPDATE agents SET hostname=?, ip=?, version=?, online=1, last_heartbeat=? WHERE id=?",
                (hostname, ip, version, now, agent_id),
            )
            if was_offline:
                self.add_audit("AGENT_RECOVERED", f"agent {agent_id} recovered", agent_id=agent_id)
        self.conn.commit()
        return self.get_agent(agent_id)

    def mark_offline_agents(self, timeout_sec: int = 30) -> list[dict[str, Any]]:
        cutoff = time.time() - timeout_sec
        rows = self.conn.execute("SELECT * FROM agents WHERE online=1 AND last_heartbeat < ?", (cutoff,)).fetchall()
        offline = []
        for row in rows:
            self.conn.execute("UPDATE agents SET online=0 WHERE id=?", (row["id"],))
            self.add_audit("AGENT_OFFLINE", f"agent {row['id']} heartbeat timeout", agent_id=row["id"])
            offline.append(dict(row))
        self.conn.commit()
        return offline

    def claim_next_task(self, agent_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE status='PENDING' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return self.transition_task(row["id"], "RUNNING", f"claimed by {agent_id}", assigned_agent=agent_id)

    def add_sample(self, task_id: str, sample: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO samples(task_id, ts, cpu_pct, rss_mb, io_read_kb, io_write_kb, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                float(sample.get("ts", time.time())),
                float(sample.get("cpu_pct", 0.0)),
                float(sample.get("rss_mb", 0.0)),
                float(sample.get("io_read_kb", 0.0)),
                float(sample.get("io_write_kb", 0.0)),
                json.dumps(sample, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def complete_task(self, task_id: str, success: bool, reason: str) -> dict[str, Any]:
        if success:
            self.transition_task(task_id, "UPLOADING", "agent uploaded raw samples")
            task = self.get_task(task_id)
            samples = self.list_samples(task_id)
            result = dumps_analysis(task, samples)
            now = time.time()
            self.conn.execute(
                "INSERT OR REPLACE INTO analysis_results(task_id, result_json, created_at) VALUES (?, ?, ?)",
                (task_id, result, now),
            )
            self.conn.commit()
            return self.transition_task(task_id, "DONE", reason)
        return self.transition_task(task_id, "FAILED", reason)

    def add_audit(self, kind: str, message: str, agent_id: str | None = None, task_id: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO audit_logs(kind, message, agent_id, task_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (kind, message, agent_id, task_id, time.time()),
        )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_tasks(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()]

    def list_transitions(self, task_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM state_transitions WHERE task_id=? ORDER BY created_at", (task_id,)
            ).fetchall()
        ]

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        return dict(row) if row else None

    def list_agents(self) -> list[dict[str, Any]]:
        self.mark_offline_agents()
        return [dict(row) for row in self.conn.execute("SELECT * FROM agents ORDER BY hostname").fetchall()]

    def list_audits(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100").fetchall()]

    def list_samples(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT raw_json FROM samples WHERE task_id=? ORDER BY ts", (task_id,)).fetchall()
        return [json.loads(row["raw_json"]) for row in rows]

    def get_analysis(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT result_json FROM analysis_results WHERE task_id=?", (task_id,)).fetchone()
        return json.loads(row["result_json"]) if row else None
