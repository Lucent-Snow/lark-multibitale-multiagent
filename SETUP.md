# 部署指南 · Deployment Guide

这份指南帮助新人 clone 项目后，**20 分钟内**完成从零到跑通全部 Demo 的部署。

---

## 前提条件

| 依赖 | 用途 | 获取方式 |
|------|------|----------|
| Python 3.10+ | 后端主语言 | python.org |
| Node.js 18+ | 前端 Next.js | nodejs.org |
| 飞书开发者账号 | 创建 Bot 应用 | open.feishu.cn |
| 飞书企业/组织空间 | 共享 Base 存储（Bot 需要成员资格） | 飞书管理后台 |
| 火山引擎 ARK 账号 | LLM 推理 | console.volcengine.com/ark |

---

## Step 1：Clone 并安装依赖

```bash
git clone https://github.com/Lucent-Snow/lark-multibitale-multiagent.git
cd lark-multibitale-multiagent

# Python
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

## Step 2：创建飞书 Bot 应用（3 个）

在 [飞书开放平台](https://open.feishu.cn) 创建 **3 个独立应用**：

| Bot 名 | 用途 | 必需权限 (scopes) |
|--------|------|-------------------|
| **manager** | Leader 拆目标、读任务、回收/重试 | `bitable:app` `im:message` |
| **editor** | Worker 写产出/消息/验证 | `bitable:app` `im:message` |
| **reviewer** | Worker 写产出/审核 | `bitable:app` `im:message` |

每个应用创建后，记录其 **App ID** 和 **App Secret**。

> 为什么 3 个 Bot？每个 Bot 对应一个独立的飞书身份，它们在 Base 中的操作记录会带上不同的"创建者"，方便审计和权限隔离。如果只用 1 个 Bot，所有 Agent 看起来是同一个人。

## Step 3：创建飞书多维表格（Base）

**关键：必须在企业/组织共享空间创建 Base，不能用个人空间。**

> 个人空间的 Base 不支持添加 Bot 为成员，SDK 用 bot token 访问会返回 91403 Forbidden。

操作步骤：
1. 进入飞书 → 云文档 → **共享空间**（或新建一个共享空间）
2. 在共享空间中新建多维表格
3. 点击右上角「…」→「更多」→「添加文档成员」→ 添加 3 个 Bot 应用为成员
4. 权限设为「可编辑」
5. 新建 4 张表（内容流水线用）：`tasks` `contents` `reviews` `logs`
6. 把 Base URL 中的 token（`/base/<TOKEN>`）填入 `config.yaml`

## Step 4：注册 Bot 凭据

```bash
# 把 3 个 Bot 的 app_id / app_secret 写入 config.yaml 的 lark.bots 段
# 然后逐个注册（会打开浏览器授权）：
python src/main.py --register manager
python src/main.py --register editor
python src/main.py --register reviewer
```

注册成功后在项目根目录生成 `.credentials.json` 和 `.tokens.json`。

## Step 5：创建 Agent-Team 控制平面表

```bash
python src/main.py --agent-team-setup
```

终端会打印 9 个 table ID，格式如下：
```
  team_objectives: "tbl3kIgvDRUfF3Mu"
  team_workers: "tblzi3i8kY0DYgWa"
  team_tasks: "tblk9KkxRDfXvoB5"
  ...
```

把这些 ID 填到 `config.yaml` 的 `lark.tables` 下对应的 key 中。

## Step 6：配置 LLM

在 [火山引擎 ARK 控制台](https://console.volcengine.com/ark) 创建推理端点：

1. 开通 ARK 服务
2. 创建 API Key
3. 创建推理端点（推荐 DeepSeek-V3 或类似模型）
4. 把 `api_key` 和 `endpoint_id` 填入 `config.yaml` 的 `llm` 段

## Step 7：验证

```bash
# 完整配置检查
python scripts/setup_check.py

# 内存协议演示（不需要 Base/LLM，总能跑）
python src/main.py --agent-team-memory-demo

# 真实 Base 演示（验证全链路）
python src/main.py --agent-team-base-demo --workers 3 --agent-team-max-tasks 4

# 启动前端
cd frontend && npm run dev
# 浏览器打开 http://localhost:3000
```

## Step 8：前端使用

前端有两个视图：

**任务中心** — 预置 3 个业务场景，一键启动 AI 团队
- 选场景 → 点「一键启动」→ Leader 自动拆目标 → Worker 并行执行

**任务看板** — 实时观察团队运转
- 顶部进度条 + 实时计时
- SVG 任务依赖图（节点会随状态变化）
- 右侧 Worker 卡片 + 事件时间线
- 目标完成时 confetti 庆祝动画 + 自动生成结项报告

---

## 常见问题

### Q: `91403 Forbidden` 或 `PermissionDenied`

**根因**：Bot 不是 Base 的成员。Base 在个人空间的话无法解决。

**解决**：在共享空间重建 Base，并把 3 个 Bot 加为成员。

### Q: `BRIDGE_TIMEOUT` 或 Python bridge 无响应

可能是 Python 环境问题。在前端终端运行：
```bash
python -m src.agent_team.dashboard_bridge snapshot
```
如果报错，根据错误信息排查 config.yaml。

### Q: LLM 调用报错 `ConnectionError`

检查 ARK endpoint 状态（https://console.volcengine.com/ark）。确认 API key 没有过期。

### Q: `Missing lark.tables config for agent-team mode`

说明 `team_*` 表 ID 还没配。先跑 `--agent-team-setup` 然后把打印的 ID 填进去。

---

## 项目架构速览

```
用户定目标 → Leader(LLM)拆解为任务依赖图 → 写入 Base
                                              ↓
Worker 进程(多角色并发) ← 从 Base 认领任务 ← 仲裁(nonce赢家)
       ↓
   LLM 写产出 + LLM 质量验证(PASS/FAIL)
       ↓
   FAIL→自动重试  PASS→任务完成
       ↓
全部完成 → Leader 生成最终报告(LLM综合所有产物/验证)
```

所有状态、产物、消息、验证记录实时写入飞书 Base 的 9 张表中，前端 8 秒轮询刷新。
