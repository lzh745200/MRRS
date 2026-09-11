"""组织模块策略 API

上级单位管理下级单位系统的功能模块可见性与编辑权限。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.core.transaction import safe_commit
from app.models.org_module_policy import (
    MODULE_DEFINITIONS,
    OrgModulePolicy,
)
from app.models.user import User
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/org-policies", tags=["组织模块策略"])


class ModulePolicyItem(BaseModel):
    module_key: str = Field(..., max_length=64)
    visibility: str = Field(default="visible", pattern="^(visible|hidden)$")
    edit_mode: str = Field(default="full_edit", pattern="^(full_edit|read_only|disabled)$")


class BatchPolicyRequest(BaseModel):
    policies: list[ModulePolicyItem]


@router.get("/modules")
def list_module_definitions(current_user: User = Depends(get_current_active_user)):
    """获取所有可管控模块定义"""
    return success_response(data=MODULE_DEFINITIONS)


@router.get("/current")
def get_current_org_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户所属组织的模块策略（供前端策略执行引擎使用）"""
    org_id = current_user.organization_id
    if not org_id:
        return success_response(data=[])

    policies = db.query(OrgModulePolicy).filter(
        OrgModulePolicy.organization_id == org_id
    ).all()

    return success_response(data=[
        {
            "module_key": p.module_key,
            "visibility": p.visibility,
            "edit_mode": p.edit_mode,
        }
        for p in policies
    ])


@router.get("/{org_id}")
def get_org_policies(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取某下级组织的模块策略（含默认值填充）"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可管理模块策略")

    db_policies = db.query(OrgModulePolicy).filter(
        OrgModulePolicy.organization_id == org_id
    ).all()
    policy_map = {p.module_key: p for p in db_policies}

    result = []
    for mod in MODULE_DEFINITIONS:
        p = policy_map.get(mod["key"])
        result.append({
            **mod,
            "visibility": p.visibility if p else "visible",
            "edit_mode": p.edit_mode if p else "full_edit",
            "is_custom": p is not None,
        })
    return success_response(data=result)


@router.put("/{org_id}")
def set_org_policies(
    org_id: int,
    body: BatchPolicyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """批量设置某下级组织的模块策略"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可管理模块策略")

    valid_keys = {m["key"] for m in MODULE_DEFINITIONS}
    for item in body.policies:
        if item.module_key not in valid_keys:
            raise HTTPException(status_code=400, detail=f"无效模块标识: {item.module_key}")

    updated = 0
    for item in body.policies:
        existing = db.query(OrgModulePolicy).filter(
            OrgModulePolicy.organization_id == org_id,
            OrgModulePolicy.module_key == item.module_key,
        ).first()

        if existing:
            existing.visibility = item.visibility
            existing.edit_mode = item.edit_mode
        else:
            policy = OrgModulePolicy(
                organization_id=org_id,
                module_key=item.module_key,
                visibility=item.visibility,
                edit_mode=item.edit_mode,
                created_by=current_user.id,
            )
            db.add(policy)
        updated += 1

    safe_commit(db)

    try:
        write_work_log(
            db, "org_module_policy", "update", org_id,
            f"更新组织{org_id}模块策略({updated}项)",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return success_response(data={"updated": updated}, message="模块策略已更新")


@router.delete("/{org_id}/{module_key}")
def reset_org_policy(
    org_id: int,
    module_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """重置某模块策略为默认值（删除自定义记录）"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可管理模块策略")

    policy = db.query(OrgModulePolicy).filter(
        OrgModulePolicy.organization_id == org_id,
        OrgModulePolicy.module_key == module_key,
    ).first()
    if policy:
        db.delete(policy)
        safe_commit(db)

    return success_response(message="已重置为默认策略")


@router.get("/{org_id}/export")
def export_org_policies(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """导出某组织的模块策略（用于管控配置包）"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可导出模块策略")

    policies = db.query(OrgModulePolicy).filter(
        OrgModulePolicy.organization_id == org_id
    ).all()

    return success_response(data=[
        {
            "module_key": p.module_key,
            "visibility": p.visibility,
            "edit_mode": p.edit_mode,
        }
        for p in policies
    ])
