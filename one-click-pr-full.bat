@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
title 一键创建 PR

echo.
echo ================================
echo      一键创建 PR 工具
echo ================================
echo.

:: 步骤1: 设置 Git 配置
echo [1/5] 配置 Git 用户信息...
git config user.email "dev@example.com"
git config user.name "Developer"
echo 已配置 Git 用户信息

:: 步骤2: 添加远程仓库
echo.
echo [2/5] 添加远程仓库 ybc...
git remote add ybc https://github.com/beicheny944-maker/lark-multibitale-multiagent-ybc.git 2>nul || echo 远程仓库已存在

:: 步骤3: 推送到主分支
echo.
echo [3/5] 推送 main 分支到新仓库...
git push -u ybc main --force
if %errorlevel% equ 0 (
    echo 成功推送 main 分支
) else (
    echo 推送失败，请手动执行：git push -u ybc main --force
    pause
    exit /b 1
)

:: 步骤4: 推送到功能分支
echo.
echo [4/5] 推送 feature/quickstart-guide 分支...
git push -u ybc feature/quickstart-guide
if %errorlevel% equ 0 (
    echo 成功推送 feature/quickstart-guide 分支
) else (
    echo 推送失败，请手动执行：git push -u ybc feature/quickstart-guide
    pause
    exit /b 1
)

:: 步骤5: 创建 PR
echo.
echo [5/5] 创建 Pull Request...
echo.
echo 请打开浏览器访问：
echo https://github.com/beicheny944-maker/lark-multibitale-multiagent-ybc/pull/new/main
echo.
echo PR 信息建议：
echo ----------------------------------------------------------------------
echo 标题: feat: 添加完整的工单系统代码
echo.
echo 描述:
echo ## 变更内容
echo - 完整的多Agent工单系统
echo - 新增 QUICKSTART.md 新人入门指南
echo - 工单创建、查询、分派、统计功能
echo - SLA超时预警和日报自动生成
echo ----------------------------------------------------------------------

pause
start https://github.com/beicheny944-maker/lark-multibitale-multiagent-ybc/pull/new/main