"""JSON bridge used by the Next.js agent-team dashboard."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import yaml

from src.auth.app_auth import Credentials
from src.agent_team_v2.base_store import BaseAgentTeamV2Store
from src.agent_team_v2.engine import AgentTeamV2Engine, LeaderV2
from src.base_client.client import BaseClient, BaseTableIds
from src.llm.client import LLMClient


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")


class BridgeError(Exception):
    """Dashboard-facing error with a stable stage."""

    def __init__(self, stage: str, message: str, detail: str = ""):
        super().__init__(message)
        self.stage = stage
        self.detail = detail


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent-team v2 dashboard bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--objective-id", default="")

    message = subparsers.add_parser("send-message")
    message.add_argument("--objective-id", required=True)
    message.add_argument("--sender", default="console")
    message.add_argument("--recipient", required=True)
    message.add_argument("--summary", required=True)
    message.add_argument("--message", required=True)
    message.add_argument("--task-id", default="")

    objective = subparsers.add_parser("start-objective")
    objective.add_argument("--title", required=True)
    objective.add_argument("--description", required=True)
    objective.add_argument("--max-tasks", type=int, default=4)

    recover = subparsers.add_parser("recover-expired")
    recover.add_argument("--objective-id", required=True)

    retry = subparsers.add_parser("retry-failed")
    retry.add_argument("--objective-id", required=True)

    run = subparsers.add_parser("run-demo")
    run.add_argument("--title", required=True)
    run.add_argument("--description", required=True)
    run.add_argument("--max-tasks", type=int, default=4)
    run.add_argument("--workers", type=int, default=3)
    run.add_argument("--timeout", type=int, default=600)

    start = subparsers.add_parser("start-demo")
    start.add_argument("--title", required=True)
    start.add_argument("--description", required=True)
    start.add_argument("--max-tasks", type=int, default=4)
    start.add_argument("--workers", type=int, default=3)
    start.add_argument("--timeout", type=int, default=600)

    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            payload = snapshot_payload(args.objective_id)
        elif args.command == "send-message":
            payload = send_message_payload(args)
        elif args.command == "start-objective":
            payload = start_objective_payload(args)
        elif args.command == "recover-expired":
            payload = recover_expired_payload(args.objective_id)
        elif args.command == "retry-failed":
            payload = retry_failed_payload(args.objective_id)
        elif args.command == "run-demo":
            payload = run_demo_payload(args)
        elif args.command == "start-demo":
            payload = start_demo_payload(args)
        else:
            raise BridgeError("parse_args", f"Unsupported command: {args.command}")
        print(json.dumps({"ok": True, "data": payload}, ensure_ascii=False))
        return 0
    except BridgeError as exc:
        print(json.dumps(_error(exc.stage, str(exc), exc.detail), ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps(
            _error("bridge", "Dashboard bridge failed", type(exc).__name__),
            ensure_ascii=False,
        ))
        return 1


def snapshot_payload(objective_id: str = "") -> dict[str, Any]:
    base, table_ids = _base_client()
    batches = _snapshot_records(base, table_ids)
    objectives = batches["objectives"]
    if not objectives:
        return {
            "mode": "real",
            "empty": True,
            "base": _base_info(base.base_token),
            "objective": None,
            "workers": [],
            "tasks": [],
            "edges": [],
            "claims": [],
            "messages": [],
            "artifacts": [],
            "verifications": [],
            "events": [],
            "generated_at": _now(),
        }

    objective_record = _select_objective(objectives, objective_id)
    objective = _objective_from_record(objective_record)
    selected_id = objective["id"]
    tasks = [_task_from_record(record) for record in batches["tasks"]
             if _record_objective_id(record) == selected_id]
    task_ids = {task["id"] for task in tasks}

    return {
        "mode": "real",
        "empty": False,
        "base": _base_info(base.base_token),
        "objective": {
            **objective,
            "progress": _progress(tasks),
        },
        "workers": _workers(batches["workers"], selected_id),
        "tasks": tasks,
        "edges": [_edge_from_record(record) for record in batches["edges"]
                  if _record_objective_id(record) == selected_id],
        "claims": _claims(batches["claims"], selected_id, task_ids),
        "messages": _filtered_records(batches["messages"], selected_id),
        "artifacts": [_artifact_from_record(record) for record in batches["artifacts"]
                      if _record_objective_id(record) == selected_id],
        "verifications": [
            record.fields or {} for record in batches["verifications"]
            if _record_objective_id(record) == selected_id
        ],
        "events": _filtered_records(batches["events"], selected_id),
        "generated_at": _now(),
    }


def send_message_payload(args: argparse.Namespace) -> dict[str, Any]:
    base, _table_ids = _base_client()
    store = BaseAgentTeamV2Store(base)
    message_id = store.create_message(
        args.objective_id,
        args.sender,
        args.recipient,
        args.summary,
        args.message,
        task_id=args.task_id,
    )
    return {"message_id": message_id}


def start_objective_payload(args: argparse.Namespace) -> dict[str, Any]:
    base, _table_ids = _base_client()
    cfg = _config()
    llm_cfg = cfg.get("llm") or {}
    if not llm_cfg.get("api_key") or not llm_cfg.get("endpoint_id"):
        raise BridgeError("llm_config", "Missing llm.api_key or llm.endpoint_id")
    store = BaseAgentTeamV2Store(base)
    llm = LLMClient(llm_cfg["api_key"], llm_cfg["endpoint_id"], timeout=90)
    result = AgentTeamV2Engine(store, LeaderV2(llm, False)).start_objective(
        args.title,
        args.description,
        max_tasks=args.max_tasks,
    )
    return {
        "objective_id": result["objective_id"],
        "task_count": len(result["tasks"]),
        "edge_count": len(result["edge_ids"]),
    }


def recover_expired_payload(objective_id: str) -> dict[str, Any]:
    base, _table_ids = _base_client()
    store = BaseAgentTeamV2Store(base)
    recovered = AgentTeamV2Engine(store, LeaderV2(None)).recover_expired_tasks(
        objective_id,
        actor="console",
    )
    return {"recovered": recovered}


def retry_failed_payload(objective_id: str) -> dict[str, Any]:
    base, _table_ids = _base_client()
    store = BaseAgentTeamV2Store(base)
    retried = AgentTeamV2Engine(store, LeaderV2(None)).retry_failed_tasks(
        objective_id,
        actor="console",
    )
    return {"retried": retried}


def run_demo_payload(args: argparse.Namespace) -> dict[str, Any]:
    base, _table_ids = _base_client()
    cfg = _config()
    llm_cfg = cfg.get("llm") or {}
    if not llm_cfg.get("api_key") or not llm_cfg.get("endpoint_id"):
        raise BridgeError("llm_config", "Missing llm.api_key or llm.endpoint_id")
    store = BaseAgentTeamV2Store(base)
    llm = LLMClient(llm_cfg["api_key"], llm_cfg["endpoint_id"], timeout=90)
    engine = AgentTeamV2Engine(store, LeaderV2(llm, False))
    objective = engine.start_objective(args.title, args.description, max_tasks=args.max_tasks)
    objective_id = objective["objective_id"]

    from src.agent_team_v2.demo import (
        run_agent_team_v2_base_demo,
        select_agent_team_v2_workers,
    )
    result = run_agent_team_v2_base_demo(
        manager_api=base,
        llm=llm,
        title=args.title,
        description=args.description,
        max_tasks=args.max_tasks,
        workers=args.workers,
        timeout_seconds=args.timeout,
    )
    tasks = [
        {
            "id": task.task_id,
            "subject": task.subject,
            "description": task.description[:200],
            "role": task.role,
            "status": task.status,
            "owner": task.owner,
        }
        for task in result["tasks"]
    ]
    return {
        "objective_id": result["objective_id"],
        "tasks": tasks,
        "all_tasks_completed": result["all_tasks_completed"],
        "objective_completed": result["objective_completed"],
        "edge_count": len(result["edges"]),
        "verification_count": len(result["verifications"]),
    }


def start_demo_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Plan objective + spawn worker subprocesses, return immediately."""
    base, _table_ids = _base_client()
    cfg = _config()
    llm_cfg = cfg.get("llm") or {}
    if not llm_cfg.get("api_key") or not llm_cfg.get("endpoint_id"):
        raise BridgeError("llm_config", "Missing llm.api_key or llm.endpoint_id")
    store = BaseAgentTeamV2Store(base)
    llm = LLMClient(llm_cfg["api_key"], llm_cfg["endpoint_id"], timeout=90)
    engine = AgentTeamV2Engine(store, LeaderV2(llm, False))
    objective = engine.start_objective(args.title, args.description, max_tasks=args.max_tasks)
    objective_id = objective["objective_id"]

    from src.agent_team_v2.demo import select_agent_team_v2_workers

    selected = select_agent_team_v2_workers(args.workers)
    spawned = []
    for worker_id, role in selected:
        proc = subprocess.Popen([
            sys.executable,
            os.path.join(ROOT, "src", "main.py"),
            "--agent-team-v2-worker",
            "--objective-id", objective_id,
            "--worker-id", worker_id,
            "--worker-role", role,
            "--worker-max-tasks", str(args.max_tasks),
            "--worker-idle-rounds", str(max(60, args.timeout)),
        ])
        spawned.append({"worker_id": worker_id, "role": role, "pid": proc.pid})

    return {
        "objective_id": objective_id,
        "task_count": len(objective["tasks"]),
        "edge_count": len(objective["edge_ids"]),
        "workers_spawned": spawned,
    }


def _base_client() -> tuple[BaseClient, BaseTableIds]:
    cfg = _config()
    lark_cfg = cfg.get("lark") or {}
    base_token = lark_cfg.get("base_token")
    if not base_token:
        raise BridgeError("config", "Missing lark.base_token in config.yaml")
    try:
        table_ids = BaseTableIds.from_config(lark_cfg.get("tables") or {})
        table_ids.require_agent_team_v2()
    except ValueError as exc:
        raise BridgeError("config", str(exc)) from exc

    if not Credentials().get("manager"):
        raise BridgeError("credentials", "Bot 'manager' not found in .credentials.json")
    return BaseClient("manager", base_token, table_ids), table_ids


def _config() -> dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        raise BridgeError("config", "config.yaml not found", CONFIG_PATH)
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _records(base: BaseClient, table_id: str | None) -> list:
    if not table_id:
        return []
    return base.list_records(table_id)


def _snapshot_records(base: BaseClient, table_ids: BaseTableIds) -> dict[str, list]:
    sources = {
        "objectives": table_ids.v2_objectives,
        "workers": table_ids.v2_workers,
        "tasks": table_ids.v2_tasks,
        "edges": table_ids.v2_task_edges,
        "claims": table_ids.v2_claims,
        "messages": table_ids.v2_messages,
        "artifacts": table_ids.v2_artifacts,
        "verifications": table_ids.v2_verifications,
        "events": table_ids.v2_events,
    }
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {
            name: executor.submit(_records, base, table_id)
            for name, table_id in sources.items()
        }
        return {name: future.result() for name, future in futures.items()}


def _select_objective(records: list, objective_id: str):
    if objective_id:
        for record in records:
            fields = record.fields or {}
            if _scalar(fields.get("objective_id"), record.record_id) == objective_id:
                return record
        raise BridgeError("objective", f"Objective not found: {objective_id}")
    return sorted(
        records,
        key=lambda item: _scalar((item.fields or {}).get("创建时间")),
    )[-1]


def _objective_from_record(record) -> dict[str, Any]:
    fields = record.fields or {}
    return {
        "id": _scalar(fields.get("objective_id"), record.record_id),
        "record_id": record.record_id,
        "title": _scalar(fields.get("标题")),
        "description": _scalar(fields.get("说明")),
        "status": _scalar(fields.get("状态")),
        "initiator": _scalar(fields.get("发起人")),
        "final_result": _scalar(fields.get("最终结论")),
        "created_at": _scalar(fields.get("创建时间")),
    }


def _workers(records: list, objective_id: str) -> list[dict]:
    workers = []
    for record in records:
        fields = record.fields or {}
        if _scalar(fields.get("objective_id")) != objective_id:
            continue
        workers.append({
            "id": _scalar(fields.get("worker_id"), record.record_id),
            "record_id": record.record_id,
            "name": _scalar(fields.get("名称")),
            "role": _scalar(fields.get("角色")),
            "status": _scalar(fields.get("状态")),
            "capabilities": _scalar(fields.get("能力")),
            "current_task_id": _scalar(fields.get("当前任务ID")),
            "heartbeat_at": _scalar(fields.get("心跳时间")),
            "process_id": _scalar(fields.get("进程ID")),
        })
    return workers


def _claims(records: list, objective_id: str, task_ids: set[str]) -> list[dict]:
    claims = []
    for record in records:
        fields = record.fields or {}
        task_id = _scalar(fields.get("task_id"))
        if _scalar(fields.get("objective_id")) != objective_id or task_id not in task_ids:
            continue
        claims.append({
            "id": _scalar(fields.get("claim_id"), record.record_id),
            "task_id": task_id,
            "worker_id": _scalar(fields.get("worker_id")),
            "status": _scalar(fields.get("状态")),
            "nonce": _scalar(fields.get("nonce")),
            "created_at": _scalar(fields.get("创建时间")),
        })
    return claims


def _filtered_records(records: list, objective_id: str) -> list[dict]:
    values = []
    for record in records:
        fields = record.fields or {}
        if _scalar(fields.get("objective_id")) == objective_id:
            values.append({"id": record.record_id, "fields": fields})
    return values


def _record_objective_id(record) -> str:
    return _scalar((record.fields or {}).get("objective_id"))


def _task_from_record(record) -> dict[str, Any]:
    fields = record.fields or {}
    metadata = _loads_json(_scalar(fields.get("metadata"), "{}"), {})
    return {
        "id": _scalar(fields.get("task_id"), record.record_id),
        "objective_id": _scalar(fields.get("objective_id")),
        "subject": _scalar(fields.get("标题")),
        "description": _scalar(fields.get("说明")),
        "role": _scalar(fields.get("角色")),
        "status": _scalar(fields.get("状态"), "pending"),
        "owner": _scalar(fields.get("owner")),
        "lease_until": _scalar(fields.get("lease_until")),
        "attempt_count": int(_scalar(fields.get("attempt_count"), "0") or 0),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def _edge_from_record(record) -> dict[str, Any]:
    fields = record.fields or {}
    return {
        "id": record.record_id,
        "objective_id": _scalar(fields.get("objective_id")),
        "from_task_id": _scalar(fields.get("from_task_id")),
        "to_task_id": _scalar(fields.get("to_task_id")),
        "relation": _scalar(fields.get("关系类型"), "blocks"),
    }


def _artifact_from_record(record) -> dict[str, Any]:
    fields = record.fields or {}
    return {
        "artifact_id": _scalar(fields.get("artifact_id"), record.record_id),
        "objective_id": _scalar(fields.get("objective_id")),
        "task_id": _scalar(fields.get("task_id")),
        "author": _scalar(fields.get("作者")),
        "title": _scalar(fields.get("标题")),
        "content": _scalar(fields.get("内容")),
        "created_at": _scalar(fields.get("创建时间")),
    }


def _progress(tasks: list[dict]) -> float:
    if not tasks:
        return 0
    done = len([task for task in tasks if task["status"] == "completed"])
    return round(done / len(tasks), 4)


def _base_info(base_token: str) -> dict[str, str]:
    suffix = base_token[-6:] if len(base_token) >= 6 else base_token
    return {"token_suffix": suffix}


def _scalar(value, default: str = "") -> str:
    return BaseAgentTeamV2Store._scalar(value, default)


def _loads_json(value: str, default):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error(stage: str, message: str, detail: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": stage.upper().replace("-", "_"),
            "stage": stage,
            "message": message,
            "detail": detail,
            "timestamp": _now(),
        },
    }


if __name__ == "__main__":
    sys.exit(main())
