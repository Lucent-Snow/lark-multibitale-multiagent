"""In-memory v2 store for protocol tests and offline demos."""

import copy
import json
import threading
from datetime import datetime, timezone

from src.agent_team_v2.contracts import (
    CLAIM_ACTIVE,
    V2Claim,
    V2Task,
    V2TaskEdge,
    WORKER_IDLE,
    TaskPlan,
)


def utc_now() -> str:
    """Return an ISO timestamp used by the v2 protocol."""
    return datetime.now(timezone.utc).isoformat()


class InMemoryAgentTeamV2Store:
    """Thread-safe in-memory implementation of the v2 control plane."""

    def __init__(self):
        self._lock = threading.RLock()
        self.objectives: dict[str, dict] = {}
        self.workers: dict[str, dict] = {}
        self.tasks: dict[str, V2Task] = {}
        self.edges: dict[str, V2TaskEdge] = {}
        self.claims: dict[str, V2Claim] = {}
        self.messages: dict[str, dict] = {}
        self.artifacts: dict[str, dict] = {}
        self.verifications: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self._counters: dict[str, int] = {}

    def _id(self, prefix: str) -> str:
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}-{self._counters[prefix]}"

    def create_objective(self, title: str, description: str,
                         initiator: str = "team-lead") -> str:
        with self._lock:
            objective_id = self._id("obj")
            self.objectives[objective_id] = {
                "objective_id": objective_id,
                "title": title,
                "description": description,
                "status": "in_progress",
                "initiator": initiator,
                "final_result": "",
                "created_at": utc_now(),
            }
            return objective_id

    def update_objective(self, objective_id: str, fields: dict) -> None:
        with self._lock:
            self.objectives[objective_id].update(fields)

    def register_worker(self, objective_id: str, worker_id: str, name: str,
                        role: str, capabilities: str, process_id: str = "") -> None:
        with self._lock:
            self.workers[worker_id] = {
                "worker_id": worker_id,
                "objective_id": objective_id,
                "name": name,
                "role": role,
                "capabilities": capabilities,
                "status": WORKER_IDLE,
                "current_task_id": "",
                "heartbeat_at": utc_now(),
                "process_id": process_id,
            }

    def heartbeat_worker(self, objective_id: str, worker_id: str,
                         status: str, current_task_id: str = "") -> None:
        with self._lock:
            worker = self.workers[worker_id]
            if worker["objective_id"] != objective_id:
                raise ValueError("Worker is outside objective scope")
            worker.update({
                "status": status,
                "current_task_id": current_task_id,
                "heartbeat_at": utc_now(),
            })

    def create_task(self, objective_id: str, plan: TaskPlan) -> V2Task:
        with self._lock:
            task_id = self._id("task")
            task = V2Task(
                task_id=task_id,
                objective_id=objective_id,
                subject=plan.subject,
                description=plan.description,
                role=plan.role,
                metadata=copy.deepcopy(plan.metadata),
            )
            self.tasks[task_id] = task
            return task

    def create_edge(self, objective_id: str, from_task_id: str,
                    to_task_id: str, relation: str = "blocks") -> str:
        with self._lock:
            self._require_task(objective_id, from_task_id)
            self._require_task(objective_id, to_task_id)
            edge_id = self._id("edge")
            self.edges[edge_id] = V2TaskEdge(
                edge_id=edge_id,
                objective_id=objective_id,
                from_task_id=from_task_id,
                to_task_id=to_task_id,
                relation=relation,
            )
            return edge_id

    def list_tasks(self, objective_id: str) -> list[V2Task]:
        with self._lock:
            return [
                task for task in self.tasks.values()
                if task.objective_id == objective_id
            ]

    def get_task(self, objective_id: str, task_id: str) -> V2Task:
        with self._lock:
            return self._require_task(objective_id, task_id)

    def update_task(self, objective_id: str, task_id: str, fields: dict) -> V2Task:
        with self._lock:
            task = self._require_task(objective_id, task_id)
            metadata = fields.get("metadata", task.metadata)
            if "metadata" in fields:
                metadata = {**metadata}
            updated = V2Task(
                task_id=task.task_id,
                objective_id=task.objective_id,
                subject=fields.get("subject", task.subject),
                description=fields.get("description", task.description),
                role=fields.get("role", task.role),
                status=fields.get("status", task.status),
                owner=fields.get("owner", task.owner),
                lease_until=fields.get("lease_until", task.lease_until),
                attempt_count=int(fields.get("attempt_count", task.attempt_count)),
                metadata=metadata,
            )
            self.tasks[task_id] = updated
            return updated

    def list_edges(self, objective_id: str) -> list[V2TaskEdge]:
        with self._lock:
            return [
                edge for edge in self.edges.values()
                if edge.objective_id == objective_id
            ]

    def create_claim(self, objective_id: str, task_id: str, worker_id: str,
                     nonce: str) -> V2Claim:
        with self._lock:
            self._require_task(objective_id, task_id)
            claim_id = self._id("claim")
            claim = V2Claim(
                claim_id=claim_id,
                objective_id=objective_id,
                task_id=task_id,
                worker_id=worker_id,
                status=CLAIM_ACTIVE,
                nonce=nonce,
                created_at=utc_now(),
            )
            self.claims[claim_id] = claim
            return claim

    def list_claims(self, objective_id: str, task_id: str) -> list[V2Claim]:
        with self._lock:
            return [
                claim for claim in self.claims.values()
                if claim.objective_id == objective_id and claim.task_id == task_id
            ]

    def update_claim(self, objective_id: str, claim_id: str, status: str) -> None:
        with self._lock:
            claim = self.claims[claim_id]
            if claim.objective_id != objective_id:
                raise ValueError("Claim is outside objective scope")
            self.claims[claim_id] = V2Claim(
                claim_id=claim.claim_id,
                objective_id=claim.objective_id,
                task_id=claim.task_id,
                worker_id=claim.worker_id,
                status=status,
                nonce=claim.nonce,
                created_at=claim.created_at,
            )

    def create_message(self, objective_id: str, sender: str, recipient: str,
                       summary: str, message: str, task_id: str = "") -> str:
        with self._lock:
            if task_id:
                self._require_task(objective_id, task_id)
            message_id = self._id("message")
            self.messages[message_id] = {
                "message_id": message_id,
                "objective_id": objective_id,
                "from": sender,
                "to": recipient,
                "summary": summary,
                "message": message,
                "task_id": task_id,
                "status": "unread",
                "created_at": utc_now(),
            }
            return message_id

    def create_artifact(self, objective_id: str, task_id: str, author: str,
                        title: str, content: str) -> str:
        with self._lock:
            self._require_task(objective_id, task_id)
            artifact_id = self._id("artifact")
            self.artifacts[artifact_id] = {
                "artifact_id": artifact_id,
                "objective_id": objective_id,
                "task_id": task_id,
                "author": author,
                "title": title,
                "content": content,
                "created_at": utc_now(),
            }
            return artifact_id

    def list_artifacts(self, objective_id: str) -> list[dict]:
        with self._lock:
            return [
                artifact for artifact in self.artifacts.values()
                if artifact["objective_id"] == objective_id
            ]

    def create_verification(self, objective_id: str, task_id: str, verifier: str,
                            verdict: str, issues: str = "",
                            suggestions: str = "") -> str:
        with self._lock:
            self._require_task(objective_id, task_id)
            verification_id = self._id("verification")
            self.verifications[verification_id] = {
                "verification_id": verification_id,
                "objective_id": objective_id,
                "task_id": task_id,
                "verifier": verifier,
                "verdict": verdict,
                "issues": issues,
                "suggestions": suggestions,
                "created_at": utc_now(),
            }
            return verification_id

    def list_verifications(self, objective_id: str) -> list[dict]:
        with self._lock:
            return [
                verification for verification in self.verifications.values()
                if verification["objective_id"] == objective_id
            ]

    def log_event(self, objective_id: str, actor: str, event_type: str,
                  target_id: str, detail: str) -> str:
        with self._lock:
            event_id = self._id("event")
            self.events[event_id] = {
                "event_id": event_id,
                "objective_id": objective_id,
                "actor": actor,
                "event_type": event_type,
                "target_id": target_id,
                "detail": detail,
                "created_at": utc_now(),
            }
            return event_id

    def _require_task(self, objective_id: str, task_id: str) -> V2Task:
        task = self.tasks[task_id]
        if task.objective_id != objective_id:
            raise ValueError(f"Task is outside objective scope: {task_id}")
        return task

    def dump_json(self) -> str:
        """Return a JSON snapshot useful for debugging tests."""
        with self._lock:
            return json.dumps({
                "objectives": self.objectives,
                "workers": self.workers,
                "tasks": [task.__dict__ for task in self.tasks.values()],
                "edges": [edge.__dict__ for edge in self.edges.values()],
                "claims": [claim.__dict__ for claim in self.claims.values()],
            }, ensure_ascii=False, indent=2)
