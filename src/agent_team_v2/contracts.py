"""Contracts for the Base-first agent-team v2 protocol."""

from dataclasses import dataclass, field
from typing import Protocol


TASK_PENDING = "pending"
TASK_CLAIMED = "claimed"
TASK_IN_PROGRESS = "in_progress"
TASK_COMPLETED = "completed"
TASK_FAILED = "failed"

WORKER_IDLE = "idle"
WORKER_WORKING = "working"

CLAIM_ACTIVE = "active"
CLAIM_WON = "won"
CLAIM_LOST = "lost"
CLAIM_EXPIRED = "expired"

VERIFICATION_PASS = "PASS"
VERIFICATION_FAIL = "FAIL"

DEFAULT_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class TaskPlan:
    """Leader-produced task plan before it is persisted."""

    subject: str
    description: str
    role: str
    blocked_by_subjects: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class V2Task:
    """Persisted v2 task state."""

    task_id: str
    objective_id: str
    subject: str
    description: str
    role: str
    status: str = TASK_PENDING
    owner: str = ""
    lease_until: str = ""
    attempt_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class V2TaskEdge:
    """Directed task dependency: from_task_id blocks to_task_id."""

    edge_id: str
    objective_id: str
    from_task_id: str
    to_task_id: str
    relation: str = "blocks"


@dataclass(frozen=True)
class V2Claim:
    """Claim attempt for deterministic winner selection."""

    claim_id: str
    objective_id: str
    task_id: str
    worker_id: str
    status: str
    nonce: str
    created_at: str


class AgentTeamV2Store(Protocol):
    """Persistence boundary for the v2 control plane."""

    def create_objective(self, title: str, description: str,
                         initiator: str = "team-lead") -> str:
        ...

    def update_objective(self, objective_id: str, fields: dict) -> None:
        ...

    def register_worker(self, objective_id: str, worker_id: str, name: str,
                        role: str, capabilities: str, process_id: str = "") -> None:
        ...

    def heartbeat_worker(self, objective_id: str, worker_id: str,
                         status: str, current_task_id: str = "") -> None:
        ...

    def create_task(self, objective_id: str, plan: TaskPlan) -> V2Task:
        ...

    def create_edge(self, objective_id: str, from_task_id: str,
                    to_task_id: str, relation: str = "blocks") -> str:
        ...

    def list_tasks(self, objective_id: str) -> list[V2Task]:
        ...

    def get_task(self, objective_id: str, task_id: str) -> V2Task:
        ...

    def update_task(self, objective_id: str, task_id: str, fields: dict) -> V2Task:
        ...

    def list_edges(self, objective_id: str) -> list[V2TaskEdge]:
        ...

    def create_claim(self, objective_id: str, task_id: str, worker_id: str,
                     nonce: str) -> V2Claim:
        ...

    def list_claims(self, objective_id: str, task_id: str) -> list[V2Claim]:
        ...

    def update_claim(self, objective_id: str, claim_id: str, status: str) -> None:
        ...

    def create_message(self, objective_id: str, sender: str, recipient: str,
                       summary: str, message: str, task_id: str = "") -> str:
        ...

    def create_artifact(self, objective_id: str, task_id: str, author: str,
                        title: str, content: str) -> str:
        ...

    def list_artifacts(self, objective_id: str) -> list[dict]:
        ...

    def create_verification(self, objective_id: str, task_id: str, verifier: str,
                            verdict: str, issues: str = "",
                            suggestions: str = "") -> str:
        ...

    def list_verifications(self, objective_id: str) -> list[dict]:
        ...

    def log_event(self, objective_id: str, actor: str, event_type: str,
                  target_id: str, detail: str) -> str:
        ...
