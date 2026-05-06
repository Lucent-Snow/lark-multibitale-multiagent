#!/usr/bin/env python3
"""Test one scenario end-to-end."""
import sys, time, os, subprocess, uuid; sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml

TOKEN='WFeZbPq5faeHt3sq51lcRU2SnKb'
with open('config.yaml',encoding='utf-8') as f: cfg=yaml.safe_load(f.read()) or {}

from src.base_client.client import BaseClient
from src.agent_team.base_store import BaseObjectiveStore
from src.agent_team.engine import Leader
from src.agent_team.demo import make_llm_artifact_fn, make_llm_verification_fn, select_agent_team_workers
from src.llm.client import LLMClient

llm=LLMClient(cfg['llm']['api_key'],cfg['llm']['endpoint_id'],timeout=120)
base=BaseClient(TOKEN)

s = {'title':'撰写本周科技产业深度周报',
     'description':'面向科技行业从业者撰写本周深度周报(2000字以上)。覆盖三个方向：AI大模型最新进展(2-3个重大事件)、硬件半导体动态(新品/供应链)、科技产业趋势(投融资/政策)。每个方向独立成章，数据标注来源，整体语言专业。最终审核员交叉核验事实准确性和章节间数据自洽。'}

print(f"Scenario: {s['title']}", flush=True)

# Plan
leader = Leader(llm, allow_fallback=False)
try:
    workers_spec, plans = leader.plan(s['title'], s['description'], max_tasks=5)
except:
    workers_spec, plans = Leader(None).plan(s['title'], s['description'], max_tasks=5)

print(f'Workers: {len(workers_spec)}', flush=True)
for w in workers_spec:
    print(f'  {w.worker_id} ({w.role}): {w.prompt[:80]}...', flush=True)
print(f'Tasks: {len(plans)}', flush=True)
for t in plans:
    deps = ','.join(t.blocked_by_subjects) if t.blocked_by_subjects else 'none'
    print(f'  [{t.role}] {t.subject} (deps: {deps})', flush=True)

# Create table
oid = f'rec{uuid.uuid4().hex[:12]}'
store = BaseObjectiveStore(base, oid)
for plan in plans:
    store.add_task(plan)
print(f'Table: {store.table_name}', flush=True)

# Spawn workers
procs = []
selected = select_agent_team_workers(len(workers_spec))
for (wid, role) in selected[:len(workers_spec)]:
    p = subprocess.Popen([
        sys.executable, 'src/main.py', 'worker',
        '--base-token', TOKEN, '--objective-id', oid,
        '--worker-id', wid, '--worker-role', role,
        '--worker-max-tasks', '3', '--worker-idle-rounds', '300',
    ])
    procs.append((wid, role, p))

# Monitor
deadline = time.time() + 900
last = ''
while time.time() < deadline:
    tasks = store.list_tasks()
    c = sum(1 for t in tasks if t.status == 'completed')
    ip = sum(1 for t in tasks if t.status == 'in_progress')
    pn = sum(1 for t in tasks if t.status == 'pending')
    fl = sum(1 for t in tasks if t.status == 'failed')
    snap = f'c={c}/{len(tasks)} ip={ip} p={pn} f={fl}'
    if snap != last:
        elapsed = int(time.time() - (deadline - 900))
        print(f'[{elapsed}s] {snap}', flush=True)
        last = snap
    if c == len(tasks) and tasks:
        print('ALL COMPLETE!', flush=True)
        break
    # Retry failed
    for t in store.list_tasks():
        if t.status == 'failed' and t.attempt_count < 3:
            store.update_task(t.task_id, {'status': 'pending', 'owner': ''})
    time.sleep(10)

# Cleanup
for _, _, p in procs:
    if p.poll() is None: p.terminate()
for _, _, p in procs:
    try: p.wait(timeout=5)
    except: p.kill()

# Results
print('\n=== RESULTS ===', flush=True)
tasks = store.list_tasks()
for t in tasks:
    al = len(t.artifact) if t.artifact else 0
    print(f'{t.status:<12} a{t.attempt_count} [{t.verdict:<5}] {t.subject[:35]:<35} art={al}c issues={t.issues[:40]}', flush=True)
