#!/usr/bin/env python3
"""Setup checker — validates config and basic health.

Usage: python scripts/setup_check.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    all_ok = True

    def check(step: int, label: str, ok: bool, detail: str = "") -> bool:
        nonlocal all_ok
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {step}. {label}", end="")
        if not ok and detail:
            print(f"\n        {detail}")
        else:
            print()
        if not ok:
            all_ok = False
        return ok

    print("=" * 56)
    print("Agent-Team Setup Checker")
    print("=" * 56)

    # 1 ─ config.yaml
    print("\n── Config ──")
    config_path = os.path.join(ROOT, "config.yaml")
    has_config = os.path.exists(config_path)
    check(1, "config.yaml exists", has_config,
          "Copy config.yaml.example → config.yaml and fill in values.")
    if not has_config:
        print("\n  Setup incomplete — fix FAIL items above and re-run.")
        return 1

    import yaml
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f.read()) or {}

    # 2 ─ LLM
    print("\n── LLM ──")
    llm_cfg = cfg.get("llm", {}) or {}
    api_key = llm_cfg.get("api_key", "")
    ep = llm_cfg.get("endpoint_id", "")
    check(2, "llm.api_key is set", bool(api_key) and "ark-" in str(api_key),
          "Get from https://console.volcengine.com/ark")
    check(3, "llm.endpoint_id is set", bool(ep) and "ep-" in str(ep),
          "Create an inference endpoint in ARK console")

    # 3 ─ Bot
    print("\n── Bot ──")
    bot_cfg = cfg.get("bot", {}) or {}
    app_id = bot_cfg.get("app_id", "")
    app_secret = bot_cfg.get("app_secret", "")
    check(4, "bot.app_id is set", bool(app_id) and "cli_" in str(app_id),
          "Create a Feishu Open Platform app at open.feishu.cn")
    check(5, "bot.app_secret is set", bool(app_secret),
          "Get from your Feishu app's credentials page")

    # 4 ─ Bot token registered
    print("\n── Bot token ──")
    creds_path = os.path.join(ROOT, ".credentials.json")
    has_creds = os.path.exists(creds_path)
    check(6, ".credentials.json exists", has_creds,
          "The bot token is auto-generated on first BaseClient use.\n"
          "        Make sure to add your Feishu app as a member of the Base.")

    # 5 ─ Memory demo
    print("\n── Smoke test ──")
    try:
        from src.agent_team.demo import run_agent_team_memory_demo
        result = run_agent_team_memory_demo("Setup check", "Verify protocol", max_tasks=3)
        ok = bool(result.get("objective_id")) and len(result.get("tasks", [])) > 0
        check(7, "Agent-team memory demo runs", ok,
              "This should always pass — check src/agent_team/ imports")
    except Exception as exc:
        check(7, "Agent-team memory demo runs", False,
              f"Error: {type(exc).__name__}: {exc}")

    # 6 ─ CLI
    print("\n── CLI ──")
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "src", "main.py"), "--help"],
            capture_output=True, text=True, timeout=60
        )
        has_run = "run" in (r.stdout or "")
        check(8, "main.py --help shows commands", has_run,
              "Check src/main.py")
    except Exception as exc:
        check(8, "main.py --help works", False, str(exc))

    # Summary
    print("\n" + "=" * 56)
    if all_ok:
        print("All checks passed. Ready:\n"
              "  python src/main.py --agent-team-memory-demo\n"
              "  python src/main.py run --base-token <TOKEN> --objective \"...\" --description \"...\"\n"
              "  cd frontend && npm run dev")
    else:
        print("Fix FAIL items above, then re-run.")
    print("=" * 56)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
