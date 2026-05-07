# 架构说明

## 1. 系统目标

本项目实现一个基于飞书 Base 的多智能体工作流。核心设计不是把 Base 当成最终结果表，而是把 Base 当成 AI 团队的共享控制平面，用来保存任务状态、负责人、产物和验证结果。

当前生产路径是 Agent-Team：

```text
业务目标 -> Leader 规划 -> Base 目标表 -> Worker 进程 -> LLM 验证 -> 前端看板
```

## 2. 运行组件

| 组件 | 路径 | 职责 |
|---|---|---|
| CLI | `src/main.py` | 运行离线内存 demo、真实 Base objective、单 worker 进程。 |
| Leader | `src/agent_team/engine.py` | 把目标拆解为 worker specs 和 task plans。 |
| Worker | `src/agent_team/engine.py` | 领取可运行任务、生成产物、验证输出、更新状态。 |
| 内存存储 | `src/agent_team/memory_store.py` | 测试和离线 demo 使用的线程安全 store。 |
| Base 存储 | `src/agent_team/base_store.py` | 把一个 objective 映射到一张飞书 Base 表。 |
| Base client | `src/base_client/client.py` | 封装 `lark-oapi` 表和记录 CRUD。 |
| LLM client | `src/llm/client.py` | 通过 OpenAI-compatible API 调用火山引擎 ARK。 |
| Dashboard bridge | `scripts/bridge_server.py`、`src/agent_team/dashboard_bridge.py` | 让 Next.js 前端调用 Python / 飞书逻辑。 |
| Frontend | `frontend/` | 启动和观察 objective 的指挥中心。 |

## 3. 存储模型

当前存储模型是“一目标一表”：

```text
飞书 Base app
    |
    +-- obj_<objective_id>
            |
            +-- metadata row
            +-- task row 1
            +-- task row 2
            +-- task row ...
```

每个目标拥有一张独立表，由 `BaseObjectiveStore` 按需创建。

### 目标元数据行

元数据行保存目标标题和描述，识别方式是：

```text
role = "__objective_meta__"
```

### 任务行

每个任务行使用文本字段：

| 字段 | 含义 |
|---|---|
| `task_id` | 飞书 record ID，创建后回写到字段中。 |
| `objective_id` | 目标 / 表标识。 |
| `subject` | 任务标题。 |
| `description` | 任务说明和共享目标上下文。 |
| `role` | 需要的 worker 角色。 |
| `status` | `pending`、`in_progress`、`completed` 或 `failed`。 |
| `owner` | 当前拥有或完成该任务的 worker ID。 |
| `attempt_count` | 重试次数。 |
| `depends_on` | 逗号分隔的依赖任务标题。 |
| `artifact` | Worker 产物。 |
| `artifact_title` | 产物短标题。 |
| `verdict` | `PASS` 或 `FAIL`。 |
| `issues` | 验证问题或重试反馈。 |
| `created_at` | ISO 时间戳。 |

## 4. 目标执行流程

```text
用户提交 title + description
    |
    v
Leader.plan()
    |
    +-- 有 LLM：解析 JSON workers/tasks
    +-- 无 LLM：使用确定性 fallback plan
    |
    v
BaseObjectiveStore 创建 obj_<objective_id>
    |
    v
写入 task rows
    |
    v
启动 Worker 子进程
    |
    v
每个 Worker 循环：
    1. 查找符合自己角色的 pending 任务
    2. 跳过依赖未完成的任务
    3. 写入 owner 领取任务
    4. 标记 in_progress
    5. 生成 artifact
    6. 验证 artifact
    7. 完成、重试或失败
```

## 5. Worker 角色

真实 demo 默认可使用：

- `researcher`
- `editor`
- `analyst`
- `reviewer`
- `manager`

Leader 可以生成自定义 worker specs，但 `select_agent_team_workers()` 会把用户指定的 worker 数量映射到当前可启动的进程角色。`manager` worker 可以兜底处理不匹配的任务。

## 6. 验证和重试

Worker 产物会经过 `verification_fn`。

- `PASS`：任务变为 `completed`，保存产物和结论。
- `FAIL` 且未超过次数：任务回到 `pending`，清空 `owner`，`attempt_count` 加一。
- `FAIL` 且超过次数：任务变为 `failed`。
- verifier 返回非 JSON 时按 `FAIL` 处理。
- 如果 verifier 自称存在阻塞性缺口，例如“无法完成任务”，即使返回 `PASS` 也会强制转为 `FAIL`。

默认重试上限：

```text
DEFAULT_MAX_ATTEMPTS = 3
```

## 7. 前端链路

```text
浏览器
    |
    | 粘贴飞书 Base URL
    v
Next.js 解析 /base/<TOKEN>
    |
    v
Next.js API route
    |
    v
scripts/bridge_server.py at 127.0.0.1:9800
    |
    v
dashboard_bridge.py / BaseObjectiveStore / BaseClient
    |
    v
飞书 Base
```

前端支持：

- Base 连接和 objective 切换。
- 使用 `frontend/app/scenarios.ts` 中的预置场景。
- 自定义目标启动。
- 任务图和任务状态列表。
- Worker 卡片。
- 产物预览。
- 验证状态。
- 对未超过重试上限的失败任务执行重试。

## 8. 离线模式和真实模式

| 模式 | 命令 | 外部调用 |
|---|---|---|
| 内存 demo | `python src/main.py --agent-team-memory-demo` | 无 |
| 单元测试 | `python -m unittest discover -s tests` | 无 |
| 真实 Base run | `python src/main.py run ...` | 飞书 Base + ARK |
| 前端 demo | `cd frontend && npm run dev:all` | 启动目标时调用飞书 Base + ARK |

## 9. 配置边界

`config.yaml` 包含：

```yaml
llm:
  api_key: "ark-xxx"
  endpoint_id: "ep-xxx"

bot:
  app_id: "cli_xxx"
  app_secret: "xxx"
```

Base token 不写入配置。它通过 CLI 参数传入，或由前端从飞书 Base URL 中解析。
