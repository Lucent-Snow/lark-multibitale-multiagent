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
    """Select workers while always keeping a manager fallback and covering all specialist roles."""
    if workers <= 0:
        return [("manager-1", "manager")]
    if workers == 1:
        return [("manager-1", "manager")]
    if workers >= len(V2_WORKERS):
        return list(V2_WORKERS)
    specialists = [w for w in V2_WORKERS if w[1] != "manager"]
    specialist_roles = len({w[1] for w in specialists})
    specialist_slots = workers - 1
    if specialist_slots >= specialist_roles:
        return specialists[:specialist_slots] + [("manager-1", "manager")]
    seen_roles = set()
    picked = []
    for w in specialists:
        if w[1] not in seen_roles:
            picked.append(w)
            seen_roles.add(w[1])
    for w in specialists:
        if w not in picked and len(picked) < specialist_slots:
            picked.append(w)
    return picked[:specialist_slots] + [("manager-1", "manager")]


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
                                timeout_seconds: int = 600) -> dict:
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
    last_recovery = time.time()
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
        if time.time() - last_recovery > 30:
            expired = engine.recover_expired_tasks(objective_id)
            retried = engine.retry_failed_tasks(objective_id)
            if expired or retried:
                print(
                    f"[Agent-Team v2] recovery: expired={expired} retried={retried}",
                    flush=True,
                )
            last_recovery = time.time()
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

    recovered = engine.recover_expired_tasks(objective_id)
    if recovered:
        print(f"[Agent-Team v2] recovered expired tasks={recovered}", flush=True)
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


ROLE_ARTIFACT_PROMPTS = {
    "researcher": (
        "You are a thorough researcher. Produce a comprehensive investigation report.\n"
        "Requirements:\n"
        "- Cover ALL domains mentioned in the task description exhaustively.\n"
        "- For each finding, note whether it is a verified fact or an assumption.\n"
        "- Explicitly list information gaps that need further verification.\n"
        "- Use structured format: ## sections, bullet lists, tables where helpful.\n"
        "- Aim for depth over breadth: fewer topics fully explored is better than many topics skimmed.\n"
        "- Output in Chinese."
    ),
    "analyst": (
        "You are a rigorous analyst. Produce a detailed analysis document.\n"
        "Requirements:\n"
        "- Evaluate ALL options/frameworks mentioned in the task.\n"
        "- Quantify trade-offs wherever possible (cost, time, risk, quality dimensions).\n"
        "- Ground your analysis in the dependency artifacts provided.\n"
        "- Design concrete, actionable recommendations with timelines and owners.\n"
        "- Use structured format with clear ## sections.\n"
        "- When data is unavailable, use reasonable estimates labeled as such.\n"
        "- Output in Chinese."
    ),
    "editor": (
        "You are a skilled editor. Produce a polished, publication-ready deliverable.\n"
        "Requirements:\n"
        "- Integrate ALL dependency artifacts into a coherent, complete final document.\n"
        "- Do NOT summarize or truncate — produce the FULL content for every section.\n"
        "- Every section must be self-contained and complete. No placeholder text.\n"
        "- Cover every required module from the task description.\n"
        "- Use professional formatting: clear hierarchy of ## headings, tables, checklists.\n"
        "- If upstream artifacts identify gaps, note them but DO NOT let them block you.\n"
        "- Output in Chinese, minimum 2000 characters."
    ),
    "reviewer": (
        "You are a meticulous reviewer. Audit the deliverables against requirements.\n"
        "Requirements:\n"
        "- Check every required domain from the task description for coverage.\n"
        "- Verify that all claims are grounded in dependency artifacts or labeled as assumptions.\n"
        "- Identify specific gaps: what is missing, not just what is weak.\n"
        "- Provide concrete, actionable suggestions for each issue found.\n"
        "- Distinguish between blocking issues (must fix) and nice-to-haves.\n"
        "- Output a structured audit report in Chinese."
    ),
    "manager": (
        "You are a coordinating manager. Synthesize across all inputs to produce a final deliverable.\n"
        "Requirements:\n"
        "- Combine ALL dependency artifacts into a unified, comprehensive output.\n"
        "- Resolve conflicts between upstream findings explicitly.\n"
        "- Ensure every objective requirement is addressed.\n"
        "- Use professional formatting with ## sections.\n"
        "- Output in Chinese, minimum 2000 characters."
    ),
}


def make_llm_artifact_fn(llm: LLMClient, worker_id: str, role: str) -> Callable[[V2Task], str]:
    """Build an artifact generator with role-specific prompts and retry feedback."""
    role_prompt = ROLE_ARTIFACT_PROMPTS.get(role, ROLE_ARTIFACT_PROMPTS["editor"])

    def generate(task: V2Task) -> str:
        retry_feedback = ""
        prev_issues = task.metadata.get("previous_issues", "")
        prev_suggestions = task.metadata.get("previous_suggestions", "")
        if prev_issues or prev_suggestions:
            retry_feedback = (
                "\n\n*** PREVIOUS ATTEMPT WAS REJECTED ***\n"
                f"Issues identified: {prev_issues}\n"
                f"Required fixes: {prev_suggestions}\n"
                "You MUST address ALL of the above issues in this attempt.\n"
                "Do NOT repeat the same mistakes.\n"
            )

        return llm.chat_with_system(
            f"You are worker {worker_id}. Your role: {role}.\n\n{role_prompt}",
            (
                "If dependency artifacts are provided, ground your answer in them. "
                "Label assumptions clearly. Do not fabricate data.\n\n"
                f"Task: {task.subject}\n\n{task.description}"
                f"{retry_feedback}"
            ),
            temperature=0.4,
            max_tokens=4096,
        )
    return generate


def make_llm_verification_fn(llm: LLMClient, worker_id: str,
                            role: str = "") -> Callable[[V2Task, str], dict]:
    """Build a quality verifier for worker artifacts."""
    def verify(task: V2Task, artifact_content: str) -> dict:
        role_hint = ""
        if role in ("reviewer", "analyst"):
            role_hint = (
                f"This worker's role is {role}. Identifying gaps, missing evidence, "
                "or risks in the subject matter IS correct task completion. "
                "Do NOT fail the artifact for correctly identifying problems — "
                "only fail if the artifact itself is empty, irrelevant, or fabricated.\n"
            )
        response = llm.chat_with_system(
            f"You are the quality verifier for worker {worker_id}.",
            (
                "Judge whether the artifact satisfies the task requirements. "
                "Return JSON only with keys: verdict, issues, suggestions. "
                "verdict must be PASS or FAIL.\n\n"
                "Quality dimensions to check:\n"
                "1. Completeness: Does it cover ALL required domains from the task?\n"
                "2. Grounding: Are claims backed by dependency artifacts or labeled as assumptions?\n"
                "3. Usability: Can a human act on this artifact without further research?\n"
                "4. Structure: Is it well-organized and readable?\n"
                "5. Honesty: Are gaps and assumptions clearly identified?\n\n"
                f"{role_hint}"
                "Passing threshold: usable and substantially complete, even if not perfect. "
                "Only FAIL if critical domains are missing, content is fabricated, "
                "or the artifact is too incomplete to be useful. "
                "For verifications that pass, issues/suggestions can contain minor improvements.\n\n"
                f"Task subject: {task.subject}\n\n"
                f"Task description:\n{task.description}\n\n"
                f"Artifact:\n{artifact_content}"
            ),
            temperature=0.0,
            max_tokens=1024,
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
    issues = str(payload.get("issues") or "")
    suggestions = str(payload.get("suggestions") or "")
    if verdict == VERIFICATION_PASS and _contains_blocking_gap(issues, suggestions):
        verdict = VERIFICATION_FAIL
    return {
        "verdict": verdict,
        "issues": issues,
        "suggestions": suggestions,
    }


def _contains_blocking_gap(*values: str) -> bool:
    """Detect self-admission that the artifact itself failed to complete the task."""
    text = "\n".join(values)
    negative_markers = [
        "无信息缺失",
        "没有信息缺失",
        "无证据缺失",
        "没有证据缺失",
        "no missing evidence",
        "no information gap",
    ]
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in negative_markers):
        return False
    markers = [
        "cannot complete the task",
        "unable to produce",
        "无法完成任务",
        "无法产出",
        "artifact is incomplete",
        "产出不完整",
    ]
    return any(marker.lower() in lowered for marker in markers)


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
