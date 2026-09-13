"""维护模式闸门（R7 · 遗留风险治理计划 2026-09-13，W3-W4 批次）。

**问题**：恢复备份会替换数据库文件。此时在途的写请求：

- Windows：仍持有旧文件句柄 → 覆盖复制抛 PermissionError（恢复直接失败）；
- POSIX：写进已被替换的旧 inode → 恢复完成后数据缺一段已提交事务，且**无任何报错**。

原有 db_coordinator.exclusive_write 只与 opt-in 的长写路径互斥，普通请求的小写
事务不经此锁，窗口始终存在。

**闸门语义**（三步，缺一不可）：

1. enter()：置位维护模式 —— 其后到达的**写**请求（POST/PUT/PATCH/DELETE）立即
   503，读请求放行（前端仍能展示"维护中"与健康状态，而不是整站不可用）；
2. wait_for_idle()：等待在途请求归零（默认 10s，与 exclusive_write 同口径；
   超时记 ERROR 并继续 —— 宁可承担窄窗口竞态，也不让恢复整体失败）；
3. leave()：解除（由 finally 保证，异常路径不滞留维护态）。

状态经 status() 暴露到 /health，运维可判断系统是否卡在维护窗口。
"""

import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Iterator, Optional

logger = logging.getLogger(__name__)

# 写方法集合：维护模式只拦写，读一律放行
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# 豁免路径（后缀匹配）：恢复入口自身必须能执行；内部关闭端点用于收尾
EXEMPT_PATH_SUFFIXES = ("/system/backup/restore", "/shutdown")

DEFAULT_IDLE_TIMEOUT_SECONDS = 10.0
_POLL_INTERVAL_SECONDS = 0.05

_lock = threading.RLock()
_active = False
_reason = ""
_since: Optional[str] = None
_last_window_ms = 0
_last_waited_ms = 0


def is_active() -> bool:
    """当前是否处于维护窗口。"""
    with _lock:
        return _active


def enter(reason: str) -> None:
    """进入维护模式（幂等：重复进入只更新原因与起始时间）。"""
    global _active, _reason, _since
    with _lock:
        _active = True
        _reason = reason
        _since = datetime.now(timezone.utc).isoformat()
    logger.warning("进入维护模式: %s（写请求将被拒绝，读请求放行）", reason)


def leave() -> None:
    """退出维护模式（幂等）。"""
    global _active, _reason
    with _lock:
        was_active = _active
        _active = False
        _reason = ""
    if was_active:
        logger.info("退出维护模式，写请求恢复")


def status() -> Dict[str, object]:
    """维护模式状态快照（/health 用）。"""
    with _lock:
        return {
            "active": _active,
            "reason": _reason or None,
            "since": _since,
            "last_window_ms": _last_window_ms,
            "last_waited_ms": _last_waited_ms,
        }


def should_reject(method: str, path: str) -> bool:
    """维护模式下是否应拒绝该请求：写方法 + 非豁免路径 + 处于维护窗口。"""
    with _lock:
        active = _active
    if not active:
        return False
    if (method or "").upper() not in WRITE_METHODS:
        return False
    return not any((path or "").endswith(suffix) for suffix in EXEMPT_PATH_SUFFIXES)


def _active_request_count() -> int:
    """MetricsMiddleware 维护的在途请求数（导入放函数内，避免环形依赖）。"""
    from app.middleware.metrics_middleware import metrics_store

    return metrics_store.active_count()


def wait_for_idle(timeout: float = DEFAULT_IDLE_TIMEOUT_SECONDS, exclude: int = 1) -> int:
    """等待在途请求降到 exclude 个以内（默认扣除当前恢复请求自身）。

    Returns:
        实际等待毫秒数。超时不再等待，记 ERROR 后返回（恢复继续执行）。
    """
    started = time.perf_counter()
    deadline = started + max(timeout, 0.0)
    while True:
        remaining = _active_request_count() - exclude
        if remaining <= 0:
            return int((time.perf_counter() - started) * 1000)
        if time.perf_counter() >= deadline:
            logger.error(
                "维护模式等待在途请求归零超时（%.1fs，仍有 %d 个在途），继续执行恢复",
                timeout,
                remaining,
            )
            return int((time.perf_counter() - started) * 1000)
        time.sleep(_POLL_INTERVAL_SECONDS)


class MaintenanceWindow:
    """一次维护窗口（记录等待与占用时长，供响应体与日志留痕）。"""

    def __init__(self, reason: str):
        self.reason = reason
        self.waited_ms = 0
        self._entered_at = 0.0

    def elapsed_ms(self) -> int:
        """维护窗口已持续毫秒数（未开始计时则为 0）。"""
        if not self._entered_at:
            return 0
        return int((time.perf_counter() - self._entered_at) * 1000)


@contextmanager
def maintenance_window(
    reason: str,
    timeout: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
    exclude: int = 1,
) -> Iterator[MaintenanceWindow]:
    """维护窗口上下文：置位 → 等在途归零 → 执行业务 → finally 解除。"""
    global _last_window_ms, _last_waited_ms
    window = MaintenanceWindow(reason)
    enter(reason)
    try:
        window.waited_ms = wait_for_idle(timeout=timeout, exclude=exclude)
        window._entered_at = time.perf_counter()
        yield window
    finally:
        _last_window_ms = window.elapsed_ms()
        _last_waited_ms = window.waited_ms
        leave()
