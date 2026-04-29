"""Feishu Base-backed store for agent-team v2."""

import json

from src.agent_team.base_store import BaseAgentTeamStore
from src.agent_team_v2.contracts import (
    CLAIM_ACTIVE,
    V2Claim,
    V2Task,
    V2TaskEdge,
    WORKER_IDLE,
    TaskPlan,
)
from src.agent_team_v2.memory_store import utc_now
from src.base_client.client import BaseClient


class BaseAgentTeamV2Store:
    """Persist v2 control-plane state in Feishu Base."""

    def __init__(self, base_client: BaseClient):
        base_client.table_ids.require_agent_team_v2()
        self.base = base_client

    def _table(self, name: str) -> str:
        table_id = getattr(self.base.table_ids, name)
        if not table_id:
            raise ValueError(f"Agent-team v2 table is not configured: {name}")
        return table_id

    @staticmethod
    def _scalar(value, default: str = "") -> str:
        return BaseAgentTeamStore._scalar(value, default)

    @staticmethod
    def _loads(value: str, default):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default
        return parsed

    def create_objective(self, title: str, description: str,
                         initiator: str = "team-lead") -> str:
        record_id = self.base.create_record(self._table("v2_objectives"), {
            "objective_id": "",
            "标题": title,
            "说明": description,
            "状态": "in_progress",
            "发起人": initiator,
            "最终结论": "",
            "创建时间": utc_now(),
        })
        self.base.update_record(
            self._table("v2_objectives"), record_id, {"objective_id": record_id}
        )
        return record_id

    def update_objective(self, objective_id: str, fields: dict) -> None:
        self.base.update_record(
            self._table("v2_objectives"), objective_id, self._objective_fields(fields)
        )

    def register_worker(self, objective_id: str, worker_id: str, name: str,
                        role: str, capabilities: str, process_id: str = "") -> None:
        existing = [
            record for record in self.base.list_records(self._table("v2_workers"))
            if self._scalar((record.fields or {}).get("worker_id")) == worker_id
            and self._scalar((record.fields or {}).get("objective_id")) == objective_id
        ]
        fields = {
            "worker_id": worker_id,
            "objective_id": objective_id,
            "名称": name,
            "角色": role,
            "能力": capabilities,
            "状态": WORKER_IDLE,
            "当前任务ID": "",
            "心跳时间": utc_now(),
            "进程ID": process_id,
        }
        if existing:
            self.base.update_record(self._table("v2_workers"), existing[0].record_id, fields)
        else:
            self.base.create_record(self._table("v2_workers"), fields)

    def heartbeat_worker(self, objective_id: str, worker_id: str,
                         status: str, current_task_id: str = "") -> None:
        for record in self.base.list_records(self._table("v2_workers")):
            fields = record.fields or {}
            if (
                self._scalar(fields.get("worker_id")) == worker_id
                and self._scalar(fields.get("objective_id")) == objective_id
            ):
                self.base.update_record(self._table("v2_workers"), record.record_id, {
                    "状态": status,
                    "当前任务ID": current_task_id,
                    "心跳时间": utc_now(),
                })
                return
        raise ValueError(f"Worker is not registered: {worker_id}")

    def create_task(self, objective_id: str, plan: TaskPlan) -> V2Task:
        metadata = dict(plan.metadata)
        record_id = self.base.create_record(self._table("v2_tasks"), {
            "task_id": "",
            "objective_id": objective_id,
            "标题": plan.subject,
            "说明": plan.description,
            "角色": plan.role,
            "状态": "pending",
            "owner": "",
            "lease_until": "",
            "attempt_count": "0",
            "metadata": json.dumps(metadata, ensure_ascii=False),
            "完成时间": "",
        })
        self.base.update_record(self._table("v2_tasks"), record_id, {"task_id": record_id})
        return V2Task(
            task_id=record_id,
            objective_id=objective_id,
            subject=plan.subject,
            description=plan.description,
            role=plan.role,
            metadata=metadata,
        )

    def create_edge(self, objective_id: str, from_task_id: str,
                    to_task_id: str, relation: str = "blocks") -> str:
        self.get_task(objective_id, from_task_id)
        self.get_task(objective_id, to_task_id)
        return self.base.create_record(self._table("v2_task_edges"), {
            "objective_id": objective_id,
            "from_task_id": from_task_id,
            "to_task_id": to_task_id,
            "关系类型": relation,
        })

    def list_tasks(self, objective_id: str) -> list[V2Task]:
        return [
            self._task_from_record(record)
            for record in self.base.list_records(self._table("v2_tasks"))
            if self._scalar((record.fields or {}).get("objective_id")) == objective_id
        ]

    def get_task(self, objective_id: str, task_id: str) -> V2Task:
        task = self._task_from_record(
            self.base.get_record(self._table("v2_tasks"), task_id)
        )
        if task.objective_id != objective_id:
            raise ValueError(f"Task is outside objective scope: {task_id}")
        return task

    def update_task(self, objective_id: str, task_id: str, fields: dict) -> V2Task:
        self.get_task(objective_id, task_id)
        base_fields = {}
        mapping = {
            "subject": "标题",
            "description": "说明",
            "role": "角色",
            "status": "状态",
            "owner": "owner",
            "lease_until": "lease_until",
            "attempt_count": "attempt_count",
            "completed_at": "完成时间",
        }
        for key, field_name in mapping.items():
            if key in fields:
                base_fields[field_name] = str(fields[key])
        if "metadata" in fields:
            base_fields["metadata"] = json.dumps(fields["metadata"], ensure_ascii=False)
        if base_fields:
            self.base.update_record(self._table("v2_tasks"), task_id, base_fields)
        return self.get_task(objective_id, task_id)

    def list_edges(self, objective_id: str) -> list[V2TaskEdge]:
        return [
            self._edge_from_record(record)
            for record in self.base.list_records(self._table("v2_task_edges"))
            if self._scalar((record.fields or {}).get("objective_id")) == objective_id
        ]

    def create_claim(self, objective_id: str, task_id: str, worker_id: str,
                     nonce: str) -> V2Claim:
        self.get_task(objective_id, task_id)
        record_id = self.base.create_record(self._table("v2_claims"), {
            "claim_id": "",
            "objective_id": objective_id,
            "task_id": task_id,
            "worker_id": worker_id,
            "状态": CLAIM_ACTIVE,
            "nonce": nonce,
            "创建时间": utc_now(),
        })
        self.base.update_record(self._table("v2_claims"), record_id, {"claim_id": record_id})
        return self._claim_from_record(
            self.base.get_record(self._table("v2_claims"), record_id)
        )

    def list_claims(self, objective_id: str, task_id: str) -> list[V2Claim]:
        return [
            self._claim_from_record(record)
            for record in self.base.list_records(self._table("v2_claims"))
            if self._scalar((record.fields or {}).get("objective_id")) == objective_id
            and self._scalar((record.fields or {}).get("task_id")) == task_id
        ]

    def update_claim(self, objective_id: str, claim_id: str, status: str) -> None:
        claim = self._claim_from_record(
            self.base.get_record(self._table("v2_claims"), claim_id)
        )
        if claim.objective_id != objective_id:
            raise ValueError(f"Claim is outside objective scope: {claim_id}")
        self.base.update_record(self._table("v2_claims"), claim_id, {"状态": status})

    def create_message(self, objective_id: str, sender: str, recipient: str,
                       summary: str, message: str, task_id: str = "") -> str:
        if task_id:
            self.get_task(objective_id, task_id)
        record_id = self.base.create_record(self._table("v2_messages"), {
            "message_id": "",
            "objective_id": objective_id,
            "from": sender,
            "to": recipient,
            "summary": summary,
            "message": message,
            "关联任务ID": task_id,
            "状态": "unread",
            "创建时间": utc_now(),
        })
        self.base.update_record(self._table("v2_messages"), record_id, {"message_id": record_id})
        return record_id

    def create_artifact(self, objective_id: str, task_id: str, author: str,
                        title: str, content: str) -> str:
        self.get_task(objective_id, task_id)
        record_id = self.base.create_record(self._table("v2_artifacts"), {
            "artifact_id": "",
            "objective_id": objective_id,
            "task_id": task_id,
            "作者": author,
            "标题": title,
            "内容": content,
            "创建时间": utc_now(),
        })
        self.base.update_record(self._table("v2_artifacts"), record_id, {"artifact_id": record_id})
        return record_id

    def create_verification(self, objective_id: str, task_id: str, verifier: str,
                            verdict: str, issues: str = "",
                            suggestions: str = "") -> str:
        self.get_task(objective_id, task_id)
        record_id = self.base.create_record(self._table("v2_verifications"), {
            "verification_id": "",
            "objective_id": objective_id,
            "task_id": task_id,
            "verifier": verifier,
            "结论": verdict,
            "问题": issues,
            "建议": suggestions,
            "创建时间": utc_now(),
        })
        self.base.update_record(
            self._table("v2_verifications"), record_id, {"verification_id": record_id}
        )
        return record_id

    def list_verifications(self, objective_id: str) -> list[dict]:
        return [
            record.fields or {}
            for record in self.base.list_records(self._table("v2_verifications"))
            if self._scalar((record.fields or {}).get("objective_id")) == objective_id
        ]

    def log_event(self, objective_id: str, actor: str, event_type: str,
                  target_id: str, detail: str) -> str:
        record_id = self.base.create_record(self._table("v2_events"), {
            "event_id": "",
            "objective_id": objective_id,
            "actor": actor,
            "event_type": event_type,
            "target_id": target_id,
            "detail": detail,
            "创建时间": utc_now(),
        })
        self.base.update_record(self._table("v2_events"), record_id, {"event_id": record_id})
        return record_id

    def _objective_fields(self, fields: dict) -> dict:
        mapping = {
            "status": "状态",
            "final_result": "最终结论",
        }
        return {mapping[key]: value for key, value in fields.items() if key in mapping}

    def _task_from_record(self, record) -> V2Task:
        fields = record.fields or {}
        metadata = self._loads(self._scalar(fields.get("metadata"), "{}"), {})
        if not isinstance(metadata, dict):
            metadata = {}
        return V2Task(
            task_id=self._scalar(fields.get("task_id"), record.record_id),
            objective_id=self._scalar(fields.get("objective_id")),
            subject=self._scalar(fields.get("标题")),
            description=self._scalar(fields.get("说明")),
            role=self._scalar(fields.get("角色")),
            status=self._scalar(fields.get("状态"), "pending"),
            owner=self._scalar(fields.get("owner")),
            lease_until=self._scalar(fields.get("lease_until")),
            attempt_count=int(self._scalar(fields.get("attempt_count"), "0") or 0),
            metadata=metadata,
        )

    def _edge_from_record(self, record) -> V2TaskEdge:
        fields = record.fields or {}
        return V2TaskEdge(
            edge_id=record.record_id,
            objective_id=self._scalar(fields.get("objective_id")),
            from_task_id=self._scalar(fields.get("from_task_id")),
            to_task_id=self._scalar(fields.get("to_task_id")),
            relation=self._scalar(fields.get("关系类型"), "blocks"),
        )

    def _claim_from_record(self, record) -> V2Claim:
        fields = record.fields or {}
        return V2Claim(
            claim_id=self._scalar(fields.get("claim_id"), record.record_id),
            objective_id=self._scalar(fields.get("objective_id")),
            task_id=self._scalar(fields.get("task_id")),
            worker_id=self._scalar(fields.get("worker_id")),
            status=self._scalar(fields.get("状态"), CLAIM_ACTIVE),
            nonce=self._scalar(fields.get("nonce")),
            created_at=self._scalar(fields.get("创建时间")),
        )

