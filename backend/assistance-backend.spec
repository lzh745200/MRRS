# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 统一打包配置 - 跨平台 / x64-x86 通用版
将 FastAPI 后端打包为单文件可执行程序 assistance-backend(.exe)，包含所有依赖。

说明:
  - 产物架构由运行时的 Python 解释器架构决定（64-bit Python -> x64 exe,
    32-bit Python -> x86 exe），因此无需维护两份 spec。
  - 前端静态资源不打包进 backend.exe，由 Electron 通过 FRONTEND_DIST_PATH
    环境变量单独提供（resources/frontend/），节省约 15MB 体积。
  - console=False：无控制台窗口，由 Electron 主进程管理生命周期。
版本: 1.5.0
"""

import os
import sys
from pathlib import Path

from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ========== 路径定义（使用 PyInstaller 预定义的 SPEC） ==========
# SPEC 是 PyInstaller 在解析 spec 文件时自动注入的变量，表示 spec 文件的完整路径
backend_dir = os.path.dirname(os.path.abspath(SPEC))          # backend 目录
project_root = os.path.dirname(backend_dir)                  # 项目根目录
resources_dir = os.path.join(project_root, 'resources')

# ========== 数据文件列表 ==========
# 注意：不再打包 resources/frontend —— Electron 通过 extraResources 单独提供，
# 后端启动时通过 FRONTEND_DIST_PATH 环境变量定位前端静态资源。
datas = [
    (os.path.join(backend_dir, 'alembic'), 'alembic'),
    (os.path.join(backend_dir, 'alembic.ini'), '.'),
    (os.path.join(backend_dir, '.env.example'), '.'),
    (os.path.join(backend_dir, 'app'), 'app'),
]

# 自动收集 prophet 包数据（如果存在；x86 构建时可能未安装，自动跳过）
import importlib.util as _ilu
_prophet_spec = _ilu.find_spec('prophet')
if _prophet_spec and _prophet_spec.submodule_search_locations:
    _prophet_dir = list(_prophet_spec.submodule_search_locations)[0]
    datas.append((_prophet_dir, 'prophet'))

# snownlp 已从依赖中移除（离线模式不再需要中文情感分析原生库）
# _snownlp_spec = _ilu.find_spec('snownlp')
# if _snownlp_spec and _snownlp_spec.submodule_search_locations:
#     _snownlp_dir = list(_snownlp_spec.submodule_search_locations)[0]
#     datas.append((_snownlp_dir, 'snownlp'))

# 自动收集 prometheus_client 包数据（包含 HTML 模板等静态文件）
datas += collect_data_files('prometheus_client')

# ========== 二进制文件列表 ==========
binaries = []

# ========== 隐藏导入（保持原有，并补充必要模块） ==========
hiddenimports = [
    # FastAPI 和 Web 框架核心
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
    'aiosqlite',
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

    # 文件处理
    'PIL.Image',

    # AI功能
    'sklearn.linear_model',
    'sklearn.preprocessing',
    'prophet',
    'jieba',
    'jieba.analyse',

    # 舆情监控（scrapy/feedparser/snownlp 已从依赖中移除，离线模式下禁用）
    'bs4.builder._lxml',

    # 业务指标监控
    'prometheus_client',
]

# Windows 平台特定隐藏导入
if is_win:
    hiddenimports.append('psutil._pswindows')

# 自动收集 app 包下的所有子模块（避免手动添加遗漏）
hiddenimports += collect_submodules('app')

# 显式添加所有 API v1 路由模块（确保 PyInstaller 能正确打包）
hiddenimports += [
    'app.api.v1.auth',
    'app.api.v1.data',
    'app.api.v1.import_export',
    'app.api.v1.system',
    'app.api.v1.system.health',
    'app.api.v1.system.env',
    'app.api.v1.system.config_package',
    'app.api.v1.monitoring',
    'app.api.v1.monitoring.metrics',
    'app.api.v1.monitoring.secrets',
    'app.api.v1.monitoring.data_tier',
    'app.api.v1.organization',
    'app.api.v1.policy',
    'app.api.v1.projects',
    'app.api.v1.school',
    'app.api.v1.supported_village',
    'app.api.v1.supported_village_export',
    'app.api.v1.rural_works',
    'app.api.v1.rural_tasks',
    'app.api.v1.villages',
    'app.api.v1.village_templates',
    'app.api.v1.validation',
    'app.api.v1.report_templates',
    'app.api.v1.approval',
    'app.api.v1.messages',
    'app.api.v1.feedback',
    'app.api.v1.todos',
    'app.api.v1.ai',
    'app.api.v1.map',
    'app.api.v1.project_milestones',
    'app.api.v1.funds',
    'app.api.v1.fund_budgets',
    'app.api.v1.fund_lifecycle',
    'app.api.v1.work_logs',
    'app.api.v1.assessment',
    'app.api.v1.system_health',
    'app.api.v1.performance',
    'app.api.v1.monitoring_legacy',
    'app.api.v1.data_quality',
    'app.api.v1.ai_enhanced',
    'app.api.v1.data_sync',
    'app.api.v1.offline_map',
    'app.api.v1.batch_operations',
    'app.api.v1.sync',
    'app.api.v1.user_permissions',
    'app.api.v1.machine_code',
    'app.api.v1.effectiveness',
    'app.api.v1.sentiment',
    'app.api.v1.messages_extended',
    'app.api.v1.encryption',
    'app.api.v1.search',
    'app.api.v1.menus',
    'app.api.v1.permission_package',
]

# ========== 排除不需要的模块（减少打包体积，避免冲突） ==========
excludes = [
    'pytest', 'pytest_asyncio', 'pytest_cov', 'pytest_mock',
    'hypothesis', 'flake8', 'black', 'mypy',
    'tkinter', 'test', 'tests',
    'matplotlib', 'IPython', 'jupyter',
    'notebook', 'spyder', 'pylint',
    'docx', 'apscheduler',
    # 注意：mammoth 不再排除（policy.py 用于 .docx → HTML 转换，是运行时依赖）
    'app.api.v1.users',           # 旧路径，已不存在
    'app.api.v1.user_management', # 旧路径
    'app.api.v1.rbac',            # 旧路径
    'app.api.v1.analytics',       # 旧路径
    'app.api.v1.statistics',      # 旧路径
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

# ========== EXE 阶段 ==========
icon_path = os.path.join(resources_dir, 'icons', 'app-circle.ico')
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='assistance-backend',          # 统一名称（非 assistance-management-backend）
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # 禁用 UPX 压缩以避免某些兼容性问题
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                   # 不显示控制台窗口（适合 GUI 服务）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,                # 架构由 Python 解释器决定，无需指定
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
)
