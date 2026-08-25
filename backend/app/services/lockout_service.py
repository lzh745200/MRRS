"""
账户锁定服务

离线桌面管理系统 — 统一账户锁定策略。
提供锁定检查、失败计数递增、过期自动清理等功能，
消除 login、refresh_token、main.py 启动解锁、machine_code 密码重置中的重复逻辑。

设计原则：
- 锁定检查：锁定未过期 → HTTP 423；已过期 → 自动清理
- 原子递增：使用读-改-写方式（兼容旧版 SQLite < 3.35，不依赖 RETURNING 子句）
- 统一入口：所有需要锁定检查的组件通过此服务调用
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import case, func, update
from sqlalchemy.orm import Session
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class LockoutService:
    """账户锁定策略的统一入口。

    使用方法：
        lockout = LockoutService()
        lockout.check_locked(user, username, db)          # 检查锁定 → 抛 423 或自动清理
        failed_count = lockout.record_failed(user, db)     # 原子递增 → 返回新计数
        lockout.clear(user, db)                            # 清除锁定状态
        lockout.unlock_expired(db)                         # 批量解锁所有过期账户
    """

    def __init__(
        self,
        max_failed_attempts: int = 5,
        lockout_minutes: int = 15,
    ):
        self.max_failed_attempts = max_failed_attempts
        self.lockout_minutes = lockout_minutes

    # ── 锁定状态检查 ────────────────────────────────────────────

    def check_locked(
        self,
        user,
        username: str,
        db: Session,
        now: Optional[datetime] = None,
    ) -> None:
        """检查账户锁定状态。

        锁定未过期时抛出 HTTPException(423)，已过期则自动清理。
        应在认证流程（login、refresh_token）中调用。

        Args:
            user: User ORM 对象
            username: 用户名（仅用于日志）
            db: 数据库会话
            now: 当前时间（None 则使用 UTC now）

        Raises:
            HTTPException(423): 账户仍在锁定期内
            HTTPException(500): 检查锁定状态时发生意外错误
        """
        from fastapi import HTTPException, status as http_status

        if now is None:
            now = datetime.now(timezone.utc)

        try:
            if getattr(user, "locked_until", None) and user.locked_until:
                lock_time = user.locked_until
                if lock_time.tzinfo is None:
                    lock_time = lock_time.replace(tzinfo=timezone.utc)

                if now >= lock_time:
                    logger.info(
                        "自动清理过期锁定: user=%s", username,
                    )
                    self.clear(user, db)
                else:
                    remaining = int((lock_time - now).total_seconds() / 60) + 1
                    logger.warning(
                        "账户已锁定: user=%s, 剩余%d分钟",
                        username, remaining,
                    )
                    raise HTTPException(
                        status_code=http_status.HTTP_423_LOCKED,
                        detail=f"账户已锁定，请{remaining}分钟后再试",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("检查锁定状态时出错: %s", e, exc_info=True)
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统错误，请稍后再试",
            )

    # ── 失败计数递增 ────────────────────────────────────────────

    def record_failed(self, user, db: Session) -> int:
        """递增登录失败计数，达到阈值时自动锁定。

        W2-T6 原子化：单条 UPDATE 在 SQL 端完成计数+锁定判定
        （COALESCE+CASE），并以 RETURNING 取回新计数值，
        消除 WAL 并发下读-改-写丢更新。

        Args:
            user: User ORM 对象
            db: 数据库会话

        Returns:
            int: 更新后的失败次数
        """
        from app.models.user import User

        now = datetime.now(timezone.utc)

        # W2-T6：单条原子 UPDATE——计数与锁定判定全部在 SQL 端完成，
        # 消除 WAL 并发下的读-改-写丢更新（历史 docstring 所述
        # "旧版 SQLite 不支持 RETURNING" 已不成立，运行时自带 3.4x）。
        new_count_expr = func.coalesce(User.failed_login_count, 0) + 1
        stmt = (
            update(User)
            .where(User.id == user.id)
            .values(
                failed_login_count=new_count_expr,
                locked_until=case(
                    (
                        new_count_expr >= self.max_failed_attempts,
                        now + timedelta(minutes=self.lockout_minutes),
                    ),
                    else_=User.locked_until,
                ),
            )
            .returning(User.failed_login_count)
        )
        failed_count = db.execute(stmt).scalar_one()
        safe_commit(db)

        new_locked_until = (
            now + timedelta(minutes=self.lockout_minutes)
            if failed_count >= self.max_failed_attempts
            else getattr(user, "locked_until", None)
        )

        # 同步 ORM 对象状态，避免后续访问时读到过期值
        user.failed_login_count = failed_count
        user.locked_until = new_locked_until

        logger.info(
            "登录失败计数: user=%s, count=%d/%d",
            getattr(user, "username", "?"), failed_count, self.max_failed_attempts,
        )
        return failed_count

    # ── 清除锁定 ────────────────────────────────────────────────

    def clear(self, user, db: Session) -> None:
        """清除账户锁定状态（failed_login_count=0, locked_until=None）。"""
        user.failed_login_count = 0
        user.locked_until = None
        safe_commit(db)

    # ── 批量解锁过期账户 ────────────────────────────────────────

    def unlock_expired(
        self, db: Session, admin_username: str = "admin"
    ) -> int:
        """解锁所有锁定已过期的账户。

        用于应用启动时自动清理过期的锁定记录。
        admin 账户强制解锁（单机版误锁后无法远程解锁）。

        Args:
            db: 数据库会话
            admin_username: 管理员用户名，强制解锁

        Returns:
            int: 解锁的账户数量
        """
        from app.models.user import User
        from sqlalchemy import select

        now = datetime.now(timezone.utc)
        unlocked_count = 0

        # 1. 解锁所有过期锁定
        stmt = select(User).where(
            User.locked_until.isnot(None),
            User.locked_until <= now,
        )
        for user in db.execute(stmt).scalars().all():
            user.locked_until = None
            user.failed_login_count = 0
            unlocked_count += 1
            logger.info("启动时解锁过期账户: user=%s", user.username)

        # 2. admin 强制解锁
        admin_stmt = select(User).where(
            User.username == admin_username,
            User.locked_until.isnot(None),
        )
        admin_user = db.execute(admin_stmt).scalar_one_or_none()
        if admin_user:
            admin_user.locked_until = None
            admin_user.failed_login_count = 0
            unlocked_count += 1
            logger.info("admin 账户强制解锁（单机版误锁保护）")

        if unlocked_count > 0:
            safe_commit(db)
            logger.info("共解锁 %d 个账户", unlocked_count)

        return unlocked_count


# 模块级单例（使用默认配置，阈值从 config.py 读取）
_lockout_service: Optional[LockoutService] = None


def get_lockout_service(
    max_failed_attempts: Optional[int] = None,
    lockout_minutes: Optional[int] = None,
) -> LockoutService:
    """获取 LockoutService 单例。

    首次调用时从 config 读取参数，后续调用返回同一实例。
    """
    global _lockout_service
    if _lockout_service is None:
        from app.core.config import settings
        _lockout_service = LockoutService(
            max_failed_attempts=max_failed_attempts or settings.MAX_FAILED_LOGIN_ATTEMPTS,
            lockout_minutes=lockout_minutes or settings.ACCOUNT_LOCKOUT_MINUTES,
        )
    return _lockout_service
