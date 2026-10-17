@echo off
chcp 65001 >nul 2>&1
title 帮扶管理信息系统 - 开发环境初始化

echo ========================================
echo   帮扶管理信息系统 - 开发环境初始化
echo ========================================
echo.

REM ── 1. Python 虚拟环境 ──
echo [1/4] 初始化 Python 虚拟环境...
cd /d "%~dp0..\backend"

where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请安装 Python 3.11 64-bit
    pause & exit /b 1
)

if not exist ".venv" (
    python -m venv .venv
    echo   虚拟环境已创建
)
call .venv\Scripts\activate
pip install -r requirements.txt -q
echo [OK] Python 依赖安装完成

REM ── 2. 前端依赖 ──
echo [2/4] 安装前端依赖...
cd /d "%~dp0..\frontend"
call npm install --legacy-peer-deps
echo [OK] 前端依赖安装完成

REM ── 3. Pre-commit hooks ──
echo [3/4] 安装 Git hooks...
cd /d "%~dp0.."
pip install pre-commit -q
pre-commit install
echo [OK] Pre-commit hooks 已安装

REM ── 4. 环境文件 ──
echo [4/4] 检查环境配置...
cd /d "%~dp0..\backend"
if not exist ".env" (
    copy .env.example .env >nul
    echo   backend\.env 已从模板创建
) else (
    echo   backend\.env 已存在，跳过
)
cd /d "%~dp0..\frontend"
if not exist ".env" (
    copy .env.example .env >nul
    echo   frontend\.env 已从模板创建
) else (
    echo   frontend\.env 已存在，跳过
)

echo.
echo ========================================
echo   初始化完成!
echo ========================================
echo.
echo 启动开发环境:
echo   后端: cd backend ^&^& .venv\Scripts\python start.py
echo   前端: cd frontend ^&^& npm run dev
echo.
echo 默认账号: admin / zgcZGC733035#  (出厂口令，首次登录强制改密；可用 DEFAULT_ADMIN_PASSWORD 覆盖)
echo API 文档: http://localhost:8000/docs
echo.
pause
