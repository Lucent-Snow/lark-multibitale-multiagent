@echo off
cd /d "%~dp0"
echo ================================
echo 推送到新仓库
echo ================================

echo [1/2] 推送到 beicheny944-maker/lark-multibitale-multiagent-ybc
git push -u ybc main --force

echo.
echo [2/2] 推送 feature/quickstart-guide 分支
git push -u ybc feature/quickstart-guide

echo.
echo ================================
echo 完成！
echo ================================
pause