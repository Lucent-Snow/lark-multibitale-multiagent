"""
Feishu Base SDK client using bot credentials (app_access_token).

Each bot has its own app_id + app_secret.
Token is automatically managed via src.auth.app_auth.get_token().
"""

from lark_oapi.api.bitable.v1 import *
from lark_oapi import Client


class BaseClient:
    """Feishu Base client using bot authentication."""

    def __init__(self, bot_name: str, base_token: str):
        from src.auth.app_auth import Credentials

        self.base_token = base_token
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
        return RequestOptionBuilder().user_access_token(get_token(self._bot_name)).build()

    def update_token(self, new_token: str):
        """Update the cached token (called after refresh)."""
        pass  # Not needed for bot token, SDK handles it internally

    # ─── task table ─────────────────────────────────────────

    def create_task(self, fields: dict) -> str:
        if "状态" not in fields:
            fields["状态"] = "待处理"
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .request_body(AppTableRecord.builder().fields(fields).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.create(request, self._opt())
        if not response.success():
            raise Exception(f"create_task failed: {response.msg}")
        return response.data.record.record_id

    def list_tasks(self) -> list:
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .page_size(100) \
            .build()
        response = self._client.bitable.v1.app_table_record.list(request, self._opt())
        if not response.success():
            raise Exception(f"list_tasks failed: {response.msg}")
        return response.data.items or []

    def update_task_status(self, record_id: str, new_status: str) -> bool:
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .record_id(record_id) \
            .request_body(AppTableRecord.builder().fields({"状态": new_status}).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.update(request, self._opt())
        if not response.success():
            raise Exception(f"update_task_status failed: {response.msg}")
        return True

    def get_task(self, record_id: str) -> dict:
        request = GetAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .record_id(record_id) \
            .build()
        response = self._client.bitable.v1.app_table_record.get(request, self._opt())
        if not response.success():
            raise Exception(f"get_task failed: {response.msg}")
        return response.data.record

    # ─── content table ──────────────────────────────────────

    def create_content(self, fields: dict) -> str:
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblPHI9PtdSZR16b") \
            .request_body(AppTableRecord.builder().fields(fields).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.create(request, self._opt())
        if not response.success():
            raise Exception(f"create_content failed: {response.msg}")
        return response.data.record.record_id

    def list_contents(self) -> list:
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblPHI9PtdSZR16b") \
            .page_size(100) \
            .build()
        response = self._client.bitable.v1.app_table_record.list(request, self._opt())
        if not response.success():
            raise Exception(f"list_contents failed: {response.msg}")
        return response.data.items or []

    def get_content(self, record_id: str) -> dict:
        request = GetAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblPHI9PtdSZR16b") \
            .record_id(record_id) \
            .build()
        response = self._client.bitable.v1.app_table_record.get(request, self._opt())
        if not response.success():
            raise Exception(f"get_content failed: {response.msg}")
        return response.data.record

    def update_content_status(self, record_id: str, new_status: str) -> bool:
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblPHI9PtdSZR16b") \
            .record_id(record_id) \
            .request_body(AppTableRecord.builder().fields({"状态": new_status}).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.update(request, self._opt())
        if not response.success():
            raise Exception(f"update_content_status failed: {response.msg}")
        return True

    # ─── review table ───────────────────────────────────────

    def create_review_task(self, fields: dict) -> str:
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tbleARaOWoXJR8a2") \
            .request_body(AppTableRecord.builder().fields(fields).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.create(request, self._opt())
        if not response.success():
            raise Exception(f"create_review_task failed: {response.msg}")
        return response.data.record.record_id

    def list_pending_reviews(self) -> list:
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tbleARaOWoXJR8a2") \
            .page_size(100) \
            .build()
        response = self._client.bitable.v1.app_table_record.list(request, self._opt())
        if not response.success():
            raise Exception(f"list_pending_reviews failed: {response.msg}")
        return response.data.items or []

    def update_review_status(self, record_id: str, status: str,
                             opinion: str = "") -> bool:
        fields = {"审核状态": status}
        if opinion:
            fields["审核意见"] = opinion
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tbleARaOWoXJR8a2") \
            .record_id(record_id) \
            .request_body(AppTableRecord.builder().fields(fields).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.update(request, self._opt())
        if not response.success():
            raise Exception(f"update_review_status failed: {response.msg}")
        return True

    # ─── log table ─────────────────────────────────────────

    def log_operation(self, operator: str, op_type: str, record_id: str,
                      detail: str) -> str:
        fields = {
            "操作者": operator,
            "操作类型": op_type,
            "关联记录ID": record_id,
            "变更内容": detail,
        }
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblTSFzb7IbwJeQm") \
            .request_body(AppTableRecord.builder().fields(fields).build()) \
            .build()
        response = self._client.bitable.v1.app_table_record.create(request, self._opt())
        if not response.success():
            raise Exception(f"log_operation failed: {response.msg}")
        return response.data.record.record_id
