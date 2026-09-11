"""下级单位系统注册表 API

上级单位追踪和管理下级单位部署的单机系统实例。
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.response import ok_list, success_response
from app.core.transaction import safe_commit
from app.models.subordinate_registry import SubordinateInstance
from app.models.user import User
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subordinates", tags=["下级单位管理"])


class SubordinateCreateRequest(BaseModel):
    organization_id: int
    instance_code: str = Field(..., min_length=8, max_length=64)
    machine_code: str | None = None
    system_version: str | None = None
    license_expiry: date | None = None
    remark: str | None = None


class SubordinateUpdateRequest(BaseModel):
    license_status: str | None = Field(None, pattern="^(pending|active|expired|revoked)$")
    license_expiry: date | None = None
    system_version: str | None = None
    remark: str | None = None


@router.get("")
def list_subordinates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    license_status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """列出所有注册的下级单位系统实例"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可查看下级单位")

    query = db.query(SubordinateInstance)
    if keyword:
        query = query.filter(
            SubordinateInstance.instance_code.contains(keyword)
            | SubordinateInstance.machine_code.contains(keyword)
        )
    if license_status:
        query = query.filter(SubordinateInstance.license_status == license_status)

    total = query.count()
    items = query.order_by(SubordinateInstance.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return ok_list(
        items=[i.to_dict() for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("")
def register_subordinate(
    body: SubordinateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """注册新的下级单位系统实例"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可注册下级单位")

    existing = db.query(SubordinateInstance).filter(
        SubordinateInstance.instance_code == body.instance_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该实例标识已注册")

    instance = SubordinateInstance(
        organization_id=body.organization_id,
        instance_code=body.instance_code,
        machine_code=body.machine_code,
        system_version=body.system_version,
        license_status="pending",
        license_expiry=body.license_expiry,
        remark=body.remark,
        created_by=current_user.id,
    )
    db.add(instance)
    safe_commit(db)
    db.refresh(instance)

    try:
        write_work_log(
            db, "subordinate", "register", instance.id,
            f"注册下级单位: {body.instance_code}",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return success_response(data=instance.to_dict(), message="下级单位注册成功")


@router.put("/{instance_id}")
def update_subordinate(
    instance_id: int,
    body: SubordinateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新下级单位信息（授权状态、有效期等）"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可管理下级单位")

    instance = db.query(SubordinateInstance).filter(
        SubordinateInstance.id == instance_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="下级单位不存在")

    if body.license_status is not None:
        instance.license_status = body.license_status
    if body.license_expiry is not None:
        instance.license_expiry = body.license_expiry
    if body.system_version is not None:
        instance.system_version = body.system_version
    if body.remark is not None:
        instance.remark = body.remark

    safe_commit(db)
    db.refresh(instance)

    try:
        write_work_log(
            db, "subordinate", "update", instance.id,
            f"更新下级单位: {instance.instance_code} 状态={body.license_status}",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return success_response(data=instance.to_dict(), message="更新成功")


@router.get("/{instance_id}")
def get_subordinate(
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取下级单位详情"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可查看下级单位")

    instance = db.query(SubordinateInstance).filter(
        SubordinateInstance.id == instance_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="下级单位不存在")

    return success_response(data=instance.to_dict())


@router.delete("/{instance_id}")
def delete_subordinate(
    instance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """删除下级单位注册记录"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可删除下级单位")

    instance = db.query(SubordinateInstance).filter(
        SubordinateInstance.id == instance_id
    ).first()
    if not instance:
        raise HTTPException(status_code=404, detail="下级单位不存在")

    db.delete(instance)
    safe_commit(db)

    try:
        write_work_log(
            db, "subordinate", "delete", instance_id,
            f"删除下级单位: {instance.instance_code}",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return success_response(message="删除成功")
