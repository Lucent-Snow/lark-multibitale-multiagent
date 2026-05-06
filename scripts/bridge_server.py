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

PORT = 9800


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

        # Forward complex commands via subprocess
        import subprocess
        cmd = ["python", "-m", "src.agent_team.dashboard_bridge"]
        mapping = {
            "/start-objective": ["start-objective", "title", "description", "maxTasks"],
            "/start-demo": ["start-demo", "title", "description", "maxTasks", "workers", "timeout"],
            "/run-demo": ["run-demo", "title", "description", "maxTasks", "workers", "timeout"],
            "/send-message": ["send-message", "objectiveId:sender:recipient:summary:message"],
            "/recover-expired": ["recover-expired", "objectiveId"],
            "/retry-failed": ["retry-failed", "objectiveId"],
        }
        for route, spec in mapping.items():
            if path == route:
                cmd += [spec[0], "--base-token", token]
                for i, arg in enumerate(spec[1:]):
                    if ":" in arg:
                        for sub_arg in arg.split(":"):
                            cmd += [f"--{sub_arg.replace('Id', '-id').replace('Tasks', '-tasks')}",
                                    str(body.get(sub_arg, ""))]
                    else:
                        key = f"--{arg.replace('Id', '-id').replace('Tasks', '-tasks')}"
                        val = body.get(arg, "")
                        cmd += [key, str(val)]
                break
        else:
            raise ValueError(f"Unknown: {path}")

        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if r.returncode != 0:
            raise Exception(r.stderr.strip() or f"Exit {r.returncode}")
        result = json.loads(r.stdout.strip())
        if not result.get("ok"):
            raise Exception(result.get("error", {}).get("message", "Unknown"))
        return result["data"]

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
