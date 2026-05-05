import requests
import json
import time
from typing import Optional, List, Dict
from datetime import datetime, timedelta

APP_ID = "cli_a97227cdd5f8dcef"
APP_SECRET = "mdA8sTOIh3LImUNmwevcCfgys8VBomCd"

WORK_ORDER_CONFIG = {
    "app_token": "Azf8bfMXRa5TQTsbPawckgyhnMh",
    "table_id": "tbldiwNce1LYRnl1",
    "name": "工单台账"
}

PRIORITY_SLA = {
    "紧急": 1,
    "高": 4,
    "中": 24,
    "低": 72
}

class WorkOrderAgent:
    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or APP_ID
        self.app_secret = app_secret or APP_SECRET
        self.base_url = "https://open.feishu.cn"
        self.token = None
        self.token_expire_time = 0

    def _get_token(self) -> str:
        if self.token and time.time() < self.token_expire_time:
            return self.token
        url = f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
        result = resp.json()
        if result.get("code") == 0:
            self.token = result["tenant_access_token"]
            self.token_expire_time = time.time() + result["expire"] - 60
            return self.token
        raise Exception(f"获取Token失败: {result.get('msg')}")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    def _calc_sla_time(self, priority: str) -> int:
        hours = PRIORITY_SLA.get(priority, 24)
        return int((datetime.now() + timedelta(hours=hours)).timestamp() * 1000)

    def create_ticket(self, title: str, description: str = "", priority: str = "中",
                     ticket_type: str = "其他", source: str = "用户反馈") -> Dict:
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{WORK_ORDER_CONFIG['app_token']}/tables/{WORK_ORDER_CONFIG['table_id']}/records"
        fields = {
            "工单标题": title,
            "工单描述": description,
            "工单状态": "待分派",
            "优先级": priority,
            "工单类型": ticket_type,
            "工单来源": source,
            "SLA截止时间": self._calc_sla_time(priority)
        }
        resp = requests.post(url, json={"fields": fields}, headers=self._headers())
        result = resp.json()
        if result.get("code") == 0:
            record = result["data"]["record"]
            return {"success": True, "record_id": record["record_id"], "title": title, "status": "待分派", "priority": priority}
        return {"success": False, "error": result.get("msg")}

    def query_tickets(self, status: str = None, priority: str = None, ticket_type: str = None) -> List[Dict]:
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{WORK_ORDER_CONFIG['app_token']}/tables/{WORK_ORDER_CONFIG['table_id']}/records"
        resp = requests.get(url, headers=self._headers())
        result = resp.json()
        if result.get("code") == 0:
            tickets = []
            for item in result.get("data", {}).get("items", []):
                fields = item.get("fields", {})
                if fields.get("工单标题"):
                    t = {
                        "record_id": item["record_id"],
                        "title": fields.get("工单标题", ""),
                        "description": fields.get("工单描述", ""),
                        "status": fields.get("工单状态", ""),
                        "priority": fields.get("优先级", ""),
                        "ticket_type": fields.get("工单类型", ""),
                        "source": fields.get("工单来源", ""),
                        "assignee": fields.get("处理人", []),
                        "sla_time": fields.get("SLA截止时间", 0)
                    }
                    if status and t["status"] != status:
                        continue
                    if priority and t["priority"] != priority:
                        continue
                    if ticket_type and t["ticket_type"] != ticket_type:
                        continue
                    tickets.append(t)
            return tickets
        return []

    def get_pending_tickets(self) -> List[Dict]:
        return self.query_tickets(status="待分派")

    def get_sla_warning_tickets(self) -> List[Dict]:
        now = int(time.time() * 1000)
        all_tickets = self.query_tickets(status="待分派")
        warnings = []
        for t in all_tickets:
            sla = t.get("sla_time") or 0
            if sla > 0 and sla < now + 3600000:
                warnings.append(t)
        return warnings

    def update_ticket_status(self, record_id: str, new_status: str, note: str = "") -> Dict:
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{WORK_ORDER_CONFIG['app_token']}/tables/{WORK_ORDER_CONFIG['table_id']}/records/{record_id}"
        fields = {"工单状态": new_status}
        if note:
            fields["处理备注"] = note
        if new_status == "已完成":
            fields["满意度评分"] = 5
        resp = requests.put(url, json={"fields": fields}, headers=self._headers())
        result = resp.json()
        if result.get("code") == 0:
            return {"success": True, "record_id": record_id, "new_status": new_status}
        return {"success": False, "error": result.get("msg")}

    def assign_ticket(self, record_id: str, assignee: str, note: str = "") -> Dict:
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{WORK_ORDER_CONFIG['app_token']}/tables/{WORK_ORDER_CONFIG['table_id']}/records/{record_id}"
        fields = {"工单状态": "处理中", "处理人": [assignee]}
        if note:
            fields["处理备注"] = note
        resp = requests.put(url, json={"fields": fields}, headers=self._headers())
        result = resp.json()
        if result.get("code") == 0:
            return {"success": True, "record_id": record_id, "assignee": assignee}
        return {"success": False, "error": result.get("msg")}

    def batch_assign(self, record_ids: List[str], assignee: str) -> Dict:
        success_count = 0
        for rid in record_ids:
            result = self.assign_ticket(rid, assignee)
            if result["success"]:
                success_count += 1
        return {"success": True, "total": len(record_ids), "assigned": success_count}

    def close_ticket(self, record_id: str, note: str = "") -> Dict:
        return self.update_ticket_status(record_id, "已关闭", note)

    def complete_ticket(self, record_id: str, note: str = "") -> Dict:
        return self.update_ticket_status(record_id, "已完成", note)

    def get_ticket_info(self, record_id: str) -> Dict:
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{WORK_ORDER_CONFIG['app_token']}/tables/{WORK_ORDER_CONFIG['table_id']}/records/{record_id}"
        resp = requests.get(url, headers=self._headers())
        result = resp.json()
        if result.get("code") == 0:
            fields = result.get("data", {}).get("record", {}).get("fields", {})
            return {
                "record_id": record_id,
                "title": fields.get("工单标题", ""),
                "description": fields.get("工单描述", ""),
                "status": fields.get("工单状态", ""),
                "priority": fields.get("优先级", ""),
                "ticket_type": fields.get("工单类型", ""),
                "source": fields.get("工单来源", ""),
                "assignee": fields.get("处理人", []),
                "note": fields.get("处理备注", ""),
                "sla_time": fields.get("SLA截止时间", 0),
                "rating": fields.get("满意度评分", 0)
            }
        return {"success": False, "error": result.get("msg")}

    def get_statistics(self) -> Dict:
        all_tickets = self.query_tickets()
        stats = {
            "total": len(all_tickets),
            "by_status": {},
            "by_priority": {},
            "by_type": {},
            "by_source": {},
            "sla_warning": 0
        }
        now = int(time.time() * 1000)
        for t in all_tickets:
            status = t.get("status") or "未知"
            priority = t.get("priority") or "未知"
            ticket_type = t.get("ticket_type") or "未知"
            source = t.get("source") or "未知"
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
            stats["by_type"][ticket_type] = stats["by_type"].get(ticket_type, 0) + 1
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1
            sla = t.get("sla_time") or 0
            if sla > 0 and sla < now and t.get("status") in ["待分派", "处理中"]:
                stats["sla_warning"] += 1
        return stats

    def generate_summary(self) -> str:
        stats = self.get_statistics()
        pending = self.get_pending_tickets()
        sla_warnings = self.get_sla_warning_tickets()
        summary = []
        summary.append("=" * 50)
        summary.append("工单系统日报 - %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
        summary.append("=" * 50)
        summary.append("")
        summary.append("【总体概况】")
        summary.append("  总工单数: %d" % stats["total"])
        for status, count in stats["by_status"].items():
            summary.append("  %s: %d" % (status, count))
        summary.append("")
        summary.append("[紧急告警]")
        if stats["sla_warning"] > 0:
            summary.append("  [!] %d 个工单已超过SLA时限!" % stats["sla_warning"])
        else:
            summary.append("  [OK] 无超时工单")
        if sla_warnings:
            summary.append("  [*] %d 个工单即将超时(1小时内)" % len(sla_warnings))
        summary.append("")
        summary.append("【待分派工单】%d 个" % len(pending))
        for t in pending[:5]:
            summary.append("  - %s [%s]" % (t["title"][:30], t["priority"]))
        if len(pending) > 5:
            summary.append("  ... 还有 %d 个" % (len(pending) - 5))
        summary.append("")
        summary.append("【类型分布】")
        for t, count in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
            summary.append("  %s: %d" % (t, count))
        summary.append("")
        summary.append("=" * 50)
        return "\n".join(summary)

agent = WorkOrderAgent()

def create_ticket(title: str, description: str = "", priority: str = "中",
                 ticket_type: str = "其他", source: str = "用户反馈") -> str:
    result = agent.create_ticket(title, description, priority, ticket_type, source)
    if result["success"]:
        return "SUCCESS: 工单创建成功\n  标题: %s\n  状态: %s\n  优先级: %s\n  ID: %s" % (
            result['title'], result['status'], result.get('priority', '中'), result['record_id'])
    return "ERROR: " + result.get('error', '未知错误')

def get_pending_tickets() -> str:
    tickets = agent.get_pending_tickets()
    if not tickets:
        return "SUCCESS: 暂无待分派工单"
    output = "SUCCESS: 待分派工单 (%d 条)\n\n" % len(tickets)
    for i, t in enumerate(tickets, 1):
        output += "%d. %s\n   类型: %s | 来源: %s | 优先级: %s\n   ID: %s\n\n" % (
            i, t['title'], t.get('ticket_type', ''), t.get('source', ''), t['priority'], t['record_id'])
    return output

def query_all_tickets() -> str:
    tickets = agent.query_tickets()
    if not tickets:
        return "SUCCESS: 暂无工单"
    by_status = {}
    for t in tickets:
        status = t.get("status") or "未知"
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(t)
    output = "SUCCESS: 工单统计 (共 %d 条)\n\n" % len(tickets)
    for status, items in by_status.items():
        output += "【%s】%d 条\n" % (status, len(items))
    return output

def get_statistics() -> str:
    stats = agent.get_statistics()
    output = "SUCCESS: 工单统计分析\n\n"
    output += "【按状态】\n"
    for s, c in stats["by_status"].items():
        output += "  %s: %d\n" % (s, c)
    output += "\n【按优先级】\n"
    for s, c in stats["by_priority"].items():
        output += "  %s: %d\n" % (s, c)
    output += "\n【按类型】\n"
    for s, c in stats["by_type"].items():
        output += "  %s: %d\n" % (s, c)
    output += "\n【按来源】\n"
    for s, c in stats["by_source"].items():
        output += "  %s: %d\n" % (s, c)
    if stats["sla_warning"] > 0:
        output += "\n[!] SLA超时告警: %d 个工单已超时\n" % stats["sla_warning"]
    return output

def get_daily_summary() -> str:
    return agent.generate_summary()

def update_ticket_status(record_id: str, new_status: str, note: str = "") -> str:
    result = agent.update_ticket_status(record_id, new_status, note)
    if result["success"]:
        return "SUCCESS: 工单状态已更新为【%s】" % new_status
    return "ERROR: " + result.get('error', '未知错误')

def assign_ticket(record_id: str, assignee: str = "待定", note: str = "") -> str:
    result = agent.assign_ticket(record_id, assignee, note)
    if result["success"]:
        return "SUCCESS: 工单已分派给【%s】" % assignee
    return "ERROR: " + result.get('error', '未知错误')

def batch_assign_tickets(record_ids: List[str], assignee: str) -> str:
    result = agent.batch_assign(record_ids, assignee)
    return "SUCCESS: 批量分派完成\n  总数: %d\n  成功分派: %d" % (result["total"], result["assigned"])

def close_ticket(record_id: str, note: str = "") -> str:
    result = agent.close_ticket(record_id, note)
    if result["success"]:
        return "SUCCESS: 工单已关闭"
    return "ERROR: " + result.get('error', '未知错误')

def complete_ticket(record_id: str, note: str = "") -> str:
    result = agent.complete_ticket(record_id, note)
    if result["success"]:
        return "SUCCESS: 工单已完成"
    return "ERROR: " + result.get('error', '未知错误')

def get_ticket_info(record_id: str) -> str:
    result = agent.get_ticket_info(record_id)
    if "error" not in result:
        sla_str = ""
        if result.get("sla_time", 0) > 0:
            sla_dt = datetime.fromtimestamp(result["sla_time"] / 1000)
            sla_str = "\n  SLA截止: %s" % sla_dt.strftime("%Y-%m-%d %H:%M")
        return ("SUCCESS: 工单详情\n"
                "  标题: %s\n"
                "  描述: %s\n"
                "  状态: %s\n"
                "  优先级: %s\n"
                "  类型: %s\n"
                "  来源: %s\n"
                "  处理人: %s\n"
                "  备注: %s\n"
                "  满意度: %s%s\n"
                "  ID: %s") % (result['title'], result['description'], result['status'],
                             result['priority'], result.get('ticket_type', ''),
                             result.get('source', ''), result.get('assignee', []),
                             result.get('note', ''), result.get('rating', 'N/A'), sla_str, result['record_id'])
    return "ERROR: " + result.get('error', '未知错误')

def get_sla_warnings() -> str:
    warnings = agent.get_sla_warning_tickets()
    if not warnings:
        return "SUCCESS: 暂无SLA预警工单"
    output = "WARNING: SLA预警工单 (%d 个)\n\n" % len(warnings)
    for t in warnings:
        output += "[!] %s\n   优先级: %s\n   ID: %s\n\n" % (t['title'], t['priority'], t['record_id'])
    return output

def get_work_order_config() -> Dict:
    return WORK_ORDER_CONFIG

if __name__ == "__main__":
    print("工单系统 Agent - 高级版")
    print("=" * 50)
    print()
    print(get_daily_summary())