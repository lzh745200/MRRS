"""管控配置包 API

上级单位生成管控配置包（加密ZIP），下级单位导入并执行。
包含：模块策略、预创建用户、RBAC快照、菜单覆盖、系统配置。
"""

import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.response import success_response
from app.models.org_module_policy import OrgModulePolicy
from app.models.user import User
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/control-packages", tags=["管控配置包"])

PACKAGE_VERSION = "1.0"


class GenerateControlPackageRequest(BaseModel):
    organization_id: int
    include_users: bool = True
    include_rbac: bool = True
    include_system_config: bool = True


@router.post("/generate")
def generate_control_package(
    body: GenerateControlPackageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """生成管控配置包（返回下载）"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可生成管控配置包")

    org_id = body.organization_id

    # 1. 模块策略
    policies = db.query(OrgModulePolicy).filter(
        OrgModulePolicy.organization_id == org_id
    ).all()
    module_policy_data = [
        {"module_key": p.module_key, "visibility": p.visibility, "edit_mode": p.edit_mode}
        for p in policies
    ]

    # 2. 预创建用户（该组织下的用户）
    users_data = []
    if body.include_users:
        org_users = db.query(User).filter(User.organization_id == org_id).all()
        users_data = [
            {
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "data_scope": u.data_scope,
                "is_active": u.is_active,
                "allowed_menus": u.allowed_menus,
            }
            for u in org_users
        ]

    # 3. 系统配置覆盖
    system_config_data = {}
    if body.include_system_config:
        from app.models.system_config import SystemConfig
        configs = db.query(SystemConfig).all()
        system_config_data = {c.key: c.value for c in configs}

    # 4. 构建 manifest
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "package_version": PACKAGE_VERSION,
        "package_type": "control",
        "target_organization_id": org_id,
        "generated_at": now,
        "generated_by": current_user.username,
        "system_version": "1.4.3",
        "contents": {
            "module_policy": len(module_policy_data),
            "users": len(users_data),
            "system_config": len(system_config_data),
        },
    }

    # 5. 打包 ZIP
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("module_policy.json", json.dumps(module_policy_data, ensure_ascii=False, indent=2))
        if users_data:
            zf.writestr("users.json", json.dumps(users_data, ensure_ascii=False, indent=2))
        if system_config_data:
            zf.writestr("system_config.json", json.dumps(system_config_data, ensure_ascii=False, indent=2))

    buffer.seek(0)
    content = buffer.read()
    content_hash = hashlib.sha256(content).hexdigest()

    # 6. 记录审计
    try:
        write_work_log(
            db, "control_package", "generate", org_id,
            f"生成管控配置包 org={org_id} hash={content_hash[:16]}",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    filename = f"control_package_org{org_id}_{now[:10]}.zip"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Package-Hash": content_hash,
        },
    )


class ImportPreviewResponse(BaseModel):
    valid: bool
    manifest: dict | None = None
    module_policy_count: int = 0
    user_count: int = 0
    error: str | None = None


@router.post("/import-preview")
async def import_control_package_preview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """预览管控配置包内容（不执行导入）"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的管控配置包")

    content = await file.read()
    try:
        buffer = io.BytesIO(content)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            if "manifest.json" not in names:
                return ImportPreviewResponse(valid=False, error="无效的管控包：缺少 manifest.json")

            manifest = json.loads(zf.read("manifest.json"))
            if manifest.get("package_type") != "control":
                return ImportPreviewResponse(valid=False, error="非管控配置包类型")

            module_policy_count = 0
            user_count = 0
            if "module_policy.json" in names:
                policies = json.loads(zf.read("module_policy.json"))
                module_policy_count = len(policies)
            if "users.json" in names:
                users = json.loads(zf.read("users.json"))
                user_count = len(users)

            return ImportPreviewResponse(
                valid=True,
                manifest=manifest,
                module_policy_count=module_policy_count,
                user_count=user_count,
            )
    except zipfile.BadZipFile:
        return ImportPreviewResponse(valid=False, error="文件损坏：非有效ZIP格式")
    except json.JSONDecodeError:
        return ImportPreviewResponse(valid=False, error="JSON解析失败：清单文件格式无效")


@router.post("/import")
async def import_control_package(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """导入并执行管控配置包"""
    if current_user.role not in ("admin", "super_admin") and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="仅管理员可导入管控配置包")

    content = await file.read()
    try:
        buffer = io.BytesIO(content)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            if "manifest.json" not in names:
                raise HTTPException(status_code=400, detail="无效的管控包：缺少 manifest.json")

            manifest = json.loads(zf.read("manifest.json"))
            if manifest.get("package_type") != "control":
                raise HTTPException(status_code=400, detail="非管控配置包类型")

            # 导入模块策略
            applied_policies = 0
            if "module_policy.json" in names:
                policies = json.loads(zf.read("module_policy.json"))
                org_id = manifest.get("target_organization_id")
                for item in policies:
                    existing = db.query(OrgModulePolicy).filter(
                        OrgModulePolicy.organization_id == org_id,
                        OrgModulePolicy.module_key == item["module_key"],
                    ).first()
                    if existing:
                        existing.visibility = item["visibility"]
                        existing.edit_mode = item["edit_mode"]
                    else:
                        db.add(OrgModulePolicy(
                            organization_id=org_id,
                            module_key=item["module_key"],
                            visibility=item["visibility"],
                            edit_mode=item["edit_mode"],
                            created_by=current_user.id,
                        ))
                    applied_policies += 1

            # 导入系统配置
            applied_configs = 0
            if "system_config.json" in names:
                from app.models.system_config import SystemConfig
                configs = json.loads(zf.read("system_config.json"))
                for key, value in configs.items():
                    existing = db.query(SystemConfig).filter(SystemConfig.key == key).first()
                    if existing:
                        existing.value = str(value)
                    else:
                        db.add(SystemConfig(key=key, value=str(value)))
                    applied_configs += 1

            db.commit()

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="文件损坏：非有效ZIP格式")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("管控配置包导入失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="导入失败，请稍后重试或联系管理员")

    content_hash = hashlib.sha256(content).hexdigest()

    try:
        write_work_log(
            db, "control_package", "import", 0,
            f"导入管控配置包 hash={content_hash[:16]} policies={applied_policies} configs={applied_configs}",
            user_id=current_user.id,
            username=getattr(current_user, "username", ""),
        )
    except Exception:
        logger.debug("记录工作日志失败", exc_info=True)

    return success_response(
        data={
            "applied_policies": applied_policies,
            "applied_configs": applied_configs,
            "package_hash": content_hash,
        },
        message="管控配置包导入成功",
    )
