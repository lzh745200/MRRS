"""权限包管理 API

权限包 = 菜单套餐：管理员定义一组可见菜单 key，批量绑定给普通用户(user/viewer)，
控制其可见功能板块。菜单解析接入点见 app.api.v1.menus._get_user_accessible_menu_keys：
    用户级 allowed_menus 配置 > 绑定的启用中权限包 > 角色默认菜单

注意：命名一律使用 permission_packs —— "permission_package" 已被 RBAC 配置
导入/导出 ZIP 功能占用。
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.api.v1.menus import MENU_DEFINITIONS, _flatten_menu_keys
from app.core.response import success_response
from app.core.transaction import safe_commit
from app.models.permission_pack import PermissionPack
from app.models.user import User
from app.schemas.permission_pack import (
    BindUsersRequest,
    PackCreate,
    PackResponse,
    PackUpdate,
)
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permission-packs", tags=["权限包管理"])

# 可被权限包绑定的目标角色（管理员/super_admin 无需套餐控制）
_BINDABLE_ROLES = ("user", "viewer")


def _require_admin(user: User) -> None:
    """权限包全部端点仅管理员可用"""
    if user.role not in ("admin", "super_admin") and not user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可管理权限包")


def _get_pack_or_404(db: Session, pack_id: int) -> PermissionPack:
    """获取权限包，不存在则抛出 404"""
    pack = db.query(PermissionPack).filter(PermissionPack.id == pack_id).first()
    if not pack:
        raise HTTPException(status_code=404, detail="权限包不存在")
    return pack


def _validate_menu_keys(menu_keys: list[str]) -> None:
    """menu_keys 必须全部是合法菜单 key，否则 422 并列出非法项"""
    valid_keys = _flatten_menu_keys(MENU_DEFINITIONS)
    invalid = [k for k in menu_keys if k not in valid_keys]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"存在无效的菜单key: {', '.join(invalid)}",
        )


def _check_name_unique(db: Session, name: str, exclude_id: int | None = None) -> None:
    """权限包名称唯一性校验"""
    query = db.query(PermissionPack).filter(PermissionPack.name == name)
    if exclude_id is not None:
        query = query.filter(PermissionPack.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail=f"权限包名称已存在: {name}")


def _bound_user_count(db: Session, pack_id: int) -> int:
    """统计绑定到指定权限包的用户数"""
    return (
        db.query(func.count(User.id))
        .filter(User.permission_pack_id == pack_id)
        .scalar()
        or 0
    )


def _pack_response(pack: PermissionPack, bound_user_count: int) -> dict:
    """序列化权限包（含绑定用户数）"""
    return PackResponse(
        id=pack.id,
        name=pack.name,
        description=pack.description,
        menu_keys=pack.menu_keys_list,
        is_active=bool(pack.is_active),
        created_by=pack.created_by,
        created_at=pack.created_at,
        updated_at=pack.updated_at,
        bound_user_count=bound_user_count,
    ).model_dump(mode="json")


def _log(pack_id: int, action: str, entity_name: str, current_user: User, db: Session) -> None:
    """写操作日志（失败不阻断主流程）"""
    try:
        write_work_log(
            db, "permission_pack", action, pack_id, entity_name,
            user_id=current_user.id, username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)


@router.get("", summary="权限包列表")
def list_packs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取全部权限包（含每个包绑定用户数）"""
    _require_admin(current_user)
    packs = db.query(PermissionPack).order_by(PermissionPack.id).all()
    counts = dict(
        db.query(User.permission_pack_id, func.count(User.id))
        .filter(User.permission_pack_id.isnot(None))
        .group_by(User.permission_pack_id)
        .all()
    )
    return success_response(data=[_pack_response(p, counts.get(p.id, 0) or 0) for p in packs])


@router.post("", summary="创建权限包")
def create_pack(
    data: PackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建权限包。menu_keys 必须全部是合法菜单 key。"""
    _require_admin(current_user)
    _validate_menu_keys(data.menu_keys)
    _check_name_unique(db, data.name)

    pack = PermissionPack(
        name=data.name,
        description=data.description,
        menu_keys=json.dumps(data.menu_keys, ensure_ascii=False),
        is_active=data.is_active,
        created_by=current_user.id,
    )
    db.add(pack)
    safe_commit(db)
    db.refresh(pack)
    _log(pack.id, "create", f"创建权限包: {pack.name}", current_user, db)
    logger.info("管理员 %s 创建权限包 %s(id=%s)", current_user.username, pack.name, pack.id)
    return success_response(data=_pack_response(pack, 0), message="创建成功")


@router.put("/{pack_id}", summary="更新权限包")
def update_pack(
    pack_id: int,
    data: PackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新权限包（仅更新传入字段）。menu_keys 变更对绑定用户即时生效。"""
    _require_admin(current_user)
    pack = _get_pack_or_404(db, pack_id)

    if data.name is not None and data.name != pack.name:
        _check_name_unique(db, data.name, exclude_id=pack.id)
        pack.name = data.name
    if data.description is not None:
        pack.description = data.description
    if data.menu_keys is not None:
        _validate_menu_keys(data.menu_keys)
        pack.menu_keys = json.dumps(data.menu_keys, ensure_ascii=False)
    if data.is_active is not None:
        pack.is_active = data.is_active

    safe_commit(db)
    db.refresh(pack)
    _log(pack.id, "update", f"更新权限包: {pack.name}", current_user, db)
    logger.info("管理员 %s 更新权限包 %s(id=%s)", current_user.username, pack.name, pack.id)
    return success_response(
        data=_pack_response(pack, _bound_user_count(db, pack.id)), message="更新成功"
    )


@router.delete("/{pack_id}", summary="删除权限包")
def delete_pack(
    pack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """删除权限包。仍有绑定用户时拒绝删除（需先解绑）。"""
    _require_admin(current_user)
    pack = _get_pack_or_404(db, pack_id)

    bound = _bound_user_count(db, pack.id)
    if bound > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该权限包仍绑定 {bound} 个用户，请先解绑后再删除",
        )

    name = pack.name
    db.delete(pack)
    safe_commit(db)
    _log(pack_id, "delete", f"删除权限包: {name}", current_user, db)
    logger.info("管理员 %s 删除权限包 %s(id=%s)", current_user.username, name, pack_id)
    return success_response(message="删除成功")


@router.post("/{pack_id}/bind-users", summary="批量绑定用户")
def bind_users(
    pack_id: int,
    data: BindUsersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """把权限包批量绑定给普通用户(user/viewer)。

    目标用户必须全部存在且角色为 user/viewer，否则整体拒绝并列出非法 id。
    """
    _require_admin(current_user)
    pack = _get_pack_or_404(db, pack_id)

    users = (
        db.query(User).filter(User.id.in_(data.user_ids)).all() if data.user_ids else []
    )
    found_ids = {u.id for u in users}
    missing = [uid for uid in data.user_ids if uid not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"用户不存在: {missing}")
    invalid_role = [u.id for u in users if u.role not in _BINDABLE_ROLES]
    if invalid_role:
        raise HTTPException(
            status_code=400,
            detail=f"仅可绑定普通用户(user/viewer)，以下用户角色不允许: {invalid_role}",
        )

    for u in users:
        u.permission_pack_id = pack.id
    safe_commit(db)
    _log(pack.id, "bind_users", f"权限包 {pack.name} 绑定用户: {sorted(found_ids)}", current_user, db)
    logger.info(
        "管理员 %s 将权限包 %s(id=%s) 绑定给用户 %s",
        current_user.username, pack.name, pack.id, sorted(found_ids),
    )
    return success_response(
        data={"bound_user_ids": sorted(found_ids)},
        message=f"已绑定 {len(users)} 个用户",
    )


@router.post("/{pack_id}/unbind-users", summary="批量解绑用户")
def unbind_users(
    pack_id: int,
    data: BindUsersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """批量解绑（permission_pack_id 置 None，用户回落到角色默认菜单）。

    仅解绑当前绑定到本包的用户；未绑定本包的 id 静默跳过。
    """
    _require_admin(current_user)
    pack = _get_pack_or_404(db, pack_id)

    users = (
        db.query(User).filter(User.id.in_(data.user_ids)).all() if data.user_ids else []
    )
    found_ids = {u.id for u in users}
    missing = [uid for uid in data.user_ids if uid not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"用户不存在: {missing}")

    unbound_ids = []
    for u in users:
        if u.permission_pack_id == pack.id:
            u.permission_pack_id = None
            unbound_ids.append(u.id)
    safe_commit(db)
    _log(pack.id, "unbind_users", f"权限包 {pack.name} 解绑用户: {sorted(unbound_ids)}", current_user, db)
    logger.info(
        "管理员 %s 解绑权限包 %s(id=%s) 的用户 %s",
        current_user.username, pack.name, pack.id, sorted(unbound_ids),
    )
    return success_response(
        data={"unbound_user_ids": sorted(unbound_ids)},
        message=f"已解绑 {len(unbound_ids)} 个用户",
    )
