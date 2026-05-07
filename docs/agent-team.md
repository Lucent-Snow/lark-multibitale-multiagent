# Agent-Team 协议

## 1. 定位

Agent-Team 是当前主工作流。它围绕单个用户目标组建临时 AI 团队：

- `Leader`：设计团队并创建任务计划。
- `Worker`：领取并执行匹配角色的任务。
- `ObjectiveStore`：持久化目标和任务状态。
- `BaseObjectiveStore`：基于飞书 Base 实现 store。

当前实现采用“一目标一张飞书 Base 表”。

## 2. 核心契约

协议定义在 `src/agent_team/contracts.py`。

### WorkerSpec

Leader 生成的 worker 身份：

```text
worker_id
name
role
prompt
```

### TaskPlan

任务持久化前的计划：

```text
subject
description
role
blocked_by_subjects
```

### Task

持久化后的任务行：

```text
task_id
objective_id
subject
description
role
status
owner
attempt_count
depends_on
artifact
artifact_title
verdict
issues
created_at
```

## 3. 状态机

当前任务状态：

```text
pending -> in_progress -> completed
pending -> in_progress -> pending     # 验证失败，允许重试
pending -> in_progress -> failed      # 验证失败，重试耗尽
pending -> in_progress -> pending     # 执行异常，清空 owner
```

当前后端没有持久化 `claimed` 状态。领取动作通过写入 `owner` 表示，随后 worker 将任务标记为 `in_progress`。

## 4. 规划规则

`Leader.plan(title, description, max_tasks)` 返回：

```text
list[WorkerSpec], list[TaskPlan]
```

配置 LLM 时，Leader 要求模型返回 JSON：

- `workers`：worker ID、名称、角色、prompt。
- `tasks`：任务标题、描述、角色、依赖任务标题。

解析规则：

- 非法 JSON 会 fallback 到确定性计划，除非 `allow_fallback=False`。
- 重复任务标题会被拒绝。
- 未知角色会归一化为 `manager`。
- 指向未知任务标题的依赖会被丢弃。
- 每个任务描述会补充共享目标上下文。

Fallback 任务角色包含：

- `researcher`
- `editor`
- `analyst`
- `reviewer`

Fallback worker 当前包含 researcher、editor、reviewer；执行阶段仍可使用 manager worker 做兜底。

## 5. 领取规则

`Worker._claim_next()` 按 `task_id` 排序扫描任务。

任务可领取条件：

- `status == pending`；
- `owner` 为空；
- `depends_on` 中的所有任务标题都已经完成；
- worker 角色匹配任务角色，或 worker 角色是 `manager`。

领取通过更新任务行实现：

```text
owner = worker_id
```

如果更新后的 owner 与当前 worker 一致，worker 继续执行。Base API 负责真实持久化；内存 store 在测试和离线 demo 中使用锁保证线程安全。

## 6. 执行规则

领取成功后：

1. Worker 更新 `status = in_progress`。
2. Worker 调用 `artifact_fn(task)`。
3. Worker 调用 `verification_fn(task, artifact)`。
4. Worker 写回结果：
   - 通过：`completed` + artifact + `PASS`。
   - 未通过但可重试：`pending` + attempt_count + issues。
   - 未通过且重试耗尽：`failed` + final issues。

离线测试默认 artifact 生成是确定性的。真实运行使用 `src/agent_team/demo.py` 中的 `make_llm_artifact_fn()`。

## 7. 验证规则

真实验证使用 `make_llm_verification_fn()`。

Verifier 必须返回 JSON：

```json
{
  "verdict": "PASS",
  "issues": "",
  "suggestions": ""
}
```

规则：

- Verdict 统一转为大写。
- 未知 verdict 转为 `FAIL`。
- 非 JSON 输出转为 `FAIL`。
- 自称存在阻塞性缺口时强制 `FAIL`，即使模型返回 `PASS`。
- `PASS` 写入 `verdict`；问题说明写入 `issues`。

## 8. Base 存储

`BaseObjectiveStore` 创建或复用：

```text
obj_<objective_id>
```

字段定义在 `src/agent_team/base_store.py` 的 `FIELDS` 中。

目标元数据行通过以下字段值识别：

```text
role = "__objective_meta__"
```

Dashboard 通过列出所有以 `obj_` 开头的 Base 表来发现目标。

## 9. 命令

离线协议 demo：

```bash
python src/main.py --agent-team-memory-demo --agent-team-max-tasks 4
```

真实 Base-backed objective：

```bash
python src/main.py run --base-token <TOKEN> --objective "目标标题" --description "目标描述" --max-tasks 4 --workers 3 --timeout 600
```

单 worker：

```bash
python src/main.py worker --base-token <TOKEN> --objective-id <OBJECTIVE_ID> --worker-id researcher-1 --worker-role researcher
```

前端 bridge：

```bash
cd frontend
npm run dev:all
```
