import os
import tempfile
import unittest
from unittest.mock import patch

from src.base_client.client import BaseTableIds
from src.main import _load_demo, _load_table_ids


class ConfigTests(unittest.TestCase):
    def test_table_ids_from_config(self):
        table_ids = BaseTableIds.from_config({
            "tasks": "tbl_tasks",
            "contents": "tbl_contents",
            "reviews": "tbl_reviews",
            "logs": "tbl_logs",
            "objectives": "tbl_objectives",
            "members": "tbl_members",
            "messages": "tbl_messages",
            "artifacts": "tbl_artifacts",
            "verifications": "tbl_verifications",
            "v2_objectives": "tbl_v2_objectives",
            "v2_workers": "tbl_v2_workers",
            "v2_tasks": "tbl_v2_tasks",
            "v2_task_edges": "tbl_v2_task_edges",
            "v2_claims": "tbl_v2_claims",
            "v2_messages": "tbl_v2_messages",
            "v2_artifacts": "tbl_v2_artifacts",
            "v2_verifications": "tbl_v2_verifications",
            "v2_events": "tbl_v2_events",
        })

        self.assertEqual(table_ids.tasks, "tbl_tasks")
        self.assertEqual(table_ids.contents, "tbl_contents")
        self.assertEqual(table_ids.reviews, "tbl_reviews")
        self.assertEqual(table_ids.logs, "tbl_logs")
        self.assertEqual(table_ids.objectives, "tbl_objectives")
        self.assertEqual(table_ids.messages, "tbl_messages")
        self.assertEqual(table_ids.v2_tasks, "tbl_v2_tasks")
        self.assertEqual(table_ids.v2_events, "tbl_v2_events")

    def test_agent_team_tables_are_optional_but_validated_when_used(self):
        table_ids = BaseTableIds.from_config({
            "tasks": "tbl_tasks",
            "contents": "tbl_contents",
            "reviews": "tbl_reviews",
            "logs": "tbl_logs",
        })

        with self.assertRaisesRegex(ValueError, "agent-team mode"):
            table_ids.require_agent_team()

    def test_table_ids_require_all_tables(self):
        with self.assertRaisesRegex(ValueError, "Missing lark.tables config"):
            BaseTableIds.from_config({
                "tasks": "tbl_tasks",
                "contents": "tbl_contents",
            })

    def test_agent_team_v2_tables_are_optional_but_validated_when_used(self):
        table_ids = BaseTableIds.from_config({
            "tasks": "tbl_tasks",
            "contents": "tbl_contents",
            "reviews": "tbl_reviews",
            "logs": "tbl_logs",
        })

        with self.assertRaisesRegex(ValueError, "agent-team v2 mode"):
            table_ids.require_agent_team_v2()

    def test_load_table_ids_from_main_config(self):
        table_ids = _load_table_ids({
            "lark": {
                "tables": {
                    "tasks": "tbl_tasks",
                    "contents": "tbl_contents",
                    "reviews": "tbl_reviews",
                    "logs": "tbl_logs",
                }
            }
        })

        self.assertEqual(table_ids.tasks, "tbl_tasks")
        self.assertEqual(table_ids.logs, "tbl_logs")

    def test_load_demo_reads_yaml(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False) as tmp:
            tmp.write(
                "topic:\n"
                "  title: Test topic\n"
                "content:\n"
                "  title: Test article\n"
                "  summary: Test summary\n"
                "  category: Test category\n"
                "  word_count: 123\n"
            )
            tmp_path = tmp.name

        try:
            with patch("src.main.DEMO_PATH", tmp_path):
                demo = _load_demo()
        finally:
            os.unlink(tmp_path)

        self.assertEqual(demo["topic_title"], "Test topic")
        self.assertEqual(demo["content_title"], "Test article")
        self.assertEqual(demo["summary"], "Test summary")
        self.assertEqual(demo["category"], "Test category")
        self.assertEqual(demo["word_count"], 123)


if __name__ == "__main__":
    unittest.main()
