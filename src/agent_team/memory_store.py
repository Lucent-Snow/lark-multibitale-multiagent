"""In-memory agent-team store for offline demos and tests."""

from dataclasses import replace

from src.agent_team.contracts import AgentTeamTask, AgentTeamStore, TaskSpec


class InMemoryAgentTeamStore(AgentTeamStore):
    """Volatile store implementing the same boundary as the Base-backed store."""

    def __init__(self):
        self.tasks: list[AgentTeamTask] = []
        self.artifacts: dict[str, dict] = {}
        self.messages: dict[str, dict] = {}
        self.logs: list[dict] = []

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
