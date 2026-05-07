# CLAUDE.md - Lark Base Multi-Agent Network

## 项目概述

飞书多维表格 Multi-Agent Network 竞赛项目，团队为 Lucent-Snow。当前主线是 Agent-Team 数字员工系统：用户给出目标，Leader 拆解任务，多个 Worker 并行执行，飞书 Base 作为控制平面和状态存储，火山引擎 ARK LLM 负责规划、生成和验证。

仓库: `https://github.com/Lucent-Snow/lark-multibitale-multiagent.git`

## 当前主系统

| 子系统 | 路径 | 当前状态 |
|---|---|---|
| Agent-Team | `src/agent_team/` | 主演示路径。Leader 拆解目标，Worker 领取任务，Base 持久化任务/产物/验证。 |
| Feishu Base Client | `src/base_client/` | 单 bot、单 base token 的 `lark-oapi` 封装。 |
| LLM Client | `src/llm/` | Volcengine ARK OpenAI-compatible client。 |
| Frontend Command Center | `frontend/` | Next.js 16 指挥中心，通过 Python bridge 操作 Agent-Team。 |

## 目录结构

```text
/
├── config.yaml.example       # 配置模板：llm + bot
├── config.yaml               # 本地敏感配置，不提交
├── requirements.txt          # Python 依赖
├── README.md                 # 评委阅读入口
├── SETUP.md                  # 部署和演示指南
├── AGENTS.md                 # AI agent 工作规则
├── docs/
│   ├── architecture.md       # 当前架构与数据流
│   └── agent-team.md         # Agent-Team 协议
├── src/
│   ├── main.py               # CLI: memory demo, run, worker
│   ├── agent_team/
│   │   ├── contracts.py      # Task/TaskPlan/WorkerSpec/ObjectStore protocol
│   │   ├── engine.py         # Leader + Worker
│   │   ├── memory_store.py   # 线程安全内存存储
│   │   ├── base_store.py     # 一目标一 Base 表存储
│   │   ├── demo.py           # 内存 demo 和 Base demo runner
│   │   └── dashboard_bridge.py # CLI bridge payloads
│   ├── base_client/client.py # Feishu Base table/record CRUD
│   ├── llm/client.py         # ARK LLM client
│   ├── agents/               # Manager/Editor/Reviewer roles
│   └── workflow/engine.py    # Workflow engine covered by offline tests
├── frontend/
│   ├── package.json
│   └── app/
│       ├── page.tsx          # 指挥中心主页面
│       ├── scenarios.ts      # 预置业务目标
│       └── api/agent-team/   # Next.js API routes
├── scripts/
│   ├── setup_check.py        # 本地配置和 smoke check
│   └── bridge_server.py      # 127.0.0.1:9800 persistent bridge
└── tests/
    ├── test_agent_team.py
    ├── test_workflow.py
    ├── test_config.py
    └── test_base_client.py
```

## Agent-Team 协议要点

- 存储模型是 **one objective, one Base table**，表名为 `obj_<objective_id>`。
- 表内第一类记录是 objective metadata row，`role` 字段使用 `__objective_meta__`。
- 普通 task row 包含 `task_id`、`subject`、`description`、`role`、`status`、`owner`、`attempt_count`、`depends_on`、`artifact`、`verdict`、`issues` 等字段。
- 状态值：`pending`、`in_progress`、`completed`、`failed`。
- Worker 只领取 `pending` 且依赖已完成的任务；非 manager worker 只能领取匹配角色任务，manager 可兜底。
- Claim 当前实现为对 task row 写入 `owner`。
- Verification 当前内联写入 task row 的 `verdict` 和 `issues`，不是独立 verification 表。
- 默认最大重试次数为 `DEFAULT_MAX_ATTEMPTS = 3`。

## CLI 入口

```bash
# 离线协议演示，不调用 Feishu/ARK
python src/main.py --agent-team-memory-demo
python src/main.py --agent-team-memory-demo --objective "AI 团队演示" --objective-description "验证协议。" --agent-team-max-tasks 4

# 真实 Base-backed objective，会调用 ARK 和飞书 Base
python src/main.py run --base-token <TOKEN> --objective "标题" --description "描述" --max-tasks 4 --workers 3 --timeout 600

# 单 worker 进程
python src/main.py worker --base-token <TOKEN> --objective-id <OBJECTIVE_ID> --worker-id researcher-1 --worker-role researcher
```

## Frontend

Next.js 16 App Router，主要页面在 `frontend/app/page.tsx`。

- `npm run dev`: 只启动 Next.js。
- `npm run bridge`: 启动 Python bridge server。
- `npm run dev:all`: 同时启动 bridge 和 Next.js。
- 前端通过 `/api/agent-team/*` routes 调用 `scripts/bridge_server.py`。
- 用户在前端粘贴 Feishu Base URL，前端解析 `/base/<TOKEN>` 并存入 session storage。
- 预置场景在 `frontend/app/scenarios.ts`。

## 依赖

```text
Python: lark-oapi, openai, PyYAML, requests
Frontend: next, react, react-dom, lucide-react, typescript, eslint
```

## 开发约定

- 中文沟通。
- 代码注释和 commit message 用英文。
- 不提交 `config.yaml`、`.credentials.json`、`.tokens.json`。
- Base token 通过 CLI 或前端输入传递，不写入配置或源码。
- 真实 Base/ARK 命令只在明确需要端到端演示时运行。

## 验证

```bash
python -m unittest discover -s tests
python -m compileall -q src tests
python src/main.py --help
python src/main.py --agent-team-memory-demo
python scripts/setup_check.py
cd frontend && npx tsc --noEmit
cd frontend && npm run lint
```
