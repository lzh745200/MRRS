"""启动种子钩子：默认管理员 / 锁定账户解锁（B3 自 main.py 迁入，逻辑不变）。"""

import logging
import os

from app.core.constants import FACTORY_ADMIN_PASSWORD, FACTORY_ADMIN_USERNAME
from app.core.security import hash_password
from app.core.transaction import safe_commit

logger = logging.getLogger("assistance_management")

# 默认管理员用户名（可通过环境变量配置）
DEFAULT_ADMIN_USERNAME = (
    os.getenv("DEFAULT_ADMIN_USERNAME", "").strip() or FACTORY_ADMIN_USERNAME
)


def _seed_default_admin():
    """确保默认管理员账户存在，并在启动时解锁所有被锁定的用户账户。

    首次启动时使用 DEFAULT_ADMIN_PASSWORD 环境变量；未设置时使用出厂默认
    密码 Admin@2026（安装包开箱即用）。must_change_password=True 强制首次
    登录修改密码。

    离线单机系统没有远程管理员可以手动解锁账户，因此每次启动时
    自动重置所有用户的锁定状态，确保用户不会因上次会话的失败尝试
    而被永久锁定。运行期间的锁定机制仍然正常生效。
    """
    from app.core.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        from app.services.lockout_service import get_lockout_service
        svc = get_lockout_service()
        unlocked_count = svc.unlock_expired(db, admin_username=DEFAULT_ADMIN_USERNAME)

        if unlocked_count > 0:
            logger.info("启动时已自动处理 %d 个账户", unlocked_count)

        admin = db.query(User).filter(User.username == DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            # 密码来源优先级：
            #   1. DEFAULT_ADMIN_PASSWORD 环境变量（保密部署可注入随机强密码）
            #   2. 文档化出厂默认密码 Admin@2026（安装包开箱即用）
            # 两种来源均强制 must_change_password=True，首次登录必须修改。
            _admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "").strip()
            if not _admin_password:
                _admin_password = FACTORY_ADMIN_PASSWORD
                logger.warning(
                    "使用出厂默认密码创建管理员（admin / %s），"
                    "首次登录强制修改；保密部署请设置 DEFAULT_ADMIN_PASSWORD 环境变量",
                    FACTORY_ADMIN_PASSWORD,
                )

            # 尝试获取顶级组织作为管理员的所属组织
            top_org_id = None
            try:
                from app.models.organization import Organization

                top_org = db.query(Organization).filter(Organization.parent_id.is_(None)).first()
                if top_org:
                    top_org_id = top_org.id
            except Exception as e:
                logger.warning("Failed to get top organization: %s", e)
            admin = User(
                username=DEFAULT_ADMIN_USERNAME,
                email="admin@example.com",
                hashed_password=hash_password(_admin_password),
                full_name="系统管理员",
                role="admin",
                is_active=True,
                is_superuser=True,
                department="系统管理部",
                organization_id=top_org_id,
                permissions="",
                must_change_password=True,
            )
            db.add(admin)
            safe_commit(db)
            logger.info(
                "默认管理员账户已创建 (用户名: %s, 请通过 DEFAULT_ADMIN_PASSWORD 环境变量设置强密码，首次登录须修改密码)",
                DEFAULT_ADMIN_USERNAME,
            )
        else:
            logger.info("管理员账户已存在，跳过创建")
    except Exception as e:
        db.rollback()
        logger.error("创建默认管理员失败: %s", e)
    finally:
        db.close()
