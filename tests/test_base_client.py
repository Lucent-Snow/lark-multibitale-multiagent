import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.base_client.client import BaseClient, BaseTableIds


class FakeCredentials:
    def get(self, name):
        return SimpleNamespace(app_id=f"{name}_app_id", app_secret=f"{name}_secret")


class FakeResponse:
    def __init__(self, record_id="rec1", items=None):
        self.code = 0
        self.msg = "ok"
        self.data = SimpleNamespace(
            record=SimpleNamespace(record_id=record_id, fields={}),
            items=items or [],
        )

    def success(self):
        return True


class FakeRecordApi:
    def __init__(self):
        self.calls = []

    def _capture(self, method, request, option):
        self.calls.append({
            "method": method,
            "app_token": request.app_token,
            "table_id": request.table_id,
            "record_id": getattr(request, "record_id", None),
            "option": option,
        })
        return FakeResponse()

    def create(self, request, option):
        return self._capture("create", request, option)

    def list(self, request, option):
        return self._capture("list", request, option)

    def update(self, request, option):
        return self._capture("update", request, option)

    def get(self, request, option):
        return self._capture("get", request, option)


class FakeLarkClient:
    def __init__(self, record_api):
        self.bitable = SimpleNamespace(
            v1=SimpleNamespace(app_table_record=record_api)
        )


class FakeClientBuilder:
    def __init__(self, record_api):
        self.record_api = record_api

    def app_id(self, value):
        return self

    def app_secret(self, value):
        return self

    def enable_set_token(self, value):
        return self

    def build(self):
        return FakeLarkClient(self.record_api)


class FakeClientFactory:
    def __init__(self, record_api):
        self.record_api = record_api

    def builder(self):
        return FakeClientBuilder(self.record_api)


class FakeRequestOptionBuilder:
    calls = []

    def app_access_token(self, token):
        self.calls.append(("app_access_token", token))
        self.token_type = "app"
        self.token = token
        return self

    def user_access_token(self, token):
        self.calls.append(("user_access_token", token))
        self.token_type = "user"
        self.token = token
        return self

    def build(self):
        return {"token_type": self.token_type, "token": self.token}


class BaseClientTests(unittest.TestCase):
    def setUp(self):
        self.table_ids = BaseTableIds(
            tasks="tbl_tasks",
            contents="tbl_contents",
            reviews="tbl_reviews",
            logs="tbl_logs",
        )
        FakeRequestOptionBuilder.calls = []

    def _client(self, record_api):
        patches = [
            patch("src.auth.app_auth.Credentials", FakeCredentials),
            patch("src.auth.app_auth.get_token", return_value="app_token_value"),
            patch("src.base_client.client.Client", FakeClientFactory(record_api)),
            patch("lark_oapi.core.token.RequestOptionBuilder", FakeRequestOptionBuilder),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return BaseClient("manager", "base_token_value", self.table_ids)

    def test_request_option_uses_app_access_token(self):
        record_api = FakeRecordApi()
        client = self._client(record_api)

        client.create_task({"任务标题": "测试"})

        self.assertEqual(FakeRequestOptionBuilder.calls, [
            ("app_access_token", "app_token_value")
        ])
        self.assertEqual(record_api.calls[0]["option"]["token_type"], "app")

    def test_table_ids_are_routed_from_config(self):
        record_api = FakeRecordApi()
        client = self._client(record_api)

        client.create_task({"任务标题": "测试"})
        client.list_tasks()
        client.update_task_status("task_rec", "处理中")
        client.get_task("task_rec")
        client.create_content({"内容标题": "测试"})
        client.list_contents()
        client.get_content("content_rec")
        client.update_content_status("content_rec", "待审核")
        client.create_review_task({"审核状态": "待审核"})
        client.list_pending_reviews()
        client.update_review_status("review_rec", "通过")
        client.log_operation("tester", "测试", "rec", "detail")

        self.assertEqual(
            [call["table_id"] for call in record_api.calls],
            [
                "tbl_tasks",
                "tbl_tasks",
                "tbl_tasks",
                "tbl_tasks",
                "tbl_contents",
                "tbl_contents",
                "tbl_contents",
                "tbl_contents",
                "tbl_reviews",
                "tbl_reviews",
                "tbl_reviews",
                "tbl_logs",
            ],
        )
        self.assertTrue(all(call["app_token"] == "base_token_value" for call in record_api.calls))


if __name__ == "__main__":
    unittest.main()
