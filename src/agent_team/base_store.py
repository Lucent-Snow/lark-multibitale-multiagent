"""Feishu Base store — one table per objective, all data in one place."""

import json
from datetime import datetime, timezone

from src.agent_team.contracts import TASK_PENDING, Task, TaskPlan, ObjectiveStore
from src.base_client.client import BaseClient

FIELDS = [
    "task_id", "objective_id", "subject", "description", "role",
    "status", "owner", "attempt_count", "depends_on",
    "artifact", "artifact_title", "verdict", "issues", "created_at",
]

# Sentinel stored in the `role` column of the objective metadata row.
# A single row per table holds the user-facing objective title/description so
# the dashboard can list multiple objectives without a separate metadata table.
OBJECTIVE_META_ROLE = "__objective_meta__"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scalar(value, default: str = "") -> str:
    if isinstance(value, list):
        if not value:
            return default
        return "".join(_scalar(item, "") for item in value)
    if isinstance(value, dict):
        if "text" in value:
            return str(value["text"])
        return str(value)
    if value is None:
        return default
    return str(value)


class BaseObjectiveStore:
    """One Base table per objective — tasks, artifacts, verifications all in one."""

    def __init__(self, base_client: BaseClient, objective_id: str):
        self.base = base_client
        self.objective_id = objective_id
        self.table_name = f"obj_{objective_id}"
        self.table_id = self._resolve_table()

    def _resolve_table(self) -> str:
        # Try to find existing table by name
        existing = self._find_table(self.table_name)
        if existing:
            return existing
        # Create new table
        return self.base.create_table(self.table_name, FIELDS)

    def _find_table(self, name: str) -> str | None:
        from lark_oapi.api.bitable.v1 import ListAppTableRequest
        request = ListAppTableRequest.builder() \
            .app_token(self.base.base_token).page_size(100).build()
        response = self.base._client.bitable.v1.app_table.list(request, self.base._opt())
        if response.success():
            for item in (response.data.items or []):
                if item.name == name:
                    return item.table_id
        return None

    def create_objective(self, title: str, description: str) -> str:
        # The table creation IS the objective creation. title/desc live in a
        # dedicated metadata row so the dashboard can show real titles instead
        # of "obj_<id>".
        self.set_objective_meta(title, description)
        return self.objective_id

    def set_objective_meta(self, title: str, description: str) -> None:
        """Upsert the single objective metadata row for this table."""
        existing = self._find_meta_record_id()
        fields = {
            "task_id": "",
            "objective_id": self.objective_id,
            "subject": title or "",
            "description": description or "",
            "role": OBJECTIVE_META_ROLE,
            "status": "meta",
            "owner": "",
            "attempt_count": "0",
            "depends_on": "",
            "artifact": "",
            "artifact_title": "",
            "verdict": "",
            "issues": "",
            "created_at": _now(),
        }
        if existing:
            self.base.update_record(self.table_id, existing, {
                "subject": fields["subject"],
                "description": fields["description"],
            })
        else:
            record_id = self.base.create_record(self.table_id, fields)
            self.base.update_record(self.table_id, record_id, {"task_id": record_id})

    def get_objective_meta(self) -> dict:
        """Return {title, description, created_at} from the metadata row, or {}."""
        for record in self.base.list_records(self.table_id):
            f = record.fields or {}
            if _scalar(f.get("role")) == OBJECTIVE_META_ROLE:
                return {
                    "title": _scalar(f.get("subject")),
                    "description": _scalar(f.get("description")),
                    "created_at": _scalar(f.get("created_at")),
                }
        return {}

    def _find_meta_record_id(self) -> str | None:
        for record in self.base.list_records(self.table_id):
            f = record.fields or {}
            if _scalar(f.get("role")) == OBJECTIVE_META_ROLE:
                return record.record_id
        return None

    def add_task(self, plan: TaskPlan) -> Task:
        record_id = self.base.create_record(self.table_id, {
            "task_id": "",
            "objective_id": self.objective_id,
            "subject": plan.subject,
            "description": plan.description,
            "role": plan.role,
            "status": TASK_PENDING,
            "owner": "",
            "attempt_count": "0",
            "depends_on": ",".join(plan.blocked_by_subjects),
            "artifact": "",
            "artifact_title": "",
            "verdict": "",
            "issues": "",
            "created_at": _now(),
        })
        self.base.update_record(self.table_id, record_id, {"task_id": record_id})
        return Task(
            task_id=record_id,
            objective_id=self.objective_id,
            subject=plan.subject,
            description=plan.description,
            role=plan.role,
            depends_on=",".join(plan.blocked_by_subjects),
        )

    def list_tasks(self) -> list[Task]:
        tasks = []
        for record in self.base.list_records(self.table_id):
            f = record.fields or {}
            if _scalar(f.get("role")) == OBJECTIVE_META_ROLE:
                continue
            tasks.append(Task(
                task_id=_scalar(f.get("task_id"), record.record_id),
                objective_id=_scalar(f.get("objective_id")),
                subject=_scalar(f.get("subject")),
                description=_scalar(f.get("description")),
                role=_scalar(f.get("role")),
                status=_scalar(f.get("status"), TASK_PENDING),
                owner=_scalar(f.get("owner")),
                attempt_count=int(_scalar(f.get("attempt_count"), "0") or 0),
                depends_on=_scalar(f.get("depends_on")),
                artifact=_scalar(f.get("artifact")),
                artifact_title=_scalar(f.get("artifact_title")),
                verdict=_scalar(f.get("verdict")),
                issues=_scalar(f.get("issues")),
                created_at=_scalar(f.get("created_at")),
            ))
        return tasks

    def get_task(self, task_id: str) -> Task:
        record = self.base.get_record(self.table_id, task_id)
        f = record.fields or {}
        return Task(
            task_id=_scalar(f.get("task_id"), record.record_id),
            objective_id=_scalar(f.get("objective_id")),
            subject=_scalar(f.get("subject")),
            description=_scalar(f.get("description")),
            role=_scalar(f.get("role")),
            status=_scalar(f.get("status"), TASK_PENDING),
            owner=_scalar(f.get("owner")),
            attempt_count=int(_scalar(f.get("attempt_count"), "0") or 0),
            depends_on=_scalar(f.get("depends_on")),
            artifact=_scalar(f.get("artifact")),
            artifact_title=_scalar(f.get("artifact_title")),
            verdict=_scalar(f.get("verdict")),
            issues=_scalar(f.get("issues")),
            created_at=_scalar(f.get("created_at")),
        )

    def update_task(self, task_id: str, fields: dict) -> Task:
        base_fields = {}
        mapping = {
            "subject": "subject", "description": "description", "role": "role",
            "status": "status", "owner": "owner",
            "attempt_count": "attempt_count", "depends_on": "depends_on",
            "artifact": "artifact", "artifact_title": "artifact_title",
            "verdict": "verdict", "issues": "issues",
        }
        for key, field_name in mapping.items():
            if key in fields:
                val = fields[key]
                if isinstance(val, int):
                    val = str(val)
                base_fields[field_name] = val
        if base_fields:
            self.base.update_record(self.table_id, task_id, base_fields)
        return self.get_task(task_id)
