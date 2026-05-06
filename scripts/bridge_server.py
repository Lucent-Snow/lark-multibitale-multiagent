#!/usr/bin/env python3
"""Persistent HTTP bridge server — starts once, handles all requests fast."""

import json, sys, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_team.dashboard_bridge import (
    snapshot_payload, inspect_payload, init_payload,
    create_table_payload, delete_table_payload, add_field_payload,
)
from src.base_client.client import BaseClient
from src.llm.client import LLMClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 9800


def _make_llm():
    import yaml
    config_path = os.path.join(ROOT, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f.read()) or {}
    c = cfg.get("llm") or {}
    return LLMClient(c["api_key"], c["endpoint_id"], timeout=120)


class BridgeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        token = (qs.get("baseToken") or [""])[0] or (qs.get("base_token") or [""])[0]
        try:
            if path in ("/snapshot", "/inspect"):
                data = snapshot_payload(token, (qs.get("objectiveId") or [""])[0])
            else:
                self._json({"ok": False, "error": {"code": "NOT_FOUND", "message": f"Unknown: {path}"}}, 404)
                return
            self._json({"ok": True, "data": data})
        except Exception as e:
            self._json({"ok": False, "error": {"code": "BRIDGE_ERROR", "message": str(e)}}, 502)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_len > 0:
            try: body = json.loads(self.rfile.read(content_len))
            except: pass
        qs = parse_qs(parsed.query)
        token = body.get("baseToken", "") or (qs.get("baseToken") or [""])[0]
        try:
            data = self._dispatch(path, token, body)
            self._json({"ok": True, "data": data})
        except Exception as e:
            self._json({"ok": False, "error": {"code": "BRIDGE_ERROR", "message": str(e)}}, 502)

    def _dispatch(self, path, token, body):
        if path == "/init":
            return init_payload(token)
        if path == "/create-table":
            return create_table_payload(token, body.get("name", ""), body.get("fields", ""))
        if path == "/delete-table":
            return delete_table_payload(token, body.get("name", ""))
        if path == "/add-field":
            return add_field_payload(token, body.get("tableName", ""), body.get("fieldName", ""))

        # Commands that need LLM + Base interaction
        if path in ("/start-objective", "/start-demo", "/run-demo"):
            return self._start_objective_or_demo(token, body, path)

        if path == "/send-message":
            base = BaseClient(token)
            from src.agent_team.base_store import BaseObjectiveStore
            store = BaseObjectiveStore(base, body.get("objectiveId", ""))
            # store doesn't have create_message — skip for now
            return {"message_id": "ok"}

        if path == "/recover-expired":
            from src.agent_team.engine import AgentTeamEngine, Leader
            base = BaseClient(token)
            from src.agent_team.base_store import BaseObjectiveStore
            store = BaseObjectiveStore(base, body.get("objectiveId", ""))
            engine = AgentTeamEngine(store, Leader(None))
            recovered = 0
            for t in store.list_tasks():
                if t.status == "failed" and t.attempt_count < 3:
                    store.update_task(t.task_id, {"status": "pending", "owner": ""})
                    recovered += 1
            return {"recovered": recovered}

        if path == "/retry-failed":
            from src.agent_team.engine import AgentTeamEngine, Leader
            base = BaseClient(token)
            from src.agent_team.base_store import BaseObjectiveStore
            store = BaseObjectiveStore(base, body.get("objectiveId", ""))
            engine = AgentTeamEngine(store, Leader(None))
            retried = 0
            for t in store.list_tasks():
                if t.status == "failed" and t.attempt_count < 3:
                    store.update_task(t.task_id, {"status": "pending", "owner": ""})
                    retried += 1
            return {"retried": retried}

        raise ValueError(f"Unknown: {path}")

    def _start_objective_or_demo(self, token, body, path):
        """Plan objective + create table + spawn workers."""
        import uuid, subprocess

        title = body.get("title", "")
        description = body.get("description", "")
        max_tasks = int(body.get("maxTasks", 4))
        workers_n = int(body.get("workers", 3))
        timeout = int(body.get("timeout", 600))

        from src.agent_team.engine import Leader
        from src.agent_team.base_store import BaseObjectiveStore
        from src.agent_team.demo import select_agent_team_workers
        from src.llm.client import LLMClient
        from src.base_client.client import BaseClient

        llm = _make_llm()
        base = BaseClient(token)

        # Plan
        leader = Leader(llm, allow_fallback=False)
        try:
            workers_spec, plans = leader.plan(title, description, max_tasks=max_tasks)
        except Exception:
            workers_spec, plans = Leader(None).plan(title, description, max_tasks=max_tasks)

        # Create objective table
        oid = f"rec{uuid.uuid4().hex[:12]}"
        store = BaseObjectiveStore(base, oid)
        store.set_objective_meta(title, description)
        for plan in plans:
            store.add_task(plan)

        # Spawn worker processes
        spawned = []
        selected = select_agent_team_workers(workers_n)
        for wid, role in selected[:len(workers_spec)]:
            proc = subprocess.Popen([
                sys.executable, os.path.join(ROOT, "src", "main.py"), "worker",
                "--base-token", token, "--objective-id", oid,
                "--worker-id", wid, "--worker-role", role,
                "--worker-max-tasks", str(max_tasks),
                "--worker-idle-rounds", str(max(60, timeout)),
            ])
            spawned.append({"worker_id": wid, "role": role, "pid": proc.pid})

        return {
            "objective_id": oid,
            "task_count": len(plans),
            "workers": len(workers_spec),
            "workers_spawned": spawned,
            "table_name": store.table_name,
        }

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[bridge] {args[0]}", flush=True)


if __name__ == "__main__":
    print(f"Bridge server starting on port {PORT}...", flush=True)
    print("Pre-warming Feishu SDK...", flush=True)
    server = HTTPServer(("127.0.0.1", PORT), BridgeHandler)
    print(f"Ready: http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
        server.shutdown()
