# 快速入门指南 - 飞书多维表格智能工单系统

> 5分钟快速启动你的第一个 AI 工单系统

## 环境要求

- Python 3.8+
- Git
- 飞书开放平台账号

---

## 第一步：克隆项目

```bash
git clone https://github.com/Lucent-Snow/lark-multibitale-multiagent.git
cd lark-multibitale-multiagent
```

---

## 第二步：安装依赖

```bash
pip install -r requirements.txt
```

**requirements.txt 内容：**
```
lark-oapi>=1.5.0
openai>=1.0.0
pyyaml>=6.0
requests>=2.28
python-dotenv>=1.0.0
```

---

## 第三步：创建飞书应用

### 3.1 创建应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 点击「创建企业自建应用」
3. 填写应用名称（如：工单系统）
4. 获取 **App ID** 和 **App Secret**

### 3.2 配置权限

在开放平台「权限管理」中添加以下权限：

| 权限名称 | 权限标识 |
|---------|---------|
| 查看、评论和编辑多维表格 | bitable:app:readonly |
| 获取多维表格数据 | bitable:app:table:record:readonly |
| 查看与编辑多维表格 | bitable:app:table:record |

### 3.3 创建多维表格

1. 在飞书中创建一个新的多维表格
2. 复制表格链接，获取 **App Token**（格式：`WNRyb8ieVaFd20sM...`）
3. 在表格中创建一个数据表，命名为「工单台账」
4. 复制数据表的 **Table ID**（格式：`tblDCfNTODCTGlJE`）

---

## 第四步：配置项目

### 4.1 创建配置文件

```bash
copy config.yaml.example config.yaml
```

### 4.2 编辑 config.yaml

```yaml
lark:
  app_id: "cli_a97227cdd5f8dcef"
  app_secret: "你的App Secret"
  base_token: "你的多维表格App Token"

agents:
  manager:
    name: "运营主管"
    ark_api_key: "你的火山引擎ARK API Key"  # 可选，用于AI智能决策
```

### 4.3 配置 .env 文件（可选）

```bash
copy .env.example .env
```

编辑 `.env`：
```
LARK_APP_ID=cli_a97227cdd5f8dcef
LARK_APP_SECRET=你的App Secret
ARK_API_KEY=你的ARK_API_KEY
```

---

## 第五步：运行工单系统

### 快速测试

```bash
cd src
python lark_tools.py
```

### 创建新工单

```python
from lark_tools import create_ticket, get_pending_tickets

# 创建工单
result = create_ticket(
    title="【Bug】用户无法登录",
    description="点击登录按钮无响应",
    priority="紧急",
    ticket_type="Bug",
    source="用户反馈"
)
print(result)

# 查询待分派工单
print(get_pending_tickets())
```

### 工单状态管理

```python
from lark_tools import assign_ticket, update_ticket_status, close_ticket

# 分派工单
assign_ticket("record_id", "张三")

# 更新状态
update_ticket_status("record_id", "处理中")

# 关闭工单
close_ticket("record_id", "已修复")
```

### 获取统计报表

```python
from lark_tools import get_daily_summary, get_statistics

# 生成日报
print(get_daily_summary())

# 详细统计
print(get_statistics())
```

---

## 常见问题

### Q1: 权限不足错误

**错误**: `code: 91403, msg: Forbidden`

**解决**:
1. 在飞书开放平台「权限管理」中确认已添加多维表格相关权限
2. 将应用添加到多维表格的「协作者」中
3. 如果是多维表格所有者，确保应用权限级别正确

### Q2: Token 获取失败

**错误**: `Failed to get token: app secret invalid`

**解决**:
1. 检查 `config.yaml` 中的 `app_secret` 是否正确
2. 确保 App Secret 没有前后空格
3. 在飞书开放平台重新获取 App Secret

### Q3: 多维表格 API 筛选失败

**错误**: `code: 1254018, msg: InvalidFilter`

**解决**:
- 当前版本使用客户端过滤，不依赖服务端筛选语法

### Q4: 中文字符编码错误

**错误**: `UnicodeEncodeError: 'gbk' codec can't encode character`

**解决**:
- Windows 终端环境变量设置：`chcp 65001`
- 或使用 Python 输出重定向到文件

---

## 项目结构

```
lark-multibitale-multiagent/
├── src/
│   ├── lark_tools.py       # 工单系统核心工具
│   ├── main.py             # 主程序入口
│   ├── feishu_client.py    # 飞书客户端封装
│   ├── agents/              # AI Agent 模块
│   │   ├── manager.py      # 运营主管 Agent
│   │   ├── editor.py       # 内容编辑 Agent
│   │   └── reviewer.py      # 质量审核 Agent
│   ├── auth/                # 认证模块
│   │   └── app_auth.py     # 飞书认证
│   ├── base_client/         # 飞书API封装
│   │   └── client.py
│   ├── llm/                 # LLM模块
│   │   └── client.py        # 火山引擎ARK客户端
│   └── workflow/            # 工作流引擎
│       └── engine.py
├── config.yaml.example      # 配置模板
├── requirements.txt         # Python依赖
├── README.md               # 项目说明
└── QUICKSTART.md          # 本教程
```

---

## API 工具函数一览

| 函数 | 说明 |
|------|------|
| `create_ticket(title, desc, priority, type, source)` | 创建新工单 |
| `get_pending_tickets()` | 获取待分派工单列表 |
| `query_all_tickets()` | 查询所有工单统计 |
| `assign_ticket(record_id, assignee)` | 分派工单给处理人 |
| `update_ticket_status(record_id, status, note)` | 更新工单状态 |
| `close_ticket(record_id, note)` | 关闭工单 |
| `complete_ticket(record_id, note)` | 完成工单 |
| `get_ticket_info(record_id)` | 获取工单详情 |
| `get_statistics()` | 获取工单统计分析 |
| `get_daily_summary()` | 生成工单日报 |
| `get_sla_warnings()` | 获取SLA预警工单 |
| `batch_assign_tickets(record_ids, assignee)` | 批量分派工单 |

---

## 联系方式

- 项目地址: https://github.com/Lucent-Snow/lark-multibitale-multiagent
- 飞书竞赛: 飞书多维表格 Multi-Agent Network