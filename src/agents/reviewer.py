"""
Quality Reviewer Agent.
Uses LLM to review content quality and make approval/rejection decisions.
"""

from src.base_client.client import BaseClient
from src.llm.client import LLMClient


REVIEWER_SYSTEM_PROMPT = """\
You are a senior quality reviewer for a content publishing platform.
Your job is to review articles and decide whether they should be published.

Review criteria:
1. Content quality - Is the article well-written, coherent, and informative?
2. Accuracy - Does the content appear accurate and well-researched?
3. Appropriateness - Is the content suitable for publication?
4. Completeness - Is the article complete and meeting its stated goals?

Your response must be in this format:
Decision: [APPROVE / REJECT]
Opinion: [Brief review opinion in Chinese, 2-3 sentences]
Reason: [Brief reason for the decision]"""


class ReviewerAgent:
    """Quality Reviewer Agent with LLM-powered content review."""

    def __init__(self, base_client: BaseClient, llm: LLMClient):
        self.api = base_client
        self.llm = llm
        self.name = "质量审核"

    def pick_review_task(self) -> dict:
        """Claim a pending review task."""
        reviews = self.api.list_pending_reviews()
        for review in reviews:
            fields = review.fields or {}
            status = fields.get("审核状态", "")
            if isinstance(status, list):
                status = status[0] if status else ""
            if status == "待审核":
                return {
                    "record_id": review.record_id or "",
                    "content_id": fields.get("关联内容ID", ""),
                    "priority": fields.get("优先级", ""),
                }
        return {}

    def review(self, review_record_id: str, article: str, title: str) -> tuple[str, str]:
        """
        Review an article using LLM.
        Returns (decision, opinion) where decision is "通过" or "驳回".
        """
        user_prompt = f"""\
Please review the following article:

Title: {title}

Article:
{(article or '')[:3000]}

Make your decision now:"""

        print(f"  [Reviewer] Reviewing with LLM...")
        response = self.llm.chat_with_system(
            REVIEWER_SYSTEM_PROMPT, user_prompt
        )

        # Parse the LLM response
        decision = "通过"
        opinion = "Content quality acceptable, approved."

        for line in response.split("\n"):
            line = line.strip()
            if line.lower().startswith("decision:"):
                if "REJECT" in line.upper():
                    decision = "驳回"
                else:
                    decision = "通过"
            elif line.lower().startswith("opinion:"):
                opinion = line.split(":", 1)[1].strip()

        self.api.update_review_status(review_record_id, decision, opinion)
        self.api.log_operation(
            operator=self.name,
            op_type="审核" if decision == "通过" else "驳回",
            record_id=review_record_id,
            detail=f"Review: {decision} - {opinion}"
        )
        return decision, opinion

    def approve(self, review_record_id: str, opinion: str = "") -> bool:
        """Approve a review task directly (non-LLM path)."""
        opinion = opinion or "Content quality meets standards, approved."
        self.api.update_review_status(review_record_id, "通过", opinion)
        self.api.log_operation(
            operator=self.name,
            op_type="审核",
            record_id=review_record_id,
            detail=f"Approved: {opinion}"
        )
        return True

    def reject(self, review_record_id: str, opinion: str) -> bool:
        """Reject a review task."""
        self.api.update_review_status(review_record_id, "驳回", opinion)
        self.api.log_operation(
            operator=self.name,
            op_type="驳回",
            record_id=review_record_id,
            detail=f"Rejected: {opinion}"
        )
        return True
