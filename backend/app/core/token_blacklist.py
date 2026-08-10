"""Persistent token blacklist.

Maintains a set of revoked JWT tokens so that compromised or logged-out
tokens cannot be reused.  Tokens are stored in-memory with an optional
database-backed persistence layer for production use.
"""

import logging
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
    _blacklist.pop(token_jti, None)


def is_blacklisted(token_jti: str) -> bool:
    """Check whether a token JTI is in the blacklist.

    Args:
        token_jti: The JWT ID to check.

    Returns:
        *True* if the token has been revoked.
    """
    _cleanup_expired()
    return token_jti in _blacklist


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
        for entry in entries:
            if entry.token_jti not in _blacklist:
                if entry.expires_at is None:
                    expiry = now + 86400
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
    _blacklist.clear()


def count() -> int:
    """Return the number of currently blacklisted tokens."""
    _cleanup_expired()
    return len(_blacklist)


def _cleanup_expired() -> None:
    """Remove entries whose expiry timestamp has passed."""
    now = time.time()
    with _BLACKLIST_LOCK:
        expired = [jti for jti, exp in _blacklist.items() if exp <= now]
        for jti in expired:
            del _blacklist[jti]
    if expired:
        logger.debug("清理过期黑名单条目: %d 个", len(expired))


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
