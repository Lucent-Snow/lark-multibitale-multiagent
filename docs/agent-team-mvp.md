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

## 演示与验证

离线演示入口不依赖飞书或 ARK：

```bash
python src/main.py --agent-team-demo
python src/main.py --agent-team-demo --objective "新品发布内容运营" --objective-description "规划一组内容生产、审核和复盘任务"
```

离线演示会使用内存存储完成：

```text
目标 -> Leader 拆任务 -> Worker 按角色领取 -> 写产物 -> 发消息给 team-lead -> 写日志
```

真实飞书端到端演示入口会调用 ARK LLM，并向飞书 Base 写入目标、成员、任务、产物、消息、验证记录和操作日志：

```bash
python src/main.py --agent-team-base-demo --agent-team-max-tasks 4
python src/main.py --agent-team-base-demo --objective "真实业务目标" --objective-description "用一段话描述要完成的目标"
```

真实演示需要先创建 agent-team 表，并在 `config.yaml` 中补齐：

```yaml
lark:
  tables:
    objectives: "tbl_objectives_here"
    members: "tbl_members_here"
    messages: "tbl_messages_here"
    artifacts: "tbl_artifacts_here"
    verifications: "tbl_verifications_here"
```

每次真实演示会把本轮目标记录 ID 写入任务的 `元数据.objective_id`，任务市场只领取本轮任务，避免重复运行时误处理旧任务。验证通过的最小标准是：

- 目标池记录最终状态为 `completed`。
- 本轮计划任务全部变为 `completed`。
- 每个完成任务都有对应产物、消息、操作日志和验证记录。
- 程序末尾读回目标、任务和验证记录，确认 Base 中的数据已经落盘。

## v2 方向

第一阶段证明了 Base-backed agent-team 可以跑通，但它仍是 demo 协议。v2 开始把飞书 Base 明确建模为控制平面，吸收 Claude Code task board 的关键经验：

- 任务依赖使用任务 ID 图，而不是标题文本。
- worker 领取任务走 claim 记录和赢家判定，避免并发抢占。
- worker 注册、心跳、idle、当前任务都写入 Base。
- 消息、产物、验证、事件分表沉淀，避免把普通输出误当作团队通信。
- objective 完成前必须有任务完成证据和验证记录。

详见 `docs/agent-team-v2.md`。
