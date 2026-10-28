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

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from app.core.audit_middleware import AuditMiddleware
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.grant_guard import enforce_write_grant
from app.core.logging_config import init_logging
from app.core.security import SecurityHeadersMiddleware
from app.core.static_files import setup_static_files
from app.middleware.camel_to_snake import CamelToSnakeMiddleware
from app.middleware.csrf_middleware import CSRFMiddleware
from app.middleware.metrics_middleware import MetricsMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.core.migration_helper import (
    _sqlite_col_spec as _migration_helper_sqlite_col_spec,
    migrate_missing_columns as _migration_helper_migrate_missing_columns,
)

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
    # R33 单位授权守卫（app 级依赖，覆盖全部路由）。
    # 默认 GRANT_GUARD_MODE=off → 函数首行即返回，零开销、零行为变化；
    # 切 shadow/enforce 才真正裁决写接口。
    dependencies=[Depends(enforce_write_grant)],
)

register_exception_handlers(app)

# 中间件注册顺序（Starlette 按添加的逆序执行：后添加者在外层、先进入）：
# 执行顺序（外→内）: _PathAndCharset → RequestID → BodySizeLimit → SecurityHeaders
#   → CORS → CacheHeaders → CamelToSnake → CSRF → RequestLogger → Audit
#   → MaintenanceGate → Metrics → SlowRequest → QueryCounter（最内层，包裹路由）
# 添加顺序（本文件自上而下）: QueryCounter → SlowRequest → Metrics → MaintenanceGate
#   → Audit → RequestLogger → CSRF → CamelToSnake → CacheHeaders → CORS
#   → SecurityHeaders → BodySizeLimit → RequestID → _PathAndCharset
# CSRF 仅在 settings.CSRF_ENABLED=True 时添加（关闭时该层不存在，其余层顺序不变）。

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

# 1b. 维护模式闸门（R7）：恢复备份期间拒绝新的写请求（503），读放行。
# 位置在本行之后添加 → 位于 Audit/RequestLogger 之内、Metrics 之外：
# 被拒请求仍进审计与访问日志，但不占用数据库与指标采集路径。
from app.middleware.maintenance_gate import MaintenanceGateMiddleware  # noqa: E402
app.add_middleware(MaintenanceGateMiddleware)

# 1c. viewer 只读闸门（W24 产品决策，2026-10-19）：viewer 角色严格只读，
# 写方法（POST/PUT/PATCH/DELETE）在非"账户自服务"白名单上直接 403，
# 判定依据为令牌内 role 声明（零 DB 查询），详见 middleware/viewer_readonly.py。
# 注册位置：与 1b 同理在 Audit/RequestLogger 之后添加（后注册者在外层）→
# 本层位于两者**之内**：被拒请求仍会经过访问日志与审计中间件（可观测、可追责），
# 又不进入 Metrics/QueryCounter 与业务路由（不产生 DB/指标副作用）。
# 与 CORS/SecurityHeaders 等外层中间件兼容：403 为普通 JSON 响应，会正常带
# CORS 与安全响应头；CSRF 若启用则先于本层执行（CSRF 失败 403 优先）。
from app.middleware.viewer_readonly import ViewerReadOnlyMiddleware  # noqa: E402
app.add_middleware(ViewerReadOnlyMiddleware)

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


# ── 尾部斜杠规范化 + Content-Type charset 补全（M36）──
# 两件事合并进一个**纯 ASGI** 中间件（原先是两个 @app.middleware("http") 函数式
# 中间件，各自再包一层 BaseHTTPMiddleware）：
# 1. 修复 API 路径尾部斜杠 404：/api/v1/xxx/?q=1 → 307 → /api/v1/xxx?q=1；
# 2. 文本类响应补 charset=utf-8。
# 语义与顺序保持：重定向发生在最外层（先于其余中间件，重定向响应直接返回），
# charset 在响应头部于下游全部中间件写完后补全，因此末尾追加即等价。
# 常量 time：模块级缓存，热路径不再每次 import（同 M34 口径）。
_TEXTUAL_CONTENT_TYPES = ("text/", "application/json", "application/javascript")


class _PathAndCharsetMiddleware:
    """纯 ASGI：尾斜杠 307 重定向 + 文本响应 charset 补全。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if len(path) > 1 and path.endswith("/"):
            query_string = scope.get("query_string", b"").decode("latin-1")
            location = path.rstrip("/") + (f"?{query_string}" if query_string else "")
            response = RedirectResponse(url=location, status_code=307)
            await response(scope, receive, send)
            return

        async def send_with_charset(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for index, (name, value) in enumerate(headers):
                    if name.lower() != b"content-type":
                        continue
                    decoded = value.decode("latin-1")
                    if "charset" not in decoded and decoded.startswith(_TEXTUAL_CONTENT_TYPES):
                        headers[index] = (name, (decoded + "; charset=utf-8").encode("latin-1"))
                    break
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_charset)


app.add_middleware(_PathAndCharsetMiddleware)


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


# 运行时依赖登记表已收敛到 app/core/required_packages.py（本文件不再自持清单；
# 下方 `from app.startup.environment import REQUIRED_PACKAGES` 提供兼容别名）。


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
    from app.core.config import settings as _settings

    info = get_build_info()
    at_head = _migration_status.get("at_head")
    # C1 恢复演练状态（架构评估）：备份可用性对监控可见。
    # 只出状态/文件名/异常类名 —— 本端点无认证，不出绝对路径与行数明细。
    # R12-3：经 snapshot_status() 取一致性快照（逐字段读模块字典会与演练
    # 线程的逐字段写交错，产出撕裂结论）。
    from app.services.restore_drill_service import snapshot_status as _drill_snapshot

    _drill = _drill_snapshot()
    # C1 备份存放可见化：备份与库同盘 = 断电/盘损时数据与备份同亡
    from app.services.backup_service import backups_share_volume_with_database
    from app.utils.paths import get_backup_path, get_database_path
    from app.core.maintenance import status as _maintenance_status

    try:
        same_volume = backups_share_volume_with_database(
            str(get_database_path()), str(get_backup_path())
        )
    except Exception as exc:  # pragma: no cover — /health 不得因附带信号失败（路径解析异常）  # noqa: BLE001 - 兜底但必须留痕
        logger.warning('health 兜底失败（已降级）: %s', exc, exc_info=True)
        same_volume = None

    # R36（离线长期运行可靠性）：
    # ① clock —— 系统时钟是否落后于数据最新记录（startup/preflight 检查结果，
    #    带 TTL 缓存，避免高频轮询把"最近审计时间"查询打到热路径）。
    #    时钟被手动改慢会让"最近 N 天"统计漏数据、定时任务错时，必须可见。
    # ② database —— WAL 的实际生效值（PRAGMA journal_mode 会被 SQLite 降级，
    #    旧实现不看返回值 → "以为开了 WAL，实际 delete 模式"，并发读写退化为互斥）。
    # 两者都**只增字段**，不改既有键与顶层 status（附带信号失败不阻断可用性）。
    from app.core.database import database_health as _database_health
    from app.startup.preflight import clock_health as _clock_health

    try:
        clock = _clock_health()
    except Exception as exc:  # noqa: BLE001 - 附带信号失败不得让 /health 5xx
        logger.warning('health 兜底失败（已降级）: %s', exc, exc_info=True)
        clock = {"status": "unknown", "behind_days": None}

    try:
        database_snapshot = _database_health()
    except Exception as exc:  # pragma: no cover - 快照读取为纯内存操作，理论上不会失败  # noqa: BLE001 - 兜底但必须留痕
        logger.warning('health 兜底失败（已降级）: %s', exc, exc_info=True)
        database_snapshot = {}
    # 尚未建立过连接（或快照被清空）时明确回报 unknown，而不是缺字段
    database_snapshot.setdefault("journal_mode", "unknown")
    database_snapshot.setdefault("journal_mode_ok", None)

    return {
        "status": "ok",
        "version": info.get("version", "unknown"),
        "git_hash": info.get("git_hash", "unknown"),
        "migration": {
            "at_head": at_head,
            "head": _migration_status.get("head"),
            "error_type": _migration_status.get("error_type"),
            # F1 单轨化可见性：true 表示仍在跑已弃用的自动补列兜底路径
            "auto_migration_enabled": bool(
                getattr(_settings, "ENABLE_AUTO_MIGRATION", False)
            ),
        },
        "backup": {
            # True=备份与数据库同卷（建议配置 backup_target_dir 到独立盘）；null=未知
            "same_volume_as_database": same_volume,
        },
        # R7：维护窗口可见性 —— active=true 表示恢复中（写请求被 503 拒绝）
        "maintenance": _maintenance_status(),
        # R36：时钟漂移（ok/warning/unknown + behind_days）与 WAL 实际生效值
        "clock": clock,
        "database": database_snapshot,
        "restore_drill": {
            "status": _drill.get("status"),
            "checked_at": _drill.get("checked_at"),
            "backup_file": _drill.get("backup_file"),
            "error_type": _drill.get("error_type"),
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
            logger.warning('_init_database_tables 兜底失败（已降级）: %s', _e, exc_info=True)
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
        except Exception as exc:  # pragma: no cover - head 推断失败不阻断迁移  # noqa: BLE001 - 兜底但必须留痕
            logger.warning('_run_alembic_upgrade 兜底失败（已降级）: %s', exc, exc_info=True)
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


# M41（R27 排查，R20 L9 未消除）：`_sqlite_col_spec` / `_migrate_missing_columns`
# 曾在本文件与 app/core/migration_helper.py 各有一份近似实现，任何一侧改动都会
# 让启动补列与 version_service 的补列行为漂移。现统一以 core.migration_helper
# 为唯一实现：本模块只保留名字转发（测试与 alembic/env.py 仍按
# `app.main._migrate_missing_columns` 导入），不再持有重复逻辑。
_sqlite_col_spec = _migration_helper_sqlite_col_spec


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

    # 发出弃用警告，提醒迁移到 Alembic（语义与 core.migration_helper 一致）
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

    # 环境变量短路保留在包装层：日志归属 app.main（既有运维脚本/测试按此定位），
    # 真正会漂移的 DDL 逻辑已单点收敛到 core.migration_helper。
    if os.getenv("DISABLE_AUTO_MIGRATION", "").strip() == "1":
        logger.info("DISABLE_AUTO_MIGRATION=1，跳过自动列补齐（请使用 Alembic 迁移）")
        return

    _migration_helper_migrate_missing_columns(engine, model_base)


__all__ = ["app"]
