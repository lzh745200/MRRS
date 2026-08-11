"""Audit middleware for logging API requests with user identity."""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs request method, path, status code, duration, and authenticated user.

    同时将每次 HTTP 请求落库到 ``api_access_logs`` 表（独立短 session，
    不影响请求事务）。落库失败仅写 WARNING 日志，绝不破坏业务请求。
    """

    async def dispatch(self, request, call_next):
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

        # 落库到 api_access_logs（独立 session，失败不破坏请求）
        self._persist_api_access_log(
            request=request,
            response_status=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id_int,
            username=username,
        )

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
                return None, username
        except Exception as e:
            logger.debug("审计中间件: token 解析失败（可能是未认证请求）: %s", e, exc_info=True)
            return None, None

    @staticmethod
    def _persist_api_access_log(request, response_status, duration_ms, user_id, username):
        """将本次请求落库到 api_access_logs，使用独立短 session。"""
        try:
            from app.core.database import SessionLocal
            from app.models.audit import APIAccessLog

            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            db = SessionLocal()
            try:
                db.add(
                    APIAccessLog(
                        user_id=user_id,
                        username=username,
                        endpoint=request.url.path,
                        method=request.method,
                        response_status=response_status,
                        response_time_ms=duration_ms,
                        ip_address=client_ip,
                        user_agent=user_agent,
                    )
                )
                safe_commit(db)
            finally:
                db.close()
        except Exception as e:
            # 审计落库失败绝不能破坏业务请求，只记录 WARNING
            logger.warning("api_access_logs 落库失败: %s", e, exc_info=True)
