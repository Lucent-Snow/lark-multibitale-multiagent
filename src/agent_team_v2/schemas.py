"""Base table schema definitions for agent-team v2."""


V2_TABLE_SCHEMAS = {
    "v2_objectives": {
        "name": "v2_objectives",
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
    "v2_workers": {
        "name": "v2_workers",
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
    "v2_tasks": {
        "name": "v2_tasks",
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
    "v2_task_edges": {
        "name": "v2_task_edges",
        "fields": [
            "objective_id",
            "from_task_id",
            "to_task_id",
            "关系类型",
        ],
    },
    "v2_claims": {
        "name": "v2_claims",
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
    "v2_messages": {
        "name": "v2_messages",
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
    "v2_artifacts": {
        "name": "v2_artifacts",
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
    "v2_verifications": {
        "name": "v2_verifications",
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
    "v2_events": {
        "name": "v2_events",
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

