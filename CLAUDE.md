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
| **Base Client** | `src/base_client/client.py` | 飞书多维表格 SDK 封装（含权限错误检测） |
| **Demo** | `demo.yaml` | 演示场景数据，编辑此文件切换演示内容 |

### 数据流

1. `app_auth.py` 加载 3 个 bot 凭据（manager / editor / reviewer），各自获取 `app_access_token`
2. `main.py` 为每个 bot 创建独立 `BaseClient`，3 个 Agent 各自身份操作 Base
3. `demo.yaml` 提供演示数据（topic / content 参数），CLI `--topic` 等可覆盖
4. `llm/client.py` 为 3 个 Agent 提供 LLM 能力
5. `workflow/engine.py` 编排 选题→生产→审核→发布→归档→报告 全链路

### 依赖

- 飞书 SDK: `lark-oapi>=1.5.0`
- LLM: `openai>=1.0.0`（火山引擎 ARK，OpenAI 兼容接口）
- YAML: `pyyaml>=6.0`
- HTTP: `requests>=2.28`

## 开发约定

- 主开发语言: Python
- 配置: `config.yaml`（含敏感信息，不提交）
- 演示数据: `demo.yaml`（可提交，AI 可编辑切换演示场景）
- 代码注释和 commit message: 英文
- Agent prompt: 中文角色描述

## 运行

```bash
# 首次：注册 3 个 bot 应用
python src/main.py --register manager
python src/main.py --register editor
python src/main.py --register reviewer

# 日常演示：编辑 demo.yaml 后直接运行
python src/main.py

# CLI 覆盖演示数据
python src/main.py --topic "突发新闻" --content-title "深度分析"
```

