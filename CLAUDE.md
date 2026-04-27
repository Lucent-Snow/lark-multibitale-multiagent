# CLAUDE.md - Lark Multi-Agent Network

## 项目概述

基于飞书多维表格的虚拟员工协作系统，3 个 AI Agent（运营主管、内容编辑、质量审核）通过飞书 Base API 协同工作，由火山引擎 ARK LLM 驱动智能行为。

## 技术架构

```
Bot Credentials → app_access_token → lark-oapi SDK → Base API
                                                        ↓
                                  ARK LLM ← Agent 智能行为
```

### 核心模块

| 模块 | 路径 | 职责 |
|------|------|------|
| **Auth** | `src/auth/app_auth.py` | Bot 凭据管理 + Device Code Flow 注册 + Token 获取 |
| **LLM** | `src/llm/client.py` | 火山引擎 ARK 客户端（OpenAI 兼容） |
| **Agents** | `src/agents/` | Manager、Editor、Reviewer 三角色 |
| **Workflow** | `src/workflow/engine.py` | 流程调度与审核流程 |
| **Base Client** | `src/base_client/client.py` | 飞书多维表格 SDK 封装 |

### 数据流

1. `app_auth.py` 加载 bot 凭据（app_id + app_secret），获取 `app_access_token`
2. `base_client/client.py` 用 app_access_token 调用飞书 Base API
3. `llm/client.py` 为 3 个 Agent 提供 LLM 能力
4. `workflow/engine.py` 编排完整业务流程

### 依赖

- 飞书 SDK: `lark-oapi`（pip 安装）
- LLM: 火山引擎 ARK（OpenAI 兼容接口，需 `openai` 包）
- YAML: `pyyaml`

## 开发约定

- 主开发语言: Python
- 配置: `config.yaml`（含敏感信息，不提交）
- 代码注释和 commit message: 英文
- Agent prompt: 中文角色描述

## 运行

```bash
python src/main.py
```

