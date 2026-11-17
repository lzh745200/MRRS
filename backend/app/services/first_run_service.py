"""出厂首装/等价空库判定（权限包与账号开通包共享）。

安全边界：只有「唯一出厂种子管理员 + 从未登录/改密 + 未真正初始化」才允许
匿名首装导入。任何状态不可读都 fail-closed，绝不把数据库异常当作空库。
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


def is_pristine_first_run(db: Session) -> bool:
    """返回是否仍处在可匿名首装的出厂状态。"""
    from app.core.constants import FACTORY_ADMIN_USERNAME
    from app.services.system_config_service import SystemConfigService

    seed_username = (
        os.getenv("DEFAULT_ADMIN_USERNAME", "").strip() or FACTORY_ADMIN_USERNAME
    )
    try:
        users = db.query(User).limit(2).all()
    except Exception as exc:  # noqa: BLE001 - 账号状态不可判定时必须 fail-closed
        logger.warning("读取账号状态失败，按已初始化处理（禁止匿名导入）：%s", exc)
        return False
    if len(users) != 1:
        return False
    seed_admin = users[0]
    if not (
        (getattr(seed_admin, "username", "") or "").strip() == seed_username
        and getattr(seed_admin, "is_superuser", False)
        and getattr(seed_admin, "must_change_password", False)
        and getattr(seed_admin, "last_login", None) is None
    ):
        return False

    cfg = SystemConfigService(db)
    try:
        # 真实初始化会同时写 organization_id/system_id；种子兜底只写 initialized。
        if (cfg.get("organization_id") or "").strip():
            return False
        if (cfg.get("system_id") or "").strip():
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - 配置读不出时退回 initialized 布尔
        logger.warning("读取系统初始化标记失败，退回 initialized 布尔判定：%s", exc)
        try:
            return not cfg.is_initialized()
        except Exception as exc2:  # noqa: BLE001 - 最终 fail-closed
            logger.warning("读取系统初始化状态失败，按已初始化处理（禁止匿名导入）：%s", exc2)
            return False
