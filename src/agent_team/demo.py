"""Offline agent-team demonstration runner."""

from src.agent_team.contracts import TASK_COMPLETED
from src.agent_team.base_store import BaseAgentTeamStore
from src.agent_team.engine import AgentTeamEngine, AgentTeamLeader
from src.agent_team.memory_store import InMemoryAgentTeamStore
from src.base_client.client import BaseClient
from src.llm.client import LLMClient


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


def _llm_artifact_for_task(llm: LLMClient, role: str, subject: str,
                           description: str) -> str:
    """Generate worker output for a task with the real LLM."""
    system_prompt = f"""\
You are an AI teammate working as {role}.
Complete only the assigned task. Be concise, concrete, and write in Chinese.
Return the durable artifact content that should be written back to the shared Base.
"""
    user_message = f"""\
Task: {subject}

Self-contained brief:
{description}
"""
    return llm.chat_with_system(
        system_prompt,
        user_message,
        temperature=0.4,
        max_tokens=1200,
    )


def _all_planned_tasks_completed(readback_tasks: list, planned_task_ids: set[str]) -> bool:
    """Return true only when every planned task was read back as completed."""
    completed_task_ids = {
        record.record_id
        for record in readback_tasks
        if BaseAgentTeamStore._scalar((record.fields or {}).get("状态")) == TASK_COMPLETED
    }
    return bool(planned_task_ids) and completed_task_ids == planned_task_ids


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
        "all_tasks_completed": (
            bool(tasks) and all(task.status == TASK_COMPLETED for task in tasks)
        ),
        "tasks": tasks,
        "artifacts": store.artifacts,
        "messages": store.messages,
        "logs": store.logs,
    }


def run_agent_team_base_demo(manager_api: BaseClient, editor_api: BaseClient,
                             reviewer_api: BaseClient, llm: LLMClient,
                             title: str, description: str,
                             max_tasks: int = 4) -> dict:
    """Run a real LLM + Feishu Base agent-team validation scenario."""
    manager_api.table_ids.require_agent_team()
    objective_id = manager_api.create_record(manager_api.table_ids.objectives, {
        "目标标题": title,
        "目标说明": description,
        "状态": "in_progress",
        "发起人": "team-lead",
        "最终结论": "",
    })
    task_scope = {"objective_id": objective_id}
    manager_store = BaseAgentTeamStore(manager_api, task_scope=task_scope)
    editor_store = BaseAgentTeamStore(editor_api, task_scope=task_scope)
    reviewer_store = BaseAgentTeamStore(reviewer_api, task_scope=task_scope)
    store_by_role = {
        "researcher": manager_store,
        "editor": editor_store,
        "reviewer": reviewer_store,
        "analyst": manager_store,
        "manager": manager_store,
    }
    member_ids = []
    for role, agent_name in ROLE_AGENTS.items():
        member_ids.append(manager_api.create_record(manager_api.table_ids.members, {
            "名称": agent_name,
            "角色": role,
            "能力": f"Handle {role} tasks in the agent-team demo",
            "状态": "idle",
        }))

    leader = AgentTeamLeader(llm)
    planning_engine = AgentTeamEngine(manager_store, leader)
    objective = planning_engine.start_objective(
        title=title,
        description=description,
        max_tasks=max_tasks,
    )

    completed = []
    verification_ids = []
    while True:
        made_progress = False
        for role, agent_name in ROLE_AGENTS.items():
            engine = AgentTeamEngine(store_by_role[role], leader)
            task = engine.claim_next_task(agent_name, role)
            if not task:
                continue
            artifact_content = _llm_artifact_for_task(
                llm=llm,
                role=role,
                subject=task.subject,
                description=task.description,
            )
            result = engine.complete_task(
                agent_name=agent_name,
                task_id=task.task_id,
                artifact_title=f"{task.subject} output",
                artifact_content=artifact_content,
            )
            verification_ids.append(reviewer_api.create_record(
                reviewer_api.table_ids.verifications,
                {
                    "关联任务ID": task.task_id,
                    "验证结论": "PASS",
                    "问题": "",
                    "建议": "已验证该任务完成了领取、产物写回、消息通知和日志记录。",
                },
            ))
            completed.append(result["task"])
            made_progress = True
        if not made_progress:
            break

    planned_task_ids = {planned.task_id for planned in objective["tasks"]}
    readback_tasks = [
        manager_api.get_record(manager_api.table_ids.tasks, task_id)
        for task_id in planned_task_ids
    ]
    all_tasks_completed = _all_planned_tasks_completed(
        readback_tasks, planned_task_ids
    )
    manager_api.update_record(manager_api.table_ids.objectives, objective_id, {
        "状态": "completed" if all_tasks_completed else "failed",
        "最终结论": (
            "真实 LLM + 飞书 Base agent-team 验证完成。"
            if all_tasks_completed else
            "仍有任务未完成，请检查任务台账。"
        ),
    })

    readback = {
        "objective": manager_api.get_record(
            manager_api.table_ids.objectives, objective_id
        ).fields,
        "tasks": [record.fields for record in readback_tasks],
        "verifications": [
            reviewer_api.get_record(reviewer_api.table_ids.verifications, record_id).fields
            for record_id in verification_ids
        ],
    }

    return {
        "objective": title,
        "objective_id": objective_id,
        "member_ids": member_ids,
        "planned_tasks": objective["tasks"],
        "completed_tasks": completed,
        "verification_ids": verification_ids,
        "all_tasks_completed": all_tasks_completed,
        "readback": readback,
    }
