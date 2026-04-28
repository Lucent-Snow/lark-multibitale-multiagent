import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO

from src.agents.reviewer import ReviewerAgent
from src.workflow.engine import WorkflowEngine


@dataclass
class FakeRecord:
    record_id: str
    fields: dict


class FakeBaseApi:
    def __init__(self, store):
        self.store = store

    def _create(self, table: str, fields: dict) -> str:
        record_id = f"rec_{table}_{len(self.store[table]) + 1}"
        self.store[table][record_id] = dict(fields)
        return record_id

    def _records(self, table: str) -> list[FakeRecord]:
        return [
            FakeRecord(record_id=record_id, fields=fields)
            for record_id, fields in self.store[table].items()
        ]

    def create_task(self, fields: dict) -> str:
        return self._create("tasks", fields)

    def list_tasks(self) -> list[FakeRecord]:
        return self._records("tasks")

    def update_task_status(self, record_id: str, new_status: str) -> bool:
        self.store["tasks"][record_id]["状态"] = new_status
        return True

    def get_task(self, record_id: str) -> FakeRecord:
        return FakeRecord(record_id=record_id, fields=self.store["tasks"][record_id])

    def create_content(self, fields: dict) -> str:
        return self._create("contents", fields)

    def list_contents(self) -> list[FakeRecord]:
        return self._records("contents")

    def get_content(self, record_id: str) -> FakeRecord:
        return FakeRecord(record_id=record_id, fields=self.store["contents"][record_id])

    def update_content_status(self, record_id: str, new_status: str) -> bool:
        self.store["contents"][record_id]["状态"] = new_status
        return True

    def create_review_task(self, fields: dict) -> str:
        return self._create("reviews", fields)

    def list_pending_reviews(self) -> list[FakeRecord]:
        return self._records("reviews")

    def update_review_status(self, record_id: str, status: str, opinion: str = "") -> bool:
        self.store["reviews"][record_id]["审核状态"] = status
        if opinion:
            self.store["reviews"][record_id]["审核意见"] = opinion
        return True

    def log_operation(self, operator: str, op_type: str, record_id: str, detail: str) -> str:
        return self._create("logs", {
            "操作者": operator,
            "操作类型": op_type,
            "关联记录ID": record_id,
            "变更内容": detail,
        })


class FakeLLM:
    def chat_with_system(self, system_prompt: str, user_message: str,
                         temperature: float = 0.7, max_tokens: int = 4096) -> str:
        if "Decision: [APPROVE / REJECT]" in system_prompt:
            return "Decision: APPROVE\nOpinion: 内容质量达标，可以发布。\nReason: ok"
        if "Generate an operational report" in user_message:
            return "运营报告：流程完成。"
        return "这是一篇由测试替身生成的文章正文。"


class WorkflowTests(unittest.TestCase):
    def test_reviewer_parses_reject_decision(self):
        store = {"tasks": {}, "contents": {}, "reviews": {}, "logs": {}}
        api = FakeBaseApi(store)
        review_id = api.create_review_task({"审核状态": "待审核"})

        class RejectLLM(FakeLLM):
            def chat_with_system(self, *args, **kwargs):
                return "Decision: REJECT\nOpinion: 内容证据不足。\nReason: weak sourcing"

        reviewer = ReviewerAgent(api, RejectLLM())
        with redirect_stdout(StringIO()):
            decision, opinion = reviewer.review(review_id, "article", "title")

        self.assertEqual(decision, "驳回")
        self.assertEqual(opinion, "内容证据不足。")
        self.assertEqual(store["reviews"][review_id]["审核状态"], "驳回")

    def test_full_chain_with_fake_clients(self):
        store = {"tasks": {}, "contents": {}, "reviews": {}, "logs": {}}
        manager_api = FakeBaseApi(store)
        editor_api = FakeBaseApi(store)
        reviewer_api = FakeBaseApi(store)

        engine = WorkflowEngine(manager_api, editor_api, reviewer_api, FakeLLM())
        with redirect_stdout(StringIO()):
            result = engine.run_full_chain(
                topic_title="测试选题",
                content_title="测试文章",
                summary="测试摘要",
                category="测试分类",
                word_count=100,
            )

        self.assertEqual(result["status"], "完成")
        self.assertEqual(result["review_result"], "通过")
        self.assertEqual(result["report"], "运营报告：流程完成。")
        self.assertEqual(store["tasks"][result["task_id"]]["状态"], "已归档")
        self.assertEqual(store["reviews"][result["review_id"]]["审核状态"], "通过")
        self.assertIn(result["content_id"], store["contents"])
        self.assertGreaterEqual(len(store["logs"]), 6)


if __name__ == "__main__":
    unittest.main()
