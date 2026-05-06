"""Entry point.
Usage:
  python src/main.py run --base-token X --objective "标题" --description "描述"
  python src/main.py worker --base-token X --objective-id Y --worker-id Z --role R
"""

import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import argparse, os, sys, time

try: sys.stdout.reconfigure(encoding="utf-8")
except: pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_team.base_store import BaseObjectiveStore
from src.agent_team.demo import (
    make_llm_artifact_fn, make_llm_verification_fn,
    run_agent_team_base_demo, run_agent_team_memory_demo,
)
from src.agent_team.engine import Worker
from src.base_client.client import BaseClient
from src.llm.client import LLMClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_llm():
    import yaml
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f.read()) or {}
    c = cfg.get("llm") or {}
    return LLMClient(c["api_key"], c["endpoint_id"])


def cmd_run(args):
    llm = _load_llm()
    result = run_agent_team_base_demo(
        base_token=args.base_token, llm=llm,
        title=args.objective, description=args.description,
        max_tasks=args.max_tasks, workers=args.workers,
        timeout_seconds=args.timeout,
    )
    print(f"\nObjective: {result['objective_id']}")
    print(f"Table: {result.get('table_name', 'N/A')}")
    for t in result["tasks"]:
        print(f"  {t.status:<12} {t.subject}")


def cmd_worker(args):
    llm = _load_llm()
    base = BaseClient(args.base_token)
    store = BaseObjectiveStore(base, args.objective_id)
    worker = Worker(
        store=store, objective_id=args.objective_id,
        worker_id=args.worker_id, role=args.worker_role,
        artifact_fn=make_llm_artifact_fn(llm, args.worker_id, args.worker_role),
        verification_fn=make_llm_verification_fn(llm, args.worker_id, args.worker_role),
    )
    completed = 0; idle = 0
    while completed < args.worker_max_tasks and idle < args.worker_idle_rounds:
        try:
            r = worker.run_once()
        except Exception:
            idle += 1; time.sleep(1); continue
        if r["status"] == "completed": completed += 1; idle = 0
        elif r["status"] == "retry": idle = 0
        elif r["status"] == "idle": idle += 1; time.sleep(1)
        else: idle = 0
    print(f"[Worker] {args.worker_id} completed={completed} idle={idle}")


def main():
    parser = argparse.ArgumentParser(description="Feishu Multi-Agent Network")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run")
    run.add_argument("--base-token", required=True)
    run.add_argument("--objective", required=True)
    run.add_argument("--description", required=True)
    run.add_argument("--max-tasks", type=int, default=5)
    run.add_argument("--workers", type=int, default=3)
    run.add_argument("--timeout", type=int, default=600)

    w = sub.add_parser("worker")
    w.add_argument("--base-token", required=True)
    w.add_argument("--objective-id", required=True)
    w.add_argument("--worker-id", required=True)
    w.add_argument("--worker-role", required=True)
    w.add_argument("--worker-max-tasks", type=int, default=3)
    w.add_argument("--worker-idle-rounds", type=int, default=180)

    parser.add_argument("--agent-team-memory-demo", action="store_true")
    parser.add_argument("--objective", default="AI 团队演示")
    parser.add_argument("--objective-description", default="验证协议。")
    parser.add_argument("--agent-team-max-tasks", type=int, default=4)
    args = parser.parse_args()

    if args.agent_team_memory_demo:
        r = run_agent_team_memory_demo(args.objective, args.objective_description, args.agent_team_max_tasks)
        for t in r["tasks"]: print(f"  {t.status} {t.subject}")
        return

    if args.command == "run": cmd_run(args)
    elif args.command == "worker": cmd_worker(args)
    else: parser.print_help()


if __name__ == "__main__":
    main()
