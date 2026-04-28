import unittest

from src.agent_team.contracts import TASK_COMPLETED, TASK_IN_PROGRESS, TASK_PENDING, TaskSpec
from src.agent_team.demo import run_agent_team_demo
from src.agent_team.engine import AgentTeamEngine, AgentTeamLeader
from src.agent_team.memory_store import InMemoryAgentTeamStore


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def chat_with_system(self, *args, **kwargs):
        return self.response


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


if __name__ == "__main__":
    unittest.main()
