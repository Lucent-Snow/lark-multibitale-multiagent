@echo off
cd /d "%~dp0"
echo ================================
echo 一键推送代码并创建PR
echo ================================
echo.

echo [1/3] 切换到SSH协议...
git remote set-url origin git@github.com:Lucent-Snow/lark-multibitale-multiagent.git

echo.
echo [2/3] 推送分支到GitHub...
git push origin feature/quickstart-guide

echo.
echo [3/3] 创建Pull Request...
"C:\Program Files\GitHub CLI\gh.exe" pr create --repo Lucent-Snow/lark-multibitale-multiagent --base dev --head feature/quickstart-guide --title "feat: 添加新人快速入门指南和工单系统优化" --body "## 变更内容

- 新增 QUICKSTART.md - 5分钟快速入门指南
- 更新 README.md - 添加新手入口提示
- 更新 src/lark_tools.py - 工单系统核心工具

## 核心功能

- 工单创建与管理
- 待分派工单查询
- 工单统计分析
- SLA超时预警
- 批量分派操作
- 日报自动生成

## 测试验证

所有功能已测试通过，系统运行正常。"

echo.
echo ================================
echo 完成！请检查浏览器中的PR页面
echo ================================
pause