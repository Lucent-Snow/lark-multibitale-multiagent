"""Contracts for the agent-team protocol."""

from dataclasses import dataclass, field
from typing import Protocol


TASK_PENDING = "pending"
TASK_IN_PROGRESS = "in_progress"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"

VERIFICATION_PASS = "PASS"
VERIFICATION_FAIL = "FAIL"

DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class WorkerSpec:
    """Leader-produced worker specification with custom prompt."""

    worker_id: str
    name: str
    role: str
    prompt: str = ""


@dataclass(frozen=True)
class TaskPlan:
    """Leader-produced task plan before it is persisted."""

    subject: str
    description: str
    role: str
    blocked_by_subjects: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Task:
    """A task record — one row in the objective's table."""

    task_id: str
    objective_id: str
    subject: str
    description: str
    role: str
    status: str = TASK_PENDING
    owner: str = ""
    attempt_count: int = 0
    depends_on: str = ""          # comma-separated task subjects
    artifact: str = ""             # worker output content
    artifact_title: str = ""       # short title for the artifact
    verdict: str = ""              # PASS or FAIL
    issues: str = ""               # verification issues found
    created_at: str = ""


class ObjectiveStore(Protocol):
    """Persistence for ONE objective. One table, all in one place."""

    def create_objective(self, title: str, description: str) -> str:
        ...

    def add_task(self, plan: TaskPlan) -> Task:
        ...

    def list_tasks(self) -> list[Task]:
        ...

    def get_task(self, task_id: str) -> Task:
        ...

    def update_task(self, task_id: str, fields: dict) -> Task:
        ...
