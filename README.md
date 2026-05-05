# Lark Base Multi-Agent Network

> 基于飞书多维表格的虚拟员工协作系统 —— 一个由 AI Agent 组成的数字组织

---

## 新手入门

**快速启动项目？→ 查看 [快速入门指南](QUICKSTART.md)**

5分钟快速配置并运行你的第一个 AI 工单系统！

---

## 一、项目概述

本项目是**飞书多维表格 Multi-Agent Network 竞赛**参赛作品，构建了一个由多个 AI Agent 扮演不同业务角色的虚拟组织系统。系统中的 Agent 作为"数字员工"，通过飞书多维表格（Base）OpenAPI 协同工作，完成业务构建、数据流转与智能决策。

### 核心特性

- **多角色 Agent 协作**：3+ 个 AI Agent 扮演不同业务角色，各司其职、协同工作
- **多维表格驱动**：所有业务数据与状态通过飞书多维表格管理
- **全链路流程覆盖**：数据产生 → 状态更新 → Agent 处理 → 决策 → 反馈 → 再流转
- **智能数据分析**：基于运行数据自动生成分析报告与决策建议

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    虚拟员工组织系统                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Agent   │    │  Agent   │    │  Agent   │              │
│  │  运营主管 │    │   编辑   │    │   审核   │              │
│  │ (Manager)│◄──►│ (Editor) │◄──►│(Reviewer)│              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                     │
│       └───────────────┴───────────────┘                     │
│                      │                                       │
│                      ▼                                       │
│            ┌──────────────────┐                             │
│            │  飞书多维表格     │                             │
│            │  (Lark Base)     │                             │
│            │                  │                             │
│            │  ┌────────────┐  │                             │
│            │  │  数据表 1   │  │                             │
│            │  │  数据表 2   │  │                             │
│            │  │  数据表 3   │  │                             │
│            │  └────────────┘  │                             │
│            └──────────────────┘                             │
│                      ▲                                       │
│                      │                                       │
│            ┌──────────────────┐                             │
│            │   LLM Model      │                             │
│            │  (国内大模型)     │                             │
│            └──────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

## 三、核心能力模块

### 3.1 虚拟员工建模

本系统定义了 **3 个核心 Agent 角色**：

| 角色 | Agent 名称 | 职责描述 |
|------|-----------|---------|
| 运营主管 | **Operation Manager** | 负责整体任务分配、进度跟踪、决策审批、报告生成 |
| 内容编辑 | **Content Editor** | 负责内容选题、生产加工、信息录入、质量初筛 |
| 质量审核 | **Quality Reviewer** | 负责内容审核、风险把控、终审放行、反馈优化 |

每个角色包含：
- 角色职责定义（Role Definition）
- 输入/输出规范（I/O Specification）
- 角色协作关系（Collaboration Matrix）

详细定义见各 Agent 源文件中的中文 system prompt

### 3.2 业务系统构建

基于飞书多维表格构建的核心数据模型：

#### 数据表设计

| 表名 | 用途 | 核心字段 |
|------|------|---------|
| `任务台账` | 全局任务状态管理 | 任务ID、标题、状态、负责人、创建时间 |
| `内容库` | 内容素材管理 | 内容ID、标题、摘要、分类、状态 |
| `审核队列` | 审核任务排队 | 审核ID、关联内容、优先级、审核人 |
| `操作日志` | 全链路操作记录 | 时间戳、操作者、操作类型、变更内容 |

#### 字段设计

- **状态字段**：`待处理 / 处理中 / 待审核 / 已发布 / 已归档`
- **关系字段**：表间关联记录，实现数据联动
- **自动化字段**：创建时间、最后修改时间等

技术实现：所有数据操作通过 **飞书多维表格 OpenAPI** 完成

### 3.3 业务运行与协同

#### 完整业务流程

```
选题提案 → 内容生产 → 质量审核 → 发布上线 → 数据反馈 → 优化迭代
   │           │           │          │         │         │
   ▼           ▼           ▼          ▼         ▼         ▼
[Manager]   [Editor]   [Reviewer]  [System] [Manager] [Editor]
              │           │
              └─────┬─────┘
                    ▼
              [Base API]
```

#### 协作示例

1. **Manager** 通过 API 创建新任务，写入任务台账
2. **Editor** 读取待处理任务，生产内容后更新内容库
3. **Reviewer** 从审核队列获取任务，审核后更新状态
4. **Manager** 分析运行数据，生成周报并通过飞书发送

### 3.4 数据分析与报告

系统自动分析业务数据，输出以下成果：

| 报告类型 | 触发条件 | 输出渠道 |
|---------|---------|---------|
| **日报/周报** | 定时触发 | 飞书消息 |
| **数据洞察** | 任务完成统计 | 多维表格 |
| **决策建议** | 流程瓶颈分析 | 报告文档 |

## 四、技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| **大语言模型** | 火山引擎 ARK | 用于 Agent 推理与生成 |
| **业务中枢** | 飞书多维表格 | 数据存储、状态管理、流程驱动 |
| **Agent 框架** | 自研 | Agent 编排与工具调用 |
| **编程语言** | Python | 主开发语言 |
| **API 调用** | 飞书开放平台 SDK | 多维表格 OpenAPI |

详见项目根目录 CLAUDE.md 与各模块源码

## 五、项目结构

```
lark-multibitale-multiagent/
├── README.md                 # 项目说明文档
├── CLAUDE.md                 # AI 协作协议
├── requirements.txt          # Python 依赖
├── config.yaml.example       # 配置文件模板（含 bot/LLM/workflow 完整结构）
├── demo.yaml                 # 演示场景数据（编辑此文件切换演示内容）
├── src/
│   ├── __init__.py
│   ├── main.py               # 系统入口（Auth + LLM + 多 Bot 初始化）
│   ├── auth/
│   │   ├── __init__.py
│   │   └── app_auth.py      # Bot 凭据管理 + Device Code Flow 注册 + Token 缓存
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py        # 火山引擎 ARK LLM 客户端（OpenAI 兼容）
│   ├── agents/              # Agent 角色定义（各自身份独立）
│   │   ├── __init__.py
│   │   ├── manager.py       # 运营主管 Agent — 任务分配、审批、报告
│   │   ├── editor.py        # 内容编辑 Agent — LLM 生成文章
│   │   └── reviewer.py      # 质量审核 Agent — LLM 审核决策
│   ├── base_client/         # 飞书多维表格交互
│   │   ├── __init__.py
│   │   └── client.py        # SDK 封装 + 权限错误自动检测与修复指引
│   └── workflow/            # 业务流程引擎
│       ├── __init__.py
│       └── engine.py        # 选题→生产→审核→发布→归档→报告 全链路调度
```

## 六、技术架构详解

### 认证流程

```
Bot Credentials → app_access_token → lark-oapi SDK → Base API
```

- `src/auth/app_auth.py` 管理 bot 凭据（app_id + app_secret）
- Device Code Flow 用于注册新 bot 应用，运行时通过 bot 凭据获取 app_access_token
- Token 自动缓存与刷新

### LLM 集成

- `src/llm/client.py` 封装火山引擎 ARK（OpenAI 兼容）
- 驱动 Editor（生成文章）、Reviewer（审核质量）、Manager（生成报告）

### Agent 职责

| Agent | LLM 驱动能力 |
|-------|------------|
| **Manager** | 生成运营报告、任务分配决策 |
| **Editor** | 生成真实文章内容 |
| **Reviewer** | 审核内容质量、风险把控 |

## 七、快速开始

### 前置条件

- Python 3.10+
- 飞书企业账号 + 开放平台应用
- 国内大模型 API 访问权限

### 安装部署

```bash
# 克隆仓库
git clone https://github.com/Lucent-Snow/lark-multibitale-multiagent.git
cd lark-multibitale-multiagent

# 安装依赖
pip install -r requirements.txt

# 配置
cp config.yaml.example config.yaml
# 编辑 config.yaml 填入 ARK API key + endpoint_id
```

### 运行系统

```bash
# 首次：注册 3 个 bot 应用（每次会打开浏览器，点"通过"即可）
python src/main.py --register manager
python src/main.py --register editor
python src/main.py --register reviewer

# 演示：编辑 demo.yaml 定制演示场景，然后直接运行
python src/main.py

# 或者 CLI 快速覆盖
python src/main.py --topic "突发新闻" --content-title "深度分析" --category "时政"
```

## 八、参赛约束声明

本项目严格遵守竞赛规则：

| 约束项 | 声明 |
|-------|------|
| **模型限制** | 仅使用国内大模型 API，未进行任何形式的微调 |
| **技术手段** | 采用 RAG、Prompt Engineering、Tool-use 编排 |
| **数据真实性** | 所有操作基于真实 API，未使用 Mock |
| **可复现性** | 评测端可通过行为回放验证系统行为 |

详见项目源码与配置

## 九、交付物清单

| 交付物 | 路径 | 状态 |
|-------|------|------|
| 源代码 | `src/` | ✅ |
| 测试报告 | `tests/` | 🔄 待开发 |
| 技术文档 | `docs/` | 🔄 待开发 |
| 演示材料 | `demo/` | 🔄 进行中 |

## 十、License

本项目基于 MIT License 开源。

---

> **竞赛信息**
> - 竞赛名称：飞书多维表格 Multi-Agent Network
> - 参赛团队：Lucent-Snow
> - 参赛日期：2026
