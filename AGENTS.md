# Lark Base Multi-Agent Network

## 技术栈

- Python 3.10+
- 飞书开放平台 SDK: `lark-oapi`
- 火山引擎 ARK: 通过 OpenAI 兼容 SDK 调用
- 配置格式: YAML
- 测试框架: Python 标准库 `unittest`

## 目录结构

- `src/`: 主程序源码
- `src/auth/`: 飞书 bot 注册、凭据读取、`app_access_token` 获取
- `src/base_client/`: 飞书多维表格 SDK 封装
- `src/llm/`: ARK LLM 客户端
- `src/agents/`: Manager、Editor、Reviewer 三个业务 Agent
- `src/workflow/`: 选题、生产、审核、发布、归档、报告的流程编排
- `tests/`: 不依赖真实飞书/ARK 的自动化测试
- `docs/`: 架构、流程和关键设计说明

## 开发命令

```bash
pip install -r requirements.txt
python -m unittest discover -s tests
python -m compileall -q src tests
python src/main.py --help
```

## 配置和敏感文件

- `config.yaml` 从 `config.yaml.example` 复制生成，不提交。
- `.credentials.json` 保存 bot `app_id` / `app_secret`，不提交。
- `.tokens.json` 是 token 缓存，不提交。
- `test_record.py` 是本地手工联调脚本，不提交，也不要作为自动测试运行。
- 表 ID 必须配置在 `config.yaml` 的 `lark.tables` 下；代码运行时不应在业务方法里写死表 ID。

## 模块边界

- `agents` 只表达角色行为，不直接调用飞书 SDK。
- `workflow` 只编排流程，不处理底层 API 细节。
- `base_client` 是唯一封装飞书 Base API 的模块。
- `llm` 是唯一封装模型供应商调用的模块。
- 测试默认使用 fake client / fake LLM，不写入真实多维表格。

## 验证方式

- 普通改动至少运行 `python -m unittest discover -s tests`。
- 语法和导入检查运行 `python -m compileall -q src tests`。
- CLI 参数检查运行 `python src/main.py --help`。
- 端到端演示才运行 `python src/main.py`，它会真实调用 ARK 和飞书 Base，并写入记录。
