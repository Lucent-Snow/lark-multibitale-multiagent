"""Shared contracts for the Base-backed agent-team mode."""

from dataclasses import dataclass, field
from typing import Protocol


TASK_PENDING = "pending"
TASK_IN_PROGRESS = "in_progress"
TASK_BLOCKED = "blocked"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"

TERMINAL_TASK_STATUSES = {TASK_COMPLETED, TASK_FAILED}


@dataclass(frozen=True)
class TaskSpec:
    """Leader-produced task specification for a worker agent."""

    subject: str
    description: str
    role: str
    blocked_by: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AgentTeamTask:
    """Stored task state used by the agent-team engine."""

    task_id: str
    subject: str
    description: str
    role: str
    status: str = TASK_PENDING
    owner: str = ""
    blocked_by: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_TASK_STATUSES


class AgentTeamStore(Protocol):
    """Persistence boundary for agent-team state.

    Implementations can be in-memory for tests or backed by Feishu Base.
    """

    def create_task(self, spec: TaskSpec) -> AgentTeamTask:
        ...

    def list_tasks(self) -> list[AgentTeamTask]:
        ...

    def update_task(self, task_id: str, fields: dict) -> AgentTeamTask:
        ...

    def create_artifact(self, task_id: str, title: str, content: str,
                        author: str) -> str:
        ...

    def create_message(self, sender: str, recipient: str, summary: str,
                       message: str, task_id: str = "") -> str:
        ...

    def log_operation(self, operator: str, op_type: str, target_id: str,
                      detail: str) -> str:
        ...
