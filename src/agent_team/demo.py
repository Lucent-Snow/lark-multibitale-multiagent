"""Demo runners for the agent-team protocol."""

import subprocess
import sys
import time
from typing import Callable

from src.agent_team.base_store import BaseObjectiveStore
from src.agent_team.contracts import TASK_COMPLETED, VERIFICATION_FAIL, VERIFICATION_PASS, Task
from src.agent_team.engine import AgentTeamEngine, Leader, Worker
from src.agent_team.memory_store import InMemoryObjectiveStore
from src.base_client.client import BaseClient
from src.llm.client import LLMClient

DEFAULT_WORKERS = [
    ("researcher-1", "researcher"),
    ("editor-1", "editor"),
    ("analyst-1", "analyst"),
    ("reviewer-1", "reviewer"),
    ("manager-1", "manager"),
]


def select_agent_team_workers(workers: int) -> list[tuple[str, str]]:
    if workers <= 0:
        return [("manager-1", "manager")]
    if workers == 1:
        return [("manager-1", "manager")]
    if workers >= len(DEFAULT_WORKERS):
        return list(DEFAULT_WORKERS)
    specialists = [w for w in DEFAULT_WORKERS if w[1] != "manager"]
    picked = []
    seen = set()
    for w in specialists:
        if w[1] not in seen:
            picked.append(w)
            seen.add(w[1])
    for w in specialists:
        if w not in picked and len(picked) < workers - 1:
            picked.append(w)
    return picked[:workers - 1] + [("manager-1", "manager")]


def run_agent_team_memory_demo(title: str, description: str, max_tasks: int = 4,
                                max_rounds: int = 10) -> dict:
    """Run the protocol with an in-memory store."""
    store = InMemoryObjectiveStore()
    engine = AgentTeamEngine(store, Leader(None))
    result = engine.start_objective(title, description, max_tasks=max_tasks)
    objective_id = result["objective_id"]

    for _round in range(max_rounds):
        made_progress = False
        for worker_id, role in DEFAULT_WORKERS:
            worker = Worker(store, objective_id, worker_id, role)
            r = worker.run_once()
            if r["status"] == "completed":
                made_progress = True
        if engine.complete_objective_if_ready():
            break
        if not made_progress:
            break

    tasks = store.list_tasks()
    return {
        "objective_id": objective_id,
        "tasks": tasks,
        "objective_completed": store.objective_status == "completed",
        "all_tasks_completed": bool(tasks) and all(t.status == TASK_COMPLETED for t in tasks),
    }


def run_agent_team_base_demo(base_token: str, llm: LLMClient,
                              title: str, description: str,
                              max_tasks: int = 4, workers: int = 4,
                              timeout_seconds: int = 600) -> dict:
    """Run a real Base-backed demo using worker subprocesses."""
    base = BaseClient(base_token)

    # Plan and create table
    engine = AgentTeamEngine(None, Leader(llm))  # temporary, just for plan
    worker_specs, plans = engine.leader.plan(title, description, max_tasks=max_tasks)

    import uuid
    objective_id = f"rec{uuid.uuid4().hex[:12]}"
    store = BaseObjectiveStore(base, objective_id)

    # Add all tasks
    created_tasks = [store.add_task(plan) for plan in plans]
    objective_id = store.objective_id

    print(f"[Agent-Team] planned: {len(worker_specs)} workers, {len(created_tasks)} tasks", flush=True)
    print(f"  Table: {store.table_name}", flush=True)

    selected = select_agent_team_workers(workers)
    processes = []
    for worker_id, role in selected[:len(worker_specs)]:
        processes.append(subprocess.Popen([
            sys.executable, "src/main.py", "worker",
            "--base-token", base_token, "--objective-id", objective_id,
            "--worker-id", worker_id, "--worker-role", role,
            "--worker-max-tasks", "3", "--worker-idle-rounds", "180",
        ]))

    deadline = time.time() + timeout_seconds
    last_recovery = time.time()
    while time.time() < deadline:
        tasks = store.list_tasks()
        if tasks and all(t.status == TASK_COMPLETED for t in tasks):
            break
        if all(p.poll() is not None for p in processes):
            break
        if time.time() - last_recovery > 30:
            # Retry failed tasks
            for t in tasks:
                if t.status == TASK_FAILED and t.attempt_count < 3:
                    store.update_task(t.task_id, {"status": "pending", "owner": ""})
            last_recovery = time.time()
        time.sleep(1)

    for p in processes:
        if p.poll() is None:
            p.terminate()
    for p in processes:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()

    tasks = store.list_tasks()
    completed = bool(tasks) and all(t.status == TASK_COMPLETED for t in tasks)
    return {
        "objective_id": objective_id,
        "table_name": store.table_name,
        "tasks": tasks,
        "all_tasks_completed": completed,
        "objective_completed": completed,
        "edges": [],
        "verifications": [{"verdict": t.verdict, "issues": t.issues} for t in tasks if t.verdict],
    }


ROLE_ARTIFACT_PROMPTS = {
    "researcher": (
        "You are a thorough researcher. Produce a comprehensive investigation report.\n"
        "Cover ALL domains mentioned in the task. Use structured format. Output in Chinese."
    ),
    "analyst": (
        "You are a rigorous analyst. Evaluate ALL options, quantify trade-offs.\n"
        "Ground analysis in provided data. Design actionable recommendations. Output in Chinese."
    ),
    "editor": (
        "You are a skilled editor. Produce a polished, publication-ready deliverable.\n"
        "Integrate ALL inputs into a coherent document. Minimum 1500 characters. Output in Chinese."
    ),
    "reviewer": (
        "You are a meticulous reviewer. Audit deliverables against requirements.\n"
        "Check every domain, verify claims, identify gaps. Output a structured audit in Chinese."
    ),
    "manager": (
        "You are a coordinating manager. Synthesize across all inputs.\n"
        "Resolve conflicts, ensure completeness. Minimum 1500 characters. Output in Chinese."
    ),
}


def make_llm_artifact_fn(llm: LLMClient, worker_id: str, role: str) -> Callable[[Task], str]:
    role_prompt = ROLE_ARTIFACT_PROMPTS.get(role, ROLE_ARTIFACT_PROMPTS["editor"])

    def generate(task: Task) -> str:
        retry_feedback = ""
        if task.attempt_count > 0 and task.issues:
            retry_feedback = (
                f"\n\n*** PREVIOUS ATTEMPT REJECTED ***\n"
                f"Issues: {task.issues}\nYou MUST address ALL issues above.\n"
            )
        return llm.chat_with_system(
            f"You are worker {worker_id}. Role: {role}.\n\n{role_prompt}",
            f"Task: {task.subject}\n\n{task.description}{retry_feedback}",
            temperature=0.4, max_tokens=4096,
        )
    return generate


def make_llm_verification_fn(llm: LLMClient, worker_id: str,
                              role: str = "") -> Callable[[Task, str], dict]:
    def verify(task: Task, artifact_content: str) -> dict:
        role_hint = ""
        if role in ("reviewer", "analyst"):
            role_hint = (
                "This worker's role is {role}. Identifying gaps and risks "
                "IS correct task completion. Do NOT fail for correctly identifying problems."
            )
        response = llm.chat_with_system(
            f"You are the quality verifier for worker {worker_id}.",
            (
                "Judge whether the artifact satisfies the task requirements.\n"
                "Return JSON only: verdict, issues, suggestions.\n"
                "verdict must be PASS or FAIL.\n\n"
                "FAIL if: required domains missing, internal data contradictions, "
                "cross-reference contradictions, or content is fabricated/empty.\n"
                "PASS only if genuinely deliverable with no contradictions.\n"
                "Be strict. A FAIL with specific issues is more valuable than a rubber-stamp PASS.\n\n"
                f"{role_hint}\n"
                f"Task: {task.subject}\n\nTask description:\n{task.description}\n\nArtifact:\n{artifact_content}"
            ),
            temperature=0.0, max_tokens=1024,
        )
        return _parse_verification_response(response)
    return verify


def _parse_verification_response(response: str) -> dict:
    import json as _json
    try:
        payload = _json.loads(response)
    except _json.JSONDecodeError:
        match = __import__('re').search(r"\{[\s\S]*\}", response)
        if match:
            try:
                payload = _json.loads(match.group())
            except _json.JSONDecodeError:
                return {"verdict": VERIFICATION_FAIL, "issues": "Verifier returned non-JSON.", "suggestions": response[:500]}
        else:
            return {"verdict": VERIFICATION_FAIL, "issues": "Verifier returned non-JSON.", "suggestions": response[:500]}
    if not isinstance(payload, dict):
        return {"verdict": VERIFICATION_FAIL, "issues": "Invalid response format."}
    verdict = str(payload.get("verdict") or "").strip().upper()
    if verdict not in {VERIFICATION_PASS, VERIFICATION_FAIL}:
        verdict = VERIFICATION_FAIL
    issues = str(payload.get("issues") or "")
    suggestions = str(payload.get("suggestions") or "")
    # Blocking gap check: self-admission of failure = FAIL regardless
    if verdict == VERIFICATION_PASS and _contains_blocking_gap(issues, suggestions):
        verdict = VERIFICATION_FAIL
    return {"verdict": verdict, "issues": issues, "suggestions": suggestions}


def _contains_blocking_gap(*values: str) -> bool:
    text = "\n".join(values).lower()
    if any(m.lower() in text for m in ["无信息缺失", "没有信息缺失", "no missing evidence"]):
        return False
    return any(m.lower() in text for m in [
        "cannot complete the task", "unable to produce",
        "无法完成任务", "无法产出", "artifact is incomplete",
    ])
