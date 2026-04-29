"""Demo runners for the agent-team v2 protocol."""

import subprocess
import sys
import time
from typing import Callable

from src.agent_team_v2.base_store import BaseAgentTeamV2Store
from src.agent_team_v2.contracts import (
    TASK_COMPLETED,
    VERIFICATION_FAIL,
    VERIFICATION_PASS,
    V2Task,
)
from src.agent_team_v2.engine import AgentTeamV2Engine, LeaderV2, WorkerV2
from src.agent_team_v2.memory_store import InMemoryAgentTeamV2Store
from src.agent_team_v2.schemas import V2_TABLE_SCHEMAS
from src.base_client.client import BaseClient
from src.llm.client import LLMClient


V2_WORKERS = [
    ("researcher-1", "researcher"),
    ("editor-1", "editor"),
    ("analyst-1", "analyst"),
    ("reviewer-1", "reviewer"),
    ("manager-1", "manager"),
]


def create_agent_team_v2_tables(base_client: BaseClient) -> dict[str, str]:
    """Create the v2 Base tables and return config keys mapped to table IDs."""
    created = {}
    for key, schema in V2_TABLE_SCHEMAS.items():
        created[key] = base_client.create_table(schema["name"], schema["fields"])
    return created


def select_agent_team_v2_workers(workers: int) -> list[tuple[str, str]]:
    """Select workers while always keeping a manager fallback."""
    limit = max(1, min(workers, len(V2_WORKERS)))
    if limit == 1:
        return [("manager-1", "manager")]
    specialists = [worker for worker in V2_WORKERS if worker[1] != "manager"]
    return specialists[:limit - 1] + [("manager-1", "manager")]


def run_agent_team_v2_memory_demo(title: str, description: str,
                                  max_tasks: int = 4,
                                  max_rounds: int = 10) -> dict:
    """Run the v2 protocol with an in-memory store."""
    store = InMemoryAgentTeamV2Store()
    engine = AgentTeamV2Engine(store, LeaderV2(None))
    objective = engine.start_objective(title, description, max_tasks=max_tasks)
    objective_id = objective["objective_id"]
    worker_results = []

    for _round in range(max_rounds):
        made_progress = False
        for worker_id, role in V2_WORKERS:
            worker = WorkerV2(store, objective_id, worker_id, role)
            result = worker.run_once()
            worker_results.append(result)
            if result["status"] == "completed":
                made_progress = True
        if engine.complete_objective_if_ready(objective_id):
            break
        if not made_progress:
            break

    tasks = store.list_tasks(objective_id)
    return {
        "objective_id": objective_id,
        "tasks": tasks,
        "edges": store.list_edges(objective_id),
        "worker_results": worker_results,
        "artifacts": store.artifacts,
        "messages": store.messages,
        "verifications": store.verifications,
        "objective_completed": store.objectives[objective_id]["status"] == "completed",
        "all_tasks_completed": bool(tasks) and all(
            task.status == TASK_COMPLETED for task in tasks
        ),
    }


def run_agent_team_v2_base_demo(manager_api: BaseClient, llm: LLMClient,
                                title: str, description: str,
                                max_tasks: int = 4,
                                workers: int = 4,
                                timeout_seconds: int = 300) -> dict:
    """Run a real Base-backed v2 demo using worker subprocesses."""
    store = BaseAgentTeamV2Store(manager_api)
    engine = AgentTeamV2Engine(store, LeaderV2(llm))
    print("[Agent-Team v2] planning objective with LLM...", flush=True)
    objective = engine.start_objective(title, description, max_tasks=max_tasks)
    objective_id = objective["objective_id"]
    print(
        f"[Agent-Team v2] objective planned: {objective_id} "
        f"tasks={len(objective['tasks'])} edges={len(objective['edge_ids'])}",
        flush=True,
    )

    selected_workers = select_agent_team_v2_workers(workers)
    processes = []
    for worker_id, role in selected_workers:
        processes.append(subprocess.Popen([
            sys.executable,
            "src/main.py",
            "--agent-team-v2-worker",
            "--objective-id",
            objective_id,
            "--worker-id",
            worker_id,
            "--worker-role",
            role,
            "--worker-max-tasks",
            str(max_tasks),
            "--worker-idle-rounds",
            str(max(30, timeout_seconds)),
        ]))

    deadline = time.time() + timeout_seconds
    objective_completed = False
    last_progress = ""
    while time.time() < deadline:
        objective_completed = engine.complete_objective_if_ready(objective_id)
        progress = _progress_summary(store, objective_id)
        if progress != last_progress:
            print(f"[Agent-Team v2] {progress}", flush=True)
            last_progress = progress
        if objective_completed:
            break
        if all(process.poll() is not None for process in processes):
            break
        time.sleep(1)

    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    if not objective_completed:
        objective_completed = engine.complete_objective_if_ready(objective_id)
    tasks = store.list_tasks(objective_id)
    return {
        "objective_id": objective_id,
        "tasks": tasks,
        "edges": store.list_edges(objective_id),
        "verifications": store.list_verifications(objective_id),
        "objective_completed": objective_completed,
        "all_tasks_completed": bool(tasks) and all(
            task.status == TASK_COMPLETED for task in tasks
        ),
    }


def make_llm_artifact_fn(llm: LLMClient, worker_id: str, role: str) -> Callable[[V2Task], str]:
    """Build an artifact generator backed by the configured LLM."""
    def generate(task: V2Task) -> str:
        return llm.chat_with_system(
            f"You are worker {worker_id} with role {role}.",
            (
                "Complete the assigned task. Write concise Chinese output that can "
                "be stored as a durable artifact.\n"
                "If dependency artifacts are provided, ground your answer in them "
                "and explicitly point out gaps instead of inventing evidence. "
                "Do not fabricate statistics, benchmarks, APIs, or customer facts. "
                "When using assumptions, label them as assumptions.\n\n"
                f"Task: {task.subject}\n\n{task.description}"
            ),
            temperature=0.4,
            max_tokens=1200,
        )
    return generate


def make_llm_verification_fn(llm: LLMClient, worker_id: str) -> Callable[[V2Task, str], dict]:
    """Build a quality verifier for worker artifacts."""
    def verify(task: V2Task, artifact_content: str) -> dict:
        response = llm.chat_with_system(
            f"You are the quality verifier for worker {worker_id}.",
            (
                "Judge whether the artifact satisfies the task. Return JSON only "
                "with keys: verdict, issues, suggestions. verdict must be PASS or FAIL.\n"
                "Fail if the artifact fabricates unsupported statistics, ignores "
                "dependency artifacts, omits the required objective context, or is empty. "
                "Passing does not require perfect prose, but it must be usable and grounded.\n\n"
                f"Task subject: {task.subject}\n\n"
                f"Task description:\n{task.description}\n\n"
                f"Artifact:\n{artifact_content}"
            ),
            temperature=0.0,
            max_tokens=500,
        )
        return _parse_verification_response(response)
    return verify


def _parse_verification_response(response: str) -> dict:
    import json

    payload = None
    try:
        payload = json.loads(response)
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        return {
            "verdict": VERIFICATION_FAIL,
            "issues": "Verifier returned non-JSON output.",
            "suggestions": response[:500],
        }
    verdict = str(payload.get("verdict") or "").strip().upper()
    if verdict not in {VERIFICATION_PASS, VERIFICATION_FAIL}:
        verdict = VERIFICATION_FAIL
    return {
        "verdict": verdict,
        "issues": str(payload.get("issues") or ""),
        "suggestions": str(payload.get("suggestions") or ""),
    }


def _progress_summary(store, objective_id: str) -> str:
    tasks = store.list_tasks(objective_id)
    counts = {}
    for task in tasks:
        counts[task.status] = counts.get(task.status, 0) + 1
    artifacts = store.list_artifacts(objective_id)
    verifications = store.list_verifications(objective_id)
    status_text = ", ".join(
        f"{status}={count}" for status, count in sorted(counts.items())
    ) or "no tasks"
    return (
        f"tasks[{status_text}] "
        f"artifacts={len(artifacts)} verifications={len(verifications)}"
    )
