"""Feishu Base implementation of the agent-team store."""

import json

from src.agent_team.contracts import (
    AgentTeamTask,
    TASK_PENDING,
    TaskSpec,
)
from src.base_client.client import BaseClient


class BaseAgentTeamStore:
    """Persist agent-team task-market state in Feishu Base."""

    def __init__(self, base_client: BaseClient,
                 task_scope: dict | None = None):
        base_client.table_ids.require_agent_team()
        self.base = base_client
        self.task_scope = task_scope or {}

    def _table(self, name: str) -> str:
        table_id = getattr(self.base.table_ids, name)
        if not table_id:
            raise ValueError(f"Agent-team table is not configured: {name}")
        return table_id

    @staticmethod
    def _scalar(value, default: str = "") -> str:
        """Normalize Base cell values that may arrive as scalar or single-item list."""
        if isinstance(value, list):
            if not value:
                return default
            return "".join(BaseAgentTeamStore._scalar(item, "") for item in value)
        if isinstance(value, dict):
            if "text" in value:
                return str(value["text"])
            if "name" in value:
                return str(value["name"])
            return str(value)
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _task_from_record(record) -> AgentTeamTask:
        fields = record.fields or {}
        blocked_by_raw = BaseAgentTeamStore._scalar(fields.get("阻塞依赖"), "[]")
        metadata_raw = BaseAgentTeamStore._scalar(fields.get("元数据"), "{}")
        try:
            blocked_by = json.loads(blocked_by_raw)
        except (TypeError, json.JSONDecodeError):
            blocked_by = []
        try:
            metadata = json.loads(metadata_raw)
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        if not isinstance(blocked_by, list):
            blocked_by = []
        if not isinstance(metadata, dict):
            metadata = {}
        return AgentTeamTask(
            task_id=record.record_id,
            subject=BaseAgentTeamStore._scalar(fields.get("任务标题")),
            description=BaseAgentTeamStore._scalar(fields.get("任务说明")),
            role=BaseAgentTeamStore._scalar(fields.get("角色")),
            status=BaseAgentTeamStore._scalar(fields.get("状态"), TASK_PENDING),
            owner=BaseAgentTeamStore._scalar(fields.get("负责人")),
            blocked_by=[str(value) for value in blocked_by],
            metadata=metadata,
        )

    def create_task(self, spec: TaskSpec) -> AgentTeamTask:
        metadata = {**spec.metadata, **self.task_scope}
        record_id = self.base.create_record(self._table("tasks"), {
            "任务标题": spec.subject,
            "任务说明": spec.description,
            "角色": spec.role,
            "状态": TASK_PENDING,
            "负责人": "",
            "阻塞依赖": json.dumps(spec.blocked_by, ensure_ascii=False),
            "元数据": json.dumps(metadata, ensure_ascii=False),
        })
        return AgentTeamTask(
            task_id=record_id,
            subject=spec.subject,
            description=spec.description,
            role=spec.role,
            blocked_by=spec.blocked_by,
            metadata=metadata,
        )

    def list_tasks(self) -> list[AgentTeamTask]:
        tasks = [
            self._task_from_record(record)
            for record in self.base.list_records(self._table("tasks"))
        ]
        if not self.task_scope:
            return tasks
        return [
            task for task in tasks
            if all(task.metadata.get(key) == value
                   for key, value in self.task_scope.items())
        ]

    def _get_scoped_task(self, task_id: str) -> AgentTeamTask:
        task = self._task_from_record(self.base.get_record(self._table("tasks"), task_id))
        if self.task_scope and not all(
            task.metadata.get(key) == value
            for key, value in self.task_scope.items()
        ):
            raise ValueError(f"Task is outside the current agent-team scope: {task_id}")
        return task

    def update_task(self, task_id: str, fields: dict) -> AgentTeamTask:
        self._get_scoped_task(task_id)
        base_fields = {}
        if "status" in fields:
            base_fields["状态"] = fields["status"]
        if "owner" in fields:
            base_fields["负责人"] = fields["owner"]
        if "metadata" in fields:
            metadata = {**fields["metadata"], **self.task_scope}
            base_fields["元数据"] = json.dumps(metadata, ensure_ascii=False)
        if base_fields:
            self.base.update_record(self._table("tasks"), task_id, base_fields)
        return self._task_from_record(self.base.get_record(self._table("tasks"), task_id))

    def create_artifact(self, task_id: str, title: str, content: str,
                        author: str) -> str:
        self._get_scoped_task(task_id)
        return self.base.create_record(self._table("artifacts"), {
            "关联任务ID": task_id,
            "产物标题": title,
            "产物内容": content,
            "作者": author,
        })

    def create_message(self, sender: str, recipient: str, summary: str,
                       message: str, task_id: str = "") -> str:
        if task_id:
            self._get_scoped_task(task_id)
        return self.base.create_record(self._table("messages"), {
            "发送者": sender,
            "接收者": recipient,
            "摘要": summary,
            "消息内容": message,
            "关联任务ID": task_id,
            "状态": "unread",
        })

    def log_operation(self, operator: str, op_type: str, target_id: str,
                      detail: str) -> str:
        return self.base.log_operation(operator, op_type, target_id, detail)
