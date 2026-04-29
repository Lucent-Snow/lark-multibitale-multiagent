# Agent-Team v2

## 定位

v2 把飞书 Base 作为 agent-team 的控制平面，而不是普通结果表。

它吸收 Claude Code task board 的关键经验：

- 团队边界对应独立任务看板。
- 任务是并发控制和上下文交接原语。
- 依赖必须使用任务 ID 图，而不是自然语言标题。
- worker 之间的通信必须写入消息表，普通输出不算通信。
- 任务完成必须有产物和验证记录。

## v2 表

`python src/main.py --agent-team-v2-setup` 会创建以下表：

| 配置键 | 作用 |
|---|---|
| `v2_objectives` | 目标池 |
| `v2_workers` | worker 注册、心跳、当前任务 |
| `v2_tasks` | 核心任务看板 |
| `v2_task_edges` | 任务 ID 依赖图 |
| `v2_claims` | 领取竞争记录 |
| `v2_messages` | agent 间消息 |
| `v2_artifacts` | 任务产物 |
| `v2_verifications` | 验证记录 |
| `v2_events` | 审计事件 |

## 协议

状态机：

```text
pending -> claimed -> in_progress -> completed
pending -> blocked
claimed/in_progress -> failed
claimed/in_progress -> expired
```

领取规则：

- worker 只看同一个 `objective_id` 下的任务。
- 非 manager worker 只能领取与自己角色匹配的任务。
- manager worker 可以兜底领取任意角色任务。
- 所有 blocker 完成前，任务不可领取。
- worker 先写 `v2_claims`，再按 `created_at, claim_id` 判定赢家。
- 输掉 claim 的 worker 不允许写产物或完成任务。
- `claimed` / `in_progress` 任务的 `lease_until` 过期后，会回到 `pending` 并释放 owner，供其他 worker 重新领取。

完成规则：

- task 写入 artifact 后才能置为 `completed`。
- worker 完成任务后必须给 `team-lead` 写 message。
- worker 执行异常时必须写入失败事件，并把任务退回 `pending`，避免控制面永久卡住。
- objective 只有在所有任务完成且每个任务有 PASS verification 后才能完成。

## 命令

离线协议验证：

```bash
python src/main.py --agent-team-v2-memory-demo --agent-team-max-tasks 4
```

真实 Base 表初始化：

```bash
python src/main.py --agent-team-v2-setup
```

真实 Base 多进程 demo：

```bash
python src/main.py --agent-team-v2-demo --workers 5 --agent-team-max-tasks 4
```

单 worker 进程：

```bash
python src/main.py --agent-team-v2-worker --objective-id <record_id> --worker-id researcher-1 --worker-role researcher
```
