"""
运营主管 Agent
职责：
- 创建选题任务
- 分配任务给 Editor
- 跟踪任务进度
- 生成报告
"""

from src.base_client.cli_wrapper import BaseAPI


class ManagerAgent:
    """运营主管 Agent"""

    def __init__(self, base_api: BaseAPI):
        self.api = base_api
        self.name = "运营主管"

    def create_topic(self, title: str, priority: str = "中") -> str:
        """创建选题任务"""
        record_id = self.api.create_task({
            "任务标题": title,
            "状态": "待处理",
            "负责人": self.name,
            "优先级": priority,
        })
        self.api.log_operation(
            operator=self.name,
            op_type="创建",
            record_id=record_id,
            detail=f"创建选题任务: {title}"
        )
        return record_id

    def assign_to_editor(self, record_id: str) -> bool:
        """将任务分配给编辑"""
        self.api.update_task_status(record_id, "处理中")
        self.api.log_operation(
            operator=self.name,
            op_type="分配",
            record_id=record_id,
            detail="任务分配给内容编辑"
        )
        return True

    def approve_publish(self, record_id: str) -> bool:
        """审批发布"""
        self.api.update_task_status(record_id, "已发布")
        self.api.log_operation(
            operator=self.name,
            op_type="发布",
            record_id=record_id,
            detail="运营主管审批通过，任务已发布"
        )
        return True

    def archive_task(self, record_id: str) -> bool:
        """归档任务"""
        self.api.update_task_status(record_id, "已归档")
        self.api.log_operation(
            operator=self.name,
            op_type="归档",
            record_id=record_id,
            detail="任务归档"
        )
        return True

    def generate_report(self) -> dict:
        """生成运营报告"""
        tasks = self.api.list_tasks()
        contents = self.api.list_contents()
        return {
            "总任务数": len(tasks),
            "内容数": len(contents),
        }
