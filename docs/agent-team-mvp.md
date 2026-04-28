# Agent-Team MVP

## 判断

当前项目资源足够做一个可控的 agent-team lite：

- 已有 ARK LLM 客户端，可让 Leader 拆解开放目标。
- 已有飞书 Base SDK 封装，可作为共享任务市场和审计账本。
- 已有 Manager / Editor / Reviewer 三个角色，可先复用为团队成员。
- 已有离线测试框架，可在不写真实 Base 的情况下验证协议。

不足之处也明确：

- 还没有真实的 agent-team Base 表。
- 还没有长驻 worker 进程或消息轮询。
- 还没有完全开放的自主调度能力。

因此第一阶段不做“完全自主团队”，先做 Base-backed agent-team 的核心协议：目标拆解、任务市场、领取任务、写回产物、通知 Leader。

## 设计原则

借鉴 Claude Code agent-team 的工程结构，但映射到飞书 Base：

| Claude Code | 本项目 |
|---|---|
| Team = TaskList | 飞书 Base = 团队任务市场 |
| Team config | 成员表 |
| TaskCreate / TaskUpdate / TaskList | 任务台账 |
| SendMessage | 消息表 |
| Worker output | 产物表 |
| Verification agent | 验证记录 / Reviewer |
| Coordinator | Leader Agent |

核心规则：

- Leader 负责理解和综合，不把判断外包。
- Worker 任务必须自包含，因为 worker 不共享完整上下文。
- Agent 之间不靠自然语言旁路通信，必须写入 Base。
- 完成任务必须同时更新状态、写产物、写日志。
- Reviewer / Verifier 要做对抗式检查，而不是礼貌确认。

## Base 表契约

第一阶段建议新增或扩展以下表：

| 表 | 必要字段 |
|---|---|
| 目标池 | 目标标题、目标说明、状态、发起人、最终结论 |
| 任务台账 | 任务标题、任务说明、角色、状态、负责人、阻塞依赖、元数据 |
| 成员表 | 名称、角色、能力、状态 |
| 消息表 | 发送者、接收者、摘要、消息内容、关联任务ID、状态 |
| 产物表 | 关联任务ID、产物标题、产物内容、作者 |
| 验证记录 | 关联任务ID、验证结论、问题、建议 |
| 操作日志 | 复用现有表 |

状态最小集合：

```text
pending -> in_progress -> completed
pending -> blocked
in_progress -> failed
```

## 第一阶段执行范围

已落地的第一批代码只处理核心协议：

- `AgentTeamLeader`：把开放目标拆成 3-5 个自包含任务。
- `AgentTeamEngine`：创建任务市场、领取任务、完成任务。
- `AgentTeamStore`：定义持久化边界。
- `BaseAgentTeamStore`：把协议映射到飞书 Base。

下一阶段再接 CLI 和真实端到端演示。
