import unittest

from src.agent_team.contracts import TASK_COMPLETED, TASK_PENDING, VERIFICATION_FAIL, VERIFICATION_PASS, TaskPlan
from src.agent_team.engine import AgentTeamEngine, Leader, PlanningError, Worker
from src.agent_team.memory_store import InMemoryObjectiveStore
from src.agent_team.demo import _parse_verification_response, run_agent_team_memory_demo


class FakeLLM:
    def __init__(self, response):
        self.response = response
    def chat_with_system(self, *args, **kwargs):
        return self.response


class AgentTeamTests(unittest.TestCase):
    def test_leader_parses_tasks_and_infers_workers(self):
        llm = FakeLLM("""[
          {"subject": "Draft plan", "description": "Draft from research.", "role": "editor",
           "blocked_by_subjects": ["Research market"], "metadata": {}},
          {"subject": "Research market", "description": "Find audience.", "role": "researcher",
           "blocked_by_subjects": [], "metadata": {}}
        ]""")
        workers, plans = Leader(llm).plan("Launch", "Plan launch")
        self.assertEqual(len(plans), 2)
        self.assertGreaterEqual(len(workers), 1)

    def test_leader_falls_back_on_duplicate_subjects(self):
        llm = FakeLLM("""[
          {"subject": "A", "description": "d1", "role": "researcher", "blocked_by_subjects": []},
          {"subject": "A", "description": "d2", "role": "editor", "blocked_by_subjects": []}
        ]""")
        _, plans = Leader(llm).plan("Launch", "Plan launch")
        # Duplicates detected → fallback triggered
        self.assertGreater(len(plans), 0)
        self.assertEqual(len(set(p.subject for p in plans)), len(plans))

    def test_leader_can_fail_closed(self):
        with self.assertRaises(PlanningError):
            Leader(FakeLLM("not json"), allow_fallback=False).plan("L", "D")

    def test_fallback_plan_self_contained(self):
        workers, plans = Leader(None).plan("OBJ", "DESC", max_tasks=4)
        self.assertEqual(len(workers), 3)
        self.assertEqual(len(plans), 4)
        # Fallback tasks should have non-empty subjects and descriptions
        for p in plans:
            self.assertTrue(p.subject)
            self.assertTrue(p.description)

    def test_start_objective_adds_tasks(self):
        store = InMemoryObjectiveStore()
        result = AgentTeamEngine(store, Leader(None)).start_objective("目标", "说明", max_tasks=3)
        tasks = store.list_tasks()
        self.assertEqual(len(tasks), 3)
        self.assertEqual(result["parallel_count"] + result["serial_count"], 3)

    def test_worker_cannot_claim_blocked_task(self):
        store = InMemoryObjectiveStore()
        store.create_objective("目标", "说明")
        blocker = store.add_task(TaskPlan(subject="Research", description="R", role="researcher"))
        store.add_task(TaskPlan(subject="Draft", description="D", role="editor",
                       blocked_by_subjects=["Research"]))
        task = Worker(store, "obj", "editor-1", "editor")._claim_next()
        self.assertIsNone(task)

    def test_worker_claims_and_completes(self):
        store = InMemoryObjectiveStore()
        store.create_objective("目标", "说明")
        store.add_task(TaskPlan(subject="Research", description="R", role="researcher"))
        w = Worker(store, "obj", "researcher-1", "researcher")
        r = w.run_once()
        self.assertEqual(r["status"], "completed")
        tasks = store.list_tasks()
        self.assertEqual(tasks[0].status, TASK_COMPLETED)
        self.assertTrue(tasks[0].artifact)

    def test_worker_retry_on_fail(self):
        store = InMemoryObjectiveStore()
        store.create_objective("目标", "说明")
        store.add_task(TaskPlan(subject="R", description="R", role="researcher"))
        def always_fail(task, art):
            return {"verdict": VERIFICATION_FAIL, "issues": "bad"}
        w = Worker(store, "obj", "researcher-1", "researcher", verification_fn=always_fail)
        r = w.run_once()
        self.assertEqual(r["status"], "retry")
        self.assertEqual(store.list_tasks()[0].status, TASK_PENDING)

    def test_memory_demo_completes(self):
        result = run_agent_team_memory_demo("Demo", "Description", max_tasks=3)
        self.assertTrue(result["objective_completed"] or result["all_tasks_completed"])

    def test_parse_verification_fails_blocking_gaps(self):
        r = _parse_verification_response('{"verdict": "PASS", "issues": "无法完成任务"}')
        self.assertEqual(r["verdict"], VERIFICATION_FAIL)

    def test_parse_verification_allows_legitimate(self):
        r = _parse_verification_response('{"verdict": "PASS", "issues": "Minor typos found"}')
        self.assertEqual(r["verdict"], VERIFICATION_PASS)


if __name__ == "__main__":
    unittest.main()
