"""
Operation Manager Agent.
Uses LLM for topic planning, report generation, and publish decisions.
"""

import json
from src.base_client.client import BaseClient
from src.llm.client import LLMClient


MANAGER_SYSTEM_PROMPT = """\
You are an operations manager for a content publishing platform.
Your responsibilities include:
1. Creating and prioritizing content topics
2. Assigning tasks to editors
3. Reviewing reports and making operational decisions
4. Approving content for publication

Be concise and professional in your responses.
When generating reports, output in Chinese with clear structure."""


class ManagerAgent:
    """Operation Manager Agent with LLM-powered decision making."""

    def __init__(self, base_client: BaseClient, llm: LLMClient):
        self.api = base_client
        self.llm = llm
        self.name = "运营主管"

    def create_topic(self, title: str, priority: str = "中") -> str:
        """Create a new content topic task."""
        record_id = self.api.create_task({
            "任务标题": title,
            "状态": "待处理",
            "负责人": self.name,
            "优先级": priority,
        })
        self.api.log_operation(
            operator=self.name,
            op_type="创建",
            record_id=record_id,
            detail=f"Created topic: {title}"
        )
        return record_id

    def assign_to_editor(self, record_id: str) -> bool:
        """Assign a task to the editor."""
        self.api.update_task_status(record_id, "处理中")
        self.api.log_operation(
            operator=self.name,
            op_type="分配",
            record_id=record_id,
            detail="Task assigned to content editor"
        )
        return True

    def approve_publish(self, record_id: str) -> bool:
        """Approve and publish a completed task."""
        self.api.update_task_status(record_id, "已发布")
        self.api.log_operation(
            operator=self.name,
            op_type="发布",
            record_id=record_id,
            detail="Manager approved, task published"
        )
        return True

    def archive_task(self, record_id: str) -> bool:
        """Archive a completed task."""
        self.api.update_task_status(record_id, "已归档")
        self.api.log_operation(
            operator=self.name,
            op_type="归档",
            record_id=record_id,
            detail="Task archived"
        )
        return True

    def generate_report(self) -> str:
        """
        Generate an operational report using LLM.
        Analyzes current task and content data.
        """
        tasks = self.api.list_tasks()
        contents = self.api.list_contents()

        stats = {
            "总任务数": len(tasks),
            "内容数": len(contents),
            "详细任务": [],
            "详细内容": [],
        }

        for task in tasks[:10]:
            f = task.fields or {}
            stats["详细任务"].append({
                "title": f.get("任务标题", ""),
                "status": f.get("状态", ""),
                "priority": f.get("优先级", ""),
            })

        for content in contents[:10]:
            f = content.fields or {}
            stats["详细内容"].append({
                "title": f.get("内容标题", ""),
                "category": f.get("分类", ""),
                "status": f.get("状态", ""),
                "word_count": f.get("字数", 0),
            })

        user_prompt = f"""\
Generate an operational report based on the following data:

{json.dumps(stats, ensure_ascii=False, indent=2)}

Please provide:
1. Overview of current operations
2. Task status summary
3. Content production summary
4. Recommendations for next steps"""

        print(f"  [Manager] Generating report with LLM...")
        report = self.llm.chat_with_system(
            MANAGER_SYSTEM_PROMPT, user_prompt
        )
        return report
