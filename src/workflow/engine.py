"""
工作流引擎
负责驱动 选题 -> 生产 -> 审核 -> 发布 -> 反馈 的完整链路
"""

import time
from src.base_client.cli_wrapper import BaseAPI
from src.agents.manager import ManagerAgent
from src.agents.editor import EditorAgent
from src.agents.reviewer import ReviewerAgent


class WorkflowEngine:
    """内容发布工作流引擎"""

    def __init__(self, base_api: BaseAPI):
        self.api = base_api
        self.manager = ManagerAgent(base_api)
        self.editor = EditorAgent(base_api)
        self.reviewer = ReviewerAgent(base_api)

    def run_full_chain(self, topic_title: str, content_title: str,
                       summary: str, category: str, word_count: int) -> dict:
        """
        跑通完整链路：
        Manager 创建选题 -> Editor 生产内容 -> 提交审核
        -> Reviewer 审核 -> Manager 审批发布
        """
        result = {}

        # 1. Manager 创建选题
        print("[Manager] 创建选题任务...")
        task_id = self.manager.create_topic(topic_title, priority="高")
        result["task_id"] = task_id
        print(f"  [OK] 任务ID: {task_id}")

        # 2. Manager 分配给 Editor
        print("[Manager] 分配任务给编辑...")
        self.manager.assign_to_editor(task_id)
        print(f"  [OK] 任务已分配")

        # 3. Editor 生产内容
        print("[Editor] 生产内容...")
        content_id = self.editor.produce_content(
            task_id, content_title, summary, category, word_count
        )
        result["content_id"] = content_id
        print(f"  [OK] 内容ID: {content_id}")

        # 4. Editor 提交审核
        print("[Editor] 提交审核...")
        review_id = self.editor.submit_for_review(content_id, task_id)
        result["review_id"] = review_id
        print(f"  [OK] 审核ID: {review_id}")

        # 5. Reviewer 审核
        print("[Reviewer] 领取审核任务...")
        review_task = self.reviewer.pick_review_task()
        if review_task:
            print(f"  [OK] 领取审核任务: {review_task['record_id']}")
            self.reviewer.approve(review_task["record_id"], "内容质量合格，通过")
            result["review_result"] = "通过"
            print(f"  [OK] 审核通过")
        else:
            result["review_result"] = "无待审核任务"
            print(f"  [!] 无待审核任务")

        # 6. Manager 审批发布
        print("[Manager] 审批发布...")
        self.manager.approve_publish(task_id)
        print(f"  [OK] 已发布")

        # 7. Manager 归档
        print("[Manager] 归档任务...")
        self.manager.archive_task(task_id)
        print(f"  [OK] 已归档")

        result["status"] = "完成"
        return result

    def run_until_blocked(self) -> list:
        """
        轮询驱动：持续扫描各表，驱动待处理任务往下流转
        返回：本次驱动了哪些任务
        """
        triggered = []

        # Editor: 处理"待处理"状态的任务
        task = self.editor.pick_task()
        if task:
            print(f"[轮询] Editor 领取任务: {task['title']}")
            content_id = self.editor.produce_content(
                task["record_id"],
                title=f"内容 - {task['title']}",
                summary="由 Editor 自动生成",
                category="运营",
                word_count=1000,
            )
            self.editor.submit_for_review(content_id, task["record_id"])
            triggered.append(f"task:{task['record_id']}")

        # Reviewer: 处理"待审核"状态的任务
        review = self.reviewer.pick_review_task()
        if review:
            print(f"[轮询] Reviewer 领取审核: {review['record_id']}")
            self.reviewer.approve(review["record_id"])
            triggered.append(f"review:{review['record_id']}")

        return triggered
