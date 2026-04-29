"""
Feishu Base SDK client using bot credentials (app_access_token).

Each bot has its own app_id + app_secret.
Token is automatically managed via src.auth.app_auth.get_token().
"""

import re
import webbrowser
import warnings
from dataclasses import dataclass

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

from lark_oapi.api.bitable.v1 import *
from lark_oapi import Client


@dataclass(frozen=True)
class BaseTableIds:
    """Configured Feishu Base table IDs."""

    tasks: str
    contents: str
    reviews: str
    logs: str
    objectives: str | None = None
    members: str | None = None
    messages: str | None = None
    artifacts: str | None = None
    verifications: str | None = None
    v2_objectives: str | None = None
    v2_workers: str | None = None
    v2_tasks: str | None = None
    v2_task_edges: str | None = None
    v2_claims: str | None = None
    v2_messages: str | None = None
    v2_artifacts: str | None = None
    v2_verifications: str | None = None
    v2_events: str | None = None

    @classmethod
    def from_config(cls, config: dict) -> "BaseTableIds":
        """Build and validate table IDs from config."""
        required = {
            "tasks": "task table",
            "contents": "content table",
            "reviews": "review table",
            "logs": "operation log table",
        }
        missing = [key for key in required if not config.get(key)]
        if missing:
            names = ", ".join(f"{key} ({required[key]})" for key in missing)
            raise ValueError(f"Missing lark.tables config: {names}")
        return cls(
            tasks=config["tasks"],
            contents=config["contents"],
            reviews=config["reviews"],
            logs=config["logs"],
            objectives=config.get("objectives"),
            members=config.get("members"),
            messages=config.get("messages"),
            artifacts=config.get("artifacts"),
            verifications=config.get("verifications"),
            v2_objectives=config.get("v2_objectives"),
            v2_workers=config.get("v2_workers"),
            v2_tasks=config.get("v2_tasks"),
            v2_task_edges=config.get("v2_task_edges"),
            v2_claims=config.get("v2_claims"),
            v2_messages=config.get("v2_messages"),
            v2_artifacts=config.get("v2_artifacts"),
            v2_verifications=config.get("v2_verifications"),
            v2_events=config.get("v2_events"),
        )

    def require_agent_team(self) -> None:
        """Validate optional agent-team table IDs before using that feature."""
        required = {
            "objectives": self.objectives,
            "members": self.members,
            "messages": self.messages,
            "artifacts": self.artifacts,
            "verifications": self.verifications,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "Missing lark.tables config for agent-team mode: "
                + ", ".join(missing)
            )

    def require_agent_team_v2(self) -> None:
        """Validate optional agent-team v2 table IDs before using that feature."""
        required = {
            "v2_objectives": self.v2_objectives,
            "v2_workers": self.v2_workers,
            "v2_tasks": self.v2_tasks,
            "v2_task_edges": self.v2_task_edges,
            "v2_claims": self.v2_claims,
            "v2_messages": self.v2_messages,
            "v2_artifacts": self.v2_artifacts,
            "v2_verifications": self.v2_verifications,
            "v2_events": self.v2_events,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                "Missing lark.tables config for agent-team v2 mode: "
                + ", ".join(missing)
            )


def _handle_api_error(op_name: str, response):
    """Unpack Feishu API error, detect permission issues, offer browser auth."""
    code = getattr(response, "code", -1)
    msg = getattr(response, "msg", str(response))

    # Permission / scope error — extract the auth URL
    auth_url = None
    url_match = re.search(
        r"https://open\.feishu\.cn/app/[a-z0-9_]+/auth\?[^\s]+", msg
    )
    if url_match:
        auth_url = url_match.group()
        print(f"\n  [AUTH] Missing permissions for this bot.")
        print(f"  [AUTH] Opening browser for authorization...")
        print(f"  [AUTH] URL: {auth_url}")
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

    # Forbidden on a specific resource (table / base access)
    if code == 17910003 or "Forbidden" in str(msg):
        hint = (
            f"\n  [HINT] The bot can authenticate but cannot access this Base.\n"
            f"  [HINT] Open the Base in Feishu → Share → add this bot's app_id as Editor."
        )
        raise Exception(f"{op_name} failed: {msg}{hint}")

    raise Exception(f"{op_name} failed: {msg}")


class BaseClient:
    """Feishu Base client using bot authentication."""

    def __init__(self, bot_name: str, base_token: str, table_ids: BaseTableIds):
        from src.auth.app_auth import Credentials

        self.base_token = base_token
        self.table_ids = table_ids
        self._bot_name = bot_name

        creds = Credentials()
        bot = creds.get(bot_name)
        if not bot:
            raise ValueError(f"Bot '{bot_name}' not found in credentials")

        self._client = Client.builder() \
            .app_id(bot.app_id) \
            .app_secret(bot.app_secret) \
            .enable_set_token(True) \
            .build()

    def _opt(self):
        """Build request option with current app_access_token."""
        from src.auth.app_auth import get_token
        from lark_oapi.core.token import RequestOptionBuilder
        return RequestOptionBuilder().app_access_token(get_token(self._bot_name)).build()

    def update_token(self, new_token: str):
        """Update the cached token (called after refresh)."""
        pass  # Not needed for bot token, SDK handles it internally

    # ─── generic table helpers ─────────────────────────────

    def create_table(self, name: str, fields: list[str]) -> str:
        """Create a Base table with text fields and return the table ID."""
        headers = [
            AppTableCreateHeader.builder()
            .field_name(field_name)
            .type(1)
            .build()
            for field_name in fields
        ]
        table = ReqTable.builder() \
            .name(name) \
            .default_view_name("Grid") \
            .fields(headers) \
            .build()
        body = CreateAppTableRequestBody.builder().table(table).build()
        request = CreateAppTableRequest.builder() \
            .app_token(self.base_token) \
            .request_body(body) \
            .build()
        response = self._client.bitable.v1.app_table.create(request, self._opt())
        if not response.success():
            _handle_api_error("create_table", response)
        return response.data.table_id

    def create_record(self, table_id: str, fields: dict) -> str:
        """Create a record in any configured Base table."""
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id(table_id) \
            .request_body(AppTableRecord.builder().fields(fields).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.create(request, self._opt())
        if not response.success():
            _handle_api_error("create_record", response)
        return response.data.record.record_id

    def list_records(self, table_id: str) -> list:
        """List records from any configured Base table."""
        items = []
        page_token = None
        while True:
            builder = ListAppTableRecordRequest.builder() \
                .app_token(self.base_token) \
                .table_id(table_id) \
                .page_size(100)
            if page_token:
                builder = builder.page_token(page_token)
            request = builder.build()
            response = self._client.bitable.v1.app_table_record.list(
                request, self._opt()
            )
            if not response.success():
                _handle_api_error("list_records", response)
            data = response.data
            items.extend(data.items or [])
            if not getattr(data, "has_more", False):
                return items
            page_token = getattr(data, "page_token", None)
            if not page_token:
                return items

    def update_record(self, table_id: str, record_id: str, fields: dict) -> bool:
        """Update a record in any configured Base table."""
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id(table_id) \
            .record_id(record_id) \
            .request_body(AppTableRecord.builder().fields(fields).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.update(request, self._opt())
        if not response.success():
            _handle_api_error("update_record", response)
        return True

    def get_record(self, table_id: str, record_id: str):
        """Get a record from any configured Base table."""
        request = GetAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id(table_id) \
            .record_id(record_id) \
            .build()
        response = self._client.bitable.v1.app_table_record.get(request, self._opt())
        if not response.success():
            _handle_api_error("get_record", response)
        return response.data.record

    # ─── task table ─────────────────────────────────────────

    def create_task(self, fields: dict) -> str:
        if "状态" not in fields:
            fields["状态"] = "待处理"
        return self.create_record(self.table_ids.tasks, fields)

    def list_tasks(self) -> list:
        return self.list_records(self.table_ids.tasks)

    def update_task_status(self, record_id: str, new_status: str) -> bool:
        return self.update_record(self.table_ids.tasks, record_id, {"状态": new_status})

    def get_task(self, record_id: str) -> dict:
        return self.get_record(self.table_ids.tasks, record_id)

    # ─── content table ──────────────────────────────────────

    def create_content(self, fields: dict) -> str:
        return self.create_record(self.table_ids.contents, fields)

    def list_contents(self) -> list:
        return self.list_records(self.table_ids.contents)

    def get_content(self, record_id: str) -> dict:
        return self.get_record(self.table_ids.contents, record_id)

    def update_content_status(self, record_id: str, new_status: str) -> bool:
        return self.update_record(self.table_ids.contents, record_id, {"状态": new_status})

    # ─── review table ───────────────────────────────────────

    def create_review_task(self, fields: dict) -> str:
        return self.create_record(self.table_ids.reviews, fields)

    def list_pending_reviews(self) -> list:
        return self.list_records(self.table_ids.reviews)

    def update_review_status(self, record_id: str, status: str,
                             opinion: str = "") -> bool:
        fields = {"审核状态": status}
        if opinion:
            fields["审核意见"] = opinion
        return self.update_record(self.table_ids.reviews, record_id, fields)

    # ─── log table ─────────────────────────────────────────

    def log_operation(self, operator: str, op_type: str, record_id: str,
                      detail: str) -> str:
        fields = {
            "操作者": operator,
            "操作类型": op_type,
            "关联记录ID": record_id,
            "变更内容": detail,
        }
        return self.create_record(self.table_ids.logs, fields)
