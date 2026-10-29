"""Audit middleware for logging API requests with user identity.

性能契约（2026-10-14 系统排查报告 H9 修复，语义变化如实声明）：
旧实现"每请求一写"——每个非跳过请求结束后独立开 session + INSERT + commit，
SQLite 单写者模型下与业务事务形成第二个写者竞争，拖慢全站延迟与吞吐、
使 -wal 持续膨胀、并抬高并发时 database is locked 概率。

新契约——批量缓冲 + 三重刷写：
1. 请求结束后仅把一条审计记录 O(1) 追加进进程内线程安全缓冲（无任何 I/O）；
2. 定量刷写：缓冲达到 ``_FLUSH_THRESHOLD``（25 条）时，由触发的那次请求在
   线程池执行一次批量落库（单 session + add_all + 单次 safe_commit）；
3. 定时兜底：惰性启动的 daemon 线程每 ``_FLUSH_INTERVAL_SECONDS``（5 秒）
   把不足阈值的余量刷掉——**低流量下日志最多延迟 5 秒落库**；
4. 进程退出兜底：``atexit`` 注册最终 flush——**进程崩溃时最多丢失一个未满批**；
5. 失败不致命：批量落库失败仅记 WARNING 并丢弃该批（访问日志是可丢的
   观测数据），绝不向请求路径抛异常，绝不影响业务响应。

跳过路径（/health 等）判定逻辑保持不变，仍不记录。
"""
import atexit
import logging
import threading
import time

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

# ── 批量落库参数（模块常量，便于测试 patch；刻意不新增 settings 配置项）──
_FLUSH_THRESHOLD = 25          # 定量刷写：缓冲满 25 条 → 触发请求批量落库一次
_FLUSH_INTERVAL_SECONDS = 5.0  # 定时兜底：不足阈值时最多 5 秒刷写一次

# ── 进程内共享的待写缓冲（所有访问都在 _buffer_lock 保护内）──
_buffer: list = []
_buffer_lock = threading.Lock()
_flush_stop_event = threading.Event()
_flusher_thread: "threading.Thread | None" = None
_flusher_lock = threading.Lock()


# api_access_logs.user_id 的 username→id 缓存（2026-10-29 审计修复）。
# 中间件在每个请求上跑，不能每次都查库；用户名→id 在会话期内基本不变，
# 用有界字典缓存即可（未命中才查一次库）。
_USER_ID_CACHE: dict = {}
_USER_ID_CACHE_MAX = 512


def _lookup_user_id(username):
    """按用户名反查 users.id，带进程内缓存；任何异常返回 None（审计不得影响请求）。"""
    if not username:
        return None
    if username in _USER_ID_CACHE:
        return _USER_ID_CACHE[username]
    uid = None
    try:
        from app.core.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        try:
            row = db.query(User.id).filter(User.username == username).first()
            uid = row[0] if row else None
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - 归因失败不得影响请求
        logger.debug("访问日志 user_id 反查失败 username=%s: %s", username, exc)
        return None
    if len(_USER_ID_CACHE) < _USER_ID_CACHE_MAX:
        _USER_ID_CACHE[username] = uid
    return uid


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs request method, path, status code, duration, and authenticated user.

    审计落库为进程内批量缓冲 + 定量/定时/退出三重刷写（语义变化见模块
    docstring：低流量下最多延迟 5 秒落库，进程崩溃最多丢一个未满批）。
    落库失败仅写 WARNING 日志，绝不破坏业务请求。
    """

    # 无需审计的路径前缀：健康检查 / 指标 / 静态资源 / API 文档。
    # 这些路径无审计价值，却会对每次请求产生日志 + api_access_logs 落库
    # （独立 session + 写事务 commit）：既是性能负担（/health 单请求 ~20ms），
    # 也会让 -wal 文件随请求量快速增长（实测 22MB 未回收）。故直接短路。
    _SKIP_PREFIXES = (
        "/health",
        "/metrics",
        "/favicon.ico",
        "/static/",
        "/uploads/",
        "/docs",
        "/redoc",
        "/openapi.json",
    )

    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in self._SKIP_PREFIXES):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)

        # Extract user identity from Authorization header
        user_id_int, username = self._extract_user_identity(request)

        logger.info(
            "%s %s -> %d (%dms) [user: %s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            username or "anonymous",
        )

        # O(1) 入缓冲，无 DB I/O、不阻塞事件循环。record 的键与
        # APIAccessLog 列一一对应，落库时直接 APIAccessLog(**record)。
        record = {
            "user_id": user_id_int,
            "username": username,
            "endpoint": request.url.path,
            "method": request.method,
            "response_status": response.status_code,
            "response_time_ms": duration_ms,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
        if _enqueue_record(record):
            # 定量刷写：由触发阈值的那次请求在线程池执行一次批量落库。
            # 同步 DB IO 必须卸载到线程池（深审 #7），不在事件循环里调用。
            await run_in_threadpool(_flush_pending)

        return response

    @staticmethod
    def _extract_user_identity(request):
        """Extract user identity from JWT in Authorization header.

        Returns:
            tuple (user_id: Optional[int], username: Optional[str]).
            (None, None) if no/invalid token.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None, None

        token = auth_header[7:]
        try:
            import jwt
            from app.core.config import settings

            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},  # Don't re-verify expiry for audit log
            )
            sub = payload.get("sub")
            username = payload.get("username") or sub
            try:
                return int(sub), username
            except (TypeError, ValueError):
                pass
            # 本项目 JWT 的 sub 就是 username（create_token_pair(subject=username)），
            # 所以 int(sub) 恒失败 —— 原实现在这里直接 return None，导致
            # api_access_logs.user_id **恒为 NULL**，访问日志无法按用户归因/检索
            # （2026-10-29 审计）。改为按用户名反查 id（带缓存）。
            return _lookup_user_id(username), username
        except Exception as e:
            logger.debug("审计中间件: token 解析失败（可能是未认证请求）: %s", e, exc_info=True)
            return None, None


def _enqueue_record(record) -> bool:
    """将审计记录追加进缓冲，返回是否达到定量刷写阈值。

    首次入缓冲时惰性启动定时兜底线程。
    """
    with _buffer_lock:
        _buffer.append(record)
        reached = len(_buffer) >= _FLUSH_THRESHOLD
    _ensure_flusher_started()
    return reached


def _ensure_flusher_started():
    """惰性启动定时兜底 daemon 线程（进程内仅启动一次）。"""
    global _flusher_thread
    with _flusher_lock:
        if _flusher_thread is not None and _flusher_thread.is_alive():
            return
        _flush_stop_event.clear()
        _flusher_thread = threading.Thread(
            target=_flusher_loop, name="audit-log-flusher", daemon=True
        )
        _flusher_thread.start()


def _flusher_loop():
    """定时兜底：每 _FLUSH_INTERVAL_SECONDS 把不足阈值的余量刷掉。"""
    while not _flush_stop_event.wait(_FLUSH_INTERVAL_SECONDS):
        _flush_pending()


def _drain_buffer():
    """线程安全取走当前缓冲全部记录；空缓冲返回 []。"""
    with _buffer_lock:
        if not _buffer:
            return []
        batch = _buffer[:]
        _buffer.clear()
        return batch


def _flush_pending():
    """刷写当前缓冲（缓冲为空是 no-op）；失败不外抛（见 _persist_batch）。"""
    batch = _drain_buffer()
    if batch:
        _persist_batch(batch)


def _persist_batch(records):
    """将一批审计记录落库：单 session + add_all + 单次 safe_commit。

    落库失败仅记 WARNING 并丢弃该批——访问日志是可丢的观测数据，
    绝不能因它让业务请求失败或让兜底线程崩溃。
    """
    if not records:
        return
    try:
        from app.core.database import SessionLocal
        from app.models.audit import APIAccessLog

        db = SessionLocal()
        try:
            db.add_all([APIAccessLog(**record) for record in records])
            safe_commit(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(
            "api_access_logs 批量落库失败，丢弃 %d 条审计记录: %s",
            len(records),
            e,
            exc_info=True,
        )


def _final_flush():
    """进程退出兜底（atexit）：停止定时线程并尽力刷掉残余缓冲。"""
    _flush_stop_event.set()
    _flush_pending()


atexit.register(_final_flush)
