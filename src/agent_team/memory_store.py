"""In-memory store for protocol tests and offline demos."""

import copy
import threading
from datetime import datetime, timezone

from src.agent_team.contracts import TASK_PENDING, Task, TaskPlan, ObjectiveStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryObjectiveStore:
    """Thread-safe in-memory store — one objective, one table."""

    def __init__(self):
        self._lock = threading.RLock()
        self.objective_title = ""
        self.objective_description = ""
        self.objective_status = "in_progress"
        self.tasks: dict[str, Task] = {}
        self._counter = 0

    def _id(self) -> str:
        self._counter += 1
        return f"task-{self._counter}"

    def create_objective(self, title: str, description: str) -> str:
        with self._lock:
            self.objective_title = title
            self.objective_description = description
            self.objective_status = "in_progress"
            return "obj-memory"

    def add_task(self, plan: TaskPlan) -> Task:
        with self._lock:
            tid = self._id()
            task = Task(
                task_id=tid,
                objective_id="obj-memory",
                subject=plan.subject,
                description=plan.description,
                role=plan.role,
                depends_on=",".join(plan.blocked_by_subjects),
            )
            self.tasks[tid] = task
            return task

    def list_tasks(self) -> list[Task]:
        with self._lock:
            return list(self.tasks.values())

    def get_task(self, task_id: str) -> Task:
        with self._lock:
            return self.tasks[task_id]

    def update_task(self, task_id: str, fields: dict) -> Task:
        with self._lock:
            task = self.tasks[task_id]
            updated = Task(
                task_id=task.task_id,
                objective_id=task.objective_id,
                subject=fields.get("subject", task.subject),
                description=fields.get("description", task.description),
                role=fields.get("role", task.role),
                status=fields.get("status", task.status),
                owner=fields.get("owner", task.owner),
                attempt_count=int(fields.get("attempt_count", task.attempt_count)),
                depends_on=fields.get("depends_on", task.depends_on),
                artifact=fields.get("artifact", task.artifact),
                artifact_title=fields.get("artifact_title", task.artifact_title),
                verdict=fields.get("verdict", task.verdict),
                issues=fields.get("issues", task.issues),
                created_at=fields.get("created_at", task.created_at),
            )
            self.tasks[task_id] = updated
            return updated
