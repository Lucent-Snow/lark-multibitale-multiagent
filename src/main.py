"""
Entry point.
Usage:
  python src/main.py                                    # read demo.yaml, run full chain
  python src/main.py --topic "标题" --summary "摘要"    # CLI args override file
  python src/main.py --poll                             # polling driver
  python src/main.py --agent-team-demo                  # offline agent-team demo
  python src/main.py --agent-team-base-demo             # real Base agent-team demo
  python src/main.py --register <BOT_NAME>              # register a bot
"""

import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import argparse
import os
import sys

# Fix garbled output on Windows terminals
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from src.auth.app_auth import register_and_save, Credentials
from src.agent_team.demo import run_agent_team_base_demo, run_agent_team_demo
from src.base_client.client import BaseClient, BaseTableIds
from src.llm.client import LLMClient
from src.workflow.engine import WorkflowEngine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
DEMO_PATH = os.path.join(ROOT, "demo.yaml")

FALLBACK = {
    "topic_title":   "【AI 前沿】本周技术热点追踪",
    "content_title": "大模型应用趋势与落地实践",
    "summary":       "盘点本周大模型领域的最新进展，涵盖推理能力、多模态融合、Agent 架构等方向。",
    "category":      "科技",
    "word_count":    2000,
}


def _load_demo() -> dict:
    """Load demo scenario from demo.yaml. Returns dict with keys matching run_full_chain params."""
    if os.path.exists(DEMO_PATH):
        with open(DEMO_PATH, "r", encoding="utf-8") as f:
            demo = yaml.safe_load(f) or {}
        topic = demo.get("topic", {}) or {}
        content = demo.get("content", {}) or {}
        return {
            "topic_title":   topic.get("title", FALLBACK["topic_title"]),
            "content_title": content.get("title", FALLBACK["content_title"]),
            "summary":       content.get("summary", FALLBACK["summary"]),
            "category":      content.get("category", FALLBACK["category"]),
            "word_count":    content.get("word_count", FALLBACK["word_count"]),
        }
    return dict(FALLBACK)


def _load_table_ids(cfg: dict) -> BaseTableIds:
    """Load Feishu Base table IDs from config."""
    lark_cfg = cfg.get("lark", {}) or {}
    return BaseTableIds.from_config(lark_cfg.get("tables") or {})


def _print_agent_team_demo(result: dict) -> None:
    """Print an agent-team demo result."""
    print("\nAgent-Team Demo Result")
    print("-" * 50)
    print(f"Objective: {result['objective']}")
    print(f"All tasks completed: {result['all_tasks_completed']}")
    print("\nTasks:")
    for task in result["tasks"]:
        print(
            f"  - {task.task_id} | {task.role} | {task.status} | "
            f"{task.owner or '-'} | {task.subject}"
        )
    print("\nArtifacts:")
    for artifact_id, artifact in result["artifacts"].items():
        print(
            f"  - {artifact_id} | {artifact['author']} | "
            f"{artifact['title']}"
        )
    print("\nMessages:")
    for message_id, message in result["messages"].items():
        print(
            f"  - {message_id} | {message['sender']} -> "
            f"{message['recipient']} | {message['summary']}"
        )
    print("\nLogs:")
    for log in result["logs"]:
        print(
            f"  - {log['log_id']} | {log['operator']} | "
            f"{log['op_type']} | {log['target_id']}"
        )


def _print_agent_team_base_demo(result: dict) -> None:
    """Print a real Base agent-team validation result."""
    print("\nAgent-Team Base Demo Result")
    print("-" * 50)
    print(f"Objective: {result['objective']}")
    print(f"Objective record: {result['objective_id']}")
    print(f"All tasks completed: {result['all_tasks_completed']}")
    print("\nPlanned tasks:")
    for task in result["planned_tasks"]:
        print(
            f"  - {task.task_id} | {task.role} | {task.status} | "
            f"{task.owner or '-'} | {task.subject}"
        )
    print("\nCompleted tasks:")
    for task in result["completed_tasks"]:
        print(
            f"  - {task.task_id} | {task.role} | {task.status} | "
            f"{task.owner} | {task.subject}"
        )
    print("\nVerification records:")
    for record_id in result["verification_ids"]:
        print(f"  - {record_id}")
    print("\nReadback:")
    print(f"  Objective status: {result['readback']['objective'].get('状态')}")
    print(f"  Task records read: {len(result['readback']['tasks'])}")
    print(f"  Verification records read: {len(result['readback']['verifications'])}")


def main():
    parser = argparse.ArgumentParser(description="Feishu Multi-Agent Content Publishing System")
    parser.add_argument("--register", metavar="BOT_NAME", help="Register a new bot (opens browser)")

    # Full chain mode — all optional, fall back to demo.yaml then FALLBACK
    parser.add_argument("--topic", default=None, help="Topic / task title")
    parser.add_argument("--content-title", default=None, help="Article title for Editor")
    parser.add_argument("--summary", default=None, help="Article summary / abstract")
    parser.add_argument("--category", default=None, help="Content category")
    parser.add_argument("--word-count", type=int, default=None, help="Target word count")

    # Polling mode
    parser.add_argument("--poll", action="store_true",
                        help="Run polling driver instead of full chain")
    parser.add_argument("--agent-team-demo", action="store_true",
                        help="Run offline agent-team task-market demo")
    parser.add_argument("--agent-team-base-demo", action="store_true",
                        help="Run real LLM + Feishu Base agent-team demo")
    parser.add_argument("--objective", default=None,
                        help="Agent-team objective title")
    parser.add_argument("--objective-description", default=None,
                        help="Agent-team objective description")
    parser.add_argument("--agent-team-max-tasks", type=int, default=4,
                        help="Maximum tasks for agent-team demo")

    args = parser.parse_args()

    print("=" * 50)
    print("Feishu Multi-Agent Content Publishing System")
    print("=" * 50)

    if args.agent_team_demo:
        title = args.objective or "AI 内容运营团队演示"
        description = args.objective_description or (
            "围绕一个开放目标，演示 Leader 拆任务、Worker 领取任务、"
            "产物写回、消息通知和操作日志。"
        )
        result = run_agent_team_demo(
            title=title,
            description=description,
            max_tasks=args.agent_team_max_tasks,
        )
        _print_agent_team_demo(result)
        return

    # Load config
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # ── Bot Registration ───────────────────────────────────
    if args.register:
        bot_name = args.register
        print(f"\n[Register] Creating bot '{bot_name}'...")
        register_and_save(bot_name)
        print(f"[Register] Bot '{bot_name}' saved to .credentials.json")
        return

    # ── Auth ───────────────────────────────────────────────
    base_token = cfg["lark"]["base_token"]
    table_ids = _load_table_ids(cfg)

    creds = Credentials()
    for bot_name in ("manager", "editor", "reviewer"):
        if not creds.get(bot_name):
            raise Exception(
                f"Bot '{bot_name}' not found. Run: python src/main.py --register {bot_name}"
            )

    # ── Base API (one client per bot identity) ─────────────
    print("[Base] Initializing bot clients...")
    manager_api = BaseClient(bot_name="manager", base_token=base_token, table_ids=table_ids)
    editor_api = BaseClient(bot_name="editor", base_token=base_token, table_ids=table_ids)
    reviewer_api = BaseClient(bot_name="reviewer", base_token=base_token, table_ids=table_ids)
    print("[Base] manager / editor / reviewer OK")

    # ── LLM ───────────────────────────────────────────────
    print("[LLM] Initializing ARK client...")
    llm = LLMClient(
        api_key=cfg["llm"]["api_key"],
        endpoint_id=cfg["llm"]["endpoint_id"],
    )
    print("[LLM] OK")

    if args.agent_team_base_demo:
        title = args.objective or "真实飞书 Base Agent-Team 验证"
        description = args.objective_description or (
            "验证 Leader 使用真实 LLM 拆解开放目标，多个角色围绕飞书 Base "
            "任务市场完成领取、产物写回、消息通知、验证记录和操作日志。"
        )
        result = run_agent_team_base_demo(
            manager_api=manager_api,
            editor_api=editor_api,
            reviewer_api=reviewer_api,
            llm=llm,
            title=title,
            description=description,
            max_tasks=args.agent_team_max_tasks,
        )
        _print_agent_team_base_demo(result)
        return

    # ── Merge args with demo file ──────────────────────────
    demo = _load_demo()
    topic_title   = args.topic         or demo["topic_title"]
    content_title = args.content_title or demo["content_title"]
    summary       = args.summary       or demo["summary"]
    category      = args.category      or demo["category"]
    word_count    = args.word_count    or demo["word_count"]

    # ── Workflow ───────────────────────────────────────────
    engine = WorkflowEngine(manager_api, editor_api, reviewer_api, llm)

    if args.poll:
        print("\nStarting polling mode (Ctrl+C to stop)...\n")
        engine.run_until_blocked()
    else:
        print(f"\nTopic: {topic_title}")
        print(f"Content: {content_title}")
        print(f"Category: {category} | Words: {word_count}")
        print(f"Source: demo.yaml (override with --topic / --content-title / ...)")
        print("\nExecuting full content publishing chain...\n")

        result = engine.run_full_chain(
            topic_title=topic_title,
            content_title=content_title,
            summary=summary,
            category=category,
            word_count=word_count,
        )

        print("\n" + "=" * 50)
        print("Result:")
        for k, v in result.items():
            if k == "report":
                print(f"  {k}:")
                for line in v.split("\n"):
                    print(f"    {line}")
            else:
                print(f"  {k}: {v}")
        print("=" * 50)


if __name__ == "__main__":
    main()
