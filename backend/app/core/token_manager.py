"""JWT token management.

Provides a high-level API for creating, validating, refreshing, and
revoking JWT access/refresh tokens, wrapping the low-level JOSE calls.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _persist_revocation(jti: str, reason: str = "",
                        expires_at: Optional[datetime] = None,
                        user_id: Optional[int] = None) -> None:
    """将吊销的 token JTI 持久化到数据库（后台安全操作，失败不影响主流程）。"""
    try:
        from app.core.database import SessionLocal
        from app.core.token_blacklist import add_to_db
        db = SessionLocal()
        try:
            add_to_db(jti, db, reason=reason, expires_at=expires_at, user_id=user_id)
        finally:
            db.close()
    except Exception as e:
        logger.debug("持久化 token 黑名单失败（非关键）: %s", e, exc_info=True)


# ---------------------------------------------------------------------------
# Configuration (loaded lazily to avoid circular imports)
# ---------------------------------------------------------------------------


def _get_settings():
    """Return the application settings singleton."""
    try:
        from app.core.config import settings  # type: ignore[import-untyped]
        return settings
    except Exception as e:
        logger.warning("Token设置加载异常: %s", e, exc_info=True)
        return None


def _get_secret_key() -> str:
    """Return the configured JWT secret key."""

    from app.core.security import SECRET_KEY as _SECRET_KEY
    return _SECRET_KEY


def _get_algorithm() -> str:
    """Return the configured JWT algorithm."""
    from app.core.security import ALGORITHM as _ALGORITHM
    return _ALGORITHM


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_token_pair(
    subject: str,
    *,
    extra_claims: Optional[Dict[str, Any]] = None,
    access_ttl_minutes: Optional[int] = None,
    refresh_ttl_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Create an access + refresh token pair.

    Args:
        subject: The token subject (typically the username).
        extra_claims: Additional claims to include in both tokens.
        access_ttl_minutes: Access token TTL in minutes.
            Defaults to ``settings.ACCESS_TOKEN_EXPIRE_MINUTES`` or 480.
        refresh_ttl_days: Refresh token TTL in days.
            Defaults to ``settings.REFRESH_TOKEN_EXPIRE_DAYS`` or 7.

    Returns:
        A dict with keys ``access_token``, ``refresh_token``,
        ``token_type``, ``expires_in``.
    """
    settings = _get_settings()
    if access_ttl_minutes is None:
        access_ttl_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 480) if settings else 480
    if refresh_ttl_days is None:
        refresh_ttl_days = getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7) if settings else 7

    now = datetime.now(timezone.utc)
    jti_access = uuid.uuid4().hex
    jti_refresh = uuid.uuid4().hex

    secret = _get_secret_key()
    algorithm = _get_algorithm()

    import jwt

    # Access token
    access_payload = {
        "sub": subject,
        "jti": jti_access,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=access_ttl_minutes),
    }
    if extra_claims:
        access_payload.update(extra_claims)
    access_token = jwt.encode(access_payload, secret, algorithm=algorithm)

    # Refresh token
    refresh_payload = {
        "sub": subject,
        "jti": jti_refresh,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=refresh_ttl_days),
    }
    refresh_token = jwt.encode(refresh_payload, secret, algorithm=algorithm)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": access_ttl_minutes * 60,
    }


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


def validate_token(token: str, *, token_type: str = "access") -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Validate a JWT token.

    Args:
        token: The JWT string.
        token_type: Expected token type (``"access"`` or ``"refresh"``).

    Returns:
        A tuple ``(is_valid, payload, error_message)``.
    """
    if not token:
        return False, None, "令牌为空"

    # Check blacklist
    from app.core.token_blacklist import is_blacklisted

    try:
        import jwt
        from jwt import InvalidTokenError as JWTError
        secret = _get_secret_key()
        algorithm = _get_algorithm()
        payload = jwt.decode(token, secret, algorithms=[algorithm])

        jti = payload.get("jti")
        if jti and is_blacklisted(jti):
            return False, None, "令牌已被吊销"

        actual_type = payload.get("type")
        if actual_type and actual_type != token_type:
            return False, None, f"令牌类型不匹配 (expected {token_type}, got {actual_type})"

        return True, payload, None
    except JWTError as e:
        return False, None, f"令牌验证失败: {e}"


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------


def revoke_token(token: str, *, reason: str = "") -> bool:
    """Revoke a token by adding its JTI to the blacklist.

    Args:
        token: The JWT string to revoke.
        reason: Optional reason for the revocation.

    Returns:
        *True* if the token was successfully revoked.
    """
    try:
        import jwt
        secret = _get_secret_key()
        algorithm = _get_algorithm()
        # Decode without expiry check so we can blacklist it anyway
        payload = jwt.decode(token, secret, algorithms=[algorithm],
                             options={"verify_exp": False})
        jti = payload.get("jti")
        if not jti:
            logger.warning("Token 缺少 jti 声明，无法吊销")
            return False

        exp_claim = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp_claim, tz=timezone.utc) if exp_claim else None

        from app.core.token_blacklist import add

        add(jti, expires_at=expires_at)
        # 持久化到数据库，确保重启后吊销仍然有效
        _persist_revocation(jti, reason, expires_at=expires_at)
        logger.info("Token 已吊销 jti=%s reason=%s", jti[:12], reason)
        return True
    except Exception as e:
        logger.error("吊销 token 失败: %s", e)
        return False


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def refresh_access_token(refresh_token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Use a valid refresh token to issue a new access token.

    Args:
        refresh_token: The refresh token JWT string.

    Returns:
        A tuple ``(success, token_pair_dict, error_message)``.
    """
    valid, payload, err = validate_token(refresh_token, token_type="refresh")
    if not valid:
        return False, None, err

    subject = payload.get("sub")
    if not subject:
        return False, None, "Refresh token 缺少 subject"

    # Revoke the used refresh token (rotation)
    revoke_token(refresh_token, reason="refresh_rotation")

    # Issue new pair
    token_pair = create_token_pair(subject)
    return True, token_pair, None


# ---------------------------------------------------------------------------
# Singleton instance (backward compatibility)
# ---------------------------------------------------------------------------

class TokenManager:
    """Token manager singleton for backward compatibility."""

    def create_token_pair(self, subject: str, extra_claims: dict = None,
                          access_ttl_minutes: int = None, refresh_ttl_days: int = None):
        return create_token_pair(
            subject,
            extra_claims=extra_claims,
            access_ttl_minutes=access_ttl_minutes,
            refresh_ttl_days=refresh_ttl_days,
        )

    def validate_token(self, token: str, token_type: str = "access"):
        return validate_token(token, token_type=token_type)

    def revoke_token(self, token: str, reason: str = ""):
        return revoke_token(token, reason=reason)

    def refresh_access_token(self, refresh_token: str):
        return refresh_access_token(refresh_token)

    def create_access_token(self, subject: str, expires_delta=None) -> str:
        """向后兼容：返回仅 access_token 字符串"""
        result = create_token_pair(subject, access_ttl_minutes=(
            int(expires_delta.total_seconds() / 60) if expires_delta else None
        ))
        return result["access_token"]

    @staticmethod
    def decode_token(token: str, expected_type: str = "access") -> Optional[dict]:
        """向后兼容：解码 token 并验证类型"""
        valid, payload, _ = validate_token(token, token_type=expected_type)
        return payload if valid else None


token_manager = TokenManager()
