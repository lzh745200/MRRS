# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 统一打包配置 - 跨平台 / x64-x86 通用版
将 FastAPI 后端打包为 onedir 目录模式可执行程序 assistance-backend(.exe)，
包含所有依赖（可执行文件 + _internal/ 依赖目录）。

说明:
  - 产物架构由运行时的 Python 解释器架构决定（64-bit Python -> x64 exe,
    32-bit Python -> x86 exe），因此无需维护两份 spec。
  - onedir 模式（ADR-0006）：免每次启动解压 %TEMP%（onefile 冷启动 3 分钟+
    杀软误报画像），examine 单一目录便于白名单审批。CI 的 extraResources
    与 electron main.js 均按目录布局取用。
  - 前端静态资源不打包进后端产物，由 Electron 通过 FRONTEND_DIST_PATH
    环境变量单独提供（resources/frontend/），节省约 15MB 体积。
  - console=False：无控制台窗口，由 Electron 主进程管理生命周期。
版本: 1.5.0
"""

import os
import sys
from pathlib import Path

from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import collect_submodules

# ========== 路径定义（使用 PyInstaller 预定义的 SPEC） ==========
# SPEC 是 PyInstaller 在解析 spec 文件时自动注入的变量，表示 spec 文件的完整路径
backend_dir = os.path.dirname(os.path.abspath(SPEC))          # backend 目录
project_root = os.path.dirname(backend_dir)                  # 项目根目录

# sys.path 确定性（v1.11.3 事故修复）：Docker 构建 CWD=/build 与 spec 目录不一致时，
# collect_submodules('app') 需要 import app 才能枚举子模块——不插入路径会静默返回
# 空列表，47 个动态业务路由全部缺失（Kylin 真机 403 事故根因）
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
resources_dir = os.path.join(project_root, 'resources')

# ========== 数据文件列表 ==========
# 注意：
#   - 不打包 resources/frontend —— Electron 通过 extraResources 单独提供，
#     后端启动时通过 FRONTEND_DIST_PATH 环境变量定位前端静态资源。
#   - 不打包 app/ 源码目录（ADR-0006）：app 包经 collect_submodules 进入 PYZ
#     字节码，alembic env.py 的 `import app.models` 由冻结导入解析；
#     alembic/ 版本脚本本身是运行时按路径扫描的文件，必须保留。
datas = [
    (os.path.join(backend_dir, 'alembic'), 'alembic'),
    (os.path.join(backend_dir, 'alembic.ini'), '.'),
    (os.path.join(backend_dir, '.env.example'), '.'),
]

# 自动收集 prophet 包数据（如果存在；x86/ARM64 构建时可能未安装，自动跳过）。
# prophet 仍为可选依赖（trend_prediction_service 函数级延迟导入，缺失时降级），
# 其数据文件无法由 Analysis 自动发现，故按存在性条件收集。
import importlib.util as _ilu
_prophet_spec = _ilu.find_spec('prophet')
if _prophet_spec and _prophet_spec.submodule_search_locations:
    _prophet_dir = list(_prophet_spec.submodule_search_locations)[0]
    datas.append((_prophet_dir, 'prophet'))

# ========== 二进制文件列表 ==========
binaries = []

# ========== 隐藏导入 ==========
# 原则（ADR-0006）：app.* 全量由下方 collect_submodules('app') 收集，不再手写；
# 已删除依赖（aiosqlite/jieba/bs4/prometheus_client/prophet）不再列出。
# 仅保留「延迟导入 / 动态发现，静态分析易漏」的第三方隐藏导入。
hiddenimports = [
    # FastAPI 和 Web 框架核心（uvicorn 各组件按字符串动态加载，必须显式列出）
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.middleware.cors',
    'fastapi.middleware.gzip',
    'starlette',
    'starlette.middleware.sessions',
    'starlette.templating',
    'anyio._backends._asyncio',

    # SQLAlchemy 核心
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.ext.asyncio',
    'sqlalchemy.ext.declarative',
    'alembic.runtime.migration',

    # Pydantic
    'pydantic_settings',
    'pydantic_core',

    # 认证和安全
    'jwt',
    'jwt.exceptions',
    'passlib.context',
    'passlib.handlers.bcrypt',
    'passlib.handlers.pbkdf2',
    'passlib.handlers.sha2_crypt',
    'bcrypt',
    'pyotp',
    'qrcode.image.svg',

    # 工具库
    'python_multipart',
    'dotenv',
    'diskcache',
    'dateutil.tz',
    'pytz',
    'filelock',

    # 日志
    'pythonjsonlogger.jsonlogger',

    # 数据处理
    'openpyxl.styles',
    'openpyxl.utils',
    'pandas.core',
    'pandas.io.excel',
    'numpy.core._multiarray_umath',

    # PDF 导出（reportlab 在 report_service 内函数级延迟导入,
    # 自动探测可能遗漏; 缺失时桌面端 PDF 导出降级为 501）
    'reportlab',
    'reportlab.pdfgen',
    'reportlab.lib.pagesizes',

    # 文件处理
    'PIL.Image',

]

# Windows 平台特定隐藏导入
if is_win:
    hiddenimports.append('psutil._pswindows')

# 自动收集 app 包下的所有子模块（避免手动添加遗漏）
hiddenimports += collect_submodules('app')

# ========== 排除不需要的模块（减少打包体积，避免冲突） ==========
excludes = [
    'pytest', 'pytest_asyncio', 'pytest_cov', 'pytest_mock',
    'hypothesis', 'flake8', 'black', 'mypy',
    'tkinter', 'test', 'tests',
    'matplotlib', 'IPython', 'jupyter',
    'notebook', 'spyder', 'pylint',
    'docx', 'apscheduler',
    # 注意：mammoth 不再排除（policy.py 用于 .docx → HTML 转换，是运行时依赖）
]

# ========== Analysis 阶段 ==========
a = Analysis(
    [os.path.join(backend_dir, 'start.py')],
    pathex=[backend_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=None,                     # 不加密字节码
    noarchive=False,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)

# ========== PYZ 阶段 ==========
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ========== EXE 阶段（onedir：exe 仅含引导器，依赖在 COLLECT 目录内） ==========
icon_path = os.path.join(resources_dir, 'icons', 'app-circle.ico')
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,           # onedir：二进制与数据交给 COLLECT
    name='assistance-backend',       # 统一名称（非 assistance-management-backend）
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # 禁用 UPX 压缩以避免某些兼容性问题
    upx_exclude=[],
    console=False,                   # 不显示控制台窗口（适合 GUI 服务）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,                # 架构由 Python 解释器决定，无需指定
    codesign_identity=None,          # macOS 专用；Windows 代码签名由 CI 构建后
    entitlements_file=None,          # 用 signtool 完成（W6-T1，build-windows.yml）
    icon=icon_path if os.path.exists(icon_path) else None,
)

# ========== COLLECT 阶段（onedir 输出目录） ==========
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='assistance-backend',       # 产物目录 backend/dist/assistance-backend/
)
