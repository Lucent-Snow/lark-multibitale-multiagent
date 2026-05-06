"""Base table schema definitions for the agent-team control plane.

Each Base gets a lightweight meta table that stores the table IDs
of the 9 data tables. Leader creates everything on first run.
"""

# Physical table name prefix (configurable, not v2_ anymore)
TABLE_PREFIX = "agent_team_"


META_TABLE = {
    "name": f"{TABLE_PREFIX}meta",
    "fields": ["key", "table_id"],
}

DATA_TABLES = {
    "objectives": {
        "name": f"{TABLE_PREFIX}objectives",
        "fields": [
            "objective_id",
            "标题",
            "说明",
            "状态",
            "发起人",
            "最终结论",
            "创建时间",
        ],
    },
    "workers": {
        "name": f"{TABLE_PREFIX}workers",
        "fields": [
            "worker_id",
            "objective_id",
            "名称",
            "角色",
            "能力",
            "状态",
            "当前任务ID",
            "心跳时间",
            "进程ID",
        ],
    },
    "tasks": {
        "name": f"{TABLE_PREFIX}tasks",
        "fields": [
            "task_id",
            "objective_id",
            "标题",
            "说明",
            "角色",
            "状态",
            "owner",
            "lease_until",
            "attempt_count",
            "metadata",
            "完成时间",
        ],
    },
    "task_edges": {
        "name": f"{TABLE_PREFIX}task_edges",
        "fields": [
            "objective_id",
            "from_task_id",
            "to_task_id",
            "关系类型",
        ],
    },
    "claims": {
        "name": f"{TABLE_PREFIX}claims",
        "fields": [
            "claim_id",
            "objective_id",
            "task_id",
            "worker_id",
            "状态",
            "nonce",
            "创建时间",
        ],
    },
    "messages": {
        "name": f"{TABLE_PREFIX}messages",
        "fields": [
            "message_id",
            "objective_id",
            "from",
            "to",
            "summary",
            "message",
            "关联任务ID",
            "状态",
            "创建时间",
        ],
    },
    "artifacts": {
        "name": f"{TABLE_PREFIX}artifacts",
        "fields": [
            "artifact_id",
            "objective_id",
            "task_id",
            "作者",
            "标题",
            "内容",
            "创建时间",
        ],
    },
    "verifications": {
        "name": f"{TABLE_PREFIX}verifications",
        "fields": [
            "verification_id",
            "objective_id",
            "task_id",
            "verifier",
            "结论",
            "问题",
            "建议",
            "创建时间",
        ],
    },
    "events": {
        "name": f"{TABLE_PREFIX}events",
        "fields": [
            "event_id",
            "objective_id",
            "actor",
            "event_type",
            "target_id",
            "detail",
            "创建时间",
        ],
    },
}

# Combined: meta + 9 data tables
ALL_TABLES = {"meta": META_TABLE, **DATA_TABLES}
