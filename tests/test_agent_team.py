import unittest
from dataclasses import replace

from src.agent_team.contracts import (
    AgentTeamTask,
    TASK_COMPLETED,
    TASK_IN_PROGRESS,
    TASK_PENDING,
    TaskSpec,
)
from src.agent_team.engine import AgentTeamEngine, AgentTeamLeader


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def chat_with_system(self, *args, **kwargs):
        return self.response


class FakeAgentTeamStore:
    def __init__(self):
        self.tasks = []
        self.artifacts = {}
        self.messages = {}
        self.logs = []

    def create_task(self, spec: TaskSpec) -> AgentTeamTask:
        task = AgentTeamTask(
            task_id=f"task-{len(self.tasks) + 1}",
            subject=spec.subject,
            description=spec.description,
            role=spec.role,
            blocked_by=spec.blocked_by,
            metadata=spec.metadata,
        )
        self.tasks.append(task)
        return task

    def list_tasks(self) -> list[AgentTeamTask]:
        return list(self.tasks)

    def update_task(self, task_id: str, fields: dict) -> AgentTeamTask:
        for index, task in enumerate(self.tasks):
            if task.task_id != task_id:
                continue
            updated = replace(
                task,
                status=fields.get("status", task.status),
                owner=fields.get("owner", task.owner),
                metadata=fields.get("metadata", task.metadata),
            )
            self.tasks[index] = updated
            return updated
        raise KeyError(task_id)

    def create_artifact(self, task_id: str, title: str, content: str,
                        author: str) -> str:
        artifact_id = f"artifact-{len(self.artifacts) + 1}"
        self.artifacts[artifact_id] = {
            "task_id": task_id,
            "title": title,
            "content": content,
            "author": author,
        }
        return artifact_id

    def create_message(self, sender: str, recipient: str, summary: str,
                       message: str, task_id: str = "") -> str:
        message_id = f"message-{len(self.messages) + 1}"
        self.messages[message_id] = {
            "sender": sender,
            "recipient": recipient,
            "summary": summary,
            "message": message,
            "task_id": task_id,
        }
        return message_id

    def log_operation(self, operator: str, op_type: str, target_id: str,
                      detail: str) -> str:
        log_id = f"log-{len(self.logs) + 1}"
        self.logs.append({
            "log_id": log_id,
            "operator": operator,
            "op_type": op_type,
            "target_id": target_id,
            "detail": detail,
        })
        return log_id


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
        store = FakeAgentTeamStore()
        engine = AgentTeamEngine(store, AgentTeamLeader(None))

        result = engine.start_objective("目标", "说明", max_tasks=3)

        self.assertEqual(result["task_count"], 3)
        self.assertEqual(len(store.tasks), 3)
        self.assertEqual(store.tasks[0].status, TASK_PENDING)
        self.assertEqual(store.logs[0]["op_type"], "plan")

    def test_claim_next_task_respects_role_and_dependencies(self):
        store = FakeAgentTeamStore()
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
        store = FakeAgentTeamStore()
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


if __name__ == "__main__":
    unittest.main()
