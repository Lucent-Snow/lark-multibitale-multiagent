#!/usr/bin/env python3
"""Run full agent-team objective with real-time Base monitoring."""
import subprocess, sys, time, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from src.base_client.client import BaseClient
from src.agent_team.base_store import BaseAgentTeamStore
from src.agent_team.engine import AgentTeamEngine, Leader
from src.llm.client import LLMClient

TOKEN = "WFeZbPq5faeHt3sq51lcRU2SnKb"

with open("config.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f.read()) or {}
llm_cfg = cfg.get("llm") or {}

llm = LLMClient(llm_cfg["api_key"], llm_cfg["endpoint_id"], timeout=120)
base = BaseClient(TOKEN)
store = BaseAgentTeamStore(base)

# ── PLAN ──
print("=" * 70, flush=True)
print("PHASE 1: Leader plans with real LLM", flush=True)
print("=" * 70, flush=True)
engine = AgentTeamEngine(store, Leader(llm, allow_fallback=False))
result = engine.start_objective(
    "浙大飞书AI黑客松完整策划",
    "为浙大策划一场2天飞书AI黑客松。需覆盖：1)紫金港3个场地详细对比(含容量/费用/设备) "
    "2)3个赛道设计+评审标准+权重 3)预算10-20万详细拆解(场地/餐饮/奖品/物料/宣传) "
    "4)2天赛程执行手册(时间线/分工/应急预案) 5)4周校园宣传方案(渠道/KOL/物料) "
    "6)最终整合审核。所有数字必须自洽且可交叉验证。",
    max_tasks=6,
)
oid = result["objective_id"]
print(f"Objective ID: {oid}", flush=True)
print(f"Workers ({len(result['workers'])}):", flush=True)
for w in result["workers"]:
    print(f"  {w.worker_id:<22} {w.name:<10} {w.role}  prompt={w.prompt[:60]}...", flush=True)
print(f"Tasks ({len(result['tasks'])}):", flush=True)
for t in result["tasks"]:
    deps = [e for e in store.list_edges(oid) if e.to_task_id == t.task_id]
    label = "PARALLEL" if not deps else f"SERIAL({len(deps)}dep)"
    print(f"  [{label}] {t.subject:<35} role={t.role}", flush=True)

# ── SPAWN ──
print(f"\n{'='*70}", flush=True)
print("PHASE 2: Spawning workers", flush=True)
print(f"{'='*70}", flush=True)
procs = []
for w in result["workers"]:
    p = subprocess.Popen([
        sys.executable, "src/main.py", "worker",
        "--base-token", TOKEN, "--objective-id", oid,
        "--worker-id", w.worker_id, "--worker-role", w.role,
        "--worker-max-tasks", "3", "--worker-idle-rounds", "180",
    ])
    procs.append((w.worker_id, p))
    print(f"  PID={p.pid} {w.worker_id} ({w.role})", flush=True)

# ── MONITOR ──
print(f"\n{'='*70}", flush=True)
print("PHASE 3: Monitoring Base tables live", flush=True)
print(f"{'='*70}", flush=True)
last_snap = ""
started = time.time()
for i in range(90):
    tasks = store.list_tasks(oid)
    arts = store.list_artifacts(oid)
    verifs = store.list_verifications(oid)
    events_list = [r for r in base.list_records(store.table_ids["events"])
                   if (r.fields or {}).get("objective_id") == oid]

    counts = {}
    for t in tasks:
        counts[t.status] = counts.get(t.status, 0) + 1
    c = counts.get("completed", 0)
    ip = counts.get("in_progress", 0)
    cl = counts.get("claimed", 0)
    p = counts.get("pending", 0)
    f = counts.get("failed", 0)

    snap = f"c={c} ip={ip} cl={cl} p={p} f={f} | arts={len(arts)} verifs={len(verifs)} events={len(events_list)}"
    if snap != last_snap:
        elapsed = int(time.time() - started)
        print(f"\n--- t={elapsed}s [{snap}] ---", flush=True)
        for t in tasks:
            ta = [a for a in arts if a.get("task_id") == t.task_id]
            tv = [v for v in verifs if v.get("task_id") == t.task_id]
            verdicts = [v.get("结论", "?") for v in tv]
            marker = ""
            if t.status == "failed":
                marker = " <<< FAIL (triggers auto-retry)"
            elif t.status == "pending" and t.attempt_count > 0:
                marker = f" <<< RETRY a{t.attempt_count} (failed verification → redo)"
            elif t.status == "in_progress" and t.attempt_count > 1:
                marker = f" <<< REWORK a{t.attempt_count}"
            print(f"  {t.status:<12} a={t.attempt_count} [{', '.join(verdicts):<6}] {t.subject[:35]} {marker}", flush=True)

        # Recent events from Base = audit trail
        for ev in list(reversed(events_list))[:3]:
            flds = ev.fields or {}
            print(f"  [BaseEvent] {flds.get('event_type','?')}: {flds.get('detail','')[:70]}", flush=True)

        last_snap = snap

    if c == len(tasks) and c > 0:
        print(f"\n>>> ALL {c} TASKS COMPLETE <<<", flush=True)
        break

    try:
        engine.recover_expired_tasks(oid)
        engine.retry_failed_tasks(oid)
    except Exception:
        pass
    time.sleep(8)

# ── CLEANUP ──
for _, proc in procs:
    if proc.poll() is None:
        proc.terminate()
for _, proc in procs:
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

# ── COMPLETE OBJECTIVE ──
try:
    engine.complete_objective_if_ready(oid)
except Exception:
    pass

# ── FINAL ──
print(f"\n{'='*70}", flush=True)
print("FINAL STATE", flush=True)
print(f"{'='*70}", flush=True)
tasks = store.list_tasks(oid)
for t in tasks:
    ta = [a for a in store.list_artifacts(oid) if a.get("task_id") == t.task_id]
    tv = [v for v in store.list_verifications(oid) if v.get("task_id") == t.task_id]
    vv = [v.get("结论", "?") for v in tv]
    print(f"  {t.status:<12} a{t.attempt_count} [{', '.join(vv):<8}] {t.subject[:40]} art={len(ta)}", flush=True)

# Check objective record for final report
for rec in base.list_records(store.table_ids["objectives"]):
    flds = rec.fields or {}
    if flds.get("objective_id") == oid:
        print(f"\nObjective Status: {flds.get('状态')}", flush=True)
        report = flds.get("最终结论", "")
        if report:
            print(f"Final Report ({len(report)} chars):")
            print(report[:800])
        break
