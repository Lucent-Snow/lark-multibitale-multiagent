# Lark Base Multi-Agent Network

> 基于飞书多维表格的 AI 数字员工协作系统：输入一个业务目标，Leader 自动拆解任务，多角色 Worker 并行执行、验证，并把全过程沉淀到飞书 Base。

## 项目概述

本项目是飞书多维表格 Multi-Agent Network 场景的参赛作品。系统把飞书 Base 从“结果表格”升级为“多智能体控制平面”：

1. 用户提交一个业务目标。
2. Leader Agent 通过火山引擎 ARK 拆解 worker 和任务。
3. 多个 Worker 进程按角色领取任务、生成产物、执行质量验证。
4. 每个任务的状态、负责人、产物、验证结论都写入飞书 Base。
5. Next.js 指挥中心实时展示目标进度、任务依赖、worker 状态、产物和质量闸门。

当前主演示路径是 `src/agent_team/` 的 Agent-Team 协作协议。

## 评委重点看什么

- **飞书 Base 是控制平面**：每个目标自动创建一张 `obj_<objective_id>` 表，表中保存目标元数据、任务、产物和验证结果。
- **真实多 Agent 协作**：Leader 负责规划，多个 Worker 子进程按 researcher / editor / analyst / reviewer / manager 等角色并行执行。
- **质量闸门**：Worker 的产物必须经过 LLM verifier 判断 `PASS` / `FAIL`，失败会自动重试，超过上限才标记失败。
- **过程可观察**：前端能连接任意飞书 Base URL，查看目标列表、任务图、worker 状态、产物摘要和验证结果。
- **可离线复现**：内存 demo 和单元测试不依赖飞书或 ARK，可稳定验证核心协议。
- **可真实落地**：真实演示路径使用 `lark-oapi` 操作飞书 Base，使用 ARK OpenAI-compatible SDK 调用国内大模型。

## 系统架构

```text
用户目标
  |
  v
Leader Agent（LLM 规划）
  |
  | 创建 obj_<objective_id> 表
  v
飞书 Base
  - 目标元数据行
  - 任务行
  - 依赖字段
  - 产物字段
  - 验证字段
  |
  v
Worker 子进程
  - 按角色领取任务
  - 调用 LLM 生成产物
  - 调用 LLM 执行验证
  - 写回 Base
  |
  v
Next.js 指挥中心
  - 目标列表
  - 任务图
  - worker 状态
  - 产物和验证结果
```

## 技术栈

| 层级 | 技术 | 用途 |
|---|---|---|
| 后端 | Python 3.10+ | Agent 协议、CLI、飞书和 LLM 集成 |
| 飞书 API | `lark-oapi` | Base 表和记录操作 |
| LLM | 火山引擎 ARK | 规划、生成、验证 |
| 配置 | YAML | 本地 `config.yaml` |
| 测试 | Python `unittest` | 离线协议和工作流验证 |
| 前端 | Next.js 16、React 18、TypeScript | 指挥中心和实时看板 |
| 图标 | `lucide-react` | 前端控件和状态展示 |

## 目录结构

```text
lark-multibitale-multiagent/
├── README.md                  # 面向评委的项目介绍
├── SETUP.md                   # 部署和演示指南
├── AGENTS.md                  # AI 编码 agent 工作规则
├── CLAUDE.md                  # AI 助手上下文
├── config.yaml.example        # 本地配置模板
├── requirements.txt           # Python 依赖
├── src/
│   ├── main.py                # CLI 入口：memory demo / run / worker
│   ├── agent_team/            # Leader、Worker、store、dashboard bridge
│   ├── base_client/           # 飞书 Base API 封装
│   └── llm/                   # ARK LLM 客户端
├── frontend/
│   ├── app/page.tsx           # 指挥中心主页面
│   ├── app/api/agent-team/    # Next.js API routes
│   └── package.json           # 前端脚本和依赖
├── scripts/
│   ├── setup_check.py         # 本地配置和 smoke check
│   └── bridge_server.py       # 前端使用的 Python HTTP bridge
├── tests/                     # 离线 unittest 测试
└── docs/
    ├── architecture.md        # 当前架构和数据流
    └── agent-team.md          # Agent-Team 协议
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

### 2. 配置凭据

复制模板：

```bash
cp config.yaml.example config.yaml
```

填写：

```yaml
llm:
  api_key: "ark-xxx"
  endpoint_id: "ep-xxx"

bot:
  app_id: "cli_xxx"
  app_secret: "xxx"
```

Base token 不写入 `config.yaml`，通过 CLI 参数传入，或在前端粘贴飞书 Base URL 自动解析。

### 3. 本地验证

```bash
python scripts/setup_check.py
python -m unittest discover -s tests
python -m compileall -q src tests
python src/main.py --help
python src/main.py --agent-team-memory-demo
```

内存 demo 不需要飞书或 ARK，是验证协议最稳定的入口。

## 真实 Base 演示

先在飞书共享空间创建 Base，把 `config.yaml` 中配置的 bot 添加为可编辑成员，然后运行：

```bash
python src/main.py run ^
  --base-token <BASE_TOKEN> ^
  --objective "本周科技产业周报" ^
  --description "整理一份面向科技行业读者的周报，要求包含趋势、重点事件、影响分析和可发布正文。" ^
  --max-tasks 4 ^
  --workers 3 ^
  --timeout 600
```

macOS/Linux 使用 `\` 替代 PowerShell 的 `^`。

该命令会：

- 调用 Leader 拆解 worker 和任务；
- 在飞书 Base 创建 `obj_<objective_id>` 表；
- 启动多个 Worker 子进程；
- 写入任务状态、产物和验证结果；
- 在终端输出最终任务状态。

## 前端指挥中心

启动 Python bridge 和 Next.js：

```bash
cd frontend
npm run dev:all
```

打开 `http://localhost:3000`，粘贴飞书 Base URL，然后使用：

- **任务中心**：启动预置场景或自定义目标。
- **任务看板**：观察任务进度、worker 状态、产物和质量验证。

前端通过 `127.0.0.1:9800` 的 Python bridge 调用后端 Agent-Team 模块。

## CLI 参考

```bash
# 离线协议演示
python src/main.py --agent-team-memory-demo
python src/main.py --agent-team-memory-demo --objective "AI 团队演示" --objective-description "验证协议。" --agent-team-max-tasks 4

# 真实 Base-backed objective
python src/main.py run --base-token <TOKEN> --objective "标题" --description "目标描述" --max-tasks 4 --workers 3 --timeout 600

# 单 worker 进程
python src/main.py worker --base-token <TOKEN> --objective-id <OBJECTIVE_ID> --worker-id researcher-1 --worker-role researcher
```

## 验证矩阵

| 命令 | 是否调用外部服务 | 用途 |
|---|---:|---|
| `python -m unittest discover -s tests` | 否 | fake / memory store 单元测试 |
| `python -m compileall -q src tests` | 否 | 语法和导入检查 |
| `python src/main.py --help` | 否 | CLI 合约检查 |
| `python src/main.py --agent-team-memory-demo` | 否 | 离线 Agent-Team smoke demo |
| `cd frontend && npx tsc --noEmit` | 否 | 前端类型检查 |
| `cd frontend && npm run lint` | 否 | 前端 lint |
| `python src/main.py run ...` | 是 | 真实飞书 Base + ARK 端到端演示 |

## 文档

- [SETUP.md](./SETUP.md)：部署和演示指南。
- [docs/architecture.md](./docs/architecture.md)：当前系统架构和数据流。
- [docs/agent-team.md](./docs/agent-team.md)：Agent-Team 协议。
- [AGENTS.md](./AGENTS.md)：AI 编码 agent 工作规则。
- [CLAUDE.md](./CLAUDE.md)：AI 助手上下文。

## 参赛说明

- 使用国内模型 API：火山引擎 ARK。
- 使用 prompt engineering、tool use、角色拆分和流程编排，不做模型微调。
- 离线测试不会写入真实飞书 Base。
- 真实演示命令会调用 ARK 和飞书 Base，并写入记录。

## License

MIT License.
