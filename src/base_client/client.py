"""
飞书多维表格客户端封装
使用 lark-oapi SDK 操作 Base
"""

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import *


class BaseClient:
    """飞书多维表格 SDK 客户端封装"""

    def __init__(self, app_id: str, app_secret: str, base_token: str):
        self.base_token = base_token
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

    # ─────────────────────────────────────────
    # 任务台账操作
    # ─────────────────────────────────────────

    def create_task(self, fields: dict) -> str:
        """创建任务记录，返回 record_id"""
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .field_name_list([
                "任务标题", "状态", "负责人", "优先级"
            ]) \
            .build()
        # 构造字段值
        fields["状态"] = lark.Text(text="待处理") if "状态" not in fields else fields["状态"]
        record = CreateAppTableRecordRequest.Record(fields=fields)
        request.record = record

        response = self.client.bitable.v1.app_table_record.create(request)
        if not response.success():
            raise Exception(f"创建任务失败: {response.msg}")
        return response.data.record.record_id

    def list_tasks(self, filter_conditions: str = None) -> list:
        """列出任务记录"""
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .page_size(100) \
            .build()

        response = self.client.bitable.v1.app_table_record.list(request)
        if not response.success():
            raise Exception(f"查询任务失败: {response.msg}")
        return response.data.items or []

    def update_task_status(self, record_id: str, new_status: str) -> bool:
        """更新任务状态"""
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .record_id(record_id) \
            .field_name_list(["状态"]) \
            .build()
        request.record = UpdateAppTableRecordRequest.Record(
            fields={"状态": lark.Text(text=new_status)}
        )

        response = self.client.bitable.v1.app_table_record.update(request)
        if not response.success():
            raise Exception(f"更新任务状态失败: {response.msg}")
        return True

    def get_task(self, record_id: str) -> dict:
        """获取单个任务"""
        request = GetAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblVPcVfpolbbPBL") \
            .record_id(record_id) \
            .build()

        response = self.client.bitable.v1.app_table_record.get(request)
        if not response.success():
            raise Exception(f"获取任务失败: {response.msg}")
        return response.data.record

    # ─────────────────────────────────────────
    # 内容库操作
    # ─────────────────────────────────────────

    def create_content(self, fields: dict) -> str:
        """创建内容记录"""
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblPHI9PtdSZR16b") \
            .build()
        request.record = CreateAppTableRecordRequest.Record(fields=fields)

        response = self.client.bitable.v1.app_table_record.create(request)
        if not response.success():
            raise Exception(f"创建内容失败: {response.msg}")
        return response.data.record.record_id

    def list_contents(self) -> list:
        """列出内容记录"""
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblPHI9PtdSZR16b") \
            .page_size(100) \
            .build()

        response = self.client.bitable.v1.app_table_record.list(request)
        if not response.success():
            raise Exception(f"查询内容失败: {response.msg}")
        return response.data.items or []

    def update_content_status(self, record_id: str, new_status: str) -> bool:
        """更新内容状态"""
        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblPHI9PtdSZR16b") \
            .record_id(record_id) \
            .field_name_list(["状态"]) \
            .build()
        request.record = UpdateAppTableRecordRequest.Record(
            fields={"状态": lark.Text(text=new_status)}
        )

        response = self.client.bitable.v1.app_table_record.update(request)
        if not response.success():
            raise Exception(f"更新内容状态失败: {response.msg}")
        return True

    # ─────────────────────────────────────────
    # 审核队列操作
    # ─────────────────────────────────────────

    def create_review_task(self, fields: dict) -> str:
        """创建审核任务"""
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tbleARaOWoXJR8a2") \
            .build()
        request.record = CreateAppTableRecordRequest.Record(fields=fields)

        response = self.client.bitable.v1.app_table_record.create(request)
        if not response.success():
            raise Exception(f"创建审核任务失败: {response.msg}")
        return response.data.record.record_id

    def list_pending_reviews(self) -> list:
        """列出待审核任务"""
        request = ListAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tbleARaOWoXJR8a2") \
            .page_size(100) \
            .build()

        response = self.client.bitable.v1.app_table_record.list(request)
        if not response.success():
            raise Exception(f"查询审核队列失败: {response.msg}")
        return response.data.items or []

    def update_review_status(self, record_id: str, status: str, opinion: str = "") -> bool:
        """更新审核状态"""
        fields = {"审核状态": lark.Text(text=status)}
        if opinion:
            fields["审核意见"] = lark.Text(text=opinion)

        request = UpdateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tbleARaOWoXJR8a2") \
            .record_id(record_id) \
            .field_name_list(list(fields.keys())) \
            .build()
        request.record = UpdateAppTableRecordRequest.Record(fields=fields)

        response = self.client.bitable.v1.app_table_record.update(request)
        if not response.success():
            raise Exception(f"更新审核状态失败: {response.msg}")
        return True

    # ─────────────────────────────────────────
    # 操作日志
    # ─────────────────────────────────────────

    def log_operation(self, operator: str, op_type: str, record_id: str, detail: str) -> str:
        """记录操作日志"""
        request = CreateAppTableRecordRequest.builder() \
            .app_token(self.base_token) \
            .table_id("tblTSFzb7IbwJeQm") \
            .build()
        request.record = CreateAppTableRecordRequest.Record(fields={
            "操作者": lark.Text(text=operator),
            "操作类型": lark.Text(text=op_type),
            "关联记录ID": lark.Text(text=record_id),
            "变更内容": lark.Text(text=detail),
        })

        response = self.client.bitable.v1.app_table_record.create(request)
        if not response.success():
            raise Exception(f"写日志失败: {response.msg}")
        return response.data.record.record_id
