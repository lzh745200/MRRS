@echo off
chcp 65001 >nul
title 后端服务
REM 由 scripts\start-all.bat 在独立窗口调用；也可单独双击运行。
REM 显式解析项目 Python（PATH 里的裸 python 可能指向已删除/32 位安装）。
cd /d "%~dp0.."
call "%~dp0find-python.bat"
if errorlevel 1 (
    echo.
    echo 后端启动失败：未找到可用的 Python 3.11。
    echo 请先运行 scripts\dev-setup.bat 初始化环境，或设置 MRRS_PYTHON。
    pause
    exit /b 1
)
if defined MRRS_DRY_RUN (
    echo [dry-run] cd /d "%~dp0.." ^&^& "%PYTHON_EXE%" "backend\start.py"
    exit /b 0
)
echo 后端服务启动中（http://localhost:8000）... 停止请按 Ctrl+C 或关闭本窗口
"%PYTHON_EXE%" "backend\start.py"
pause
