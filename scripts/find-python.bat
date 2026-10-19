@echo off
REM ============================================================
REM find-python.bat - 解析项目 Python 解释器（供其他 .bat 以 call 方式复用）
REM
REM 背景（W24 构建缺陷）：PATH 里的裸 python 可能指向已删除 / 32 位安装，
REM 导致脚本不可复现甚至直接失败。本脚本显式解析并导出 PYTHON_EXE。
REM
REM 优先级：
REM   1) 环境变量 MRRS_PYTHON（显式覆盖）
REM   2) %PROJECT_ROOT%\backend\.venv\Scripts\python.exe
REM   3) py -3.11 启动器（解析其真实解释器绝对路径）
REM   4) 全部不可用 -> 打印修复指引并 exit /b 1
REM
REM 成功：设置 PYTHON_EXE（绝对路径），errorlevel=0
REM 失败：errorlevel=1（调用方应中止）
REM 注意：不得使用 setlocal —— 变量必须泄漏给调用方
REM ASCII 输出：避免 Windows 控制台 cp936/cp1252 编码差异
REM ============================================================
set "PYTHON_EXE="
for %%i in ("%~dp0..") do set "PROJECT_ROOT=%%~fi"

if defined MRRS_PYTHON (
    if exist "%MRRS_PYTHON%" (
        set "PYTHON_EXE=%MRRS_PYTHON%"
    ) else (
        echo [WARN] MRRS_PYTHON is set but not found: %MRRS_PYTHON%
    )
)

if not defined PYTHON_EXE (
    if exist "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe" (
        set "PYTHON_EXE=%PROJECT_ROOT%\backend\.venv\Scripts\python.exe"
    )
)

if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('py -3.11 -c "import sys;print(sys.executable)" 2^>nul') do (
        if exist "%%i" set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE (
    echo.
    echo [ERROR] No usable Python 3.11 interpreter found.
    echo   Missing: "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe"
    echo   Fallback "py -3.11" is unavailable too.
    echo   Fix: install 64-bit Python 3.11, then rebuild the venv:
    echo     cd backend ^&^& py -3.11 -m venv .venv
    echo     cd backend ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
    echo   Or set MRRS_PYTHON to an explicit interpreter path.
    exit /b 1
)

echo [python] %PYTHON_EXE%
exit /b 0
