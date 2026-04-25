"""
入口文件
运行方式：
  python src/main.py
"""

import sys
import os

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base_client.cli_wrapper import BaseAPI
from src.workflow.engine import WorkflowEngine


def main():
    print("=" * 50)
    print("Feishu Multi-Agent Content Publishing System")
    print("=" * 50)

    # 读取配置
    import yaml
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    base_token = config["lark"]["base_token"]

    # 初始化 API 层（内部调用 lark-cli，复用已登录 token）
    print("\nInitializing Base API layer...")
    api = BaseAPI(base_token=base_token)
    print("[OK] Base API initialized")

    # 初始化工作流引擎
    engine = WorkflowEngine(api)

    # 跑一次完整链路
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
        print(f"  {k}: {v}")
    print("=" * 50)


if __name__ == "__main__":
    main()
