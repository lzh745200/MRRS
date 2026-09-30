# -*- coding: utf-8 -*-
"""
机器码权限服务

管理基于机器码的功能权限**限制**（restriction）。

语义（2026-09-30 深审澄清，与 models/rbac.py:225 及 rbac_service 的
`permissions - restricted_perms` 扣减逻辑一致）：本服务写入
machine_code_permissions 的每一行都表示"该机器码上禁用某权限"，RBAC 计算
用户有效权限时会把它从直接权限/角色权限中**扣除**。因此 grant_permission /
batch_grant_permissions 的实际效果是"限制/禁用"，而非放行——命名保留是为兼容
既有调用方，含义以本说明为准（fail-closed 方向，不会造成越权放行）。
"""

import logging
from datetime import datetime
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.models.machine_code import MachineCode
from app.models.rbac import MachineCodePermission
from app.models.base import _utcnow
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class MachineCodePermissionService:
    """机器码权限服务"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db

    def get_machine_code_permissions(self, machine_code_id: int) -> List[MachineCodePermission]:
        """获取机器码关联的功能权限列表

        Args:
            machine_code_id: 机器码ID

        Returns:
            List[MachineCodePermission]: 权限列表
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        return (
            self.db.query(MachineCodePermission).filter(MachineCodePermission.machine_code_id == machine_code_id).all()
        )

    def get_restricted_permissions(self, machine_code_id: int) -> Set[str]:
        """获取机器码限制的权限集合

        Args:
            machine_code_id: 机器码ID

        Returns:
            Set[str]: 被限制的权限标识符集合
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        now = _utcnow()
        rows = (
            self.db.query(MachineCodePermission.permission)
            .filter(
                MachineCodePermission.machine_code_id == machine_code_id,
                (MachineCodePermission.expires_at.is_(None) | (MachineCodePermission.expires_at > now)),
            )
            .all()
        )
        return {row[0] for row in rows}

    def get_user_restricted_permissions(self, user_id: int) -> Set[str]:
        """获取用户绑定机器码所限制的权限

        Args:
            user_id: 用户ID

        Returns:
            Set[str]: 被限制的权限标识符集合
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        # 获取用户的激活机器码
        machine_code_record = (
            self.db.query(MachineCode)
            .filter(
                MachineCode.user_id == user_id,
                MachineCode.status == "active",
            )
            .first()
        )

        if not machine_code_record:
            return set()

        return self.get_restricted_permissions(machine_code_record.id)

    def grant_permission(
        self,
        machine_code_id: int,
        permission: str,
        granted_by: int,
        expires_at: Optional[datetime] = None,
    ) -> MachineCodePermission:
        """为机器码登记一条权限**限制**（见模块 docstring）

        写入的行会被 rbac_service 从该机器码绑定用户的有效权限中扣除，即调用本
        方法的效果是"禁用该权限"，不是"放行该权限"。

        Args:
            machine_code_id: 机器码ID
            permission: 权限标识符
            granted_by: 授权人ID
            expires_at: 过期时间

        Returns:
            MachineCodePermission: 创建/更新的限制记录
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        # 检查是否已存在
        existing = (
            self.db.query(MachineCodePermission)
            .filter(
                MachineCodePermission.machine_code_id == machine_code_id,
                MachineCodePermission.permission == permission,
            )
            .first()
        )

        if existing:
            # 更新过期时间
            existing.granted_by = granted_by
            existing.expires_at = expires_at
            existing.updated_at = _utcnow()
            safe_commit(self.db)
            self.db.refresh(existing)
            return existing

        # 创建新记录
        record = MachineCodePermission(
            machine_code_id=machine_code_id,
            permission=permission,
            granted_by=granted_by,
            expires_at=expires_at,
        )
        self.db.add(record)
        safe_commit(self.db)
        self.db.refresh(record)

        logger.info(
            f"机器码权限已授予: machine_code_id={machine_code_id}, " f"permission={permission}, granted_by={granted_by}"
        )
        return record

    def revoke_permission(self, machine_code_id: int, permission: str) -> bool:
        """撤销机器码的权限

        Args:
            machine_code_id: 机器码ID
            permission: 权限标识符

        Returns:
            bool: 是否成功撤销
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        record = (
            self.db.query(MachineCodePermission)
            .filter(
                MachineCodePermission.machine_code_id == machine_code_id,
                MachineCodePermission.permission == permission,
            )
            .first()
        )

        if not record:
            return False

        self.db.delete(record)
        safe_commit(self.db)

        logger.info(f"机器码权限已撤销: machine_code_id={machine_code_id}, " f"permission={permission}")
        return True

    def batch_grant_permissions(
        self,
        machine_code_id: int,
        permissions: List[str],
        granted_by: int,
        expires_at: Optional[datetime] = None,
    ) -> int:
        """批量登记机器码权限**限制**（见模块 docstring；效果是禁用而非放行）

        Args:
            machine_code_id: 机器码ID
            permissions: 权限标识符列表
            granted_by: 授权人ID
            expires_at: 过期时间

        Returns:
            int: 已登记的限制条数
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        count = 0
        try:
            for perm in permissions:
                # 检查是否已存在
                existing = (
                    self.db.query(MachineCodePermission)
                    .filter(
                        MachineCodePermission.machine_code_id == machine_code_id,
                        MachineCodePermission.permission == perm,
                    )
                    .first()
                )
                if existing:
                    existing.granted_by = granted_by
                    existing.expires_at = expires_at
                    existing.updated_at = _utcnow()
                else:
                    record = MachineCodePermission(
                        machine_code_id=machine_code_id,
                        permission=perm,
                        granted_by=granted_by,
                        expires_at=expires_at,
                    )
                    self.db.add(record)
                count += 1
            safe_commit(self.db)
        except Exception as e:
            self.db.rollback()
            logger.warning(f"批量授予权限失败: machine_code_id={machine_code_id}, error={e}")
        return count

    def batch_revoke_permissions(self, machine_code_id: int, permissions: List[str]) -> int:
        """批量撤销机器码权限

        Args:
            machine_code_id: 机器码ID
            permissions: 权限标识符列表

        Returns:
            int: 成功撤销的权限数量
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        count = 0
        try:
            for perm in permissions:
                record = (
                    self.db.query(MachineCodePermission)
                    .filter(
                        MachineCodePermission.machine_code_id == machine_code_id,
                        MachineCodePermission.permission == perm,
                    )
                    .first()
                )
                if record:
                    self.db.delete(record)
                    count += 1
            safe_commit(self.db)
            logger.info(f"批量撤销机器码权限: machine_code_id={machine_code_id}, count={count}")
        except Exception as e:
            self.db.rollback()
            logger.warning(f"批量撤销权限失败: machine_code_id={machine_code_id}, error={e}")
        return count

    def delete_all_permissions(self, machine_code_id: int) -> int:
        """删除机器码的所有权限

        Args:
            machine_code_id: 机器码ID

        Returns:
            int: 删除的权限数量
        """
        if not self.db:
            raise ValueError("数据库会话未初始化")

        count = (
            self.db.query(MachineCodePermission)
            .filter(MachineCodePermission.machine_code_id == machine_code_id)
            .delete()
        )
        safe_commit(self.db)

        logger.info(f"机器码所有权限已删除: machine_code_id={machine_code_id}, count={count}")
        return count
