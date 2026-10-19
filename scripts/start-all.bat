@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   帮扶管理信息系统 - 一键启动
echo ========================================
echo.

:: 设置项目根目录
set "PROJECT_ROOT=%~dp0.."

:: 检查并清理后端端口
echo [1/3] 清理后端端口 (8000)...
netstat -ano 2>nul | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo   端口 8000 已被占用，正在清理...
    for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    echo   后端端口已清理
) else (
    echo   后端端口空闲
)

:: 启动后端与前端（各自独立窗口；窗口标题与 stop-all.bat 的清理规则一致）
:: 两端脚本内部显式解析项目 Python / npm，不再依赖 PATH 里的裸 python
echo.
echo [2/3] 启动后端服务...
cd /d "%PROJECT_ROOT%"

start "" "%~dp0run-backend.bat"
timeout /t 3 /nobreak >nul
start "" "%~dp0run-frontend.bat"

:: 等待后端启动（使用 PowerShell 替代 curl）
echo.
echo [3/3] 等待后端服务就绪...
set /a count=0
:wait_backend
timeout /t 2 /nobreak >nul
    netstat -ano 2>nul | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo   后端服务已就绪
    goto backend_ready
)
set /a count+=1
echo   ... 等待中 (!count!/30)
if !count! lss 30 goto wait_backend
echo   后端服务启动超时, 请查看后端窗口排查...

:backend_ready

:: 等待额外2秒确保静态文件服务就绪
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   启动完成!
echo ========================================
echo.
echo   访问地址: http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo.
echo   默认管理员账号: admin
echo   密码: 请查看后端服务窗口的启动日志
echo.
echo   提示: 需要关闭"帮扶管理信息系统-后端"窗口
echo         要停止系统时直接关闭该窗口即可
echo ========================================
echo.

:: 自动打开浏览器
start http://localhost:8000

pause
