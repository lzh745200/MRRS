@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo 停止所有服务
echo ========================================
echo.

:: 停止后端服务 (端口 8000)
echo [1/2] 停止后端服务...
set backend_killed=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo   终止进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        set backend_killed=1
    )
)
if !backend_killed! equ 1 (
    echo   ? 后端服务已停止
) else (
    echo   ? 未找到运行中的后端服务
)

:: 停止前端服务 (端口 5173)
echo.
echo [2/2] 停止前端服务...
set frontend_killed=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    echo   终止进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        set frontend_killed=1
    )
)
if !frontend_killed! equ 1 (
    echo   ? 前端服务已停止
) else (
    echo   ? 未找到运行中的前端服务
)

:: 额外清理：关闭所有相关的 cmd 窗口
echo.
echo [额外] 清理服务窗口...
taskkill /FI "WINDOWTITLE eq 后端服务*" //F >nul 2>&1
taskkill /FI "WINDOWTITLE eq 前端服务*" //F >nul 2>&1

echo.
echo ========================================
echo 所有服务已停止
echo ========================================
pause
