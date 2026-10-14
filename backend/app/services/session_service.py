"""登录会话登记与按会话吊销。

对应问题（2026-10-14）：`GET /system/admin/users/{id}/sessions` 恒返回空数组，
会话区与"强制登出"不可达。根因是**没有会话表** —— 本模块把"登录/刷新时登记会话"
与"按会话精确吊销"补齐，并以 `core.token_blacklist` 作为吊销的执行通道
（`validate_token` 会拦截黑名单 jti，因此吊销即时生效）。

设计取舍：
- 多端登录**允许**（同用户可多条活跃会话）；按会话吊销只影响该条；
  "踢掉全部设备"仍由既有的 `token_version` 递增路径负责。
- 会话行不随令牌过期删除（留审计），列表按 `expires_at` 过滤。
- 所有登记/更新动作**绝不因失败而阻断主流程**（登录不能因为审计表写不进去就登不上）。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.transaction import safe_commit
from app.models.user_session import UserSession
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)


def _decode(token: str) -> Dict[str, Any]:
    """解析令牌载荷；任何异常都返回空字典（会话登记是旁路，不得阻断登录）。"""
    if not token:
        return {}
    try:
        from app.core.token_manager import validate_token

        ok, payload, _err = validate_token(token)
        return payload if ok and payload else {}
    except Exception:  # pragma: no cover - 纯防御：解析失败即视为无会话信息
        logger.debug("会话登记：令牌解析失败", exc_info=True)
        return {}


def _exp_to_dt(exp_ts: Any) -> Optional[datetime]:
    """JWT 的 exp（epoch 秒）→ aware UTC。"""
    if not exp_ts:
        return None
    try:
        return datetime.fromtimestamp(int(exp_ts), tz=timezone.utc)
    except (TypeError, ValueError):  # pragma: no cover - 纯防御
        return None


def record_login_session(
    db: Session,
    user: Any,
    tokens: Dict[str, str],
    request: Any = None,
) -> Optional[UserSession]:
    """登录（含 2FA 校验）成功后登记一条会话。失败只记日志，不影响登录结果。"""
    try:
        access_payload = _decode(tokens.get("access_token") or "")
        jti = access_payload.get("jti")
        if not user or not getattr(user, "id", None) or not jti:
            return None
        refresh_payload = _decode(tokens.get("refresh_token") or "")
        client = getattr(request, "client", None)
        headers = getattr(request, "headers", None)
        session = UserSession(
            user_id=user.id,
            token_jti=jti,
            refresh_jti=refresh_payload.get("jti"),
            ip_address=getattr(client, "host", None),
            user_agent=(headers.get("user-agent") if headers is not None else None),
            login_at=utcnow(),
            last_seen_at=utcnow(),
            expires_at=_exp_to_dt(refresh_payload.get("exp"))
            or (utcnow() + timedelta(days=7)),
        )
        db.add(session)
        safe_commit(db)
        return session
    except Exception:
        logger.warning("登记登录会话失败（不阻断登录）", exc_info=True)
        return None


def list_active_sessions(db: Session, user_id: int) -> List[UserSession]:
    """该用户当前活跃会话：未吊销且未过期（按登录时间倒序）。"""
    now = utcnow()
    return (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            or_(UserSession.expires_at.is_(None), UserSession.expires_at > now),
        )
        .order_by(UserSession.login_at.desc())
        .all()
    )


def get_session(db: Session, user_id: int, session_id: Any) -> Optional[UserSession]:
    """按主键取某用户的会话；id 非法/不存在返回 None。"""
    try:
        sid = int(session_id)
    except (TypeError, ValueError):
        return None
    return (
        db.query(UserSession)
        .filter(UserSession.id == sid, UserSession.user_id == user_id)
        .first()
    )


def revoke_session(
    db: Session,
    session: UserSession,
    *,
    operator_id: Optional[int] = None,
    reason: str = "",
) -> bool:
    """按会话精确吊销：jti 写入内存黑名单 + 持久化，并标记 revoked_at。

    内存黑名单让 `validate_token` 立刻拒绝该令牌；`add_to_db` 保证重启后依然生效。
    access 与 refresh 的 jti 一并吊销（否则可用刷新令牌"复活"该会话）。
    """
    from app.core import token_blacklist as blacklist

    for jti in (session.token_jti, session.refresh_jti):
        if not jti:
            continue
        blacklist.add(jti, expires_at=session.expires_at)
        try:
            blacklist.add_to_db(
                jti,
                db,
                reason=reason or "admin_revoke_session",
                expires_at=session.expires_at,
                user_id=session.user_id,
            )
        except Exception:  # pragma: no cover - 持久化失败不阻断，内存黑名单已生效
            logger.warning("会话吊销持久化失败 jti=%s", str(jti)[:12], exc_info=True)

    session.revoked_at = utcnow()
    session.revoked_by = operator_id
    session.revoke_reason = reason or None
    safe_commit(db)
    return True


def revoke_all_sessions(
    db: Session,
    user_id: int,
    *,
    operator_id: Optional[int] = None,
    reason: str = "admin_force_logout",
) -> int:
    """标记该用户全部活跃会话为已吊销（配合 token_version 递增使用）。"""
    sessions = list_active_sessions(db, user_id)
    for session in sessions:
        session.revoked_at = utcnow()
        session.revoked_by = operator_id
        session.revoke_reason = reason
    if sessions:
        safe_commit(db)
    return len(sessions)


def update_session_on_refresh(
    db: Session,
    old_refresh_jti: Optional[str],
    new_tokens: Dict[str, str],
) -> Optional[UserSession]:
    """令牌刷新后把会话指向新 jti。

    Args:
        old_refresh_jti: 旧刷新令牌的 jti —— **必须由调用方在吊销旧令牌之前解析**，
            （刷新流程会先把旧令牌写入黑名单，之后再 decode 必然失败）。

    不更新的话，会话行仍记着已被替换的旧 jti → 之后"按会话吊销"会吊销不到
    实际在用的令牌（表面成功、实际失效），属隐蔽的安全缺口。
    """
    old_jti = old_refresh_jti
    if not old_jti:
        return None
    session = (
        db.query(UserSession)
        .filter(UserSession.refresh_jti == old_jti, UserSession.revoked_at.is_(None))
        .first()
    )
    if not session:
        return None
    access_payload = _decode(new_tokens.get("access_token") or "")
    refresh_payload = _decode(new_tokens.get("refresh_token") or "")
    if access_payload.get("jti"):
        session.token_jti = access_payload["jti"]
    if refresh_payload.get("jti"):
        session.refresh_jti = refresh_payload["jti"]
    new_exp = _exp_to_dt(refresh_payload.get("exp"))
    if new_exp:
        session.expires_at = new_exp
    session.last_seen_at = utcnow()
    safe_commit(db)
    return session
