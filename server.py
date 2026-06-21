from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mini_drop.store import Store


ROOT = Path(__file__).resolve().parent


def make_handler(store: Store, web_dir: Path):
    class MiniDropHandler(BaseHTTPRequestHandler):
        server_version = "MiniDrop/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self.json_response({"ok": True, "service": "mini-drop"})
            elif parsed.path == "/api/agents":
                self.json_response({"agents": store.list_agents(), "audits": store.list_audits()})
            elif parsed.path == "/api/tasks":
                self.json_response({"tasks": store.list_tasks()})
            elif parsed.path == "/api/continuous/sessions":
                self.json_response({"sessions": store.list_continuous_sessions()})
            elif parsed.path == "/api/continuous/window":
                qs = parse_qs(parsed.query)
                session_id = qs.get("session_id", [""])[0]
                if not session_id:
                    self.error_response(HTTPStatus.BAD_REQUEST, "session_id is required")
                    return
                now = time.time()
                start_ts = float(qs.get("from", [now - 300])[0])
                end_ts = float(qs.get("to", [now])[0])
                self.json_response({"tasks": store.list_continuous_window(session_id, start_ts, end_ts)})
            elif parsed.path.startswith("/api/tasks/"):
                task_id = parsed.path.rsplit("/", 1)[-1]
                task = store.get_task(task_id)
                if not task:
                    self.error_response(HTTPStatus.NOT_FOUND, "task not found")
                    return
                self.json_response(
                    {
                        "task": task,
                        "transitions": store.list_transitions(task_id),
                        "samples": store.list_samples(task_id),
                        "analysis": store.get_analysis(task_id),
                    }
                )
            elif parsed.path == "/api/agent/next":
                qs = parse_qs(parsed.query)
                agent_id = qs.get("agent_id", [""])[0]
                if not agent_id:
                    self.error_response(HTTPStatus.BAD_REQUEST, "agent_id is required")
                    return
                self.json_response({"task": store.claim_next_task(agent_id)})
            else:
                self.serve_static(parsed.path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                data = self.read_json()
                if parsed.path == "/api/tasks":
                    task = store.create_task(
                        pid=int(data.get("pid", 0)),
                        duration=int(data.get("duration", 10)),
                        sample_rate=int(data.get("sample_rate", 1)),
                        collector=str(data.get("collector", "proc")),
                        session_id=str(data["session_id"]) if data.get("session_id") else None,
                    )
                    self.json_response({"task": task}, HTTPStatus.CREATED)
                elif parsed.path == "/api/continuous/sessions":
                    session = store.create_continuous_session(
                        pid=int(data.get("pid", 0)),
                        collector=str(data.get("collector", "proc")),
                        interval=int(data.get("interval", 5)),
                        duration=int(data.get("duration", 5)),
                    )
                    self.json_response({"session": session}, HTTPStatus.CREATED)
                elif parsed.path.startswith("/api/continuous/sessions/") and parsed.path.endswith("/stop"):
                    session_id = parsed.path.split("/")[-2]
                    session = store.stop_continuous_session(session_id)
                    self.json_response({"session": session})
                elif parsed.path == "/api/agent/heartbeat":
                    agent = store.heartbeat(
                        agent_id=str(data["agent_id"]),
                        hostname=str(data.get("hostname", "unknown")),
                        ip=str(data.get("ip", "127.0.0.1")),
                        version=str(data.get("version", "dev")),
                    )
                    self.json_response({"agent": agent})
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/transition"):
                    task_id = parsed.path.split("/")[-2]
                    task = store.transition_task(task_id, str(data["state"]), str(data.get("reason", "api transition")))
                    self.json_response({"task": task})
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/samples"):
                    task_id = parsed.path.split("/")[-2]
                    samples = data.get("samples", [])
                    if isinstance(samples, dict):
                        samples = [samples]
                    for sample in samples:
                        store.add_sample(task_id, sample)
                    self.json_response({"ok": True, "count": len(samples)})
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/complete"):
                    task_id = parsed.path.split("/")[-2]
                    task = store.complete_task(task_id, bool(data.get("success", True)), str(data.get("reason", "agent complete")))
                    self.json_response({"task": task})
                else:
                    self.error_response(HTTPStatus.NOT_FOUND, "unknown endpoint")
            except (KeyError, ValueError) as exc:
                self.error_response(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception as exc:  # explicit API error boundary for demo reliability
                self.error_response(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(exc).__name__}: {exc}")

        def read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def json_response(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def error_response(self, status: HTTPStatus, message: str) -> None:
            self.json_response({"error": message, "status": int(status)}, status)

        def serve_static(self, path: str) -> None:
            rel = "index.html" if path in {"", "/"} else path.lstrip("/")
            file_path = (web_dir / rel).resolve()
            if not str(file_path).startswith(str(web_dir.resolve())) or not file_path.exists() or file_path.is_dir():
                self.error_response(HTTPStatus.NOT_FOUND, "not found")
                return
            body = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            print(json.dumps({"ts": time.time(), "level": "info", "message": fmt % args}, ensure_ascii=False))

    return MiniDropHandler


def start_offline_scanner(store: Store, interval: int = 5) -> threading.Event:
    stop = threading.Event()

    def scan() -> None:
        while not stop.is_set():
            store.mark_offline_agents()
            stop.wait(interval)

    threading.Thread(target=scan, daemon=True).start()
    return stop


def run(host: str, port: int, db_path: str, web_dir: str | None = None) -> None:
    store = Store(db_path)
    stop = start_offline_scanner(store)
    directory = Path(web_dir) if web_dir else ROOT / "web"
    httpd = ThreadingHTTPServer((host, port), make_handler(store, directory))
    print(json.dumps({"level": "info", "message": "server started", "host": host, "port": port}, ensure_ascii=False))
    try:
        httpd.serve_forever()
    finally:
        stop.set()
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", default=str(ROOT / "data" / "mini_drop.sqlite3"))
    parser.add_argument("--web-dir", default=str(ROOT / "web"))
    args = parser.parse_args()
    run(args.host, args.port, args.db, args.web_dir)


if __name__ == "__main__":
    main()
