@echo off
chcp 65001 >nul
echo ============================================================
echo   帮扶管理信息系统 - 磁盘清理工具
echo ============================================================
echo.
echo  [1] 预览清理内容
echo  [2] 执行清理
echo  [3] 安装每周自动清理任务（管理员权限）
echo  [0] 退出
echo.
set /p choice="请选择: "

REM 显式解析项目 Python（PATH 里的裸 python 可能指向已删除/32 位安装）
call "%~dp0find-python.bat"
if errorlevel 1 (
    pause
    exit /b 1
)

if "%choice%"=="1" (
    "%PYTHON_EXE%" "%~dp0cleanup.py"
    pause
) else if "%choice%"=="2" (
    "%PYTHON_EXE%" "%~dp0cleanup.py" --execute
    pause
) else if "%choice%"=="3" (
    echo 需要管理员权限...
    "%PYTHON_EXE%" "%~dp0cleanup.py" --schedule
    pause
) else (
    echo 已取消
)
