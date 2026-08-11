# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
block_cipher = None
backend_dir = os.path.dirname(os.path.abspath(SPEC))
datas = [
    (os.path.join(backend_dir, 'alembic'), 'alembic'),
    (os.path.join(backend_dir, 'app'), 'app'),
]
binaries = []
hiddenimports = [
    'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl', 'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'fastapi', 'fastapi.middleware', 'fastapi.middleware.cors',
    'starlette', 'starlette.middleware', 'starlette.middleware.base',
    'sqlalchemy', 'sqlalchemy.dialects.sqlite', 'sqlalchemy.orm', 'sqlalchemy.ext.declarative',
    'pydantic', 'pydantic.v1', 'pydantic_settings',
    'passlib', 'passlib.handlers.bcrypt', 'passlib.handlers.sha2_crypt',
    'jwt', 'jwt.jwt', 'jwt.exceptions',
    'cryptography', 'cryptography.fernet', 'cryptography.hazmat',
    'aiosqlite', 'alembic', 'alembic.config',
    'email_validator', 'python_multipart', 'multipart',
    'pandas', 'numpy', 'openpyxl', 'xlsxwriter',
    'docx', 'fpdf', 'reportlab', 'pptx',
    'PIL', 'PIL.Image', 'qrcode', 'jieba',
    'apscheduler', 'structlog', 'slowapi', 'diskcache',
    'bcrypt', 'bleach', 'httpx',
    'app.main', 'app.core.config', 'app.core.database',
    'app.core.security', 'app.api.v1',
]
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('sqlalchemy')
a = Analysis(
    ['start.py'], pathex=[backend_dir], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=['tkinter', 'matplotlib', 'scipy', 'sklearn', 'scrapy', 'redis'],
    win_no_prefer_redirects=False, win_private_assemblies=False,
    cipher=block_cipher, noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='assistance-management-backend',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True,
    upx_exclude=[], name='assistance-management-backend')
