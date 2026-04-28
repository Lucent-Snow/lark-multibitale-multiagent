import unittest
import json
from types import SimpleNamespace

from src.agent_team.contracts import TASK_COMPLETED, TASK_IN_PROGRESS, TASK_PENDING, TaskSpec
from src.agent_team.base_store import BaseAgentTeamStore
from src.agent_team.demo import _all_planned_tasks_completed, run_agent_team_demo
from src.agent_team.engine import AgentTeamEngine, AgentTeamLeader
from src.agent_team.memory_store import InMemoryAgentTeamStore


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def chat_with_system(self, *args, **kwargs):
        return self.response


class FakeTableIds:
    tasks = "tbl_tasks"
    artifacts = "tbl_artifacts"
    messages = "tbl_messages"

    def require_agent_team(self):
        return None


class FakeBaseClient:
    def __init__(self):
        self.table_ids = FakeTableIds()
        self.records = []
        self._records_by_id = {}

    def create_record(self, table_id, fields):
        record_id = f"rec{len(self.records) + 1}"
        self.records.append((table_id, fields))
        self._records_by_id[record_id] = (table_id, dict(fields))
        return record_id

    def list_records(self, table_id):
        return [
            SimpleNamespace(record_id=record_id, fields=fields)
            for record_id, (record_table_id, fields) in self._records_by_id.items()
            if record_table_id == table_id
        ]

    def get_record(self, table_id, record_id):
        record_table_id, fields = self._records_by_id[record_id]
        if record_table_id != table_id:
            raise KeyError(record_id)
        return SimpleNamespace(record_id=record_id, fields=fields)

    def update_record(self, table_id, record_id, fields):
        record_table_id, existing_fields = self._records_by_id[record_id]
        if record_table_id != table_id:
            raise KeyError(record_id)
        existing_fields.update(fields)
        return True


class AgentTeamTests(unittest.TestCase):
    def test_leader_parses_json_plan(self):
        llm = FakeLLM("""[
          {
            "subject": "Research market",
            "description": "Find audience and constraints.",
            "role": "researcher",
            "blocked_by": [],
            "metadata": {"priority": "high"}
          }
        ]""")
        leader = AgentTeamLeader(llm)

        specs = leader.plan_objective("Launch", "Plan launch content")

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].subject, "Research market")
        self.assertEqual(specs[0].role, "researcher")
        self.assertEqual(specs[0].metadata["priority"], "high")

    def test_leader_falls_back_on_invalid_json(self):
        leader = AgentTeamLeader(FakeLLM("not json"))

        specs = leader.plan_objective("目标", "说明")

        self.assertGreaterEqual(len(specs), 3)
        self.assertEqual(specs[0].role, "researcher")
        self.assertIn("目标", specs[0].description)

    def test_leader_drops_unknown_dependencies(self):
        llm = FakeLLM("""[
          {
            "subject": "Research market",
            "description": "Find audience and constraints.",
            "role": "researcher",
            "blocked_by": ["Missing task"],
            "metadata": {}
          },
          {
            "subject": "Draft plan",
            "description": "Draft from research.",
            "role": "editor",
            "blocked_by": ["Research market"],
            "metadata": {}
          }
        ]""")
        leader = AgentTeamLeader(llm)

        specs = leader.plan_objective("Launch", "Plan launch content")

        self.assertEqual(specs[0].blocked_by, [])
        self.assertEqual(specs[1].blocked_by, ["Research market"])

    def test_leader_preserves_forward_dependencies(self):
        llm = FakeLLM("""[
          {
            "subject": "Draft plan",
            "description": "Draft from research.",
            "role": "editor",
            "blocked_by": ["Research market"],
            "metadata": {}
          },
          {
            "subject": "Research market",
            "description": "Find audience and constraints.",
            "role": "researcher",
            "blocked_by": [],
            "metadata": {}
          }
        ]""")
        leader = AgentTeamLeader(llm)
        specs = leader.plan_objective("Launch", "Plan launch content")
        store = InMemoryAgentTeamStore()
        for spec in specs:
            store.create_task(spec)
        engine = AgentTeamEngine(store, leader)

        editor_task = engine.claim_next_task("editor-1", "editor")

        self.assertEqual(specs[0].blocked_by, ["Research market"])
        self.assertIsNone(editor_task)

    def test_base_store_scalar_normalizes_text_segments(self):
        value = [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}]

        result = BaseAgentTeamStore._scalar(value)

        self.assertEqual(result, "hello world")

    def test_base_store_scope_overrides_llm_metadata(self):
        base = FakeBaseClient()
        store = BaseAgentTeamStore(base, task_scope={"objective_id": "new-objective"})

        store.create_task(TaskSpec(
            subject="Scoped task",
            description="Do work",
            role="manager",
            metadata={"objective_id": "old-objective", "priority": "high"},
        ))

        metadata = json.loads(base.records[0][1]["元数据"])
        self.assertEqual(metadata["objective_id"], "new-objective")
        self.assertEqual(metadata["priority"], "high")

    def test_base_store_rejects_update_outside_scope(self):
        base = FakeBaseClient()
        store = BaseAgentTeamStore(base, task_scope={"objective_id": "objA"})
        out_of_scope_task_id = base.create_record("tbl_tasks", {
            "任务标题": "Other task",
            "任务说明": "Outside current objective",
            "角色": "manager",
            "状态": TASK_PENDING,
            "负责人": "",
            "阻塞依赖": "[]",
            "元数据": json.dumps({"objective_id": "objB"}),
        })

        with self.assertRaises(ValueError):
            store.update_task(out_of_scope_task_id, {"status": TASK_COMPLETED})

        record = base.get_record("tbl_tasks", out_of_scope_task_id)
        self.assertEqual(record.fields["状态"], TASK_PENDING)

    def test_base_store_rejects_artifact_outside_scope(self):
        base = FakeBaseClient()
        store = BaseAgentTeamStore(base, task_scope={"objective_id": "objA"})
        out_of_scope_task_id = base.create_record("tbl_tasks", {
            "任务标题": "Other task",
            "任务说明": "Outside current objective",
            "角色": "manager",
            "状态": TASK_PENDING,
            "负责人": "",
            "阻塞依赖": "[]",
            "元数据": json.dumps({"objective_id": "objB"}),
        })

        with self.assertRaises(ValueError):
            store.create_artifact(
                out_of_scope_task_id,
                "Output",
                "Content",
                "manager-1",
            )

        artifact_records = [
            table_id for table_id, _fields in base.records
            if table_id == "tbl_artifacts"
        ]
        self.assertEqual(artifact_records, [])

    def test_base_store_rejects_message_outside_scope(self):
        base = FakeBaseClient()
        store = BaseAgentTeamStore(base, task_scope={"objective_id": "objA"})
        out_of_scope_task_id = base.create_record("tbl_tasks", {
            "任务标题": "Other task",
            "任务说明": "Outside current objective",
            "角色": "manager",
            "状态": TASK_PENDING,
            "负责人": "",
            "阻塞依赖": "[]",
            "元数据": json.dumps({"objective_id": "objB"}),
        })

        with self.assertRaises(ValueError):
            store.create_message(
                "manager-1",
                "team-lead",
                "Done",
                "Task completed",
                task_id=out_of_scope_task_id,
            )

        message_records = [
            table_id for table_id, _fields in base.records
            if table_id == "tbl_messages"
        ]
        self.assertEqual(message_records, [])

    def test_base_store_scope_overrides_metadata_updates(self):
        base = FakeBaseClient()
        store = BaseAgentTeamStore(base, task_scope={"objective_id": "objA"})
        task = store.create_task(TaskSpec(
            subject="Scoped task",
            description="Do work",
            role="manager",
        ))

        updated = store.update_task(task.task_id, {
            "metadata": {"objective_id": "objB", "note": "keep me"},
        })

        self.assertEqual(updated.metadata["objective_id"], "objA")
        self.assertEqual(updated.metadata["note"], "keep me")

    def test_planned_task_completion_requires_readback_records(self):
        planned_task_ids = {"rec1"}

        result = _all_planned_tasks_completed([], planned_task_ids)

        self.assertFalse(result)

    def test_planned_task_completion_requires_all_statuses_completed(self):
        readback_tasks = [
            SimpleNamespace(record_id="rec1", fields={"状态": TASK_COMPLETED}),
            SimpleNamespace(record_id="rec2", fields={"状态": TASK_IN_PROGRESS}),
        ]

        result = _all_planned_tasks_completed(readback_tasks, {"rec1", "rec2"})

        self.assertFalse(result)

    def test_start_objective_creates_task_market(self):
        store = InMemoryAgentTeamStore()
        engine = AgentTeamEngine(store, AgentTeamLeader(None))

        result = engine.start_objective("目标", "说明", max_tasks=3)

        self.assertEqual(result["task_count"], 3)
        self.assertEqual(len(store.tasks), 3)
        self.assertEqual(store.tasks[0].status, TASK_PENDING)
        self.assertEqual(store.logs[0]["op_type"], "plan")

    def test_claim_next_task_respects_role_and_dependencies(self):
        store = InMemoryAgentTeamStore()
        store.create_task(TaskSpec(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        store.create_task(TaskSpec(
            subject="Draft",
            description="Draft",
            role="editor",
            blocked_by=["Research"],
        ))
        engine = AgentTeamEngine(store, AgentTeamLeader(None))

        blocked_editor_task = engine.claim_next_task("editor-1", "editor")
        researcher_task = engine.claim_next_task("researcher-1", "researcher")

        self.assertIsNone(blocked_editor_task)
        self.assertIsNotNone(researcher_task)
        self.assertEqual(researcher_task.status, TASK_IN_PROGRESS)
        self.assertEqual(researcher_task.owner, "researcher-1")

    def test_complete_task_writes_artifact_message_and_log(self):
        store = InMemoryAgentTeamStore()
        task = store.create_task(TaskSpec(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        engine = AgentTeamEngine(store, AgentTeamLeader(None))

        result = engine.complete_task(
            agent_name="researcher-1",
            task_id=task.task_id,
            artifact_title="Research output",
            artifact_content="Findings",
        )

        self.assertEqual(result["task"].status, TASK_COMPLETED)
        self.assertIn(result["artifact_id"], store.artifacts)
        self.assertIn(result["message_id"], store.messages)
        self.assertEqual(store.messages[result["message_id"]]["recipient"], "team-lead")
        self.assertEqual(store.logs[-1]["op_type"], "complete")

    def test_offline_demo_completes_planned_task_chain(self):
        result = run_agent_team_demo("目标", "说明", max_tasks=4)

        self.assertTrue(result["all_tasks_completed"])
        self.assertEqual(len(result["tasks"]), 4)
        self.assertEqual(len(result["artifacts"]), 4)
        self.assertEqual(len(result["messages"]), 4)
        self.assertTrue(all(task.status == TASK_COMPLETED for task in result["tasks"]))

    def test_offline_demo_does_not_complete_empty_task_set(self):
        result = run_agent_team_demo("目标", "说明", max_tasks=0)

        self.assertFalse(result["all_tasks_completed"])
        self.assertEqual(result["tasks"], [])


if __name__ == "__main__":
    unittest.main()
