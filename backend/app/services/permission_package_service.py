"""
权限配置包管理服务

用于离线多机协作场景：管理员导出完整权限配置为 ZIP 包，
在另一台电脑导入后完全还原权限分配。

ZIP 结构:
  manifest.json           — 版本、时间戳、用户数、角色数、SHA-256 校验和
  data/roles.json         — 所有 RBAC 角色 + 权限定义
  data/user_roles.json    — 用户↔角色关联
  data/user_permissions.json — 用户直接权限
  data/user_menus.json    — 用户 allowed_menus 覆盖
  data/user_legacy.json   — User.role, User.permissions, User.data_scope

导入策略：完全替换（mirror mode）。目标电脑的所有权限配置被包内容覆盖。
用户名匹配用户，不存在则跳过。
"""

import hashlib
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.rbac import (
    RbacRole,
    RolePermission,
    UserPermission,
    UserRole,
)
from app.models.user import User

logger = logging.getLogger(__name__)

CURRENT_VERSION = "1.0"

# 系统内置角色名 — 导入时不删除/不覆盖
SYSTEM_ROLE_NAMES = {"super_admin", "admin", "user", "viewer"}


class PermissionPackageService:
    """权限配置包服务"""

    def __init__(self, db: Session):
        self.db = db

    # ================================================================
    # 导出
    # ================================================================

    def export_package(
        self,
        password: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        导出完整权限配置包

        Args:
            password: 可选的加密密码
            description: 导出说明

        Returns:
            PermissionPackageExportResult 字典
        """
        # 1. 收集所有 RBAC 角色 + 权限
        roles = self.db.query(RbacRole).order_by(RbacRole.priority).all()
        roles_data = []
        for role in roles:
            role_perms = (
                self.db.query(RolePermission)
                .filter(RolePermission.role_id == role.id)
                .all()
            )
            roles_data.append({
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "is_system": role.is_system,
                "is_active": role.is_active,
                "priority": role.priority,
                "permissions": [rp.permission for rp in role_perms],
            })

        # 2. 收集用户-角色关联（附带 username/role_name，跨机器按名称匹配而非数字ID）
        user_roles = self.db.query(UserRole).all()
        user_id_to_name = {
            u.id: u.username
            for u in self.db.query(User.id, User.username).all()
        }
        role_id_to_name = {
            r.id: r.name for r in self.db.query(RbacRole.id, RbacRole.name).all()
        }
        org_id_to_code = {}
        from app.models.organization import Organization

        for o in self.db.query(Organization.id, Organization.code).all():
            org_id_to_code[o.id] = o.code

        user_roles_data = []
        for ur in user_roles:
            user_roles_data.append({
                "user_id": ur.user_id,
                "username": user_id_to_name.get(ur.user_id),
                "role_id": ur.role_id,
                "role_name": role_id_to_name.get(ur.role_id),
                "expires_at": ur.expires_at.isoformat() if ur.expires_at else None,
            })

        # 3. 收集用户直接权限（附带 username）
        user_permissions = self.db.query(UserPermission).all()
        user_permissions_data = []
        for up in user_permissions:
            user_permissions_data.append({
                "user_id": up.user_id,
                "username": user_id_to_name.get(up.user_id),
                "permission": up.permission,
                "expires_at": up.expires_at.isoformat() if up.expires_at else None,
            })

        # 4. 收集用户菜单覆盖
        users = self.db.query(User).filter(User.is_active == True).all()  # noqa: E712
        user_menus_data = []
        user_legacy_data = []
        for user in users:
            # 菜单覆盖
            if user.allowed_menus is not None:
                try:
                    menus = (
                        json.loads(user.allowed_menus)
                        if isinstance(user.allowed_menus, str)
                        else user.allowed_menus
                    )
                except (json.JSONDecodeError, TypeError):
                    menus = None
                if menus is not None:
                    user_menus_data.append({
                        "username": user.username,
                        "allowed_menus": menus,
                    })
            # 遗留权限字段（附带组织编码，跨机器按编码恢复归属）
            user_legacy_data.append({
                "username": user.username,
                "role": user.role or "user",
                "permissions": user.permissions or "",
                "data_scope": user.data_scope or "org",
                "is_superuser": user.is_superuser or False,
                "organization_id": user.organization_id,
                "organization_code": org_id_to_code.get(user.organization_id),
            })

        # 5. 收集组织信息（用于跨机器迁移时恢复用户-组织关联）
        orgs = self.db.query(Organization).filter(Organization.is_active == True).all()  # noqa: E712
        organizations_data = []
        for org in orgs:
            organizations_data.append({
                "id": org.id,
                "name": org.name,
                "code": org.code,
                "org_type": getattr(org, "org_type", None),
                "level": getattr(org, "level", None),
                "parent_id": getattr(org, "parent_id", None),
                "is_active": org.is_active,
                "sort_order": getattr(org, "sort_order", 0),
            })

        # 内容级校验和：对数据段规范化序列化后取 SHA-256，
        # 写入 manifest 供导入端校验（ZIP 字节自身无法嵌入自身校验和）
        content_checksum = self._calculate_content_checksum({
            "roles": roles_data,
            "user_roles": user_roles_data,
            "user_permissions": user_permissions_data,
            "user_menus": user_menus_data,
            "user_legacy": user_legacy_data,
            "organizations": organizations_data,
        })

        # 构建清单
        manifest = {
            "version": CURRENT_VERSION,
            "export_time": datetime.now(timezone.utc).isoformat(),
            "user_count": len(user_legacy_data),
            "role_count": len(roles_data),
            "organization_count": len(organizations_data),
            "description": description,
            "content_checksum": content_checksum,
        }

        # 生成 ZIP
        from app.utils.paths import get_uploads_path

        upload_dir = str(get_uploads_path("permission_packages"))
        os.makedirs(upload_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"permission_package_{timestamp}.zip"
        file_path = os.path.join(upload_dir, file_name)

        with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("data/roles.json", json.dumps(roles_data, ensure_ascii=False, indent=2))
            zf.writestr("data/user_roles.json", json.dumps(user_roles_data, ensure_ascii=False, indent=2))
            zf.writestr("data/user_permissions.json", json.dumps(user_permissions_data, ensure_ascii=False, indent=2))
            zf.writestr("data/user_menus.json", json.dumps(user_menus_data, ensure_ascii=False, indent=2))
            zf.writestr("data/user_legacy.json", json.dumps(user_legacy_data, ensure_ascii=False, indent=2))
            zf.writestr("data/organizations.json", json.dumps(organizations_data, ensure_ascii=False, indent=2))

        # 计算校验和
        checksum = self._calculate_checksum(file_path)

        logger.info(
            "权限配置包已导出: %s (角色 %d, 用户 %d, checksum=%s)",
            file_path,
            len(roles_data),
            len(user_legacy_data),
            checksum,
        )

        return {
            "success": True,
            "file_path": file_path,
            "file_name": file_name,
            "file_size": os.path.getsize(file_path),
            "checksum": checksum,
            "user_count": len(user_legacy_data),
            "role_count": len(roles_data),
            "message": f"导出完成: {len(roles_data)} 个角色, {len(user_legacy_data)} 个用户, {len(organizations_data)} 个组织",
        }

    # ================================================================
    # 导入 — 预览阶段
    # ================================================================

    def import_package(self, file_path: str) -> Dict[str, Any]:
        """
        导入权限配置包（预览阶段 — 验证 + 返回预览数据）

        Args:
            file_path: ZIP 文件路径

        Returns:
            {"success": bool, "preview": dict | None, "errors": list, "message": str}
        """
        errors = []
        warnings = []

        if not os.path.exists(file_path):
            return {"success": False, "errors": ["文件不存在"], "message": "文件不存在"}

        if not zipfile.is_zipfile(file_path):
            return {"success": False, "errors": ["不是有效的 ZIP 文件"], "message": "不是有效的 ZIP 文件"}

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()

                # 验证必要文件
                required = ["manifest.json", "data/roles.json", "data/user_legacy.json"]
                for req in required:
                    if req not in names:
                        errors.append(f"缺少必要文件: {req}")

                if errors:
                    return {"success": False, "errors": errors, "message": "包结构不完整"}

                # 读取清单
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                version = manifest.get("version", "unknown")
                if version != CURRENT_VERSION:
                    warnings.append(f"配置包版本 {version} 与当前版本 {CURRENT_VERSION} 不匹配")

                # 读取角色
                roles_data = json.loads(zf.read("data/roles.json").decode("utf-8"))

                # 读取用户遗留数据用于用户名匹配
                user_legacy_data = json.loads(zf.read("data/user_legacy.json").decode("utf-8"))

                # 读取全部数据段并做内容校验和强校验（防损坏/篡改）
                def _read_json(name):
                    return (
                        json.loads(zf.read(name).decode("utf-8"))
                        if name in names else []
                    )

                segments = {
                    "roles": roles_data,
                    "user_roles": _read_json("data/user_roles.json"),
                    "user_permissions": _read_json("data/user_permissions.json"),
                    "user_menus": _read_json("data/user_menus.json"),
                    "user_legacy": user_legacy_data,
                    "organizations": _read_json("data/organizations.json"),
                }
                expected_checksum = manifest.get("content_checksum")
                if expected_checksum:
                    actual_checksum = self._calculate_content_checksum(segments)
                    if actual_checksum != expected_checksum:
                        errors.append(
                            "内容校验和不匹配：权限包已损坏或被篡改，拒绝导入"
                        )
                        return {
                            "success": False,
                            "errors": errors,
                            "message": "内容校验失败，请重新导出权限包",
                        }
                else:
                    warnings.append("配置包缺少内容校验和（旧版本导出），已跳过完整性校验")

                export_usernames = {u["username"] for u in user_legacy_data}

                # 检查哪些用户在当前系统中存在
                existing_users = (
                    self.db.query(User)
                    .filter(User.username.in_(export_usernames))
                    .all()
                )
                existing_usernames = {u.username for u in existing_users}
                missing_usernames = export_usernames - existing_usernames
                if missing_usernames:
                    warnings.append(
                        f"以下 {len(missing_usernames)} 个用户在目标系统中不存在，将跳过: "
                        + ", ".join(sorted(list(missing_usernames))[:10])
                        + ("..." if len(missing_usernames) > 10 else "")
                    )

                preview = {
                    "version": version,
                    "export_time": manifest.get("export_time"),
                    "roles": roles_data[:20],  # 预览前 20 个角色
                    "role_count": len(roles_data),
                    "user_role_count": (
                        len(json.loads(zf.read("data/user_roles.json").decode("utf-8")))
                        if "data/user_roles.json" in names else 0
                    ),
                    "user_permission_count": (
                        len(json.loads(zf.read("data/user_permissions.json").decode("utf-8")))
                        if "data/user_permissions.json" in names else 0
                    ),
                    "user_menu_count": (
                        len(json.loads(zf.read("data/user_menus.json").decode("utf-8")))
                        if "data/user_menus.json" in names else 0
                    ),
                    "user_legacy_count": len(user_legacy_data),
                    "warnings": warnings,
                }

            return {
                "success": True,
                "preview": preview,
                "errors": [],
                "message": f"验证通过。将导入 {len(roles_data)} 个角色，更新 {len(existing_usernames)} 个用户权限",
            }

        except json.JSONDecodeError as e:
            return {"success": False, "errors": [f"JSON 解析错误: {e}"], "message": f"JSON 解析错误: {e}"}
        except Exception as e:  # pragma: no cover
            logger.error("权限配置包预览失败: %s", e, exc_info=True)
            return {"success": False, "errors": [str(e)], "message": f"预览失败: {e}"}

    # ================================================================
    # 导入 — 确认阶段
    # ================================================================

    def confirm_import(self, file_path: str, overwrite_existing: bool = True) -> Dict[str, Any]:
        """确认导入权限配置包（应用阶段 — 完全替换）"""
        if not os.path.exists(file_path) or not zipfile.is_zipfile(file_path):
            return {"success": False, "errors": ["无效的文件"], "message": "无效的文件"}

        parsed = self._parse_import_zip(file_path)
        if not parsed:
            return {"success": False, "errors": ["解析 ZIP 失败"], "message": "解析失败"}

        roles_data, user_roles_data, user_permissions_data, \
            user_menus_data, user_legacy_data, organizations_data = parsed

        errors = []
        stats = self._init_import_stats()

        try:
            if overwrite_existing:
                self._clear_existing_data()

            role_id_map, stats, errors = self._import_roles(roles_data, stats, errors)
            self.db.flush()

            # 先导入组织信息（用户导入时需要匹配组织）
            stats, errors = self._import_organizations(organizations_data, stats, errors)
            self.db.flush()

            stats, errors = self._import_user_roles(user_roles_data, role_id_map, stats, errors)
            stats, errors = self._import_user_permissions(user_permissions_data, stats, errors)
            stats, errors = self._import_user_menus(user_menus_data, stats, errors)
            stats, errors = self._import_user_legacy(user_legacy_data, stats, errors)

            self.db.commit()
            self._log_import_result(stats)
            return self._build_import_response(stats, errors)
        except Exception as e:  # pragma: no cover
            self.db.rollback()
            logger.error("权限配置包导入失败: %s", e, exc_info=True)
            return {"success": False, "errors": [str(e)], "message": f"导入失败: {e}"}

    def _parse_import_zip(self, file_path: str):
        """解析 ZIP 导入包，返回各数据段。"""
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                roles_data = json.loads(zf.read("data/roles.json").decode("utf-8"))
                user_roles_data = (
                    json.loads(zf.read("data/user_roles.json").decode("utf-8"))
                    if "data/user_roles.json" in zf.namelist() else []
                )
                user_permissions_data = (
                    json.loads(zf.read("data/user_permissions.json").decode("utf-8"))
                    if "data/user_permissions.json" in zf.namelist() else []
                )
                user_menus_data = (
                    json.loads(zf.read("data/user_menus.json").decode("utf-8"))
                    if "data/user_menus.json" in zf.namelist() else []
                )
                user_legacy_data = json.loads(zf.read("data/user_legacy.json").decode("utf-8"))
                organizations_data = (
                    json.loads(zf.read("data/organizations.json").decode("utf-8"))
                    if "data/organizations.json" in zf.namelist() else []
                )
            return (roles_data, user_roles_data, user_permissions_data,
                    user_menus_data, user_legacy_data, organizations_data)
        except Exception as e:  # pragma: no cover
            logger.error("解析权限配置包 JSON 数据失败: %s", e)
            return None

    def _init_import_stats(self) -> Dict[str, int]:
        return {
            "roles_created": 0, "roles_updated": 0,
            "user_roles_assigned": 0, "user_permissions_assigned": 0,
            "user_roles_skipped": 0, "user_permissions_skipped": 0,
            "user_menus_updated": 0, "user_legacy_updated": 0,
            "organizations_created": 0, "organizations_updated": 0,
        }

    def _clear_existing_data(self):
        """完全替换模式：删除现有非系统角色和权限关联。"""
        system_role_ids = {
            r.id for r in self.db.query(RbacRole)
            .filter(RbacRole.name.in_(SYSTEM_ROLE_NAMES))
            .all()
        }
        non_system_roles = (
            self.db.query(RbacRole)
            .filter(~RbacRole.name.in_(SYSTEM_ROLE_NAMES))
            .all()
        )
        for role in non_system_roles:
            self.db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
            self.db.delete(role)
        for sid in system_role_ids:
            self.db.execute(delete(RolePermission).where(RolePermission.role_id == sid))

        self.db.execute(delete(UserRole))
        self.db.execute(delete(UserPermission))
        self.db.flush()

    def _import_organizations(self, organizations_data, stats, errors):
        """导入组织信息。按 code 匹配，不存在则创建。"""
        from app.models.organization import Organization

        for org_data in organizations_data:
            try:
                code = org_data.get("code")
                name = org_data.get("name", "")
                if not name:
                    continue

                # 优先按 code 匹配，其次按 name 匹配
                existing = None
                if code:
                    existing = (
                        self.db.query(Organization)
                        .filter(Organization.code == code)
                        .first()
                    )
                if not existing:
                    existing = (
                        self.db.query(Organization)
                        .filter(Organization.name == name)
                        .first()
                    )

                if existing:
                    # 更新现有组织
                    if code:
                        existing.code = code
                    existing.org_type = org_data.get("org_type", existing.org_type)
                    existing.level = org_data.get("level", existing.level)
                    existing.is_active = org_data.get("is_active", True)
                    existing.sort_order = org_data.get("sort_order", existing.sort_order or 0)
                    stats["organizations_updated"] += 1
                else:
                    # 创建新组织
                    new_org = Organization(
                        name=name,
                        code=code,
                        org_type=org_data.get("org_type"),
                        level=org_data.get("level"),
                        is_active=org_data.get("is_active", True),
                        sort_order=org_data.get("sort_order", 0),
                    )
                    self.db.add(new_org)
                    self.db.flush()
                    stats["organizations_created"] += 1
            except Exception as e:  # pragma: no cover
                errors.append(f"组织「{org_data.get('name', '未知')}」导入失败: {e}")
        return stats, errors

    def _import_roles(self, roles_data, stats, errors):
        """导入角色及角色权限。"""
        role_id_map: Dict[str, str] = {}
        for role_data in roles_data:
            try:
                old_id, new_id = self._upsert_role(role_data, stats)
                role_id_map[old_id] = new_id
                for perm in role_data.get("permissions", []):
                    self.db.add(RolePermission(role_id=new_id, permission=perm))
            except Exception as e:  # pragma: no cover
                errors.append(f"角色「{role_data.get('name', '未知')}」导入失败: {e}")
        return role_id_map, stats, errors

    def _upsert_role(self, role_data, stats):
        """创建或更新单个角色。"""
        name = role_data.get("name", "")
        existing = self.db.query(RbacRole).filter(RbacRole.name == name).first()
        if existing:
            existing.description = role_data.get("description", existing.description)
            existing.is_active = role_data.get("is_active", True)
            existing.priority = role_data.get("priority", 100)
            stats["roles_updated"] += 1
            return role_data["id"], existing.id
        new_role = RbacRole(
            name=name,
            description=role_data.get("description"),
            is_system=role_data.get("is_system", False),
            is_active=role_data.get("is_active", True),
            priority=role_data.get("priority", 100),
        )
        self.db.add(new_role)
        self.db.flush()
        stats["roles_created"] += 1
        return role_data["id"], new_role.id

    def _import_user_roles(self, user_roles_data, role_id_map, stats, errors):
        """导入用户-角色关联（优先 username 匹配用户、role_name 兜底匹配角色）。"""
        for ur_data in user_roles_data:
            try:
                user = self._resolve_user_by_username_or_id(
                    ur_data.get("username"), ur_data.get("user_id")
                )
                if not user:
                    stats["user_roles_skipped"] = stats.get("user_roles_skipped", 0) + 1
                    continue

                new_role_id = self._resolve_role_id(ur_data, role_id_map)
                if new_role_id is None:
                    stats["user_roles_skipped"] = stats.get("user_roles_skipped", 0) + 1
                    continue

                self.db.add(UserRole(
                    user_id=user.id,
                    role_id=new_role_id,
                    expires_at=(
                        datetime.fromisoformat(ur_data["expires_at"])
                        if ur_data.get("expires_at") else None
                    ),
                ))
                stats["user_roles_assigned"] += 1
            except Exception as e:  # pragma: no cover
                errors.append(f"用户-角色关联导入失败: {e}")
        return stats, errors

    def _resolve_user_by_username_or_id(self, username, user_id):
        """跨机器安全匹配：优先 username，回退数字 ID（旧包兼容）。"""
        if username:
            user = self.db.query(User).filter(User.username == username).first()
            if user:
                return user
        if user_id is not None:
            return self.db.query(User).filter(User.id == user_id).first()
        return None

    def _resolve_role_id(self, ur_data, role_id_map):
        """角色 ID 解析：优先本次导入建立的映射，其次按 role_name 匹配，
        最后校验原 ID 在本机是否存在；均未命中时原样回退（与旧版行为一致，
        由数据库外键约束兜底）。"""
        old_role_id = ur_data.get("role_id", "")
        if old_role_id in role_id_map and role_id_map[old_role_id] is not None:
            return role_id_map[old_role_id]
        role_name = ur_data.get("role_name")
        if role_name:
            by_name = (
                self.db.query(RbacRole).filter(RbacRole.name == role_name).first()
            )
            if by_name:
                return by_name.id
        exists = self.db.query(RbacRole).filter(RbacRole.id == old_role_id).first()
        return exists.id if exists else old_role_id

    def _import_user_permissions(self, user_permissions_data, stats, errors):
        """导入用户直接权限（优先 username 匹配）。"""
        for up_data in user_permissions_data:
            try:
                user = self._resolve_user_by_username_or_id(
                    up_data.get("username"), up_data.get("user_id")
                )
                if not user:
                    stats["user_permissions_skipped"] = stats.get("user_permissions_skipped", 0) + 1
                    continue
                self.db.add(UserPermission(
                    user_id=user.id,
                    permission=up_data.get("permission", ""),
                    expires_at=(
                        datetime.fromisoformat(up_data["expires_at"])
                        if up_data.get("expires_at") else None
                    ),
                ))
                stats["user_permissions_assigned"] += 1
            except Exception as e:  # pragma: no cover
                errors.append(f"用户权限导入失败: {e}")
        return stats, errors

    def _import_user_menus(self, user_menus_data, stats, errors):
        """导入用户菜单覆盖。"""
        for menu_data in user_menus_data:
            username = ""
            try:
                if not isinstance(menu_data, dict):
                    raise ValueError(f"菜单数据格式错误（应为对象，实际 {type(menu_data).__name__}）")
                username = menu_data.get("username", "")
                user = self.db.query(User).filter(User.username == username).first()
                if not user:
                    continue
                user.allowed_menus = json.dumps(
                    menu_data.get("allowed_menus", []), ensure_ascii=False
                )
                stats["user_menus_updated"] += 1
            except Exception as e:  # pragma: no cover
                errors.append(f"用户菜单「{username}」导入失败: {e}")
        return stats, errors

    def _import_user_legacy(self, user_legacy_data, stats, errors):
        """导入遗留权限字段。"""
        for legacy_data in user_legacy_data:
            username = ""
            try:
                if not isinstance(legacy_data, dict):
                    raise ValueError(f"遗留权限数据格式错误（应为对象，实际 {type(legacy_data).__name__}）")
                username = legacy_data.get("username", "")
                user = self.db.query(User).filter(User.username == username).first()
                if not user:
                    continue
                user.role = legacy_data.get("role", "user")
                user.permissions = legacy_data.get("permissions", "")
                user.data_scope = legacy_data.get("data_scope", "org")
                # 恢复组织关联：优先按组织编码匹配（跨机器稳定），
                # 回退按导出机原始 ID，均失败则置空（用户可通过界面重新指定）
                org_id = legacy_data.get("organization_id")
                if org_id:
                    from app.models.organization import Organization

                    org = None
                    org_code = legacy_data.get("organization_code")
                    if org_code:
                        org = (
                            self.db.query(Organization)
                            .filter(Organization.code == org_code)
                            .first()
                        )
                    if not org:
                        org = (
                            self.db.query(Organization)
                            .filter(Organization.id == org_id)
                            .first()
                        )
                    if org:
                        user.organization_id = org.id
                    else:
                        user.organization_id = None
                stats["user_legacy_updated"] += 1
            except Exception as e:  # pragma: no cover
                errors.append(f"用户遗留权限「{username}」导入失败: {e}")
        return stats, errors

    def _log_import_result(self, stats):
        logger.info(
            "权限配置包导入完成: 角色创建%d/更新%d, 组织创建%d/更新%d, "
            "用户角色%d, 用户权限%d, 菜单%d, 遗留%d",
            stats["roles_created"], stats["roles_updated"],
            stats["organizations_created"], stats["organizations_updated"],
            stats["user_roles_assigned"], stats["user_permissions_assigned"],
            stats["user_menus_updated"], stats["user_legacy_updated"],
        )

    def _build_import_response(self, stats, errors):
        return {
            "success": True,
            "roles_created": stats["roles_created"],
            "roles_updated": stats["roles_updated"],
            "organizations_created": stats["organizations_created"],
            "organizations_updated": stats["organizations_updated"],
            "user_roles_assigned": stats["user_roles_assigned"],
            "user_permissions_assigned": stats["user_permissions_assigned"],
            "user_roles_skipped": stats.get("user_roles_skipped", 0),
            "user_permissions_skipped": stats.get("user_permissions_skipped", 0),
            "user_menus_updated": stats["user_menus_updated"],
            "user_legacy_updated": stats["user_legacy_updated"],
            "errors": errors,
            "message": (
                f"导入完成: 角色 {stats['roles_created']}新建/{stats['roles_updated']}更新, "
                f"组织 {stats['organizations_created']}新建/{stats['organizations_updated']}更新, "
                f"用户角色关联 {stats['user_roles_assigned']}, "
                f"用户权限 {stats['user_permissions_assigned']}, "
                f"菜单覆盖 {stats['user_menus_updated']}, "
                f"遗留字段 {stats['user_legacy_updated']}"
            ),
        }

    # ================================================================
    # 工具方法
    # ================================================================

    def _calculate_checksum(self, file_path: str) -> str:
        """计算文件的 SHA-256 校验和"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        return f"sha256:{sha256.hexdigest()}"

    @staticmethod
    def _calculate_content_checksum(segments: Dict[str, Any]) -> str:
        """对包内数据段计算规范化 SHA-256（键排序，稳定序列化）"""
        canonical = json.dumps(segments, ensure_ascii=False, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
