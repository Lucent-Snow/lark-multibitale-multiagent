"""Leader and worker protocol for the agent-team control plane."""

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable

from src.agent_team.contracts import (
    DEFAULT_MAX_ATTEMPTS,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_IN_PROGRESS,
    TASK_PENDING,
    VERIFICATION_FAIL,
    VERIFICATION_PASS,
    ObjectiveStore,
    Task,
    TaskPlan,
    WorkerSpec,
)
from src.agent_team.memory_store import utc_now

if TYPE_CHECKING:
    from src.llm.client import LLMClient


LEADER_SYSTEM_PROMPT = """\
You are the leader of an AI worker team. Your job is twofold:

1. DESIGN the team — decide exactly which workers are needed (names, roles, custom prompts)
2. PLAN the work — break the objective into MAXIMALLY PARALLEL tasks

CRITICAL RULES:
- MAXIMIZE PARALLELISM. If two tasks don't truly depend on each other, they MUST run in parallel (empty blocked_by_subjects).
- Create 1-2 workers per distinct role needed. Give each a custom system prompt that defines their expertise.
- The prompt field is the worker's permanent instruction. Put domain knowledge and quality standards in it.
- Each task must be self-contained with: specific deliverable, domains to cover, format to use.
- 4-6 tasks spread across 2-4 workers = good parallelism.
- Output JSON only. No markdown.
"""


class PlanningError(Exception):
    """Raised when a real leader plan cannot be trusted."""


class Leader:
    """Leader that plans objectives into workers + tasks."""

    def __init__(self, llm: "LLMClient | None" = None, allow_fallback: bool = True):
        self.llm = llm
        self.allow_fallback = allow_fallback

    def plan(self, title: str, description: str, max_tasks: int = 5) -> tuple[list[WorkerSpec], list[TaskPlan]]:
        """Return workers and tasks for the objective."""
        if not self.llm:
            return self._fallback_workers(title), self._fallback_tasks(title, description, max_tasks)
        prompt = f"""\
Objective title: {title}
Objective description:
{description}

Return a JSON object with two keys:
- "workers": array of worker specs, each with:
    worker_id: short kebab-case id (e.g. "lead-editor")
    name: Chinese display name
    role: one of researcher|editor|analyst|reviewer|manager
    prompt: 3-5 sentence custom system prompt defining this worker's expertise
- "tasks": array of task specs (max {max_tasks}), each with:
    subject: specific task name (8-15 Chinese characters)
    description: 3-5 sentence self-contained brief covering deliverables, domains, format
    role: which worker role handles this
    blocked_by_subjects: list of task subjects this depends on (EMPTY for independent tasks)

CRITICAL: Most tasks should have EMPTY blocked_by_subjects. Only add dependencies when genuinely needed.
"""
        try:
            response = self.llm.chat_with_system(LEADER_SYSTEM_PROMPT, prompt, temperature=0.3, max_tokens=4096)
        except Exception as exc:
            return self._fallback_or_raise(f"Leader LLM call failed: {type(exc).__name__}", title, description, max_tasks)
        return self._parse(response, title, description, max_tasks)

    def _parse(self, response, title, description, max_tasks):
        payload = self._extract_json(response)
        if payload is None:
            return self._fallback_or_raise("Leader response was not valid JSON", title, description, max_tasks)

        if isinstance(payload, list):
            tasks = self._parse_tasks(payload, max_tasks)
            workers = self._infer_workers(tasks)
            if not tasks:
                return self._fallback_or_raise("No valid tasks", title, description, max_tasks)
            normalized = self._normalize_tasks(tasks, title, description)
            if not normalized:
                return self._fallback_or_raise("Duplicate task subjects", title, description, max_tasks)
            return workers, normalized

        if isinstance(payload, dict):
            raw_workers = payload.get("workers") or []
            raw_tasks = payload.get("tasks") or []
            if not isinstance(raw_tasks, list):
                return self._fallback_or_raise("tasks must be a JSON array", title, description, max_tasks)
            workers = self._parse_workers(raw_workers)
            tasks = self._parse_tasks(raw_tasks, max_tasks)
            if not tasks:
                return self._fallback_or_raise("No valid tasks", title, description, max_tasks)
            normalized = self._normalize_tasks(tasks, title, description)
            if not normalized:
                return self._fallback_or_raise("Duplicate task subjects", title, description, max_tasks)
            return workers, normalized

        return self._fallback_or_raise("Unexpected JSON structure", title, description, max_tasks)

    def _extract_json(self, response):
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"[\{\[][\s\S]*[\}\]]", response)
            if not match:
                return None
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None

    def _parse_workers(self, raw):
        workers, seen = [], set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            wid = str(item.get("worker_id") or "").strip()
            if not wid or wid in seen:
                continue
            seen.add(wid)
            workers.append(WorkerSpec(wid, str(item.get("name") or wid),
                          str(item.get("role") or "manager").strip().lower(),
                          str(item.get("prompt") or "")))
        return workers

    def _parse_tasks(self, raw, max_tasks):
        tasks = []
        for item in raw[:max_tasks]:
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
            if subject and brief:
                tasks.append(TaskPlan(subject=subject, description=brief, role=role,
                           blocked_by_subjects=[str(v) for v in blockers]))
        return tasks

    def _normalize_tasks(self, tasks, title, description):
        known = {t.subject for t in tasks}
        if len(known) != len(tasks):
            return []
        return [TaskPlan(subject=t.subject,
                description=f"{t.description}\n\nShared objective context:\nObjective: {title}\n{description}",
                role=t.role,
                blocked_by_subjects=[b for b in t.blocked_by_subjects if b in known and b != t.subject])
                for t in tasks]

    def _infer_workers(self, tasks):
        seen, workers = {}, []
        for task in tasks:
            if task.role not in seen:
                wid = f"{task.role}-1"
                seen[task.role] = wid
                workers.append(WorkerSpec(wid, task.role, task.role,
                              f"You are a {task.role}. Complete assigned tasks autonomously."))
        return workers

    def _fallback_or_raise(self, reason, title, description, max_tasks):
        if not self.allow_fallback:
            raise PlanningError(reason)
        return self._fallback_workers(title), self._fallback_tasks(title, description, max_tasks)

    def _fallback_workers(self, title):
        return [
            WorkerSpec("researcher-1", "研究员", "researcher", "Investigate facts, constraints, data. Output in Chinese."),
            WorkerSpec("editor-1", "编辑", "editor", "Produce polished deliverables. Output in Chinese."),
            WorkerSpec("reviewer-1", "审核员", "reviewer", "Audit for completeness and quality. Output in Chinese."),
        ]

    def _fallback_tasks(self, title, description, max_tasks):
        ctx = f"{title}\n{description}"
        plans = [
            TaskPlan("收集背景资料", f"调研约束、受众、风险。\n{ctx}", "researcher"),
            TaskPlan("撰写主体内容", f"产出完整交付物。\n{ctx}", "editor"),
            TaskPlan("补充数据分析", f"量化评估方案优劣。\n{ctx}", "analyst"),
            TaskPlan("审核最终质量", "检查完整性、一致性，返回 pass/fail。", "reviewer",
                     blocked_by_subjects=["收集背景资料", "撰写主体内容", "补充数据分析"]),
        ]
        return [TaskPlan(subject=p.subject, description=p.description,
                role=p.role, blocked_by_subjects=p.blocked_by_subjects)
                for p in plans[:max_tasks]]


class AgentTeamEngine:
    """Coordinates one objective — one table, simple."""

    def __init__(self, store: ObjectiveStore, leader: Leader):
        self.store = store
        self.leader = leader

    def start_objective(self, title: str, description: str, max_tasks: int = 5) -> dict:
        """Plan, create tasks, return objective_id + workers + tasks."""
        workers, plans = self.leader.plan(title, description, max_tasks=max_tasks)
        objective_id = self.store.create_objective(title, description)

        tasks = [self.store.add_task(plan) for plan in plans]

        parallel = sum(1 for t in plans if not t.blocked_by_subjects)
        serial = sum(1 for t in plans if t.blocked_by_subjects)

        return {
            "objective_id": objective_id,
            "workers": workers,
            "tasks": tasks,
            "task_count": len(tasks),
            "parallel_count": parallel,
            "serial_count": serial,
        }

    def complete_objective_if_ready(self) -> bool:
        """Check if all tasks are complete and verified."""
        tasks = self.store.list_tasks()
        if not tasks:
            return False
        if any(t.status != TASK_COMPLETED for t in tasks):
            return False
        if any(t.verdict != VERIFICATION_PASS for t in tasks):
            return False
        return True


class Worker:
    """One worker process — claims tasks, writes artifacts, self-verifies."""

    def __init__(self, store: ObjectiveStore, objective_id: str,
                 worker_id: str, role: str,
                 artifact_fn: Callable[[Task], str] | None = None,
                 verification_fn: Callable[[Task, str], dict] | None = None,
                 max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        self.store = store
        self.objective_id = objective_id
        self.worker_id = worker_id
        self.role = role
        self.artifact_fn = artifact_fn or self._default_artifact
        self.verification_fn = verification_fn or self._default_verification
        self.max_attempts = max_attempts

    def run_once(self) -> dict:
        """Claim and complete one available task."""
        task = self._claim_next()
        if not task:
            return {"status": "idle", "task_id": ""}

        task = self.store.update_task(task.task_id, {"status": TASK_IN_PROGRESS, "owner": self.worker_id})

        try:
            artifact = self.artifact_fn(task)
            verification = self.verification_fn(task, artifact)
            verdict = str(verification.get("verdict") or VERIFICATION_FAIL)
            issues = str(verification.get("issues") or "")

            if verdict != VERIFICATION_PASS:
                if task.attempt_count < self.max_attempts:
                    self.store.update_task(task.task_id, {
                        "status": TASK_PENDING, "owner": "",
                        "attempt_count": task.attempt_count + 1,
                        "issues": issues,
                    })
                    return {"status": "retry", "task_id": task.task_id, "verdict": verdict}

                self.store.update_task(task.task_id, {
                    "status": TASK_FAILED, "owner": self.worker_id,
                    "verdict": verdict, "issues": issues,
                })
                return {"status": "failed", "task_id": task.task_id, "verdict": verdict}

            self.store.update_task(task.task_id, {
                "status": TASK_COMPLETED, "owner": self.worker_id,
                "artifact": artifact, "artifact_title": f"{task.subject} output",
                "verdict": VERIFICATION_PASS, "issues": issues,
                "created_at": utc_now(),
            })
            return {"status": "completed", "task_id": task.task_id}

        except Exception as exc:
            self.store.update_task(task.task_id, {"status": TASK_PENDING, "owner": ""})
            raise

    def _claim_next(self) -> Task | None:
        tasks = self.store.list_tasks()
        completed = {t.subject for t in tasks if t.status == TASK_COMPLETED}

        for task in sorted(tasks, key=lambda t: t.task_id):
            if task.status != TASK_PENDING or task.owner:
                continue
            if self.role != "manager" and task.role != self.role:
                continue
            # Check dependencies
            deps = [d.strip() for d in task.depends_on.split(",") if d.strip()]
            if deps and not all(d in completed for d in deps):
                continue
            # Atomic claim: set owner
            updated = self.store.update_task(task.task_id, {"owner": self.worker_id})
            if updated.owner == self.worker_id:
                return updated
        return None

    def _default_artifact(self, task: Task) -> str:
        return f"[{self.worker_id}] {task.subject}\n\n{task.description}\n\nResult: completed."

    def _default_verification(self, _task: Task, artifact: str) -> dict:
        if artifact.strip():
            return {"verdict": VERIFICATION_PASS, "issues": ""}
        return {"verdict": VERIFICATION_FAIL, "issues": "Artifact is empty."}
