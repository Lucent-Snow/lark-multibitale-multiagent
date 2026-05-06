"""JSON bridge used by the Next.js agent-team dashboard."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import yaml

from src.agent_team.base_store import BaseObjectiveStore, _scalar
from src.agent_team.engine import AgentTeamEngine, Leader
from src.base_client.client import BaseClient
from src.llm.client import LLMClient

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")


class BridgeError(Exception):
    def __init__(self, stage: str, message: str, detail: str = ""):
        super().__init__(message)
        self.stage = stage
        self.detail = detail


def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f.read()) or {}


def _make_llm():
    cfg = _load_config()
    c = cfg.get("llm") or {}
    return LLMClient(c["api_key"], c["endpoint_id"], timeout=90)


def _make_base(token):
    return BaseClient(token)


def snapshot_payload(base_token: str, objective_id: str = "") -> dict[str, Any]:
    base = _make_base(base_token)

    # Find objective tables (prefixed obj_)
    from lark_oapi.api.bitable.v1 import ListAppTableRequest
    request = ListAppTableRequest.builder() \
        .app_token(base.base_token).page_size(100).build()
    response = base._client.bitable.v1.app_table.list(request, base._opt())
    if not response.success():
        return _empty_snapshot(base_token)

    obj_tables = [item for item in (response.data.items or []) if item.name.startswith("obj_")]
    all_tables = [{"name": item.name, "table_id": item.table_id}
                  for item in (response.data.items or [])]

    if not objective_id:
        # Pick latest objective
        objective_id = _latest_objective_id(obj_tables)
    if not objective_id:
        return {**_empty_snapshot(base_token), "table_count": len(all_tables), "tables": all_tables}

    # Read the single objective table
    table_name = f"obj_{objective_id}"
    target = next((t for t in all_tables if t["name"] == table_name), None)
    if not target:
        return {**_empty_snapshot(base_token), "table_count": len(all_tables), "tables": all_tables}

    store = BaseObjectiveStore(base, objective_id)
    tasks = store.list_tasks()

    workers = list({t.owner for t in tasks if t.owner})
    completed = sum(1 for t in tasks if t.status == "completed")
    progress = round(completed / len(tasks), 4) if tasks else 0

    return {
        "mode": "real",
        "empty": False,
        "base": {"token_suffix": base_token[-6:]},
        "table_count": len(all_tables),
        "tables": all_tables,
        "has_agent_team": bool(obj_tables),
        "objective": {
            "id": objective_id,
            "title": f"Objective {objective_id[-8:]}",
            "description": "",
            "status": "completed" if progress == 1 else "in_progress",
            "progress": progress,
        },
        "workers": [{"id": w, "name": w, "role": "", "status": "working" if any(
            t.owner == w and t.status == "in_progress" for t in tasks) else "idle"} for w in workers],
        "tasks": [{
            "id": t.task_id, "subject": t.subject, "description": t.description[:200],
            "role": t.role, "status": t.status, "owner": t.owner,
            "attempt_count": t.attempt_count, "depends_on": t.depends_on,
        } for t in tasks],
        "edges": _edges_from_tasks(tasks),
        "claims": [],
        "messages": [],
        "artifacts": [{
            "artifact_id": t.task_id, "task_id": t.task_id, "author": t.owner,
            "title": t.artifact_title or t.subject, "content": t.artifact[:500],
            "created_at": t.created_at,
        } for t in tasks if t.artifact],
        "verifications": [{
            "task_id": t.task_id, "verdict": t.verdict, "issues": t.issues,
        } for t in tasks if t.verdict],
        "events": [],
        "generated_at": _now(),
    }


def _edges_from_tasks(tasks):
    edges = []
    for t in tasks:
        deps = [d.strip() for d in t.depends_on.split(",") if d.strip()]
        for dep in deps:
            dep_task = next((dt for dt in tasks if dt.subject == dep), None)
            if dep_task:
                edges.append({"id": f"edge-{dep_task.task_id}-{t.task_id}",
                              "from_task_id": dep_task.task_id, "to_task_id": t.task_id})
    return edges


def _latest_objective_id(obj_tables):
    if not obj_tables:
        return ""
    return sorted(obj_tables, key=lambda t: t.name)[-1].name.replace("obj_", "")


def _empty_snapshot(base_token):
    return {
        "mode": "real", "empty": True,
        "base": {"token_suffix": base_token[-6:]},
        "table_count": 0, "tables": [],
        "has_agent_team": False,
        "objective": None, "workers": [], "tasks": [], "edges": [],
        "claims": [], "messages": [], "artifacts": [], "verifications": [],
        "events": [], "generated_at": _now(),
    }


def _now():
    return datetime.now(timezone.utc).isoformat()


# Keep table management tools
def inspect_payload(base_token: str) -> dict[str, Any]:
    data = snapshot_payload(base_token)
    return {"table_count": data["table_count"], "tables": data["tables"],
            "has_agent_team": data["has_agent_team"]}


def init_payload(base_token: str) -> dict[str, Any]:
    # No more init needed — tables are created per objective
    return {"table_count": 0, "tables": {}, "message": "Tables are now created per objective by Leader"}


def create_table_payload(base_token: str, name: str, fields_str: str) -> dict[str, Any]:
    base = _make_base(base_token)
    fields = [f.strip() for f in fields_str.split(",") if f.strip()]
    if not fields:
        raise BridgeError("create_table", "At least one field required")
    tid = base.create_table(name, fields)
    return {"table_id": tid, "name": name, "fields": fields}


def delete_table_payload(base_token: str, name: str) -> dict[str, Any]:
    base = _make_base(base_token)
    from lark_oapi.api.bitable.v1 import ListAppTableRequest, DeleteAppTableRequest
    r = ListAppTableRequest.builder().app_token(base.base_token).page_size(100).build()
    resp = base._client.bitable.v1.app_table.list(r, base._opt())
    target = next((item for item in (resp.data.items or []) if item.name == name), None)
    if not target:
        raise BridgeError("delete_table", f"Table not found: {name}")
    req = DeleteAppTableRequest.builder().app_token(base.base_token).table_id(target.table_id).build()
    dr = base._client.bitable.v1.app_table.delete(req, base._opt())
    if not dr.success():
        raise BridgeError("delete_table", f"Failed: {dr.msg}")
    return {"deleted": True, "name": name}


def add_field_payload(base_token: str, table_name: str, field_name: str) -> dict[str, Any]:
    base = _make_base(base_token)
    from lark_oapi.api.bitable.v1 import ListAppTableRequest, CreateAppTableFieldRequest, AppTableField
    r = ListAppTableRequest.builder().app_token(base.base_token).page_size(100).build()
    resp = base._client.bitable.v1.app_table.list(r, base._opt())
    target = next((item for item in (resp.data.items or []) if item.name == table_name), None)
    if not target:
        raise BridgeError("add_field", f"Table not found: {table_name}")
    f = AppTableField.builder().field_name(field_name).type(1).build()
    req = CreateAppTableFieldRequest.builder().app_token(base.base_token).table_id(target.table_id).request_body(f).build()
    ar = base._client.bitable.v1.app_table_field.create(req, base._opt())
    if not ar.success():
        raise BridgeError("add_field", f"Failed: {ar.msg}")
    return {"added": True, "table_name": table_name, "field_name": field_name}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    def bt(p): p.add_argument("--base-token", required=True)

    snapshot_p = sub.add_parser("snapshot"); bt(snapshot_p)
    snapshot_p.add_argument("--objective-id", default="")
    inspect_p = sub.add_parser("inspect"); bt(inspect_p)
    init_p = sub.add_parser("init"); bt(init_p)
    ct = sub.add_parser("create-table"); bt(ct)
    ct.add_argument("--name", required=True); ct.add_argument("--fields", required=True)
    dt = sub.add_parser("delete-table"); bt(dt); dt.add_argument("--name", required=True)
    af = sub.add_parser("add-field"); bt(af)
    af.add_argument("--table-name", required=True); af.add_argument("--field-name", required=True)

    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            payload = snapshot_payload(args.base_token, args.objective_id)
        elif args.command == "inspect":
            payload = inspect_payload(args.base_token)
        elif args.command == "init":
            payload = init_payload(args.base_token)
        elif args.command == "create-table":
            payload = create_table_payload(args.base_token, args.name, args.fields)
        elif args.command == "delete-table":
            payload = delete_table_payload(args.base_token, args.name)
        elif args.command == "add-field":
            payload = add_field_payload(args.base_token, args.table_name, args.field_name)
        else:
            raise BridgeError("parse_args", f"Unknown: {args.command}")
        print(json.dumps({"ok": True, "data": payload}, ensure_ascii=False))
    except BridgeError as e:
        print(json.dumps({"ok": False, "error": {"code": e.stage, "stage": e.stage, "message": str(e)}}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "error": {"code": "BRIDGE", "message": f"{type(e).__name__}: {e}"}}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
