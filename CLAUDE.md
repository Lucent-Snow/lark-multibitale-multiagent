# CLAUDE.md - Lark Multi-Agent Network

## 项目概述

飞书多维表格多智能体网络竞赛项目（团队: Lucent-Snow）。虚拟员工协作系统，AI Agent 通过飞书 Base 协同工作，火山引擎 ARK LLM 驱动。
仓库: `https://github.com/Lucent-Snow/lark-multibitale-multiagent.git`

## 三大子系统

| 子系统 | 路径 | 说明 |
|--------|------|------|
| **Content Publishing Chain** | `src/workflow/` + `src/agents/` | 三角色（Manager/Editor/Reviewer）内容生产流水线 |
| **Agent-Team v1** | `src/agent_team/` | 任务市场：Leader 拆解目标→Worker 按角色认领→写产出 |
| **Agent-Team v2** | `src/agent_team_v2/` | 控制平面：并发 Worker、认领仲裁、租约过期、重试、质量验证门 |
| **Frontend** | `frontend/` | Next.js 16 任务指挥中心，Python bridge 驱动 |

## 目录结构

```
/
├── config.yaml          # 敏感配置（不提交）
├── config.yaml.example  # 配置模板
├── demo.yaml            # 演示场景数据
├── requirements.txt     # Python 依赖
├── .credentials.json    # Bot 凭据缓存
├── .tokens.json         # OAuth token 缓存
├── docs/
│   ├── architecture.md      # 架构流程图
│   ├── agent-team-mvp.md    # v1 设计文档
│   └── agent-team-v2.md     # v2 协议设计文档
├── src/
│   ├── main.py              # CLI 入口（22 个标志）
│   ├── auth/app_auth.py     # Bot 注册、凭据管理、Token 获取
│   ├── base_client/client.py# 飞书 Base SDK 封装（CRUD、权限检测）
│   ├── llm/client.py        # 火山引擎 ARK（OpenAI 兼容，含重试）
│   ├── agents/              # Manager、Editor、Reviewer 三角色
│   ├── workflow/engine.py   # 内容流水线引擎
│   ├── agent_team/          # v1 任务市场
│   │   ├── contracts.py     # TaskSpec、AgentTeamTask 协议
│   │   ├── engine.py        # Leader + Engine
│   │   ├── memory_store.py  # 内存存储（离线演示）
│   │   ├── base_store.py    # Base 存储
│   │   └── demo.py          # 演示入口
│   └── agent_team_v2/       # v2 控制平面
│       ├── contracts.py     # V2Task、V2Claim、V2TaskEdge 协议
│       ├── schemas.py       # 9 张 Base 表结构定义
│       ├── engine.py        # LeaderV2 + WorkerV2（认领/重试/验证门）
│       ├── memory_store.py  # 线程安全内存存储
│       ├── base_store.py    # Base 存储
│       ├── dashboard_bridge.py # CLI bridge 供前端调用
│       └── demo.py          # 演示入口（内存/多进程）
├── tests/
│   ├── test_config.py       # 6 测试
│   ├── test_base_client.py  # 4 测试
│   ├── test_workflow.py     # 2 测试
│   ├── test_agent_team.py   # 17 测试
│   └── test_agent_team_v2.py# 30 测试（共 59 测试，全部离线 fake）
└── frontend/
    ├── package.json         # Next.js 16、React 18、lucide-react
    ├── app/
    │   ├── page.tsx         # 主仪表盘（Monitor + Mission Control）
    │   └── api/agent-team/  # 6 个 API route → Python bridge
    └── ...
```

## agent_team_v2 协议要点

- **9 张 Base 表**: objectives、workers、tasks、task_edges、claims、messages、artifacts、verifications、events
- **认领仲裁**: 多 Worker 可同时申领同一任务，nonce 最大者胜出
- **租约过期**: 任务有超时，过期自动回收
- **验证门**: 任务完成须经 LLM 验证（PASS/FAIL），FAIL 触发重试
- **重试上限**: DEFAULT_MAX_ATTEMPTS = 3
- **依赖注入**: Worker 可见上游任务产出物

## CLI 入口

```bash
# 内容流水线
python src/main.py                                    # 运行完整内容发布链
python src/main.py --topic "..." --content-title "..." # 覆盖 demo 参数
python src/main.py --poll                              # 轮询模式

# Agent-Team v1
python src/main.py --agent-team-demo                   # 离线演示
python src/main.py --agent-team-base-demo              # 真实 Base 演示

# Agent-Team v2
python src/main.py --agent-team-v2-memory-demo         # 内存协议演示
python src/main.py --agent-team-v2-demo                # 真实 Base 多进程演示
python src/main.py --agent-team-v2-worker              # 运行单个 Worker
python src/main.py --agent-team-v2-setup               # 创建 9 张 v2 Base 表

# 注册 Bot
python src/main.py --register <manager|editor|reviewer>

# 调参
--objective --objective-description --workers --agent-team-max-tasks --agent-team-timeout
```

## Frontend

Next.js 16 App Router，单页两视图：

- **Monitor（任务看板）**: 连接状态、指标面板、任务流图、Worker 卡片、事件日志。8 秒自动刷新。
- **Mission Control（任务中心）**: 新建目标表单、执行参数配置（任务数/Worker数/超时/运行模式）。

后端通过 Next.js API route → `dashboard_bridge.py` 子进程与 Base 交互。写操作需 `x-agent-team-token` 认证。

## 依赖

```
# Python (requirements.txt)
lark-oapi>=1.5.0  openai>=1.0.0  PyYAML>=6.0  requests>=2.28

# Frontend (package.json)
next ^16.2.4  react ^18.3.1  lucide-react ^0.468.0  typescript ^5.7.2
```

## 开发约定

- 主语言: Python + TypeScript
- 配置: `config.yaml`（含敏感信息，不提交）
- 演示数据: `demo.yaml`（可提交，AI 可编辑切换演示场景）
- 代码注释和 commit message: 英文
- Agent prompt: 中文角色描述

## 验证

```bash
python -m unittest discover -s tests    # 59 测试，全部离线
python -m compileall -q src tests
python src/main.py --help
cd frontend && npx tsc --noEmit        # TypeScript 类型检查
```
