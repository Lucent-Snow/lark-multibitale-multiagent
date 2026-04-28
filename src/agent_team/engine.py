"""Agent-team leader and task-market orchestration."""

import json
import re

from src.agent_team.contracts import (
    AgentTeamStore,
    AgentTeamTask,
    TASK_COMPLETED,
    TASK_IN_PROGRESS,
    TASK_PENDING,
    TaskSpec,
)
from src.llm.client import LLMClient


LEADER_SYSTEM_PROMPT = """\
You are the leader of an AI operations team.
Your job is to break an open objective into a small, executable task list.

Rules:
- Produce tasks that are self-contained. Workers cannot see your conversation.
- Assign each task to exactly one role: researcher, editor, reviewer, analyst, or manager.
- Keep the first version small: 3 to 5 tasks.
- Prefer clear dependencies over vague coordination.
- Output JSON only. No markdown.
"""


class AgentTeamLeader:
    """Leader agent that turns open objectives into task specifications."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm

    def plan_objective(self, title: str, description: str,
                       max_tasks: int = 5) -> list[TaskSpec]:
        """Plan an objective into executable tasks."""
        if not self.llm:
            return self._fallback_plan(title, description, max_tasks)

        prompt = f"""\
Objective title: {title}
Objective description:
{description}

Return a JSON array. Each item must have:
- subject: short imperative task title
- description: self-contained worker brief
- role: researcher | editor | reviewer | analyst | manager
- blocked_by: array of earlier task subjects this task depends on
- metadata: object

Max tasks: {max_tasks}
"""
        response = self.llm.chat_with_system(
            LEADER_SYSTEM_PROMPT,
            prompt,
            temperature=0.2,
            max_tokens=2048,
        )
        return self._parse_plan(response, title, description, max_tasks)

    def _parse_plan(self, response: str, title: str, description: str,
                    max_tasks: int) -> list[TaskSpec]:
        """Parse leader JSON output with deterministic fallback."""
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\[[\s\S]*\]", response)
            if not match:
                return self._fallback_plan(title, description, max_tasks)
            try:
                payload = json.loads(match.group())
            except json.JSONDecodeError:
                return self._fallback_plan(title, description, max_tasks)

        if not isinstance(payload, list):
            return self._fallback_plan(title, description, max_tasks)

        specs: list[TaskSpec] = []
        for item in payload[:max_tasks]:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject") or "").strip()
            brief = str(item.get("description") or "").strip()
            role = str(item.get("role") or "manager").strip().lower()
            if not subject or not brief:
                continue
            if role not in {"researcher", "editor", "reviewer", "analyst", "manager"}:
                role = "manager"
            blocked_by = item.get("blocked_by") or []
            if not isinstance(blocked_by, list):
                blocked_by = []
            metadata = item.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            specs.append(TaskSpec(
                subject=subject,
                description=brief,
                role=role,
                blocked_by=[str(value) for value in blocked_by],
                metadata=metadata,
            ))

        return specs or self._fallback_plan(title, description, max_tasks)

    def _fallback_plan(self, title: str, description: str,
                       max_tasks: int) -> list[TaskSpec]:
        """Deterministic plan used when LLM planning is unavailable."""
        objective = f"{title}\n\n{description}".strip()
        tasks = [
            TaskSpec(
                subject="Research objective context",
                description=(
                    "Gather the key background, constraints, audience, and risks for "
                    f"this objective. Objective:\n{objective}"
                ),
                role="researcher",
            ),
            TaskSpec(
                subject="Draft primary deliverable",
                description=(
                    "Create the first complete deliverable using the research context. "
                    f"Objective:\n{objective}"
                ),
                role="editor",
                blocked_by=["Research objective context"],
            ),
            TaskSpec(
                subject="Review deliverable quality",
                description=(
                    "Review the deliverable for completeness, quality, risk, and "
                    "alignment with the objective. Return concrete fixes if needed."
                ),
                role="reviewer",
                blocked_by=["Draft primary deliverable"],
            ),
            TaskSpec(
                subject="Synthesize final report",
                description=(
                    "Summarize completed work, remaining risks, and recommended next "
                    "actions for the human owner."
                ),
                role="manager",
                blocked_by=["Review deliverable quality"],
            ),
        ]
        return tasks[:max_tasks]


class AgentTeamEngine:
    """Coordinates an agent team through a shared task market."""

    def __init__(self, store: AgentTeamStore, leader: AgentTeamLeader):
        self.store = store
        self.leader = leader

    def start_objective(self, title: str, description: str,
                        max_tasks: int = 5) -> dict:
        """Create a task market for an open objective."""
        specs = self.leader.plan_objective(title, description, max_tasks=max_tasks)
        tasks = [self.store.create_task(spec) for spec in specs]
        self.store.log_operation(
            operator="team-lead",
            op_type="plan",
            target_id=title,
            detail=f"Created {len(tasks)} tasks for objective: {title}",
        )
        return {
            "objective": title,
            "task_count": len(tasks),
            "tasks": tasks,
        }

    def claim_next_task(self, agent_name: str, role: str) -> AgentTeamTask | None:
        """Claim the earliest unblocked pending task for a role."""
        tasks = self.store.list_tasks()
        completed_subjects = {
            task.subject for task in tasks if task.status == TASK_COMPLETED
        }

        for task in tasks:
            if task.status != TASK_PENDING or task.owner:
                continue
            if task.role != role:
                continue
            if any(dep not in completed_subjects for dep in task.blocked_by):
                continue
            claimed = self.store.update_task(task.task_id, {
                "status": TASK_IN_PROGRESS,
                "owner": agent_name,
            })
            self.store.log_operation(
                operator=agent_name,
                op_type="claim",
                target_id=task.task_id,
                detail=f"Claimed task: {task.subject}",
            )
            return claimed
        return None

    def complete_task(self, agent_name: str, task_id: str, artifact_title: str,
                      artifact_content: str) -> dict:
        """Complete a task, write its artifact, and notify the leader."""
        artifact_id = self.store.create_artifact(
            task_id=task_id,
            title=artifact_title,
            content=artifact_content,
            author=agent_name,
        )
        task = self.store.update_task(task_id, {"status": TASK_COMPLETED})
        message_id = self.store.create_message(
            sender=agent_name,
            recipient="team-lead",
            summary=f"Completed {task.subject}",
            message=f"Task {task.task_id} completed. Artifact: {artifact_id}",
            task_id=task_id,
        )
        self.store.log_operation(
            operator=agent_name,
            op_type="complete",
            target_id=task_id,
            detail=f"Completed task with artifact {artifact_id}",
        )
        return {
            "task": task,
            "artifact_id": artifact_id,
            "message_id": message_id,
        }
