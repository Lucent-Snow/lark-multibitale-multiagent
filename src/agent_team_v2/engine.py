"""Leader and worker protocol for agent-team v2."""

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable

from src.agent_team_v2.contracts import (
    CLAIM_ACTIVE,
    CLAIM_EXPIRED,
    CLAIM_LOST,
    CLAIM_WON,
    DEFAULT_MAX_ATTEMPTS,
    TASK_CLAIMED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_IN_PROGRESS,
    TASK_PENDING,
    VERIFICATION_FAIL,
    VERIFICATION_PASS,
    WORKER_IDLE,
    WORKER_WORKING,
    AgentTeamV2Store,
    TaskPlan,
    V2Task,
)
from src.agent_team_v2.memory_store import utc_now

if TYPE_CHECKING:
    from src.llm.client import LLMClient


V2_LEADER_SYSTEM_PROMPT = """\
You are the leader of an AI worker team.
Break the objective into a task graph where each task produces a concrete, reviewable artifact.

Rules:
- Workers cannot see your conversation. Every task description must be self-contained and include:
  1) What specific deliverable to produce
  2) What domains/aspects to cover (be specific, referencing the objective)
  3) What format/structure to use
- Use roles only from: researcher, editor, reviewer, analyst, manager.
- researcher: investigate facts, constraints, existing solutions, data
- editor: produce polished final deliverables, reports, integrated documents
- analyst: evaluate options, quantify trade-offs, design frameworks
- reviewer: find gaps, assess quality, suggest concrete improvements
- manager: coordinate across dependencies, synthesize multi-source inputs
- Prefer 4 to 5 tasks. More tasks = better parallelism and deeper coverage.
- Each task subject must be specific and descriptive (8-15 Chinese characters).
- Use blocked_by_subjects to express task dependencies by subject.
- The LAST task must be a reviewer task that audits all previous work.
- Output JSON only. No markdown.
"""


class PlanningError(Exception):
    """Raised when a real leader plan cannot be trusted."""


class LeaderV2:
    """Leader that plans objectives into task graphs."""

    def __init__(self, llm: "LLMClient | None" = None, allow_fallback: bool = True):
        self.llm = llm
        self.allow_fallback = allow_fallback

    def plan(self, title: str, description: str, max_tasks: int = 5) -> list[TaskPlan]:
        """Return a bounded, self-contained task plan."""
        if not self.llm:
            return self._fallback_or_raise("LLM client is not configured", title, description, max_tasks)
        prompt = f"""\
Objective title: {title}
Objective description:
{description}

Return a JSON array. Each item must have:
- subject: specific, descriptive task name (8-15 Chinese characters)
- description: detailed instructions covering what to produce, what domains to cover,
  what structure to use, and how it connects to the objective. Must be 3-5 sentences.
- role: one of researcher, editor, analyst, reviewer, manager
- blocked_by_subjects: list of task subjects this depends on (empty for entry tasks)
- metadata: {{"deliverable_type": "research_report|design_doc|integration_report|audit_report"}}

Max tasks: {max_tasks}
"""
        try:
            response = self.llm.chat_with_system(
                V2_LEADER_SYSTEM_PROMPT,
                prompt,
                temperature=0.2,
                max_tokens=4096,
            )
        except Exception as exc:
            return self._fallback_or_raise(
                f"Leader LLM call failed: {type(exc).__name__}",
                title,
                description,
                max_tasks,
            )
        return self._parse(response, title, description, max_tasks)

    def _parse(self, response: str, title: str, description: str,
               max_tasks: int) -> list[TaskPlan]:
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\[[\s\S]*\]", response)
            if not match:
                return self._fallback_or_raise(
                    "Leader response did not contain a JSON array",
                    title,
                    description,
                    max_tasks,
                )
            try:
                payload = json.loads(match.group())
            except json.JSONDecodeError:
                return self._fallback_or_raise(
                    "Leader response contained invalid JSON",
                    title,
                    description,
                    max_tasks,
                )
        if not isinstance(payload, list):
            return self._fallback_or_raise(
                "Leader response must be a JSON array",
                title,
                description,
                max_tasks,
            )

        plans = []
        for item in payload[:max_tasks]:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject") or "").strip()
            brief = str(item.get("description") or "").strip()
            role = str(item.get("role") or "manager").strip().lower()
            if role not in {"researcher", "editor", "reviewer", "analyst", "manager"}:
                role = "manager"
            blockers = item.get("blocked_by_subjects") or item.get("blocked_by") or []
            if not isinstance(blockers, list):
                blockers = []
            metadata = item.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            if subject and brief:
                plans.append(TaskPlan(
                    subject=subject,
                    description=brief,
                    role=role,
                    blocked_by_subjects=[str(value) for value in blockers],
                    metadata=metadata,
                ))

        known_subjects = {plan.subject for plan in plans}
        if len(known_subjects) != len(plans):
            return self._fallback_or_raise(
                "Leader response contains duplicate task subjects",
                title,
                description,
                max_tasks,
            )
        normalized = [
            TaskPlan(
                subject=plan.subject,
                description=_with_objective_context(
                    plan.description, title, description
                ),
                role=plan.role,
                blocked_by_subjects=[
                    blocker for blocker in plan.blocked_by_subjects
                    if blocker in known_subjects and blocker != plan.subject
                ],
                metadata=plan.metadata,
            )
            for plan in plans
        ]
        if not normalized:
            return self._fallback_or_raise(
                "Leader response did not contain valid tasks",
                title,
                description,
                max_tasks,
            )
        return normalized

    def _fallback_or_raise(self, reason: str, title: str, description: str,
                           max_tasks: int) -> list[TaskPlan]:
        if not self.allow_fallback:
            raise PlanningError(reason)
        return self._fallback_plan(title, description, max_tasks)

    def _fallback_plan(self, title: str, description: str,
                       max_tasks: int) -> list[TaskPlan]:
        objective = f"{title}\n\n{description}".strip()
        plans = [
            TaskPlan(
                subject="Research objective context",
                description=f"Research constraints, audience, and risks.\nObjective:\n{objective}",
                role="researcher",
            ),
            TaskPlan(
                subject="Draft primary deliverable",
                description=f"Produce the first complete deliverable.\nObjective:\n{objective}",
                role="editor",
                blocked_by_subjects=["Research objective context"],
            ),
            TaskPlan(
                subject="Analyze completion evidence",
                description="Check whether the deliverable covers the objective and identify gaps.",
                role="analyst",
                blocked_by_subjects=["Draft primary deliverable"],
            ),
            TaskPlan(
                subject="Verify final quality",
                description="Verify completeness, risks, and next actions. Return pass/fail evidence.",
                role="reviewer",
                blocked_by_subjects=["Analyze completion evidence"],
            ),
        ]
        return [
            TaskPlan(
                subject=plan.subject,
                description=_with_objective_context(plan.description, title, description),
                role=plan.role,
                blocked_by_subjects=plan.blocked_by_subjects,
                metadata=plan.metadata,
            )
            for plan in plans[:max_tasks]
        ]


class AgentTeamV2Engine:
    """Coordinates the v2 Base-first task board protocol."""

    def __init__(self, store: AgentTeamV2Store, leader: LeaderV2):
        self.store = store
        self.leader = leader

    def start_objective(self, title: str, description: str,
                        max_tasks: int = 5) -> dict:
        """Create an objective, tasks, and task-id dependency edges."""
        plans = self.leader.plan(title, description, max_tasks=max_tasks)
        fallback_subjects = {
            "Research objective context",
            "Draft primary deliverable",
            "Analyze completion evidence",
            "Verify final quality",
        }
        if {plan.subject for plan in plans} == fallback_subjects:
            plans = self.leader.plan(title, description, max_tasks=max_tasks)
        objective_id = self.store.create_objective(title, description)
        tasks: list[V2Task] = []
        tasks_by_subject: dict[str, V2Task] = {}
        for plan in plans:
            task = self.store.create_task(objective_id, plan)
            tasks.append(task)
            tasks_by_subject[plan.subject] = task
        edge_ids = []
        for plan in plans:
            to_task = tasks_by_subject[plan.subject]
            for blocker_subject in plan.blocked_by_subjects:
                blocker = tasks_by_subject.get(blocker_subject)
                if not blocker:
                    self.store.log_event(
                        objective_id,
                        "team-lead",
                        "planning_dependency_dropped",
                        to_task.task_id,
                        blocker_subject,
                    )
                    continue
                edge_ids.append(self.store.create_edge(
                    objective_id,
                    from_task_id=blocker.task_id,
                    to_task_id=to_task.task_id,
                ))
        self.store.log_event(
            objective_id,
            "team-lead",
            "objective_planned",
            objective_id,
            f"Created {len(tasks_by_subject)} tasks and {len(edge_ids)} edges",
        )
        return {
            "objective_id": objective_id,
            "tasks": tasks,
            "edge_ids": edge_ids,
        }

    def complete_objective_if_ready(self, objective_id: str) -> bool:
        """Close the objective only after tasks and verifications are complete."""
        tasks = self.store.list_tasks(objective_id)
        if not tasks or any(task.status != TASK_COMPLETED for task in tasks):
            return False
        verified_task_ids = {
            _scalar(verification.get("task_id") or verification.get("关联任务ID") or "")
            for verification in self.store.list_verifications(objective_id)
            if _verification_verdict(verification) == VERIFICATION_PASS
        }
        if {task.task_id for task in tasks} - verified_task_ids:
            return False
        self.store.update_objective(objective_id, {
            "status": "completed",
            "final_result": "Agent-team v2 objective completed with verification.",
        })
        self.store.log_event(
            objective_id,
            "team-lead",
            "objective_completed",
            objective_id,
            f"Completed {len(tasks)} verified tasks",
        )
        return True

    def recover_expired_tasks(self, objective_id: str, actor: str = "team-lead") -> int:
        """Recover expired leased tasks without requiring a worker claim attempt."""
        recovered_count = 0
        now = datetime.now(timezone.utc)
        for task in self.store.list_tasks(objective_id):
            if task.status not in {TASK_CLAIMED, TASK_IN_PROGRESS}:
                continue
            if not _lease_expired(task.lease_until, now=now):
                continue
            self.store.update_task(objective_id, task.task_id, {
                "status": TASK_PENDING,
                "owner": "",
                "lease_until": "",
            })
            for claim in self.store.list_claims(objective_id, task.task_id):
                if claim.status in {CLAIM_ACTIVE, CLAIM_WON}:
                    self.store.update_claim(objective_id, claim.claim_id, CLAIM_EXPIRED)
            self.store.log_event(
                objective_id,
                actor,
                "task_lease_expired",
                task.task_id,
                f"Recovered expired {task.status} task from owner {task.owner}",
            )
            recovered_count += 1
        return recovered_count

    def retry_failed_tasks(self, objective_id: str, max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                           actor: str = "team-lead") -> int:
        """Retry failed tasks that are still under the max attempt threshold."""
        retried = 0
        for task in self.store.list_tasks(objective_id):
            if task.status != TASK_FAILED:
                continue
            if task.attempt_count >= max_attempts:
                continue
            for claim in self.store.list_claims(objective_id, task.task_id):
                if claim.status in {CLAIM_ACTIVE, CLAIM_WON}:
                    self.store.update_claim(objective_id, claim.claim_id, CLAIM_EXPIRED)
            self.store.update_task(objective_id, task.task_id, {
                "status": TASK_PENDING,
                "owner": "",
                "lease_until": "",
            })
            self.store.log_event(
                objective_id,
                actor,
                "task_retry",
                task.task_id,
                f"Retrying failed task (attempt {task.attempt_count}/{max_attempts})",
            )
            retried += 1
        return retried


class WorkerV2:
    """One worker process participating through the shared v2 task board."""

    def __init__(self, store: AgentTeamV2Store, objective_id: str,
                 worker_id: str, role: str,
                 artifact_fn: Callable[[V2Task], str] | None = None,
                 verification_fn: Callable[[V2Task, str], dict] | None = None,
                 lease_seconds: int = 120,
                 max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        self.store = store
        self.objective_id = objective_id
        self.worker_id = worker_id
        self.role = role
        self.artifact_fn = artifact_fn or self._default_artifact
        self.verification_fn = verification_fn or self._default_verification
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def register(self) -> None:
        """Register or refresh this worker in the worker table."""
        self.store.register_worker(
            objective_id=self.objective_id,
            worker_id=self.worker_id,
            name=self.worker_id,
            role=self.role,
            capabilities=f"Handle {self.role} tasks",
            process_id=str(os.getpid()),
        )

    def run_once(self) -> dict:
        """Claim and complete one available task."""
        self.register()
        task = self.claim_next_task()
        if not task:
            self.store.heartbeat_worker(
                self.objective_id, self.worker_id, WORKER_IDLE, ""
            )
            return {"status": "idle", "task_id": ""}
        self.store.heartbeat_worker(
            self.objective_id, self.worker_id, WORKER_WORKING, task.task_id
        )
        active_task = task
        try:
            active_task = self.store.update_task(self.objective_id, task.task_id, {
                "status": TASK_IN_PROGRESS,
                "owner": self.worker_id,
            })
            task_with_context = self._with_dependency_context(active_task)
            artifact_content = self.artifact_fn(task_with_context)
            artifact_id = self.store.create_artifact(
                self.objective_id,
                active_task.task_id,
                self.worker_id,
                f"{active_task.subject} output",
                artifact_content,
            )
            verification = self.verification_fn(task_with_context, artifact_content)
            verdict = str(verification.get("verdict") or VERIFICATION_FAIL)
            issues = str(verification.get("issues") or "")
            suggestions = str(verification.get("suggestions") or "")
            self.store.create_verification(
                self.objective_id,
                active_task.task_id,
                verifier=f"{self.worker_id}-verifier",
                verdict=verdict,
                issues=issues,
                suggestions=suggestions,
            )
            if verdict != VERIFICATION_PASS:
                if active_task.attempt_count < self.max_attempts:
                    self._expire_open_claims(active_task.task_id)
                    retry_metadata = dict(active_task.metadata)
                    retry_metadata["previous_issues"] = issues
                    retry_metadata["previous_suggestions"] = suggestions
                    retried = self.store.update_task(self.objective_id, active_task.task_id, {
                        "status": TASK_PENDING,
                        "owner": "",
                        "lease_until": "",
                        "metadata": retry_metadata,
                    })
                    self.store.create_message(
                        self.objective_id,
                        self.worker_id,
                        "team-lead",
                        f"Verification failed, retrying {retried.subject}",
                        f"Task {retried.task_id} attempt {active_task.attempt_count}/{self.max_attempts}: "
                        f"{issues or 'Verification failed'}. Artifact: {artifact_id}",
                        task_id=retried.task_id,
                    )
                    self.store.log_event(
                        self.objective_id,
                        self.worker_id,
                        "task_verification_retry",
                        retried.task_id,
                        f"Retry {active_task.attempt_count}/{self.max_attempts}: {issues or 'Verification failed'}",
                    )
                    return {
                        "status": "retry",
                        "task_id": retried.task_id,
                        "artifact_id": artifact_id,
                        "verdict": verdict,
                    }
                failed = self.store.update_task(self.objective_id, active_task.task_id, {
                    "status": TASK_FAILED,
                    "owner": self.worker_id,
                    "completed_at": utc_now(),
                })
                self.store.create_message(
                    self.objective_id,
                    self.worker_id,
                    "team-lead",
                    f"Failed verification for {failed.subject}",
                    f"Task {failed.task_id} exhausted {self.max_attempts} attempts. "
                    f"Artifact: {artifact_id}. Issues: {issues}",
                    task_id=failed.task_id,
                )
                self.store.log_event(
                    self.objective_id,
                    self.worker_id,
                    "task_verification_failed",
                    failed.task_id,
                    issues or suggestions or f"Exhausted {self.max_attempts} attempts",
                )
                return {
                    "status": "failed",
                    "task_id": failed.task_id,
                    "artifact_id": artifact_id,
                    "verdict": verdict,
                }
            completed = self.store.update_task(self.objective_id, active_task.task_id, {
                "status": TASK_COMPLETED,
                "owner": self.worker_id,
                "completed_at": utc_now(),
            })
            self.store.create_message(
                self.objective_id,
                self.worker_id,
                "team-lead",
                f"Completed {completed.subject}",
                f"Task {completed.task_id} completed. Artifact: {artifact_id}",
                task_id=completed.task_id,
            )
            self.store.log_event(
                self.objective_id,
                self.worker_id,
                "task_completed",
                completed.task_id,
                artifact_id,
            )
            return {
                "status": "completed",
                "task_id": completed.task_id,
                "artifact_id": artifact_id,
            }
        except Exception as exc:
            self._recover_failed_execution(active_task, exc)
            raise
        finally:
            self.store.heartbeat_worker(
                self.objective_id, self.worker_id, WORKER_IDLE, ""
            )

    def claim_next_task(self) -> V2Task | None:
        """Claim the earliest unblocked compatible task with claim arbitration."""
        for task in self._claimable_tasks():
            claimed = self._try_claim(task)
            if claimed:
                return claimed
        return None

    def _claimable_tasks(self) -> list[V2Task]:
        tasks = [
            self._recover_expired_task(task)
            for task in self.store.list_tasks(self.objective_id)
        ]
        completed_task_ids = {
            task.task_id for task in tasks if task.status == TASK_COMPLETED
        }
        blockers_by_task: dict[str, set[str]] = {}
        for edge in self.store.list_edges(self.objective_id):
            blockers_by_task.setdefault(edge.to_task_id, set()).add(edge.from_task_id)
        claimable = []
        for task in tasks:
            if task.status != TASK_PENDING or task.owner:
                continue
            if self.role != "manager" and task.role != self.role:
                continue
            unresolved = blockers_by_task.get(task.task_id, set()) - completed_task_ids
            if unresolved:
                continue
            claimable.append(task)
        return sorted(claimable, key=lambda item: item.task_id)

    def _recover_expired_task(self, task: V2Task) -> V2Task:
        if task.status not in {TASK_CLAIMED, TASK_IN_PROGRESS}:
            return task
        if not _lease_expired(task.lease_until):
            return task
        recovered = self.store.update_task(self.objective_id, task.task_id, {
            "status": TASK_PENDING,
            "owner": "",
            "lease_until": "",
        })
        self._expire_open_claims(task.task_id)
        self.store.log_event(
            self.objective_id,
            self.worker_id,
            "task_lease_expired",
            task.task_id,
            f"Recovered expired {task.status} task from owner {task.owner}",
        )
        return recovered

    def _try_claim(self, task: V2Task) -> V2Task | None:
        nonce = uuid.uuid4().hex
        claim = self.store.create_claim(
            self.objective_id, task.task_id, self.worker_id, nonce
        )
        self._expire_stale_active_claims(task)
        claims = [
            item for item in self.store.list_claims(self.objective_id, task.task_id)
            if item.status in {CLAIM_ACTIVE, CLAIM_WON}
        ]
        winner = sorted(claims, key=lambda item: (item.created_at, item.claim_id))[0]
        if winner.claim_id != claim.claim_id:
            self.store.update_claim(self.objective_id, claim.claim_id, CLAIM_LOST)
            return None
        lease_until = (
            datetime.now(timezone.utc) + timedelta(seconds=self.lease_seconds)
        ).isoformat()
        updated = self.store.update_task(self.objective_id, task.task_id, {
            "status": TASK_CLAIMED,
            "owner": self.worker_id,
            "lease_until": lease_until,
            "attempt_count": task.attempt_count + 1,
        })
        if updated.owner != self.worker_id:
            self.store.update_claim(self.objective_id, claim.claim_id, CLAIM_LOST)
            return None
        self.store.update_claim(self.objective_id, claim.claim_id, CLAIM_WON)
        self.store.log_event(
            self.objective_id,
            self.worker_id,
            "task_claimed",
            task.task_id,
            claim.claim_id,
        )
        return updated

    def _expire_stale_active_claims(self, task: V2Task) -> None:
        """Expire old active claims when the task is still unowned and pending."""
        current = self.store.get_task(self.objective_id, task.task_id)
        if current.status != TASK_PENDING or current.owner:
            return
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=self.lease_seconds)
        for claim in self.store.list_claims(self.objective_id, task.task_id):
            if claim.status != CLAIM_ACTIVE:
                continue
            try:
                created_at = datetime.fromisoformat(claim.created_at)
            except ValueError:
                created_at = cutoff - timedelta(seconds=1)
            if created_at < cutoff:
                self.store.update_claim(
                    self.objective_id, claim.claim_id, CLAIM_EXPIRED
                )

    def _default_artifact(self, task: V2Task) -> str:
        return (
            f"Worker: {self.worker_id}\n"
            f"Role: {self.role}\n"
            f"Task: {task.subject}\n\n"
            f"{task.description}\n\n"
            "Result: completed through the agent-team v2 task-board protocol."
        )

    def _default_verification(self, _task: V2Task, artifact_content: str) -> dict:
        if artifact_content.strip():
            return {
                "verdict": VERIFICATION_PASS,
                "issues": "",
                "suggestions": "Protocol verification passed for task completion.",
            }
        return {
            "verdict": VERIFICATION_FAIL,
            "issues": "Artifact content is empty.",
            "suggestions": "Regenerate the task artifact with concrete content.",
        }

    def _with_dependency_context(self, task: V2Task) -> V2Task:
        context = self._dependency_artifact_context(task)
        if not context:
            return task
        return V2Task(
            task_id=task.task_id,
            objective_id=task.objective_id,
            subject=task.subject,
            description=(
                f"{task.description}\n\n"
                "Dependency artifacts available to this worker:\n"
                f"{context}"
            ),
            role=task.role,
            status=task.status,
            owner=task.owner,
            lease_until=task.lease_until,
            attempt_count=task.attempt_count,
            metadata=task.metadata,
        )

    def _dependency_artifact_context(self, task: V2Task) -> str:
        blocker_ids = [
            edge.from_task_id for edge in self.store.list_edges(self.objective_id)
            if edge.to_task_id == task.task_id
        ]
        if not blocker_ids:
            return ""
        artifacts = [
            artifact for artifact in self.store.list_artifacts(self.objective_id)
            if artifact.get("task_id") in blocker_ids
        ]
        if not artifacts:
            return "No upstream artifact has been written yet."
        chunks = []
        for artifact in sorted(artifacts, key=lambda item: item.get("created_at", "")):
            content = str(artifact.get("content") or "")
            if len(content) > 2000:
                content = content[:2000] + "\n[truncated]"
            chunks.append(
                f"- Artifact from task {artifact.get('task_id')}"
                f" by {artifact.get('author')}:\n{content}"
            )
        return "\n\n".join(chunks)

    def _recover_failed_execution(self, task: V2Task, exc: Exception) -> None:
        self.store.update_task(self.objective_id, task.task_id, {
            "status": TASK_PENDING,
            "owner": "",
            "lease_until": "",
        })
        self._expire_open_claims(task.task_id)
        try:
            self.store.create_message(
                self.objective_id,
                self.worker_id,
                "team-lead",
                f"Failed {task.subject}",
                f"Task {task.task_id} returned to pending: {type(exc).__name__}: {exc}",
                task_id=task.task_id,
            )
        except Exception:
            pass
        self.store.log_event(
            self.objective_id,
            self.worker_id,
            "task_execution_failed",
            task.task_id,
            f"{type(exc).__name__}: {exc}",
        )

    def _expire_open_claims(self, task_id: str) -> None:
        for claim in self.store.list_claims(self.objective_id, task_id):
            if claim.status in {CLAIM_ACTIVE, CLAIM_WON}:
                self.store.update_claim(
                    self.objective_id, claim.claim_id, CLAIM_EXPIRED
                )


def _verification_verdict(verification: dict) -> str:
    return _scalar(
        verification.get("verdict")
        or verification.get("结论")
        or verification.get("VerDICT")
        or ""
    )


def _with_objective_context(brief: str, title: str, description: str) -> str:
    objective = f"Objective title: {title}\nObjective description:\n{description}"
    if title in brief and description in brief:
        return brief
    return f"{brief}\n\nShared objective context:\n{objective}"


def _scalar(value, default: str = "") -> str:
    if isinstance(value, list):
        if not value:
            return default
        return "".join(_scalar(item, "") for item in value)
    if isinstance(value, dict):
        if "text" in value:
            return str(value["text"])
        if "name" in value:
            return str(value["name"])
        return str(value)
    if value is None:
        return default
    return str(value)


def _lease_expired(value: str, now: datetime | None = None) -> bool:
    if not value:
        return False
    try:
        expires_at = datetime.fromisoformat(value)
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < (now or datetime.now(timezone.utc))
