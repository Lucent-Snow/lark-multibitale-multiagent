"""
内容编辑 Agent
职责：
- 接收选题任务
- 生产内容
- 提交审核
"""

from src.base_client.cli_wrapper import BaseAPI


class EditorAgent:
    """内容编辑 Agent"""

    def __init__(self, base_api: BaseAPI):
        self.api = base_api
        self.name = "内容编辑"

    def pick_task(self) -> dict:
        """领取任务：从任务台账找"待处理"任务"""
        tasks = self.api.list_tasks()
        for task in tasks:
            fields = task.get("fields", {})
            status = fields.get("状态", "")
            if isinstance(status, list):
                status = status[0] if status else ""
            if status == "待处理":
                return {
                    "record_id": task.get("record_id", ""),
                    "title": fields.get("任务标题", ""),
                    "priority": fields.get("优先级", ""),
                }
        return {}

    def produce_content(self, task_record_id: str, title: str, summary: str, category: str, word_count: int) -> str:
        """生产内容：写入内容库"""
        content_id = self.api.create_content({
            "内容标题": title,
            "正文摘要": summary,
            "分类": category,
            "字数": word_count,
            "关联任务ID": task_record_id,
            "状态": "处理中",
        })
        self.api.update_task_status(task_record_id, "待审核")
        self.api.log_operation(
            operator=self.name,
            op_type="创建",
            record_id=content_id,
            detail=f"内容已生产: {title}，字数: {word_count}"
        )
        return content_id

    def submit_for_review(self, content_record_id: str, task_record_id: str) -> str:
        """提交审核：创建审核任务"""
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
            detail=f"提交内容 {content_record_id} 到审核队列"
        )
        return review_id
