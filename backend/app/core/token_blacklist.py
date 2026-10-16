"""Persistent token blacklist.

Maintains a set of revoked JWT tokens so that compromised or logged-out
tokens cannot be reused.  Tokens are stored in-memory with an optional
database-backed persistence layer for production use.
"""

import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

# Stores (token_jti, expires_at_epoch) tuples
_blacklist: dict[str, float] = {}

# 并发保护锁（is_blacklisted 每次请求都会触发 _cleanup_expired，多线程下防 KeyError）
_BLACKLIST_LOCK = threading.Lock()

# 永久吊销哨兵：expires_at IS NULL 语义为「永不过期」，内存中绝不可降级为有限 TTL。
# 否则条目会在 24h 后被 _cleanup_expired 清掉，而已吊销的 token 重新可用（安全回归）。
_PERMANENT = math.inf

# ── M39（R27 性能排查）：清理节流与永久条目上限 ──
# 1. 全量清理（O(n) 扫描 + 持锁）不再挂在每次 is_blacklisted 上——鉴权路径每请求
#    调用一次，条目越多越慢且长时间占锁。改为：(a) is_blacklisted 只做 O(1) 定向
#    过期判定（命中已过期条目就地删除），(b) 全量扫描按 _CLEANUP_INTERVAL_SECONDS 节流。
# 2. 永久条目（expires_at IS NULL）历史上永不清理且无上限 → 内存无界增长。
#    超出 _MAX_PERMANENT_ENTRIES 时把**最早**的溢出条目降级为超长有限 TTL
#    （_PERMANENT_RETENTION_SECONDS = 180 天），既不无界增长，也不立刻放行已吊销令牌；
#    数据库侧的永久吊销记录不受影响（重启后 load_from_db 会重新装载）。
_CLEANUP_INTERVAL_SECONDS = 60.0
_PERMANENT_RETENTION_SECONDS = 180 * 24 * 3600
_MAX_PERMANENT_ENTRIES = 10_000
_last_cleanup_at: float = 0.0


def add(token_jti: str, *, expires_at: Optional[datetime] = None, ttl_seconds: int = 0) -> None:
    """Add a token JTI to the blacklist.

    Args:
        token_jti: The JWT ID (``jti`` claim) of the token to revoke.
        expires_at: UTC datetime when the token naturally expires.
            After this time the entry is auto-cleaned.  If not given,
            *ttl_seconds* is used.
        ttl_seconds: TTL in seconds (used only if *expires_at* is None;
            defaults to 86400 = 24 hours).
    """
    if not token_jti:
        return

    if expires_at is not None:
        exp = expires_at
        if exp.tzinfo is None:
            # 统一按 UTC 解释（与 JWT exp 一致），避免本地时区偏移
            exp = exp.replace(tzinfo=timezone.utc)
        expiry = exp.timestamp()
    else:
        expiry = time.time() + max(ttl_seconds, 1) if ttl_seconds else time.time() + 86400

    with _BLACKLIST_LOCK:
        _blacklist[token_jti] = expiry
    _cleanup_expired()


def remove(token_jti: str) -> None:
    """Remove a token JTI from the blacklist (e.g. admin un-revoke)."""
    with _BLACKLIST_LOCK:
        _blacklist.pop(token_jti, None)


def is_blacklisted(token_jti: str) -> bool:
    """Check whether a token JTI is in the blacklist.

    O(1) 定向判定：只检查目标条目自身的过期时间，命中已过期条目时就地删除。
    全量清理由 add()/count() 按 _CLEANUP_INTERVAL_SECONDS 节流触发（M39）。

    Args:
        token_jti: The JWT ID to check.

    Returns:
        *True* if the token has been revoked.
    """
    now = time.time()
    with _BLACKLIST_LOCK:
        expiry = _blacklist.get(token_jti)
        if expiry is None:
            return False
        if expiry <= now:
            # 惰性删除：过期的吊销条目不再拦截（与清理语义一致）
            del _blacklist[token_jti]
            return False
        return True


def load_from_db(db_session) -> int:
    """从数据库加载未过期黑名单到内存，返回加载条数。"""
    try:
        from app.models.token_blacklist import TokenBlacklist  # type: ignore[import-untyped]
        now = time.time()
        entries = (
            db_session.query(TokenBlacklist)
            .filter(
                TokenBlacklist.expires_at.is_(None)
                | (TokenBlacklist.expires_at > datetime.fromtimestamp(now, tz=timezone.utc))
            )
            .all()
        )
        # 与 add()/remove()/clear()/_cleanup_expired() 共用同一把锁：
        # 该函数在启动路径可能与应用线程并发写入，裸写会与清理遍历竞态。
        with _BLACKLIST_LOCK:
            for entry in entries:
                if entry.token_jti not in _blacklist:
                    if entry.expires_at is None:
                        # expires_at IS NULL = 永久吊销，用哨兵保留其语义
                        expiry = _PERMANENT
                    else:
                        # expires_at 为 UTC 存储的 aware/naive datetime：
                        # 统一按 UTC 解析，避免按本地时区解释导致吊销条目提前 8h 过期
                        exp = entry.expires_at
                        if exp.tzinfo is None:
                            exp = exp.replace(tzinfo=timezone.utc)
                        expiry = exp.timestamp()
                    _blacklist[entry.token_jti] = expiry
        if entries:
            logger.info("从数据库加载 %d 条黑名单记录", len(entries))
        return len(entries)
    except Exception as e:
        logger.debug("数据库黑名单加载失败（可能表未创建）: %s", e, exc_info=True)
        return 0


def clear() -> None:
    """Remove all entries from the blacklist."""
    with _BLACKLIST_LOCK:
        _blacklist.clear()


def count() -> int:
    """Return the number of currently blacklisted tokens."""
    _cleanup_expired()
    return len(_blacklist)


def _cleanup_expired() -> None:
    """Remove entries whose expiry timestamp has passed.

    全量扫描按 _CLEANUP_INTERVAL_SECONDS 节流（M39）：鉴权路径不再为每次判定
    付出 O(n)+持锁代价；单条过期判定由 is_blacklisted 就地完成。
    """
    global _last_cleanup_at
    now = time.time()
    with _BLACKLIST_LOCK:
        if now - _last_cleanup_at < _CLEANUP_INTERVAL_SECONDS:
            return
        _last_cleanup_at = now
        expired = [jti for jti, exp in _blacklist.items() if exp <= now]
        for jti in expired:
            del _blacklist[jti]
        degraded = _cap_permanent_entries(now)
    if expired:
        logger.debug("清理过期黑名单条目: %d 个", len(expired))
    if degraded:
        logger.warning(
            "永久吊销条目超过上限 %d，已将最早 %d 条降级为 %d 天有限 TTL（防内存无界增长）",
            _MAX_PERMANENT_ENTRIES,
            degraded,
            _PERMANENT_RETENTION_SECONDS // 86400,
        )


def _cap_permanent_entries(now: float) -> int:
    """把超出上限的最早永久条目降级为超长有限 TTL，返回降级条数（调用方须持锁）。"""
    permanent = [jti for jti, exp in _blacklist.items() if exp == _PERMANENT]
    overflow = len(permanent) - _MAX_PERMANENT_ENTRIES
    if overflow <= 0:
        return 0
    degraded_expiry = now + _PERMANENT_RETENTION_SECONDS
    for jti in permanent[:overflow]:
        _blacklist[jti] = degraded_expiry
    return overflow


# ---------------------------------------------------------------------------
# Database-backed blacklist (optional)
# ---------------------------------------------------------------------------


def add_to_db(token_jti: str, db_session, *, reason: str = "",
              expires_at: Optional[datetime] = None,
              user_id: Optional[int] = None) -> None:
    """Persist a blacklist entry to the database.

    Args:
        token_jti: The JWT ID.
        db_session: An active SQLAlchemy session.
        reason: Optional reason for revocation.
        expires_at: Optional token expiry datetime.
        user_id: Optional user ID associated with the token.
    """
    try:
        from app.models.token_blacklist import TokenBlacklist  # type: ignore[import-untyped]

        entry = TokenBlacklist(
            token_jti=token_jti,
            reason=reason or "manual_revoke",
            expires_at=expires_at,
            user_id=user_id,
        )
        db_session.add(entry)
        db_session.commit()
        logger.info("Token 已加入数据库黑名单: %s", token_jti[:12])
    except Exception as e:
        logger.exception("数据库黑名单写入失败: %s", e)
        try:
            db_session.rollback()
        except Exception as rollback_err:
            logger.debug("Rollback failed after blacklist write error: %s", rollback_err)
