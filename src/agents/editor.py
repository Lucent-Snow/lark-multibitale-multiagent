"""
Content Editor Agent.
Uses LLM to generate article content, then writes to Base.
"""

from src.base_client.client import BaseClient
from src.llm.client import LLMClient


EDITOR_SYSTEM_PROMPT = """\
You are a professional content editor. Your task is to write high-quality articles
based on a given topic, title, summary, and category. The article should be:
- Well-structured with a clear beginning, middle, and end
- Engaging and informative
- Appropriate for the specified category
- At approximately the requested word count
Write the full article text directly. No meta-commentary."""


class EditorAgent:
    """Content Editor Agent with LLM-powered content generation."""

    def __init__(self, base_client: BaseClient, llm: LLMClient):
        self.api = base_client
        self.llm = llm
        self.name = "内容编辑"

    def pick_task(self) -> dict:
        """Claim a pending task from the task table."""
        tasks = self.api.list_tasks()
        for task in tasks:
            fields = task.fields or {}
            status = fields.get("状态", "")
            if isinstance(status, list):
                status = status[0] if status else ""
            if status == "待处理":
                return {
                    "record_id": task.record_id or "",
                    "title": fields.get("任务标题", ""),
                    "priority": fields.get("优先级", ""),
                }
        return {}

    def produce_content(self, task_record_id: str, title: str, summary: str,
                        category: str, word_count: int) -> str:
        """Generate article content via LLM and write to content table."""
        user_prompt = f"""\
Write an article with the following specifications:
- Title: {title}
- Category: {category}
- Summary: {summary}
- Approximate word count: {word_count} words

Write the full article now:"""

        print(f"  [Editor] Generating content with LLM...")
        article = self.llm.chat_with_system(
            EDITOR_SYSTEM_PROMPT, user_prompt,
            max_tokens=max(4096, word_count * 3),
        )

        content_id = self.api.create_content({
            "内容标题": title,
            "正文摘要": summary,
            "正文全文": article,
            "分类": category,
            "字数": len(article),
            "关联任务ID": task_record_id,
            "状态": "处理中",
        })
        self.api.update_task_status(task_record_id, "待审核")
        self.api.log_operation(
            operator=self.name,
            op_type="创建",
            record_id=content_id,
            detail=f"Content generated: {title}, words: {len(article)}"
        )
        return content_id

    def submit_for_review(self, content_record_id: str, task_record_id: str) -> str:
        """Submit content for review."""
        review_id = self.api.create_review_task({
            "关联内容ID": content_record_id,
            "审核人": "质量审核",
            "审核状态": "待审核",
            "优先级": "中",
        })
        self.api.log_operation(
            operator=self.name,
            op_type="审核",
            record_id=review_id,
            detail=f"Submitted content {content_record_id} for review"
        )
        return review_id
