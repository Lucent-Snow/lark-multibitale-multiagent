"""
质量审核 Agent
职责：
- 领取审核任务
- 审核内容
- 给出通过/驳回结论
"""

from src.base_client.cli_wrapper import BaseAPI


class ReviewerAgent:
    """质量审核 Agent"""

    def __init__(self, base_api: BaseAPI):
        self.api = base_api
        self.name = "质量审核"

    def pick_review_task(self) -> dict:
        """领取审核任务：从审核队列找"待审核"任务"""
        reviews = self.api.list_pending_reviews()
        for review in reviews:
            fields = review.get("fields", {})
            status = fields.get("审核状态", "")
            if isinstance(status, list):
                status = status[0] if status else ""
            if status == "待审核":
                return {
                    "record_id": review.get("record_id", ""),
                    "content_id": fields.get("关联内容ID", ""),
                    "priority": fields.get("优先级", ""),
                }
        return {}

    def approve(self, review_record_id: str, opinion: str = "内容质量达标，通过发布") -> bool:
        """审核通过"""
        self.api.update_review_status(review_record_id, "通过", opinion)
        self.api.log_operation(
            operator=self.name,
            op_type="审核",
            record_id=review_record_id,
            detail=f"审核通过: {opinion}"
        )
        return True

    def reject(self, review_record_id: str, opinion: str) -> bool:
        """审核驳回"""
        self.api.update_review_status(review_record_id, "驳回", opinion)
        self.api.log_operation(
            operator=self.name,
            op_type="驳回",
            record_id=review_record_id,
            detail=f"审核驳回: {opinion}"
        )
        return True
