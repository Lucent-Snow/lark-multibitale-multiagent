# 部署和演示指南

这份指南描述当前 Agent-Team 版本的部署方式。

## 1. 前置条件

| 依赖 | 用途 |
|---|---|
| Python 3.10+ | 后端、CLI、Agent-Team worker |
| Node.js 18+ | Next.js 指挥中心 |
| 飞书账号和共享空间 | Base 存储和 bot 访问 |
| 飞书开放平台应用 | Base API 使用的 bot 凭据 |
| 火山引擎 ARK 账号 | LLM 规划、生成、验证 |

## 2. 安装依赖

```bash
git clone https://github.com/Lucent-Snow/lark-multibitale-multiagent.git
cd lark-multibitale-multiagent

pip install -r requirements.txt

cd frontend
npm install
cd ..
```

## 3. 创建一个飞书 Bot 应用

在 `open.feishu.cn` 创建一个应用。

需要准备：

- App ID，例如 `cli_xxx`。
- App Secret。
- Base 相关权限，至少包含 `bitable:app`。

在飞书共享空间中新建一个 Base，并把该 bot 应用添加为可编辑成员。真实演示不建议使用个人空间 Base，因为个人空间可能无法把 bot 添加为文档成员。

## 4. 配置本地凭据

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

Base token 运行时传入：

- CLI：`--base-token <TOKEN>`
- 前端：粘贴飞书 Base URL，例如 `https://xxx.feishu.cn/base/<TOKEN>`

## 5. 本地检查

```bash
python scripts/setup_check.py
python -m unittest discover -s tests
python -m compileall -q src tests
python src/main.py --help
python src/main.py --agent-team-memory-demo
```

内存 demo 不需要飞书或 ARK。

## 6. 运行真实 Base 目标

```bash
python src/main.py run ^
  --base-token <TOKEN> ^
  --objective "AI 产品市场调研报告" ^
  --description "为产品决策者准备一份 AI 市场调研报告，包含市场格局、竞品对比、风险和建议。" ^
  --max-tasks 4 ^
  --workers 3 ^
  --timeout 600
```

macOS/Linux 使用 `\` 替代 PowerShell 的 `^`。

预期结果：

- Base 中出现一张新的 `obj_<objective_id>` 表。
- 元数据行保存目标标题和描述。
- 任务行在 `pending`、`in_progress`、`completed` 或 `failed` 状态间流转。
- Worker 完成任务后填入 artifact 和 verification 字段。

## 7. 运行前端

```bash
cd frontend
npm run dev:all
```

打开：

```text
http://localhost:3000
```

操作步骤：

1. 粘贴飞书 Base URL。
2. 在 **任务中心** 启动预置场景或自定义目标。
3. 在 **任务看板** 观察进度、worker、产物和验证结果。

`npm run dev:all` 会启动：

- `scripts/bridge_server.py`，监听 `127.0.0.1:9800`；
- Next.js dev server。

## 8. 常用命令

```bash
# 离线 smoke demo
python src/main.py --agent-team-memory-demo --agent-team-max-tasks 4

# CLI help
python src/main.py --help

# 真实运行
python src/main.py run --base-token <TOKEN> --objective "标题" --description "描述"

# 单 worker
python src/main.py worker --base-token <TOKEN> --objective-id <OBJECTIVE_ID> --worker-id manager-1 --worker-role manager

# 前端类型检查
cd frontend && npx tsc --noEmit

# 前端 lint
cd frontend && npm run lint
```

## 9. 常见问题

### Bot 不能访问 Base

典型现象：

- `Forbidden`
- `17910003`
- 飞书 SDK 返回权限相关错误

处理方式：

1. 确认 Base 位于共享空间。
2. 把 bot 应用添加为 Base 可编辑成员。
3. 确认应用已开通所需 Base 权限。

### 缺少 bot 凭据

如果 `BaseClient` 报缺少凭据，检查 `config.yaml`：

```yaml
bot:
  app_id: "cli_xxx"
  app_secret: "xxx"
```

### ARK 请求失败

检查：

- `llm.api_key`
- `llm.endpoint_id`
- ARK endpoint 是否可用
- 当前网络是否能访问火山引擎 ARK

### 前端无法加载数据

先单独启动 bridge：

```bash
cd frontend
npm run bridge
```

然后访问：

```text
http://127.0.0.1:9800/snapshot?baseToken=<TOKEN>
```

如果 bridge 返回错误，优先修复 Python / 飞书配置。

## 10. 演示建议

- 用 `python src/main.py --agent-team-memory-demo` 展示无需外部服务的核心协议。
- 面向评委优先使用前端，因为它能可视化目标、任务、worker、产物和验证。
- 需要终端版真实演示时使用 `python src/main.py run ...`。
- 面向评委演示时优先使用 README 和本文档中的命令。
