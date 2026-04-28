"""Offline agent-team demonstration runner."""

from src.agent_team.contracts import TASK_COMPLETED
from src.agent_team.engine import AgentTeamEngine, AgentTeamLeader
from src.agent_team.memory_store import InMemoryAgentTeamStore


ROLE_AGENTS = {
    "researcher": "researcher-1",
    "editor": "editor-1",
    "reviewer": "reviewer-1",
    "analyst": "analyst-1",
    "manager": "manager-1",
}


def _artifact_for_task(role: str, subject: str, description: str) -> str:
    """Generate deterministic offline artifact content for a claimed task."""
    return (
        f"Role: {role}\n"
        f"Task: {subject}\n\n"
        f"Work brief:\n{description}\n\n"
        "Result:\n"
        "This offline demo artifact shows the worker received a self-contained "
        "task, executed within its role boundary, and wrote a durable output "
        "back to the shared task market."
    )


def run_agent_team_demo(title: str, description: str,
                        max_tasks: int = 4) -> dict:
    """Run the agent-team protocol without external services."""
    store = InMemoryAgentTeamStore()
    engine = AgentTeamEngine(store, AgentTeamLeader(None))
    objective = engine.start_objective(title, description, max_tasks=max_tasks)

    completed = []
    while True:
        made_progress = False
        for role, agent_name in ROLE_AGENTS.items():
            task = engine.claim_next_task(agent_name, role)
            if not task:
                continue
            result = engine.complete_task(
                agent_name=agent_name,
                task_id=task.task_id,
                artifact_title=f"{task.subject} output",
                artifact_content=_artifact_for_task(
                    role=role,
                    subject=task.subject,
                    description=task.description,
                ),
            )
            completed.append(result["task"])
            made_progress = True
        if not made_progress:
            break

    tasks = store.list_tasks()
    return {
        "objective": objective["objective"],
        "planned_tasks": objective["tasks"],
        "completed_tasks": completed,
        "all_tasks_completed": all(task.status == TASK_COMPLETED for task in tasks),
        "tasks": tasks,
        "artifacts": store.artifacts,
        "messages": store.messages,
        "logs": store.logs,
    }
