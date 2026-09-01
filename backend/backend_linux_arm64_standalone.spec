# -*- mode: python ; coding: utf-8 -*-
"""
麒麟 V10 ARM64 专用 PyInstaller spec
一体化单机版（无 Electron 依赖）

构建命令:
  pyinstaller --clean --noconfirm backend_linux_arm64_standalone.spec

datas 使用目录收集方式（非 glob），避免 PyInstaller 6.21 glob 解析问题。
参照 backend_linux_arm64.spec 的稳健写法。
"""

import os
import sys
import glob
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
backend_dir = os.path.dirname(os.path.abspath(SPEC))

# ── 数据文件：直接收集整个目录，避免 glob 解析问题 ──
datas = [
    # 收集整个 app 目录（含 .py / .json / .html 等所有数据文件）
    (os.path.join(backend_dir, 'app'), 'app'),
    # 收集整个 alembic 目录（含 env.py / script.py.mako / versions/*.py）
    (os.path.join(backend_dir, 'alembic'), 'alembic'),
    # alembic 配置文件
    (os.path.join(backend_dir, 'alembic.ini'), '.'),
]

# ── 二进制文件：手动收集 libmagic 共享库（确保离线可用） ──
binaries = []
for libmagic_path in glob.glob('/usr/lib/*/libmagic.so*') + glob.glob('/lib/*/libmagic.so*'):
    binaries.append((libmagic_path, 'lib'))
    print(f"[SPEC] 收集 libmagic: {libmagic_path}")
# 同时收集 libsqlite3（虽然 Python 自带，但确保系统库可用）
for libsqlite_path in glob.glob('/usr/lib/*/libsqlite3.so*') + glob.glob('/lib/*/libsqlite3.so*'):
    binaries.append((libsqlite_path, 'lib'))
    print(f"[SPEC] 收集 libsqlite3: {libsqlite_path}")

hiddenimports = [
    # ── FastAPI + Starlette + Uvicorn ──
    'fastapi', 'starlette', 'uvicorn',
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'httptools', 'websockets', 'watchfiles',

    # ── SQLAlchemy + SQLite + Alembic ──
    'sqlalchemy', 'sqlalchemy.dialects.sqlite',
    'sqlalchemy.ext.asyncio', 'aiosqlite',
    'alembic', 'alembic.config', 'alembic.command',
    'alembic.script', 'alembic.runtime.environment',
    'alembic.migration', 'alembic.autogenerate',

    # ── 应用模块（确保所有子模块被扫描） ──
    'app.models', 'app.api', 'app.services', 'app.core',
    'app.middleware', 'app.utils', 'app.schemas',
    'app.api.v1', 'app.static_files',

    # ── 认证与安全 ──
    'jwt', 'bcrypt', 'passlib', 'passlib.hash',
    'pyotp', 'cryptography', 'cryptography.hazmat',

    # ── 调度与缓存 ──
    'apscheduler', 'apscheduler.schedulers.asyncio',
    'apscheduler.triggers.cron', 'apscheduler.triggers.interval',
    'diskcache',

    # ── 数据处理 ──
    'pandas', 'numpy', 'openpyxl', 'xlsxwriter',

    # ── 文档生成 ──
    'reportlab', 'docx', 'pptx', 'mammoth',

    # ── 图像处理 ──
    'PIL', 'PIL.Image', 'qrcode',

    # ── 中文处理 ──
    'jieba',

    # ── Web 工具 ──
    'email_validator', 'multipart', 'python_multipart',
    'httpx', 'aiofiles',

    # ── 日志与监控 ──
    'prometheus_client',

    # ── 文件类型检测 ──
    'magic',

    # ── 配置 ──
    'pydantic', 'pydantic_settings', 'dotenv',
]

# 自动收集 uvicorn 和 sqlalchemy 的所有子模块
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('sqlalchemy')

# app.* 全量收集（v1.11.3）：业务路由此前动态 importlib 加载，静态分析不可见，
# 打包后 ModuleNotFoundError（Kylin 403 事故）；统一 spec 同步修复
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
hiddenimports += collect_submodules('app')

a = Analysis(
    ['start.py'],
    pathex=[backend_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    excludes=[
        # GUI 框架（后端不需要）
        'tkinter', 'matplotlib.backends.backend_tkagg',
        'PIL.ImageTk', 'PIL.ImageQt',

        # 测试与开发工具
        'unittest', 'test', 'tests', 'pytest', 'coverage',
        'IPython', 'jupyter', 'notebook',

        # 无 ARM64 wheel 或非核心功能
        'scrapy', 'twisted',
        'redis', 'hiredis',
        'selenium', 'playwright',
        'prophet', 'cmdstanpy', 'stanio',
        'scipy', 'sklearn',
        'matplotlib',

        # Windows 专用
        'pywin32_ctypes', 'win32api', 'win32com',

        # 其他不需要的标准库
        'curses', 'distutils', 'setuptools',
        'xmlrpc', 'pydoc', 'difflib', 'ftplib',
    ],
    runtime_hooks=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='assistance-management-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台输出便于诊断
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='assistance-management-backend',
    strip=True,
    upx=True,
    upx_exclude=[],
)
