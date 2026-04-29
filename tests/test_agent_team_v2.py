import unittest
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from contextlib import redirect_stdout
from unittest.mock import patch

from src.agent_team_v2.contracts import (
    CLAIM_ACTIVE,
    CLAIM_EXPIRED,
    TASK_CLAIMED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_PENDING,
    VERIFICATION_FAIL,
    VERIFICATION_PASS,
    TaskPlan,
)
from src.agent_team_v2.base_store import BaseAgentTeamV2Store
from src.agent_team_v2.demo import (
    V2_WORKERS,
    _parse_verification_response,
    _progress_summary,
    create_agent_team_v2_tables,
    run_agent_team_v2_memory_demo,
    run_agent_team_v2_base_demo,
    select_agent_team_v2_workers,
)
from src.agent_team_v2.engine import AgentTeamV2Engine, LeaderV2, WorkerV2
from src.agent_team_v2.memory_store import InMemoryAgentTeamV2Store


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def chat_with_system(self, *args, **kwargs):
        return self.response


class FakeProcess:
    instances = []

    def __init__(self, args):
        self.args = args
        self.terminated = False
        self.killed = False
        self.waited = False
        self.returncode = None
        self.__class__.instances.append(self)

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        self.waited = True
        self.returncode = 0
        return self.returncode


class FakeBaseClientForSetup:
    def __init__(self):
        self.created = []

    def create_table(self, name, fields):
        table_id = f"tbl_{name}"
        self.created.append((name, fields))
        return table_id


class FakeV2TableIds:
    v2_objectives = "tbl_objectives"
    v2_workers = "tbl_workers"
    v2_tasks = "tbl_tasks"
    v2_task_edges = "tbl_edges"
    v2_claims = "tbl_claims"
    v2_messages = "tbl_messages"
    v2_artifacts = "tbl_artifacts"
    v2_verifications = "tbl_verifications"
    v2_events = "tbl_events"

    def require_agent_team_v2(self):
        return None


class FakeV2BaseClient:
    def __init__(self):
        self.table_ids = FakeV2TableIds()
        self._records = {}
        self._counter = 0

    def create_record(self, table_id, fields):
        self._counter += 1
        record_id = f"rec{self._counter}"
        self._records[record_id] = (table_id, dict(fields))
        return record_id

    def update_record(self, table_id, record_id, fields):
        record_table_id, existing = self._records[record_id]
        if record_table_id != table_id:
            raise KeyError(record_id)
        existing.update(fields)
        return True

    def get_record(self, table_id, record_id):
        record_table_id, fields = self._records[record_id]
        if record_table_id != table_id:
            raise KeyError(record_id)
        return SimpleNamespace(record_id=record_id, fields=dict(fields))

    def list_records(self, table_id):
        return [
            SimpleNamespace(record_id=record_id, fields=dict(fields))
            for record_id, (record_table_id, fields) in self._records.items()
            if record_table_id == table_id
        ]


class AgentTeamV2Tests(unittest.TestCase):
    def test_leader_preserves_forward_dependencies_and_drops_unknown(self):
        llm = FakeLLM("""[
          {
            "subject": "Draft plan",
            "description": "Draft from research.",
            "role": "editor",
            "blocked_by_subjects": ["Research market", "Missing task"],
            "metadata": {}
          },
          {
            "subject": "Research market",
            "description": "Find audience and constraints.",
            "role": "researcher",
            "blocked_by_subjects": [],
            "metadata": {}
          }
        ]""")

        plans = LeaderV2(llm).plan("Launch", "Plan launch content")

        self.assertEqual(plans[0].blocked_by_subjects, ["Research market"])
        self.assertIn("Shared objective context", plans[0].description)
        self.assertIn("Launch", plans[0].description)
        self.assertIn("Plan launch content", plans[0].description)

    def test_leader_falls_back_on_duplicate_subjects(self):
        llm = FakeLLM("""[
          {"subject": "A", "description": "d1", "role": "researcher", "blocked_by_subjects": [], "metadata": {}},
          {"subject": "A", "description": "d2", "role": "editor", "blocked_by_subjects": [], "metadata": {}}
        ]""")

        plans = LeaderV2(llm).plan("Launch", "Plan launch content")

        self.assertEqual([plan.subject for plan in plans], [
            "Research objective context",
            "Draft primary deliverable",
            "Analyze completion evidence",
            "Verify final quality",
        ])

    def test_fallback_plan_keeps_all_tasks_self_contained(self):
        plans = LeaderV2(None).plan("OBJ", "DESC", max_tasks=4)

        self.assertEqual(len(plans), 4)
        for plan in plans:
            self.assertIn("OBJ", plan.description)
            self.assertIn("DESC", plan.description)

    def test_start_objective_creates_task_id_edges(self):
        store = InMemoryAgentTeamV2Store()
        engine = AgentTeamV2Engine(store, LeaderV2(None))

        result = engine.start_objective("目标", "说明", max_tasks=2)

        edges = store.list_edges(result["objective_id"])
        self.assertEqual(len(edges), 1)
        tasks = {task.subject: task for task in result["tasks"]}
        self.assertEqual(edges[0].from_task_id, tasks["Research objective context"].task_id)
        self.assertEqual(edges[0].to_task_id, tasks["Draft primary deliverable"].task_id)

    def test_worker_cannot_claim_blocked_task(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        blocker = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        draft = store.create_task(objective_id, TaskPlan(
            subject="Draft",
            description="Draft",
            role="editor",
        ))
        store.create_edge(objective_id, blocker.task_id, draft.task_id)

        task = WorkerV2(store, objective_id, "editor-1", "editor").claim_next_task()

        self.assertIsNone(task)

    def test_claim_expires_old_active_claim_when_task_unowned(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        old_claim = store.create_claim(objective_id, task.task_id, "researcher-0", "old")
        store.claims[old_claim.claim_id] = type(old_claim)(
            claim_id=old_claim.claim_id,
            objective_id=old_claim.objective_id,
            task_id=old_claim.task_id,
            worker_id=old_claim.worker_id,
            status=old_claim.status,
            nonce=old_claim.nonce,
            created_at="2000-01-01T00:00:00+00:00",
        )

        claimed = WorkerV2(store, objective_id, "researcher-1", "researcher").claim_next_task()

        self.assertIsNotNone(claimed)
        claims = store.list_claims(objective_id, task.task_id)
        statuses = {claim.worker_id: claim.status for claim in claims}
        self.assertEqual(statuses["researcher-0"], CLAIM_EXPIRED)
        self.assertEqual(statuses["researcher-1"], "won")

    def test_expired_claimed_task_is_recovered_and_reclaimed(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        old_claim = store.create_claim(objective_id, task.task_id, "researcher-0", "old")
        store.update_claim(objective_id, old_claim.claim_id, "won")
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        store.update_task(objective_id, task.task_id, {
            "status": TASK_CLAIMED,
            "owner": "researcher-0",
            "lease_until": expired,
        })

        claimed = WorkerV2(store, objective_id, "researcher-1", "researcher").claim_next_task()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.owner, "researcher-1")
        self.assertEqual(claimed.status, TASK_CLAIMED)
        statuses = {claim.worker_id: claim.status for claim in store.list_claims(objective_id, task.task_id)}
        self.assertEqual(statuses["researcher-0"], CLAIM_EXPIRED)

    def test_worker_failure_returns_task_to_pending_for_retry(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))

        def fail(_task):
            raise RuntimeError("boom")

        with self.assertRaisesRegex(RuntimeError, "boom"):
            WorkerV2(
                store, objective_id, "researcher-1", "researcher", artifact_fn=fail
            ).run_once()

        recovered = store.get_task(objective_id, task.task_id)
        self.assertEqual(recovered.status, TASK_PENDING)
        self.assertEqual(recovered.owner, "")
        self.assertEqual(len(store.messages), 1)
        self.assertTrue(any(
            event["event_type"] == "task_execution_failed"
            for event in store.events.values()
        ))

        retried = WorkerV2(store, objective_id, "researcher-2", "researcher").claim_next_task()

        self.assertIsNotNone(retried)
        self.assertEqual(retried.owner, "researcher-2")

    def test_fresh_active_claim_blocks_younger_claim(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        store.create_claim(objective_id, task.task_id, "researcher-0", "old")

        claimed = WorkerV2(store, objective_id, "researcher-1", "researcher").claim_next_task()

        self.assertIsNone(claimed)
        statuses = {claim.worker_id: claim.status for claim in store.list_claims(objective_id, task.task_id)}
        self.assertEqual(statuses["researcher-0"], CLAIM_ACTIVE)
        self.assertEqual(statuses["researcher-1"], "lost")

    def test_worker_completion_writes_artifact_message_and_verification(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))

        result = WorkerV2(store, objective_id, "researcher-1", "researcher").run_once()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(store.get_task(objective_id, task.task_id).status, TASK_COMPLETED)
        self.assertEqual(len(store.artifacts), 1)
        self.assertEqual(len(store.messages), 1)
        self.assertEqual(len(store.verifications), 1)

    def test_worker_failed_verification_marks_task_failed(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))

        result = WorkerV2(
            store,
            objective_id,
            "researcher-1",
            "researcher",
            artifact_fn=lambda _task: "unsupported claims",
            verification_fn=lambda _task, _artifact: {
                "verdict": VERIFICATION_FAIL,
                "issues": "Unsupported statistics.",
                "suggestions": "Ground the artifact in evidence.",
            },
        ).run_once()

        self.assertEqual(result["status"], "failed")
        self.assertEqual(store.get_task(objective_id, task.task_id).status, TASK_FAILED)
        self.assertEqual(len(store.artifacts), 1)
        self.assertEqual(len(store.verifications), 1)
        self.assertFalse(
            AgentTeamV2Engine(store, LeaderV2(None)).complete_objective_if_ready(objective_id)
        )

    def test_worker_receives_direct_dependency_artifacts(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        research = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        draft = store.create_task(objective_id, TaskPlan(
            subject="Draft",
            description="Draft",
            role="editor",
        ))
        store.create_edge(objective_id, research.task_id, draft.task_id)
        store.update_task(objective_id, research.task_id, {"status": TASK_COMPLETED})
        store.create_artifact(
            objective_id, research.task_id, "researcher-1", "Research output",
            "Upstream evidence A",
        )
        seen = {}

        def capture(task):
            seen["description"] = task.description
            return "Draft grounded in upstream evidence."

        WorkerV2(store, objective_id, "editor-1", "editor", artifact_fn=capture).run_once()

        self.assertIn("Dependency artifacts available", seen["description"])
        self.assertIn("Upstream evidence A", seen["description"])

    def test_objective_requires_verification_before_completion(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        store.update_task(objective_id, task.task_id, {"status": TASK_COMPLETED})
        engine = AgentTeamV2Engine(store, LeaderV2(None))

        self.assertFalse(engine.complete_objective_if_ready(objective_id))

        store.create_verification(
            objective_id, task.task_id, "reviewer-1", VERIFICATION_PASS
        )
        self.assertTrue(engine.complete_objective_if_ready(objective_id))

    def test_objective_completion_normalizes_base_list_values(self):
        class Store:
            def __init__(self):
                self.updated = False

            def list_tasks(self, _objective_id):
                return [SimpleNamespace(task_id="task-1", status=TASK_COMPLETED)]

            def list_verifications(self, _objective_id):
                return [{"task_id": ["task-1"], "verdict": ["PASS"]}]

            def update_objective(self, *_args, **_kwargs):
                self.updated = True

            def log_event(self, *_args, **_kwargs):
                return "event-1"

        store = Store()

        result = AgentTeamV2Engine(store, LeaderV2(None)).complete_objective_if_ready("obj")

        self.assertTrue(result)
        self.assertTrue(store.updated)

    def test_scope_outside_task_cannot_write_artifact_or_message(self):
        store = InMemoryAgentTeamV2Store()
        objective_a = store.create_objective("A", "A")
        objective_b = store.create_objective("B", "B")
        task = store.create_task(objective_b, TaskPlan(
            subject="Other",
            description="Other",
            role="manager",
        ))

        with self.assertRaises(ValueError):
            store.create_artifact(objective_a, task.task_id, "manager-1", "Out", "Text")
        with self.assertRaises(ValueError):
            store.create_message(objective_a, "manager-1", "team-lead", "Out", "Text", task.task_id)

    def test_memory_demo_completes_protocol(self):
        result = run_agent_team_v2_memory_demo("目标", "说明", max_tasks=4)

        self.assertTrue(result["all_tasks_completed"])
        self.assertTrue(result["objective_completed"])
        self.assertEqual(len(result["tasks"]), 4)
        self.assertEqual(len(result["artifacts"]), 4)
        self.assertEqual(len(result["messages"]), 4)
        self.assertEqual(len(result["verifications"]), 4)

    def test_worker_loop_can_complete_two_same_role_tasks(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        store.create_task(objective_id, TaskPlan(
            subject="Research one",
            description="Research one",
            role="researcher",
        ))
        store.create_task(objective_id, TaskPlan(
            subject="Research two",
            description="Research two",
            role="researcher",
        ))
        worker = WorkerV2(store, objective_id, "researcher-1", "researcher")

        first = worker.run_once()
        second = worker.run_once()

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "completed")
        self.assertTrue(all(task.status == TASK_COMPLETED for task in store.list_tasks(objective_id)))

    def test_setup_creates_all_v2_tables(self):
        base = FakeBaseClientForSetup()

        created = create_agent_team_v2_tables(base)

        self.assertIn("v2_tasks", created)
        self.assertIn("v2_events", created)
        self.assertEqual(len(created), 9)
        self.assertTrue(any(name == "v2_claims" for name, _fields in base.created))

    def test_manager_worker_can_claim_any_role_task(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))

        task = WorkerV2(store, objective_id, "manager-1", "manager").claim_next_task()

        self.assertIsNotNone(task)
        self.assertEqual(task.owner, "manager-1")

    def test_non_matching_worker_cannot_claim_role_task(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))

        task = WorkerV2(store, objective_id, "editor-1", "editor").claim_next_task()

        self.assertIsNone(task)
        self.assertEqual(store.list_tasks(objective_id)[0].status, TASK_PENDING)

    def test_base_store_round_trips_task_artifact_message_and_verification(self):
        base = FakeV2BaseClient()
        store = BaseAgentTeamV2Store(base)
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
            metadata={"priority": "high"},
        ))

        updated = store.update_task(objective_id, task.task_id, {
            "status": TASK_COMPLETED,
            "owner": "researcher-1",
        })
        artifact_id = store.create_artifact(objective_id, task.task_id, "researcher-1", "Out", "Text")
        message_id = store.create_message(objective_id, "researcher-1", "team-lead", "Done", "Text", task.task_id)
        verification_id = store.create_verification(objective_id, task.task_id, "reviewer-1", VERIFICATION_PASS)

        self.assertEqual(updated.owner, "researcher-1")
        self.assertEqual(store.get_task(objective_id, task.task_id).metadata["priority"], "high")
        self.assertTrue(artifact_id)
        self.assertTrue(message_id)
        self.assertTrue(verification_id)
        self.assertEqual(len(store.list_verifications(objective_id)), 1)

    def test_base_store_worker_receives_direct_dependency_artifacts(self):
        base = FakeV2BaseClient()
        store = BaseAgentTeamV2Store(base)
        objective_id = store.create_objective("目标", "说明")
        research = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        draft = store.create_task(objective_id, TaskPlan(
            subject="Draft",
            description="Draft",
            role="editor",
        ))
        store.create_edge(objective_id, research.task_id, draft.task_id)
        store.update_task(objective_id, research.task_id, {"status": TASK_COMPLETED})
        store.create_artifact(
            objective_id, research.task_id, "researcher-1", "Research output",
            "Base upstream evidence",
        )
        seen = {}

        def capture(task):
            seen["description"] = task.description
            return "Draft grounded in Base upstream evidence."

        WorkerV2(store, objective_id, "editor-1", "editor", artifact_fn=capture).run_once()

        self.assertIn("Dependency artifacts available", seen["description"])
        self.assertIn("Base upstream evidence", seen["description"])

    def test_worker_roles_are_available_for_real_demo(self):
        roles = {role for _worker_id, role in V2_WORKERS}

        self.assertIn("researcher", roles)
        self.assertIn("reviewer", roles)

    def test_real_demo_worker_selection_keeps_manager_fallback(self):
        self.assertEqual(select_agent_team_v2_workers(1), [("manager-1", "manager")])

        roles = [role for _worker_id, role in select_agent_team_v2_workers(4)]

        self.assertIn("manager", roles)
        self.assertEqual(len(roles), 4)

    def test_base_demo_cleans_up_worker_processes_on_timeout(self):
        FakeProcess.instances = []
        base = FakeV2BaseClient()

        with patch("src.agent_team_v2.demo.subprocess.Popen", FakeProcess):
            with redirect_stdout(io.StringIO()):
                result = run_agent_team_v2_base_demo(
                    manager_api=base,
                    llm=FakeLLM("""[
                      {"subject": "Manage", "description": "Manage", "role": "manager", "blocked_by_subjects": [], "metadata": {}}
                    ]"""),
                    title="目标",
                    description="说明",
                    max_tasks=1,
                    workers=1,
                    timeout_seconds=0,
                )

        self.assertFalse(result["objective_completed"])
        self.assertEqual(len(FakeProcess.instances), 1)
        self.assertTrue(FakeProcess.instances[0].terminated)
        self.assertTrue(FakeProcess.instances[0].waited)

    def test_progress_summary_reports_control_plane_counts(self):
        store = InMemoryAgentTeamV2Store()
        objective_id = store.create_objective("目标", "说明")
        task = store.create_task(objective_id, TaskPlan(
            subject="Research",
            description="Research",
            role="researcher",
        ))
        store.create_artifact(objective_id, task.task_id, "researcher-1", "Out", "Text")
        store.create_verification(objective_id, task.task_id, "reviewer-1", VERIFICATION_PASS)

        summary = _progress_summary(store, objective_id)

        self.assertIn("pending=1", summary)
        self.assertIn("artifacts=1", summary)
        self.assertIn("verifications=1", summary)

    def test_parse_verification_response_is_strict(self):
        passed = _parse_verification_response(
            '{"verdict": "PASS", "issues": "", "suggestions": "ok"}'
        )
        failed = _parse_verification_response("not json")
        mixed = _parse_verification_response(
            'note before {"verdict": "PASS", "issues": "", "suggestions": ""} note after'
        )

        self.assertEqual(passed["verdict"], VERIFICATION_PASS)
        self.assertEqual(failed["verdict"], VERIFICATION_FAIL)
        self.assertEqual(mixed["verdict"], VERIFICATION_FAIL)
        self.assertIn("non-JSON", failed["issues"])


if __name__ == "__main__":
    unittest.main()
