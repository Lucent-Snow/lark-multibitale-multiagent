# Lark Base Multi-Agent Network

## 技术栈

- Python 3.10+
- 飞书开放平台 SDK: `lark-oapi`
- LLM: 火山引擎 ARK，通过 OpenAI 兼容 SDK 调用
- 配置格式: YAML
- 后端测试: Python 标准库 `unittest`
- 前端: Next.js 16、React 18、TypeScript、`lucide-react`

## 当前系统定位

项目当前主线是 **Agent-Team 控制平面**：

- 用户提交一个业务目标。
- `Leader` 使用 LLM 拆解 worker 和任务。
- 每个目标在飞书 Base 中创建一张 `obj_<objective_id>` 表。
- 多个 `Worker` 进程按角色领取任务、生成产物、执行 LLM 验证。
- 任务状态、产物、验证结果直接写回同一张目标表。
- Next.js 前端通过 Python bridge 展示目标、任务图、worker 状态和产物。

## 目录结构

- `src/`: 后端源码。
- `src/main.py`: CLI 入口，支持内存 demo、真实 Base objective run、单 worker 进程。
- `src/agent_team/`: Agent-Team 核心协议、内存存储、Base 存储、demo runner、dashboard bridge。
- `src/base_client/`: 飞书 Base API 封装，是唯一直接调用 `lark-oapi` 的业务模块。
- `src/llm/`: ARK LLM 客户端，是唯一封装模型供应商调用的模块。
- `src/agents/`: Manager、Editor、Reviewer 角色实现。
- `src/workflow/`: 业务流程编排和离线测试目标。
- `frontend/`: Next.js 指挥中心。
- `frontend/app/api/agent-team/`: 前端 API routes，代理到 Python bridge。
- `scripts/`: 本地检查和 bridge server。
- `tests/`: 默认不依赖真实飞书/ARK 的自动化测试。
- `docs/`: 架构和协议文档。

## 开发命令

```bash
pip install -r requirements.txt
python -m unittest discover -s tests
python -m compileall -q src tests
python src/main.py --help
python src/main.py --agent-team-memory-demo
python scripts/setup_check.py
```

前端命令：

```bash
cd frontend
npm install
npx tsc --noEmit
npm run lint
npm run dev
npm run dev:all
```

## 真实演示命令

真实演示会调用 ARK 和飞书 Base，并写入记录：

```bash
python src/main.py run --base-token <TOKEN> --objective "目标标题" --description "目标描述" --max-tasks 4 --workers 3 --timeout 600
```

单 worker 调试：

```bash
python src/main.py worker --base-token <TOKEN> --objective-id <OBJECTIVE_ID> --worker-id researcher-1 --worker-role researcher
```

## 配置和敏感文件

- `config.yaml` 从 `config.yaml.example` 复制生成，不提交。
- `config.yaml` 只放 `llm` 与单个 `bot` 配置。
- Base token 不写入 `config.yaml`，通过 CLI 参数或前端 Base URL 传入。
- `.credentials.json` 是运行时生成/维护的 bot 凭据缓存，不提交。
- `.tokens.json` 是 token 缓存，不提交。
- `test_record.py` 是本地手工联调脚本，不提交，也不要作为自动测试运行。
- 不要在业务方法中写死真实 Base token、表 ID、ARK key 或 app secret。

## 模块边界

- `agent_team` 表达 Leader / Worker 协议、任务状态机和存储抽象。
- `BaseObjectiveStore` 采用“一目标一表”模型。
- `base_client` 是唯一封装飞书 Base API 的模块。
- `llm` 是唯一封装模型供应商调用的模块。
- `frontend` 不直接调用飞书 SDK，只通过 API route 和 Python bridge 调后端。
- `tests` 默认使用 fake client / fake LLM / in-memory store，不写真实多维表格。
- 文档、命令和测试说明必须和 `src/main.py`、`config.yaml.example`、`frontend/package.json` 保持一致。

## 验证方式

- 普通 Python 改动至少运行 `python -m unittest discover -s tests`。
- 语法和导入检查运行 `python -m compileall -q src tests`。
- CLI 改动运行 `python src/main.py --help` 和 `python src/main.py --agent-team-memory-demo`。
- 前端改动运行 `cd frontend && npx tsc --noEmit`，并尽量运行 `npm run lint`。
- UI 相关改动需要启动前端并用浏览器工具验证关键页面。
- 端到端演示才运行 `python src/main.py run ...` 或前端一键启动，它会真实调用 ARK 和飞书 Base。

## 协作约定

- 中文沟通。
- 代码注释和 commit message 用英文。
- 最小改动，先读相关代码再改。
- 写完代码必须自测或说明未能验证的原因。
- 每个独立功能点一个 commit，commit message 格式为 `<type>: <summary>`。
