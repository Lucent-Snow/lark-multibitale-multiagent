"""
Feishu Base SDK client using bot credentials.
One bot, one base_token — simple.
"""

import re
import webbrowser
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

from lark_oapi.api.bitable.v1 import *
from lark_oapi import Client


def _handle_api_error(op_name: str, response):
    """Unpack Feishu API error, detect permission issues."""
    code = getattr(response, "code", -1)
    msg = getattr(response, "msg", str(response))

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

    if code == 17910003 or "Forbidden" in str(msg):
        hint = (
            f"\n  [HINT] The bot cannot access this Base.\n"
            f"  [HINT] Open the Base in Feishu → Share → add the bot as Editor.\n"
            f"  [HINT] If the Base is in your personal space, move it to a shared space first."
        )
        raise Exception(f"{op_name} failed: {msg}{hint}")

    raise Exception(f"{op_name} failed: {msg}")


class BaseClient:
    """Feishu Base client — one bot, one base."""

    def __init__(self, base_token: str):
        import yaml
        import os
        import json

        self.base_token = base_token

        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(root, "config.yaml")
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f.read()) or {}

        bot = (cfg.get("bot") or {})
        app_id = bot.get("app_id", "")
        app_secret = bot.get("app_secret", "")
        if not app_id or not app_secret:
            raise ValueError("Missing bot.app_id or bot.app_secret in config.yaml")

        # Ensure credentials are saved for auth module
        creds_path = os.path.join(root, ".credentials.json")
        existing = {}
        if os.path.exists(creds_path):
            try:
                with open(creds_path, "r", encoding="utf-8") as f:
                    existing = json.loads(f.read()) or {}
            except Exception:
                pass
        bots = existing.get("bots", [])
        if not any(b.get("app_id") == app_id for b in bots):
            bots.append({"name": "bot", "app_id": app_id, "app_secret": app_secret})
            existing["bots"] = bots
            with open(creds_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

        self._bot_name = "bot"

        self._client = Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .enable_set_token(True) \
            .build()

    def _opt(self):
        from src.auth.app_auth import get_token
        from lark_oapi.core.token import RequestOptionBuilder
        return RequestOptionBuilder().app_access_token(get_token(self._bot_name)).build()

    # ─── Generic CRUD ──────────────────────────────────────

    def create_table(self, name: str, fields: list[str]) -> str:
        """Create a table and return its ID."""
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
            response = self._client.bitable.v1.app_table_record.list(request, self._opt())
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
        request = GetAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id(table_id) \
            .record_id(record_id) \
            .build()
        response = self._client.bitable.v1.app_table_record.get(request, self._opt())
        if not response.success():
            _handle_api_error("get_record", response)
        return response.data.record
