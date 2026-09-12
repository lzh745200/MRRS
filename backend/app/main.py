"""帮扶管理信息系统 - FastAPI 入口模块"""

from __future__ import annotations

import os
import sys
import logging
import time as _time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from pathlib import Path

# ── 关键修复：PyInstaller 无控制台模式下 sys.stdout/stderr 为 None ──
# Uvicorn AccessFormatter.__init__ 调用 sys.stderr.isatty() 无 None 检查，
# 在 windowed 模式 EXE 中直接崩溃（sys.stderr is None）。
if sys.stdout is None:  # pragma: no cover — PyInstaller windowed EXE 专有，pytest 环境不可达
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:  # pragma: no cover — PyInstaller windowed EXE 专有，pytest 环境不可达
    sys.stderr = open(os.devnull, 'w')

# ── 关键修复：Windows ProactorEventLoop ConnectionResetError ──
# 必须在 import fastapi/uvicorn 之前应用：本修复会替换全局 EventLoopPolicy，
# 需赶在任何事件循环被创建之前。三层纵深防御：
#   Layer 1: Monkey-patch _ProactorBasePipeTransport._call_connection_lost
#   Layer 2: 替换全局 EventLoopPolicy，所有新 loop 自动继承异常处理器
#   Layer 3: 对当前运行时 loop 设置异常处理器
# 无条件调用：apply_windows_proactor_fix() 自身首句即判 sys.platform != "win32"
# 并返回 False，故外层再包 `if sys.platform == "win32"` 纯属冗余，且会让下面两行
# 在 Linux 上永不执行（不可覆盖，击穿 .coveragerc 的 fail_under=100）。
# 这行裸调用位于框架 import 之前，是 app/main.py 在 .flake8 里带 E402
# per-file-ignore 的原因（入口模块的 bootstrap 必须先于框架导入）。
from app.utils.win_proactor_fix import apply_windows_proactor_fix

apply_windows_proactor_fix()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from app.core.audit_middleware import AuditMiddleware
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import init_logging
from app.core.security import SecurityHeadersMiddleware
from app.core.static_files import setup_static_files
from app.middleware.camel_to_snake import CamelToSnakeMiddleware
from app.middleware.csrf_middleware import CSRFMiddleware
from app.middleware.metrics_middleware import MetricsMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware

env = os.getenv("ENV", "dev")
# P2-1: 统一日志入口——移除 SafeLogger，走 logging_config.init_logging()
init_logging()
logger = logging.getLogger("assistance_management")

# ── 迁移状态（任务#6 风险6·静默失败放大修复）──
# 供 /health 端点与启动日志明确暴露“迁移是否达到 head”，不再静默吞掉。
#   at_head:   None=尚未检测 / True=已达 head / False=未达 head（迁移失败或落后）
#   head:      脚本目录的目标 head 版本号（仅读文件，不连数据库）
#   error_type: 最近一次迁移失败的异常类名（成功时为 None）。
#              只存类名而非异常原文 —— /health 无需认证，原文可能含数据库
#              绝对路径与 SQL 片段；完整细节由 logger.error(exc_info=True) 留痕。
_migration_status: dict = {"at_head": None, "head": None, "error_type": None}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用生命周期：启动时初始化数据库、种子数据、依赖检查"""
    _init_database_tables()
    _load_token_blacklist()
    _recover_interrupted_exports()
    # C1 恢复演练：启动时回填上次演练结论，/health 重启后仍有数据
    from app.services.restore_drill_service import _load_persisted_status

    try:
        _load_persisted_status()
    except Exception as e:  # pragma: no cover — 双保险，内层已捕获
        logger.warning("恢复演练历史状态回填失败: %s", e)
    _check_and_record_version_change()
    _seed_default_admin()
    _check_required_packages()
    _verify_file_integrity()
    _start_resource_monitoring()
    _start_database_health_monitoring()
    _run_database_startup_check()
    _start_approval_reminder()
    # 每日凌晨 3 点 WAL checkpoint（轻量，不含 VACUUM，防止 -wal 文件膨胀）
    _start_wal_checkpoint_scheduler()
    # 备份调度器（KPI 预计算/异常检测/自动备份/待办提醒/周报）
    _start_backup_scheduler()
    # 本地任务队列（异步导出等后台任务执行）
    from app.services.task_queue import task_queue

    await task_queue.start()
    # _start_db_maintenance() — 已禁用，VACUUM 会生成大量临时文件
    yield
    # _stop_db_maintenance()
    await task_queue.stop()
    _stop_backup_scheduler()
    _stop_wal_checkpoint_scheduler()
    _stop_approval_reminder()
    _stop_resource_monitoring()
    _stop_database_health_monitoring()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="帮扶管理信息系统 API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    redirect_slashes=True,
    lifespan=lifespan,
)

register_exception_handlers(app)

# 中间件注册顺序（Starlette 按添加的逆序执行）：
# 执行顺序: RequestID → SecurityHeaders → CORS → CamelToSnake → CSRF → RequestLogger → Audit → Metrics
# 添加顺序: Metrics → Audit → RequestLogger → CSRF → CamelToSnake → CORS → SecurityHeaders → RequestID

# 1. 性能监控中间件（最内层，最后执行，包裹实际请求处理）
# 0. 数据库查询计数中间件（记录每个请求的 SQL 查询次数）
from app.middleware.query_counter import QueryCounterMiddleware  # noqa: E402
app.add_middleware(QueryCounterMiddleware)

# 1a. 慢请求监控中间件（记录超过阈值的 SQL 查询）
from app.middleware.slow_request_monitor import SlowRequestMiddleware  # noqa: E402
app.add_middleware(
    SlowRequestMiddleware,
    slow_api_ms=settings.SLOW_API_MS,
    slow_sql_ms=settings.SLOW_SQL_MS,
)

app.add_middleware(MetricsMiddleware)

# 2. 审计日志中间件
app.add_middleware(AuditMiddleware)

# 3. 请求日志中间件
app.add_middleware(RequestLoggerMiddleware)

# 4. CSRF 保护中间件（仅在 settings.CSRF_ENABLED=True 时生效）
# E1（架构评估 2026-09-12）：已改写为纯 ASGI 实现，不再经过 BaseHTTPMiddleware
# （其响应缓冲/任务包装在流式与大 body 请求下会触发 h11 协议错误），可常开
if settings.CSRF_ENABLED:
    app.add_middleware(CSRFMiddleware)

# 4.5 驼峰→蛇形转换中间件（将前端 camelCase JSON 转为后端 snake_case）
app.add_middleware(CamelToSnakeMiddleware)

# 4.6 缓存头中间件（对静态/低变化数据添加 Cache-Control 减少重复查询）
from app.middleware.cache_headers import CacheHeadersMiddleware  # noqa: E402
app.add_middleware(CacheHeadersMiddleware)

# 5. CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOWED_METHODS,
    allow_headers=settings.CORS_ALLOWED_HEADERS,
    expose_headers=["Content-Disposition", "X-Request-ID", "X-Total-Count"],
    max_age=3600,
)

# 6. 安全响应头中间件（在 CORS 之后，确保所有响应都有安全头）
app.add_middleware(SecurityHeadersMiddleware)

# 6.5 全局请求体大小限制（文件上传端点通过 MAX_FILE_SIZE 单独控制）
from app.middleware.body_size_limit import BodySizeLimitMiddleware  # noqa: E402
app.add_middleware(BodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)

# 7. 请求ID链路追踪中间件（最外层，最先执行）
app.add_middleware(RequestIDMiddleware)

# ── 启用审计事件监听（SQLAlchemy 事件自动记录所有写操作）──
try:
    from app.services.audit_event_handler import setup_audit_events

    setup_audit_events()
except Exception:
    logger.exception("审计事件钩子启动失败")  # 不影响主应用启动，但必须记录错误

# ── 加载路由（懒模型已提速，模块级加载安全可靠）──
print("  加载路由模块...", flush=True)
_rt0 = _time.time()
from app.api.v1 import api_v1_router  # noqa: E402
app.include_router(api_v1_router)
print(f"  路由加载完成 ({_time.time() - _rt0:.1f}s)", flush=True)


# 全局 Content-Type charset=UTF-8 修复
@app.middleware("http")
async def _ensure_charset_utf8(request: Request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if ct and "charset" not in ct:
        if ct.startswith("text/") or ct.startswith("application/json") or ct.startswith("application/javascript"):
            response.headers["content-type"] = f"{ct}; charset=utf-8"
    return response


# 修复 API 路径尾部斜杠 404：/api/v1/xxx/?q=1 → 307 → /api/v1/xxx?q=1
@app.middleware("http")
async def _trailing_slash_redirect(request: Request, call_next):
    path = request.url.path
    if len(path) > 1 and path.endswith("/"):
        new_path = path.rstrip("/")
        qs = request.url.query
        redirect_url = f"{new_path}?{qs}" if qs else new_path
        return RedirectResponse(url=redirect_url, status_code=307)
    return await call_next(request)


class CachedStaticFiles(StaticFiles):
    """带 Cache-Control 头的静态文件服务。

    对带 hash 的文件名（如 index-AY635XGl.js）设置长期缓存（immutable），
    因为这些文件内容永不改变，hash 变化意味着新版本用新文件名。
    """

    def __init__(self, *args, cache_max_age: int = 31536000, **kwargs):
        self._cache_max_age = cache_max_age
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        # 安全策略：对静态资源设置长期缓存 + immutable
        response.headers["Cache-Control"] = (
            f"public, max-age={self._cache_max_age}, immutable"
        )
        return response


REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pandas",
    "openpyxl",
]


# /health 等非API路由必须在 SPA catch-all 之前注册
@app.get("/health", summary="健康检查", tags=["系统"])
def health():
    """健康检查端点

    除版本/构建信息外，明确暴露数据库迁移是否已达 head（任务#6 风险6）。
    迁移失败时应用仍可启动（自动补列兜底），故顶层 status 保持 "ok"
    不影响可用性；但在 migration 子对象中如实回报 at_head=False 与异常类名，
    使 schema 漂移对监控/运维可见，不再静默。

    本端点无需认证，故只出异常类名（error_type），不出异常原文 ——
    原文可能含数据库绝对路径与 SQL 片段，完整细节见服务端日志。
    """
    from app.core.build_info import get_build_info

    info = get_build_info()
    at_head = _migration_status.get("at_head")
    # C1 恢复演练状态（架构评估）：备份可用性对监控可见。
    # 只出状态/文件名/异常类名 —— 本端点无认证，不出绝对路径与行数明细。
    from app.services.restore_drill_service import RESTORE_DRILL_STATUS

    return {
        "status": "ok",
        "version": info.get("version", "unknown"),
        "git_hash": info.get("git_hash", "unknown"),
        "migration": {
            "at_head": at_head,
            "head": _migration_status.get("head"),
            "error_type": _migration_status.get("error_type"),
        },
        "restore_drill": {
            "status": RESTORE_DRILL_STATUS.get("status"),
            "checked_at": RESTORE_DRILL_STATUS.get("checked_at"),
            "backup_file": RESTORE_DRILL_STATUS.get("backup_file"),
            "error_type": RESTORE_DRILL_STATUS.get("error_type"),
        },
    }


@app.post("/api/v1/shutdown", include_in_schema=False)
async def shutdown(request: Request):
    """内部关闭端点，仅接受 127.0.0.1 来源 + 内部密钥验证"""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="仅限本机调用")

    # 内部密钥验证：防止本机恶意进程关闭服务
    import os

    from fastapi import HTTPException

    expected_key = os.getenv("INTERNAL_SHUTDOWN_KEY", "")
    if not expected_key:
        # 未配置关闭密钥时拒绝所有关闭请求（非 Electron 启动场景）
        raise HTTPException(status_code=403, detail="未配置内部关闭密钥，拒绝关闭请求")
    request_key = request.headers.get("X-Internal-Shutdown", "")
    if request_key != expected_key:
        raise HTTPException(status_code=403, detail="内部密钥验证失败")
    logger.info("收到 shutdown 请求，正在关闭...")
    # 在后台线程中延迟关闭，使用 sys.exit 以触发正常清理流程
    import signal
    import threading

    threading.Timer(0.5, lambda: signal.raise_signal(signal.SIGINT)).start()
    return {"status": "shutting_down"}


# 静态文件和 SPA catch-all 必须在所有路由之后注册
_frontend_dir = setup_static_files(app)

if _frontend_dir:
    # ── 挂载前端静态资源 ──
    # 使用 CachedStaticFiles 为带 hash 的静态资源设置长期缓存（1 年 + immutable）。
    # Vite 构建产物文件名包含内容 hash（如 index-AY635XGl.js），
    # 内容变化 → hash 变化 → 新文件名 → 浏览器自动获取新版本。
    # 安全策略：Cache-Control: public, max-age=31536000, immutable

    assets_dir = os.path.join(_frontend_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount(
            "/assets",
            CachedStaticFiles(directory=assets_dir, cache_max_age=31536000),
            name="frontend_assets",
        )
    images_dir = os.path.join(_frontend_dir, "images")
    if os.path.isdir(images_dir):
        app.mount(
            "/images",
            CachedStaticFiles(directory=images_dir, cache_max_age=31536000),
            name="frontend_images",
        )
    # 挂载静态文件目录（模板、下载文件等离线兜底资源）
    # 注意：这些文件没有内容 hash 文件名（如 project_import_template.xlsx），
    # 不能使用 immutable 缓存策略，否则更新模板后浏览器仍使用过期缓存。
    static_dir = os.path.join(_frontend_dir, "static")
    if os.path.isdir(static_dir):
        app.mount(
            "/static",
            StaticFiles(directory=static_dir),
            name="frontend_static",
        )

    # index.html 路径（每次请求时重新读取，避免 rebuild 后缓存旧版本）
    _index_path = Path(_frontend_dir) / "index.html"
    _favicon_raw_path = Path(_frontend_dir) / "favicon.ico"
    _favicon_path: Optional[Path] = _favicon_raw_path if _favicon_raw_path.exists() else None
    _version_json_raw_path = Path(_frontend_dir) / "version.json"
    _version_json_path: Optional[Path] = _version_json_raw_path if _version_json_raw_path.exists() else None

    @app.get("/favicon.ico")
    async def favicon():
        if _favicon_path:
            return FileResponse(_favicon_path)
        return JSONResponse({"message": "Favicon not found"}, status_code=404)

    @app.get("/version.json")
    async def version_json():
        """构建版本指纹 — 前端 useVersionCheck 启动时拉取"""
        if _version_json_path:
            return FileResponse(
                _version_json_path,
                media_type="application/json",
                headers={"Cache-Control": "no-cache"},
            )
        return JSONResponse({"version": "unknown"}, status_code=404)

    # ── SPA fallback ──
    # 所有非 API / 非文档 / 非已挂载静态路径的 GET 请求，返回 index.html。
    # 前端 Vue Router 在浏览器端接管路由（History 模式）。
    # index.html 不缓存：确保浏览器始终获取最新版本，避免引用过时的 hash 资源。

    _reserved = (
        settings.API_PREFIX.lstrip("/"),
        "docs", "openapi", "uploads", "version.json",
    )

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def spa_fallback(request: Request, full_path: str = ""):
        if full_path.startswith(_reserved):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # 每次请求重新读取 index.html — 确保 rebuild 后不返回缓存旧版本
        return HTMLResponse(
            _index_path.read_text(encoding="utf-8"),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
else:
    logger.warning(
        "前端静态资源未挂载。可能原因：\n"
        "  1. 开发模式：请先执行 'cd frontend && npm run build' 构建前端\n"
        "  2. 打包模式：确认 resources/frontend 目录存在且包含 index.html\n"
        "  3. 环境变量 FRONTEND_DIST_PATH 指向的目录不存在"
    )


# ── 启动钩子（B3 拆包：实现迁至 app/startup/*，main 只留编排清单）──
# 同名 re-export 保证既有 `from app.main import _xxx` 与
# `patch("app.main._xxx")` 用法完全兼容（tests/unit/test_main_*.py 依赖）。
from app.startup.environment import (  # noqa: F401
    REQUIRED_PACKAGES,
    _check_and_record_version_change,
    _check_required_packages,
    _verify_file_integrity,
)
from app.startup.monitors import (  # noqa: F401
    _run_database_startup_check,
    _start_approval_reminder,
    _start_backup_scheduler,
    _start_database_health_monitoring,
    _start_db_maintenance,
    _start_resource_monitoring,
    _start_wal_checkpoint_scheduler,
    _stop_approval_reminder,
    _stop_backup_scheduler,
    _stop_database_health_monitoring,
    _stop_db_maintenance,
    _stop_resource_monitoring,
    _stop_wal_checkpoint_scheduler,
)
from app.startup.recovery import (  # noqa: F401
    _load_token_blacklist,
    _recover_interrupted_exports,
)
from app.startup.seed import (  # noqa: F401
    DEFAULT_ADMIN_USERNAME,
    _seed_default_admin,
)


def _init_database_tables():
    """确保所有数据库表已创建，并补全已有表中缺失的列"""
    # 导入所有模型确保表定义已注册。
    # import app.models 只加载 __init__.py（懒加载入口），不会注册具体模型表；
    # 必须通过 __getattr__ 触发所有模型类的实际导入，否则 _migrate_missing_columns
    # 只能看到已被路由导入的模型，导致其余表的缺失列检测遗漏。
    import app.models  # noqa: F401
    _missing_models = []
    for _name in app.models.__all__:
        try:
            getattr(app.models, _name)
        except Exception as _e:
            _missing_models.append(f"{_name}({_e})")
    if _missing_models:
        logger.warning("部分模型导入失败: %s", ", ".join(_missing_models))

    from app.core.database import engine
    from app.models.base import Base as ModelBase

    ModelBase.metadata.create_all(bind=engine)
    # P2-1: 编程式 Alembic 升级（正式 schema 变更），失败时回退到自动补列
    _run_alembic_upgrade()
    # SQLite: create_all 不会给已有表添加新列，需手动 ALTER TABLE（兜底）
    if settings.ENABLE_AUTO_MIGRATION:
        _migrate_missing_columns(engine, ModelBase)
    else:
        logger.info("Schema auto-migration disabled (ENABLE_AUTO_MIGRATION=false)")
    # 创建性能优化索引
    from app.core.database_indexes import create_indexes

    create_indexes(engine)
    logger.info("数据库表初始化完成")


def _run_alembic_upgrade():
    """编程式执行 alembic upgrade head。

    失败处理（任务#6 风险6·静默失败放大修复）：
    - 不再用 warning 静默吞掉异常：记录 ERROR 级日志 + 完整异常栈（exc_info）。
    - 通过模块级 _migration_status 暴露“迁移未达 head”状态，/health 与启动日志可见。
    - 生产环境（ENVIRONMENT=production）迁移失败直接抛出，中止启动（fail-loud），
      避免带着漂移的 schema 长期运行导致不可见的数据风险（如风险3的孤儿临时表
      使数据库永久停在旧版本）；开发/测试环境保持启动韧性：记录错误后回退
      到自动补列兜底，不崩溃。

    优化：如果数据库表已存在但 alembic_version 表不存在（如 create_all 新建），
    直接 stamp 到 head，避免重放全部历史迁移。
    """
    is_production = settings.ENVIRONMENT == "production"
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory
        from sqlalchemy import inspect as sa_inspect

        alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
        if not alembic_ini.exists():
            logger.info("alembic.ini 不存在，跳过编程式迁移")
            return
        cfg = AlembicConfig(str(alembic_ini))
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        cfg.set_main_option("script_location", str(alembic_ini.parent / "alembic"))

        # 记录目标 head 版本号（仅读脚本目录，不连数据库），供健康检查暴露
        try:
            _migration_status["head"] = ScriptDirectory.from_config(cfg).get_current_head()
        except Exception:  # pragma: no cover - head 推断失败不阻断迁移
            _migration_status["head"] = None

        # 检查是否需要 stamp（表已存在但无 alembic_version 表）
        from app.core.database import engine
        insp = sa_inspect(engine)
        all_tables = set(insp.get_table_names())
        has_alembic_version = "alembic_version" in all_tables
        has_business_tables = "users" in all_tables and "supported_villages" in all_tables

        if not has_alembic_version and has_business_tables:
            # create_all 已建表但未记录版本 → stamp 到 head，跳过全部历史迁移
            logger.info("数据库已有业务表但无 alembic_version，直接 stamp 到 head")
            alembic_command.stamp(cfg, "head")
            logger.info("Alembic stamp head 完成（跳过历史迁移重放）")
        else:
            alembic_command.upgrade(cfg, "head")
            logger.info("Alembic upgrade head 完成")
        _migration_status["at_head"] = True
        _migration_status["error_type"] = None
    except Exception as e:
        _migration_status["at_head"] = False
        # 只记类名：_migration_status 经无认证的 /health 出站，异常原文可能含
        # 数据库绝对路径与 SQL 片段。原文仅进服务端日志（下方 exc_info=True）。
        _migration_status["error_type"] = type(e).__name__
        logger.error(
            "Alembic upgrade 失败，数据库 schema 未达 head（目标 head=%s）：%s",
            _migration_status.get("head"),
            e,
            exc_info=True,
        )
        if is_production:
            logger.critical(
                "生产环境迁移失败——中止启动以避免 schema 漂移导致不可见的数据风险。"
                "请排查数据库迁移状态（alembic current / alembic heads）后重试。"
            )
            raise
        logger.warning(
            "开发/测试环境：保持启动韧性，迁移失败降级为自动补列兜底（schema 可能落后 head）"
        )


def _migrate_missing_columns(engine, model_base):
    """检测列差异并自动添加缺失列 [DEPRECATED: 逐步迁移到纯 Alembic]

    ⚠️ 生产环境警告：此函数在启动时执行自动 DDL，存在风险。
    请尽快完成 Alembic 迁移迁移后，通过环境变量 DISABLE_AUTO_MIGRATION=1 禁用此函数。

    推荐迁移路径：新增字段后先生成 Alembic 迁移脚本，而非依赖此自动补齐。

    改进点：
    - 为 Boolean/Integer/Numeric 列添加 DEFAULT 值，确保已有行获得合理默认值
    - 对 nullable=False 且有默认值的列添加 NOT NULL DEFAULT 约束
    """
    import os
    import warnings

    # 发出弃用警告，提醒迁移到 Alembic
    warnings.warn(
        "_migrate_missing_columns 已弃用，请迁移到 Alembic 数据库迁移。"
        "设置 DISABLE_AUTO_MIGRATION=1 可禁用此功能。",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.warning(
        "[DEPRECATED] 自动列补齐功能已弃用，请尽快迁移到 Alembic。"
        "设置 DISABLE_AUTO_MIGRATION=1 可禁用。"
    )

    if os.getenv("DISABLE_AUTO_MIGRATION", "").strip() == "1":
        logger.info("DISABLE_AUTO_MIGRATION=1，跳过自动列补齐（请使用 Alembic 迁移）")
        return

    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    try:
        inspector = sa_inspect(engine)
    except Exception as e:
        logger.warning("Schema migration: failed to create inspector: %s", e)
        return

    total_added = 0
    total_failed = 0
    for table_name, table in model_base.metadata.tables.items():
        try:
            if not inspector.has_table(table_name):
                continue
            db_cols = {c["name"] for c in inspector.get_columns(table_name)}
            model_cols = {c.name for c in table.columns}
            missing = model_cols - db_cols
            if not missing:
                continue
            logger.info(
                "Schema migration: table [%s] has %d missing column(s): %s",
                table_name,
                len(missing),
                sorted(missing),
            )
            with engine.connect() as conn:
                for col_name in sorted(missing):
                    try:
                        col = table.c[col_name]
                        stype, default_clause = _sqlite_col_spec(col)
                        # SQLite: nullable=False 列必须有 DEFAULT 才能 ADD COLUMN
                        not_null = ""
                        if not col.nullable and default_clause:
                            not_null = "NOT NULL "
                        ddl = (
                            f"ALTER TABLE [{table_name}] ADD COLUMN [{col_name}] " f"{stype} {not_null}{default_clause}"
                        ).rstrip()
                        conn.execute(text(ddl))
                        total_added += 1
                        default_info = f" {default_clause}" if default_clause else ""
                        logger.info(
                            "Schema migration: [AUTO-ADD] %s.%s (%s%s)",
                            table_name,
                            col_name,
                            stype,
                            default_info,
                        )
                    except (ValueError, TypeError, AttributeError) as col_err:
                        total_failed += 1
                        logger.warning(
                            "Schema migration: failed to add %s.%s: %s",
                            table_name,
                            col_name,
                            col_err,
                        )
                conn.commit()
        except (ValueError, TypeError, KeyError) as tbl_err:
            logger.warning(
                "Schema migration: error processing table %s: %s",
                table_name,
                tbl_err,
            )

    if total_added or total_failed:
        logger.info(
            "Schema migration summary: %d column(s) added, %d failed",
            total_added,
            total_failed,
        )
    else:
        logger.info("Schema migration: all tables up to date, no columns to add")


def _sqlite_col_spec(col):
    """根据 SQLAlchemy Column 推断 SQLite 列类型和 DEFAULT 子句。

    Returns:
        (sqlite_type, default_clause) - 例如 ("INTEGER", "DEFAULT 0")
    """
    t = str(col.type).upper()

    # 类型映射
    if "INT" in t or "BOOL" in t:
        stype = "INTEGER"
    elif "FLOAT" in t or "REAL" in t or "NUMERIC" in t:
        stype = "REAL"
    else:
        # DATE, DATETIME, JSON, VARCHAR, TEXT, ENUM 等在 SQLite 中均用 TEXT
        stype = "TEXT"

    # 推断 DEFAULT 值
    default_clause = ""
    # 优先使用模型 default（ColumnDefault）
    if (
        col.default is not None
        and hasattr(col.default, "arg")
        and col.default.arg is not None
        and not callable(col.default.arg)
    ):
        raw = col.default.arg
        if isinstance(raw, bool):
            default_clause = f"DEFAULT {1 if raw else 0}"
        elif isinstance(raw, (int, float)):
            default_clause = f"DEFAULT {raw}"
        elif isinstance(raw, str):
            escaped = raw.replace("'", "''")
            default_clause = f"DEFAULT '{escaped}'"
    elif col.server_default is not None:
        # 注意: SQLite ALTER TABLE ADD COLUMN 不支持非常量 DEFAULT
        # (CURRENT_TIMESTAMP 会报错 "Cannot add a column with non-constant default")
        # 对于 server_default=func.now() 这类情况，跳过 DEFAULT，
        # ORM 层的 default=_utcnow 会为新行自动赋值。
        pass
    elif not col.nullable:
        # nullable=False 但没有显式 default → 给一个类型感知的零值
        if stype == "INTEGER":
            default_clause = "DEFAULT 0"
        elif stype == "REAL":
            default_clause = "DEFAULT 0"
        else:
            default_clause = "DEFAULT ''"

    return stype, default_clause


__all__ = ["app"]
