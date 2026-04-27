"""
Entry point.
Usage:
  python src/main.py              # run full chain
  python src/main.py --register   # register a new bot
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from src.auth.app_auth import register_and_save, Credentials, get_token
from src.base_client.client import BaseClient
from src.llm.client import LLMClient
from src.workflow.engine import WorkflowEngine


def main():
    parser = argparse.ArgumentParser(description="Feishu Multi-Agent Content Publishing System")
    parser.add_argument("--register", metavar="BOT_NAME", help="Register a new bot (opens browser)")
    args = parser.parse_args()

    print("=" * 50)
    print("Feishu Multi-Agent Content Publishing System")
    print("=" * 50)

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
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
    bots_cfg = cfg["lark"]["bots"]

    # Default bot is manager
    manager_bot = bots_cfg.get("manager", {})
    manager_name = "manager"

    creds = Credentials()
    if not creds.get(manager_name):
        raise Exception(f"Bot '{manager_name}' not found. Run: python src/main.py --register manager")

    print(f"\n[Auth] Initializing bot '{manager_name}'...")
    get_token(manager_name)  # Validate credentials
    print("[Auth] OK")

    # ── Base API ───────────────────────────────────────────
    print("[Base] Initializing SDK client...")
    api = BaseClient(bot_name=manager_name, base_token=base_token)
    print("[Base] OK")

    # ── LLM ───────────────────────────────────────────────
    print("[LLM] Initializing ARK client...")
    llm = LLMClient(
        api_key=cfg["llm"]["api_key"],
        endpoint_id=cfg["llm"]["endpoint_id"],
    )
    print("[LLM] OK")

    # ── Workflow ───────────────────────────────────────────
    engine = WorkflowEngine(api, llm)
    print("\nExecuting full content publishing chain...\n")

    result = engine.run_full_chain(
        topic_title="【首发】Claude 4.7 发布实测",
        content_title="Claude 4.7 发布：上下文窗口扩展至 20M",
        summary="实测 Claude 4.7 在代码补全、多文件重构、测试生成三大场景的表现...",
        category="科技",
        word_count=3200,
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
