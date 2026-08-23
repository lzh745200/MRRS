"""下级单位上报包 API

下级单位生成注册上报包和状态报告包，上级单位导入并处理。
包含：用户注册上报、系统状态心跳、配置应用确认。
"""

import io
import json
import logging
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.subordinate_registry import SubordinateInstance
from app.models.user import User
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subordinate-reports", tags=["下级上报包"])


@router.post("/generate-registration")
def generate_registration_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """生成注册上报包（下级单位 → 上级单位）

    包含本系统所有注册用户的基本信息，供上级审批。
    """
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    org_id = current_user.organization_id

    report_data = {
        "report_type": "registration",
        "organization_id": org_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": current_user.username,
        "user_count": len(users),
        "users": [
            {
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("registration_report.json", json.dumps(report_data, ensure_ascii=False, indent=2))

    buffer.seek(0)
    content = buffer.read()
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"registration_report_org{org_id}_{now_str}.zip"

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate-status")
def generate_status_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """生成状态报告包（下级单位 → 上级单位）

    包含系统版本、用户统计、数据库大小、错误计数等运行状态。
    """
    from app.core.config import settings

    user_count = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0  # noqa: E712
    org_id = current_user.organization_id

    # 获取数据库文件大小
    db_size_mb = 0.0
    try:
        import os
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path):
            db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)
    except Exception:
        pass

    report_data = {
        "report_type": "status",
        "organization_id": org_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_version": settings.PROJECT_VERSION,
        "user_count": user_count,
        "db_size_mb": db_size_mb,
        "instance_code": _get_instance_code(db, org_id),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("status_report.json", json.dumps(report_data, ensure_ascii=False, indent=2))

    buffer.seek(0)
    content = buffer.read()
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"status_report_org{org_id}_{now_str}.zip"

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class ImportReportResult(BaseModel):
    report_type: str
    organization_id: int | None = None
    user_count: int = 0
    instance_updated: bool = False
    message: str = ""


@router.post("/import")
async def import_subordinate_report(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """导入下级单位上报包（上级单位操作）

    自动识别包类型（registration/status），更新注册表。
    """
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可导入下级上报包")

    content = await file.read()
    try:
        buffer = io.BytesIO(content)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()

            if "status_report.json" in names:
                return _process_status_report(zf, db, current_user)
            elif "registration_report.json" in names:
                return _process_registration_report(zf, db, current_user)
            else:
                raise HTTPException(status_code=400, detail="无法识别的上报包格式")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="文件损坏：非有效ZIP格式")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("导入下级上报包失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试或联系管理员")


def _process_status_report(zf: zipfile.ZipFile, db: Session, current_user: User):
    """处理状态报告包"""
    report = json.loads(zf.read("status_report.json"))
    org_id = report.get("organization_id")
    instance_code = report.get("instance_code")

    instance_updated = False
    if instance_code:
        instance = db.query(SubordinateInstance).filter(
            SubordinateInstance.instance_code == instance_code
        ).first()
        if instance:
            instance.system_version = report.get("system_version")
            instance.user_count = report.get("user_count", 0)
            instance.last_report_at = datetime.now(timezone.utc)
            instance.status = "online"
            instance_updated = True
            db.commit()

    try:
        write_work_log(
            db, "subordinate_report", "import_status", org_id or 0,
            f"导入状态报告 org={org_id} version={report.get('system_version')}",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return success_response(data={
        "report_type": "status",
        "organization_id": org_id,
        "user_count": report.get("user_count", 0),
        "instance_updated": instance_updated,
        "message": "状态报告已处理",
    })


def _process_registration_report(zf: zipfile.ZipFile, db: Session, current_user: User):
    """处理注册上报包"""
    report = json.loads(zf.read("registration_report.json"))
    org_id = report.get("organization_id")
    users = report.get("users", [])

    # 更新注册表中的用户数
    if org_id:
        instance = db.query(SubordinateInstance).filter(
            SubordinateInstance.organization_id == org_id
        ).first()
        if instance:
            instance.user_count = len(users)
            instance.last_report_at = datetime.now(timezone.utc)
            instance.status = "online"
            db.commit()

    try:
        write_work_log(
            db, "subordinate_report", "import_registration", org_id or 0,
            f"导入注册上报 org={org_id} users={len(users)}",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return success_response(data={
        "report_type": "registration",
        "organization_id": org_id,
        "user_count": len(users),
        "instance_updated": False,
        "message": f"注册上报已处理，共 {len(users)} 名用户",
    })


def _get_instance_code(db: Session, org_id: int | None) -> str | None:
    """获取当前系统的实例标识"""
    if not org_id:
        return None
    instance = db.query(SubordinateInstance).filter(
        SubordinateInstance.organization_id == org_id
    ).first()
    return instance.instance_code if instance else None
