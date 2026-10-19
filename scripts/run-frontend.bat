@echo off
chcp 65001 >nul
title 前端服务
REM 由 scripts\start-all.bat 在独立窗口调用；也可单独双击运行。
cd /d "%~dp0..\frontend"
where npm >nul 2>&1
if errorlevel 1 (
    echo.
    echo 前端启动失败：未找到 npm，请安装 Node.js 22+ 并重试。
    pause
    exit /b 1
)
if defined MRRS_DRY_RUN (
    echo [dry-run] cd /d "%~dp0..\frontend" ^&^& npm run dev
    exit /b 0
)
echo 前端开发服务器启动中（http://localhost:5173）... 停止请按 Ctrl+C 或关闭本窗口
call npm run dev
pause
