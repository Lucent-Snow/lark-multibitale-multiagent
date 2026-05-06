#!/usr/bin/env python3
"""Run a full agent-team objective end-to-end. Never stops until complete."""

import subprocess
import sys
import time
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base_client.client import BaseClient
from src.agent_team.base_store import BaseAgentTeamStore
from src.agent_team.engine import AgentTeamEngine, Leader, Worker
from src.agent_team.demo import make_llm_artifact_fn, make_llm_verification_fn
from src.llm.client import LLMClient

BASE_TOKEN = "WFeZbPq5faeHt3sq51lcRU2SnKb"

OBJECTIVE_TITLE = "如何在浙大举办一场飞书AI黑客松"

OBJECTIVE_DESCRIPTION = """\
为浙江大学策划一场为期2天的飞书AI主题黑客松大赛，需要输出完整的可执行策划方案。

具体需求：
1. 场地调研：浙大紫金港校区有哪些适合100-200人的活动场地（如蒙民伟楼报告厅、月牙楼多功能厅、校友林等），场地费用、设备配置、网络条件如何？需要详细对比至少3个候选场地。
2. 赛制设计：结合飞书AI能力（多维表格自动化、消息推送、Bot工作流、Base协作等），设计有吸引力的赛题方向（至少3个赛道），制定2天赛程安排（开题→开发→评审→颁奖），设计评审标准（技术创新30%、商业价值25%、飞书集成度25%、展示效果20%）。
3. 资源评估：预估参赛规模（50-100支队伍、200-400人），计算预算（场地、餐饮、奖品、物料、宣传），列出需要的赞助资源和企业合作方（飞书、字节、浙大团委/信息中心）。
4. 执行方案：撰写完整的执行手册，包含时间线（赛前4周准备、赛中2天、赛后1周收尾）、人员分工（组委会、志愿者、评委、技术保障）、应急预案（网络故障、报名不足、天气变化）。
5. 宣传方案：设计校园传播策略（微信/98/BBS/海报/宣讲会），制定KOL和社团合作计划，准备宣传物料清单。
6. 产出标准：一份可直接呈交浙大团委和飞书官方的完整策划书，不少于3000字，包含预算表、赛程表、场地对比表、风险预案表。

约束条件：
- 必须考虑浙大实际校情（紫金港为主校区，玉泉/西溪/华家池/之江校区也可考虑）
- 预算需合理控制在10-20万元人民币
- 时间安排在2026年秋季学期（9-11月）
- 必须充分利用飞书多维表格作为活动管理工具"""

MAX_TASKS = 6
WORKERS_COUNT = 4
TIMEOUT_SECONDS = 900  # 15 minutes


def _load_llm():
    import yaml
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f.read()) or {}
    llm_cfg = cfg.get("llm") or {}
    return LLMClient(llm_cfg["api_key"], llm_cfg["endpoint_id"], timeout=120)


def print_separator(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def main():
    print_separator("Agent-Team: Full Objective Execution")
    print(f"  Objective: {OBJECTIVE_TITLE}")
    print(f"  Base: ...{BASE_TOKEN[-6:]}")

    # ── Init ──
    llm = _load_llm()
    base = BaseClient(BASE_TOKEN)
    store = BaseAgentTeamStore(base)
    engine = AgentTeamEngine(store, Leader(llm, allow_fallback=False))

    # ── Plan ──
    print_separator("Phase 1: Leader plans workers + tasks")
    try:
        result = engine.start_objective(OBJECTIVE_TITLE, OBJECTIVE_DESCRIPTION, max_tasks=MAX_TASKS)
    except Exception as e:
        print(f"  [FAIL] Planning error: {e}")
        print("  Falling back to memory-based plan...")
        from src.agent_team.engine import Leader as FallbackLeader
        engine2 = AgentTeamEngine(store, FallbackLeader(None))
        result = engine2.start_objective(OBJECTIVE_TITLE, OBJECTIVE_DESCRIPTION, max_tasks=MAX_TASKS)

    objective_id = result["objective_id"]
    print(f"  Objective: {objective_id}")
    print(f"  Workers: {len(result['workers'])}")
    for w in result['workers']:
        print(f"    {w.worker_id:<20} {w.name:<10} role={w.role}")
    print(f"  Tasks: {len(result['tasks'])}")
    for t in result['tasks']:
        deps = [e for e in store.list_edges(objective_id) if e.to_task_id == t.task_id]
        dep_count = len(deps)
        label = "PARALLEL" if dep_count == 0 else f"SERIAL({dep_count} dep)"
        print(f"    [{label}] {t.subject:<35} role={t.role}")
    print(f"  Edges: {len(result['edge_ids'])}")

    # ── Spawn workers ──
    print_separator("Phase 2: Spawning worker processes")
    processes = []
    spawned_workers = list(result['workers'])[:WORKERS_COUNT]
    for w in spawned_workers:
        proc = subprocess.Popen([
            sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "main.py"),
            "worker",
            "--base-token", BASE_TOKEN,
            "--objective-id", objective_id,
            "--worker-id", w.worker_id,
            "--worker-role", w.role,
            "--worker-max-tasks", "3",
            "--worker-idle-rounds", "300",
        ])
        processes.append((w.worker_id, w.role, proc))
        print(f"  Started: {w.worker_id} ({w.role}) pid={proc.pid}")

    # ── Monitor loop ──
    print_separator("Phase 3: Monitoring execution")
    deadline = time.time() + TIMEOUT_SECONDS
    last_progress = ""
    objective_completed = False
    recovery_count = 0
    last_recovery = time.time()

    while time.time() < deadline:
        # Check completion
        try:
            objective_completed = engine.complete_objective_if_ready(objective_id)
        except Exception:
            pass

        # Progress snapshot
        tasks = store.list_tasks(objective_id)
        counts = {}
        for t in tasks:
            counts[t.status] = counts.get(t.status, 0) + 1
        artifacts = store.list_artifacts(objective_id)
        verifications = store.list_verifications(objective_id)

        progress = (f"tasks[completed={counts.get('completed',0)} in_progress={counts.get('in_progress',0)} "
                    f"claimed={counts.get('claimed',0)} pending={counts.get('pending',0)} "
                    f"failed={counts.get('failed',0)}] "
                    f"artifacts={len(artifacts)} verifications={len(verifications)}")
        if progress != last_progress:
            elapsed = int(time.time() - (deadline - TIMEOUT_SECONDS))
            print(f"  [{elapsed}s] {progress}")
            last_progress = progress

        if objective_completed:
            print_separator("OBJECTIVE COMPLETED!")
            break

        # Check if all workers died
        alive = [p for _, _, p in processes if p.poll() is None]
        if not alive:
            print(f"  All workers exited. Checking if we can complete...")
            # Try one more time
            try:
                if engine.complete_objective_if_ready(objective_id):
                    print_separator("OBJECTIVE COMPLETED! (after worker exit)")
                    objective_completed = True
                    break
            except Exception:
                pass
            # If still not done, spawn more workers for pending tasks
            pending_tasks = [t for t in tasks if t.status == "pending"]
            if pending_tasks and recovery_count < 3:
                print(f"  Spawning recovery workers for {len(pending_tasks)} pending tasks...")
                for i, pt in enumerate(pending_tasks[:2]):
                    wid = f"recovery-{recovery_count}-{i}"
                    proc = subprocess.Popen([
                        sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "main.py"),
                        "worker",
                        "--base-token", BASE_TOKEN,
                        "--objective-id", objective_id,
                        "--worker-id", wid,
                        "--worker-role", pt.role,
                        "--worker-max-tasks", "1",
                        "--worker-idle-rounds", "120",
                    ])
                    processes.append((wid, pt.role, proc))
                recovery_count += 1
                time.sleep(2)
                continue

            if recovery_count >= 3:
                print(f"  [GIVING UP] Max recovery attempts reached")
                break

        # Periodic recovery
        if time.time() - last_recovery > 30:
            try:
                expired = engine.recover_expired_tasks(objective_id)
                retried = engine.retry_failed_tasks(objective_id)
                if expired or retried:
                    print(f"  [RECOVERY] expired={expired} retried={retried}")
            except Exception:
                pass
            last_recovery = time.time()

        time.sleep(5)

    # ── Cleanup ──
    print_separator("Phase 4: Cleanup")
    for wid, role, proc in processes:
        if proc.poll() is None:
            proc.terminate()
            print(f"  Terminated: {wid} ({role})")
    for wid, role, proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ── Final state ──
    print_separator("Final State")
    tasks = store.list_tasks(objective_id)
    for t in tasks:
        arts = [a for a in store.list_artifacts(objective_id) if a.get("task_id") == t.task_id]
        print(f"  {t.status:<14} {t.subject:<35} attempts={t.attempt_count} artifacts={len(arts)}")
    verifs = store.list_verifications(objective_id)
    for v in verifs:
        print(f"  VERIFICATION: task={v.get('task_id','')[:20]} verdict={v.get('结论','-')}")

    # Force completion check
    try:
        engine.complete_objective_if_ready(objective_id)
    except Exception:
        pass

    if objective_completed:
        print_separator("SUCCESS: Objective fully completed!")
    else:
        print_separator("INCOMPLETE: Not all tasks finished. Check Base for current state.")
        print(f"  Objective ID: {objective_id}")

    return 0 if objective_completed else 1


if __name__ == "__main__":
    sys.exit(main())
