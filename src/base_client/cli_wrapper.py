"""
Base API 封装层
内部调用 lark-cli（复用已登录的 user token）
对外暴露和 SDK 一样的接口
"""

import json
import os
import subprocess
from typing import Any, Optional


class BaseAPI:
    """
    通过 lark-cli 调用飞书多维表格 API
    好处：自动使用 lark-cli 已登录的 user token，无需手动管理
    """

    def __init__(self, base_token: str):
        self.base_token = base_token
        # 扩展 PATH，确保 lark-cli.cmd 能被找到
        npm_path = r"C:\Users\William\AppData\Roaming\npm"
        self.env = os.environ.copy()
        if npm_path not in self.env.get("PATH", ""):
            self.env["PATH"] = self.env.get("PATH", "") + ";" + npm_path

    def _call(self, command: list) -> dict:
        """内部调用 lark-cli，返回解析后的 JSON"""
        try:
            # 通过 cmd /c 运行 lark-cli.cmd（Windows 批处理需要 shell）
            cmd = ["cmd", "/c", "lark-cli"] + command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=self.env,
            )
            if result.returncode != 0:
                print(f"[CLI Error] returncode={result.returncode}: {result.stderr[:300]}")
                return {}
            output = result.stdout.strip()
            if not output:
                return {}
            return json.loads(output)
        except Exception as e:
            print(f"[CLI Exception] {e}")
            return {}

    # ─────────────────────────────────────────
    # 任务台账
    # ─────────────────────────────────────────

    def create_task(self, fields: dict) -> str:
        """创建任务"""
        result = self._call([
            "base", "+record-upsert",
            "--base-token", self.base_token,
            "--table-id", "任务台账",
            "--json", json.dumps(fields, ensure_ascii=False),
        ])
        if result.get("ok"):
            return result["data"]["record"]["record_id_list"][0]
        raise Exception(f"创建任务失败: {result}")

    def list_tasks(self) -> list:
        """列出所有任务"""
        result = self._call([
            "base", "+record-list",
            "--base-token", self.base_token,
            "--table-id", "任务台账",
        ])
        if result.get("ok"):
            return result.get("data", {}).get("items", [])
        return []

    def update_task_status(self, record_id: str, status: str) -> bool:
        """更新任务状态"""
        result = self._call([
            "base", "+record-batch-update",
            "--base-token", self.base_token,
            "--table-id", "任务台账",
            "--json", json.dumps({
                "record_id_list": [record_id],
                "patch": {"状态": status}
            }, ensure_ascii=False),
        ])
        return result.get("ok", False)

    def get_task(self, record_id: str) -> Optional[dict]:
        """获取单个任务"""
        result = self._call([
            "base", "+record-get",
            "--base-token", self.base_token,
            "--table-id", "任务台账",
            "--record-id", record_id,
        ])
        if result.get("ok"):
            return result.get("data", {}).get("record", {})
        return None

    # ─────────────────────────────────────────
    # 内容库
    # ─────────────────────────────────────────

    def create_content(self, fields: dict) -> str:
        """创建内容"""
        result = self._call([
            "base", "+record-upsert",
            "--base-token", self.base_token,
            "--table-id", "内容库",
            "--json", json.dumps(fields, ensure_ascii=False),
        ])
        if result.get("ok"):
            return result["data"]["record"]["record_id_list"][0]
        raise Exception(f"创建内容失败: {result}")

    def list_contents(self) -> list:
        """列出所有内容"""
        result = self._call([
            "base", "+record-list",
            "--base-token", self.base_token,
            "--table-id", "内容库",
        ])
        if result.get("ok"):
            return result.get("data", {}).get("items", [])
        return []

    def update_content_status(self, record_id: str, status: str) -> bool:
        """更新内容状态"""
        result = self._call([
            "base", "+record-batch-update",
            "--base-token", self.base_token,
            "--table-id", "内容库",
            "--json", json.dumps({
                "record_id_list": [record_id],
                "patch": {"状态": status}
            }, ensure_ascii=False),
        ])
        return result.get("ok", False)

    # ─────────────────────────────────────────
    # 审核队列
    # ─────────────────────────────────────────

    def create_review_task(self, fields: dict) -> str:
        """创建审核任务"""
        result = self._call([
            "base", "+record-upsert",
            "--base-token", self.base_token,
            "--table-id", "审核队列",
            "--json", json.dumps(fields, ensure_ascii=False),
        ])
        if result.get("ok"):
            return result["data"]["record"]["record_id_list"][0]
        raise Exception(f"创建审核任务失败: {result}")

    def list_pending_reviews(self) -> list:
        """列出待审核任务"""
        result = self._call([
            "base", "+record-list",
            "--base-token", self.base_token,
            "--table-id", "审核队列",
        ])
        if result.get("ok"):
            return result.get("data", {}).get("items", [])
        return []

    def update_review_status(self, record_id: str, status: str, opinion: str = "") -> bool:
        """更新审核状态"""
        patch = {"审核状态": status}
        if opinion:
            patch["审核意见"] = opinion
        result = self._call([
            "base", "+record-batch-update",
            "--base-token", self.base_token,
            "--table-id", "审核队列",
            "--json", json.dumps({
                "record_id_list": [record_id],
                "patch": patch
            }, ensure_ascii=False),
        ])
        return result.get("ok", False)

    # ─────────────────────────────────────────
    # 操作日志
    # ─────────────────────────────────────────

    def log_operation(self, operator: str, op_type: str, record_id: str, detail: str) -> str:
        """记录操作日志"""
        fields = {
            "操作者": operator,
            "操作类型": op_type,
            "关联记录ID": record_id,
            "变更内容": detail,
        }
        result = self._call([
            "base", "+record-upsert",
            "--base-token", self.base_token,
            "--table-id", "操作日志",
            "--json", json.dumps(fields, ensure_ascii=False),
        ])
        if result.get("ok"):
            return result["data"]["record"]["record_id_list"][0]
        raise Exception(f"写日志失败: {result}")
