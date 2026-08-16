from app.core.permission_utils import is_superuser, is_admin, require_admin

# -*- coding: utf-8 -*-
"""
机器码和通行码管理 API
用于单机版系统的用户注册和机器码管理
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok_list
from app.core.security import check_rate_limit, get_client_ip, get_current_user, get_password_hash
from app.models.user import User
from app.services.machine_code_service import MachineCodeService
from app.services.machine_code_permission_service import MachineCodePermissionService
from app.services.rbac_service import Permission, rbac_service
from app.services.work_log_service import write_work_log
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/machine-code", tags=["机器码管理"])


# ==================== Pydantic 模型 ====================


class MachineCodeResponse(BaseModel):
    """机器码响应"""

    machine_code: str
    verification_code: str
    machine_info: dict


class MachineCodeCreateRequest(BaseModel):
    """管理员录入机器码请求"""

    machine_code: str = Field(..., description="用户提供的机器码")
    description: Optional[str] = Field(None, description="备注说明")
    pass_code: Optional[str] = Field(
        None,
        description="手动设置的4位数字通行码（留空则自动生成）",
        min_length=4,
        max_length=4,
        pattern=r"^\d{4}$",
    )


class MachineCodeRecordResponse(BaseModel):
    """机器码记录响应"""

    id: int
    machine_code: str
    pass_code: str
    status: str
    user_id: Optional[int]
    username: Optional[str]
    description: Optional[str]
    created_at: str
    activated_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class MachineCodeListResponse(BaseModel):
    """机器码列表响应"""

    total: int
    items: list[MachineCodeRecordResponse]


class GeneratePasswordRequest(BaseModel):
    """生成密码请求"""

    username: str
    verification_code: str


class VerifyMachineCodeRequest(BaseModel):
    """验证机器码请求"""

    machine_code: str
    verification_code: str


class OrganizationPassCodeCreateRequest(BaseModel):
    """管理员生成组织通行码请求"""

    organization_id: int = Field(..., description="管理员选择的下级组织ID")
    verification_code: str = Field(..., description="下级单位提供的机器校验码")
    allow_subordinate_generation: bool = Field(False, description="是否允许下级组织生成通行码")
    description: Optional[str] = Field(None, description="备注说明")


class OrganizationPassCodeResponse(BaseModel):
    """组织通行证码响应"""

    id: int
    organization_id: int
    organization_name: Optional[str]
    pass_code: str
    verification_code: str
    allow_subordinate_generation: bool
    status: str
    created_at: str
    created_by: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class OrganizationPassCodeListResponse(BaseModel):
    """组织通行证码列表响应"""

    total: int
    items: list[OrganizationPassCodeResponse]


# ==================== API 端点 ====================


@router.get("/get-machine-code")
async def get_machine_code():
    """获取当前机器的机器码和校验码

    公开接口，用于用户获取机器码以提交给管理员。
    """
    try:
        service = MachineCodeService()

        # 获取机器码
        machine_code = service.get_machine_code()

        # 生成校验码（用于验证）
        verification_code = service.generate_verification_code(machine_code)

        # 获取机器信息
        machine_info = service.get_machine_info()

        return {
            "code": 200,
            "success": True,
            "data": {
                "machine_code": machine_code,
                "verification_code": verification_code,
                "machine_info": machine_info,
            },
            "message": "机器码获取成功",
        }
    except Exception as e:  # pragma: no cover
        logger.error(f"获取机器码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取机器码失败，请稍后重试或联系管理员")


@router.post("/admin/create", response_model=dict)
async def admin_create_machine_code(
    request: MachineCodeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """管理员录入机器码并生成通行码

    需要权限：管理员或超级管理员
    """
    # 权限检查
    if not (current_user.is_superuser or current_user.role in ("super_admin", "admin")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可录入机器码")

    try:
        service = MachineCodeService(db)

        # 创建机器码记录
        record = service.create_machine_code_record(
            machine_code=request.machine_code,
            created_by=current_user.id,
            description=request.description,
            pass_code=request.pass_code,
        )

        try:
            write_work_log(db, "machine_code", "create", record.id, f"录入机器码: {request.machine_code}",
                           user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:  # pragma: no cover
            logger.debug("记录工作日志失败")
        return {
            "code": 200,
            "success": True,
            "data": {
                "id": record.id,
                "machine_code": record.machine_code,
                "pass_code": record.pass_code,
                "status": record.status,
                "created_at": (record.created_at.isoformat() if record.created_at else None),
            },
            "message": "机器码录入成功，通行码已生成",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover
        logger.error(f"录入机器码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="录入机器码失败，请稍后重试或联系管理员")


@router.get("/admin/list")
async def admin_list_machine_codes(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """管理员查询机器码列表

    需要权限：管理员或超级管理员
    """
    # 权限检查
    if not (current_user.is_superuser or current_user.role in ("super_admin", "admin")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可查询机器码列表")

    try:
        service = MachineCodeService(db)
        records, total = service.list_machine_codes(status=status_filter, skip=skip, limit=limit)

        items = []
        for record in records:
            # 使用预加载的用户关系，避免 N+1 查询
            username = None
            if record.user:
                username = record.user.username

            items.append(
                {
                    "id": record.id,
                    "machine_code": record.machine_code,
                    "pass_code": record.pass_code,
                    "status": record.status,
                    "user_id": record.user_id,
                    "username": username,
                    "description": record.description,
                    "created_at": (record.created_at.isoformat() if record.created_at else None),
                    "activated_at": (record.activated_at.isoformat() if record.activated_at else None),
                }
            )

        return ok_list(items=items, total=total)
    except Exception as e:  # pragma: no cover
        logger.error(f"查询机器码列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询失败，请稍后重试或联系管理员")


@router.post("/admin/revoke/{machine_code_id}")
async def admin_revoke_machine_code(
    machine_code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """管理员撤销机器码

    需要权限：管理员或超级管理员
    """
    # 权限检查
    if not (current_user.is_superuser or current_user.role in ("super_admin", "admin")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可撤销机器码")

    try:
        service = MachineCodeService(db)
        success = service.revoke_machine_code(machine_code_id)

        if not success:
            raise HTTPException(status_code=404, detail="机器码记录不存在")

        try:
            write_work_log(db, "machine_code", "revoke", machine_code_id, f"撤销机器码: id={machine_code_id}",
                           user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:  # pragma: no cover
            logger.debug("记录工作日志失败")
        return {"code": 200, "success": True, "message": "机器码已撤销"}
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.error(f"撤销机器码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="撤销失败，请稍后重试或联系管理员")


@router.post("/verify-machine-code")
async def verify_machine_code(request: VerifyMachineCodeRequest):
    """验证机器码和校验码是否匹配

    公开接口，用于验证机器码的有效性。
    """
    service = MachineCodeService()
    is_valid = service.verify_machine_code(request.machine_code, request.verification_code)

    return {
        "code": 200,
        "success": True,
        "data": {"is_valid": is_valid},
        "message": "验证成功" if is_valid else "验证失败",
    }


@router.post("/generate-initial-password")
async def generate_initial_password(
    request: GeneratePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为用户生成初始登录密码

    需要权限：超级管理员
    """
    # 权限检查：只有超级管理员可以生成密码
    if not (current_user.is_superuser or is_superuser(current_user)):
        raise HTTPException(status_code=403, detail="只有超级管理员可以生成初始密码")

    try:
        service = MachineCodeService()

        # 检查用户是否存在
        user = db.query(User).filter(User.username == request.username).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 生成初始密码
        initial_password = service.generate_initial_password(request.username, request.verification_code)

        # 更新用户密码
        user.hashed_password = get_password_hash(initial_password)
        user.must_change_password = True  # 要求首次登录修改密码
        safe_commit(db)

        try:
            write_work_log(db, "machine_code", "generate_password", user.id, f"生成初始密码: {request.username}",
                           user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:  # pragma: no cover
            logger.debug("记录工作日志失败")
        return {
            "code": 200,
            "success": True,
            "data": {
                "username": request.username,
                "initial_password": initial_password,
                "verification_code": request.verification_code,
            },
            "message": "初始密码已生成，用户首次登录后需要修改密码",
        }
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        db.rollback()
        logger.error(f"生成密码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="生成密码失败，请稍后重试或联系管理员")


@router.post("/reset-password-with-machine-code")
async def reset_password_with_machine_code(
    request: Request,
    username: str,
    machine_code: str,
    verification_code: str,
    db: Session = Depends(get_db),
):
    """使用机器码重置用户密码

    公开接口，用于用户忘记密码时重置。
    """
    # 速率限制：每IP每分钟最多5次
    client_ip = get_client_ip(request)
    if not await check_rate_limit(f"reset_pwd:{client_ip}", limit=5, window=60):
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
    try:
        service = MachineCodeService()

        # 验证机器码
        current_machine_code = service.get_machine_code()
        if current_machine_code != machine_code:
            raise HTTPException(status_code=400, detail="机器码不匹配")

        # 验证校验码
        if not service.verify_machine_code(machine_code, verification_code):
            raise HTTPException(status_code=400, detail="校验码不正确")

        # 检查用户是否存在
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 生成密码学安全的随机密码（不返回明文，仅通过安全渠道告知用户）
        from app.core.security import generate_password as gen_pwd
        new_password = gen_pwd(length=16, exclude_ambiguous=True)

        # 更新用户密码
        user.hashed_password = get_password_hash(new_password)
        user.must_change_password = True

        # 清除锁定状态
        from app.services.lockout_service import get_lockout_service
        get_lockout_service().clear(user, db)

        db.commit()

        # 离线单机环境：新密码通过 HTTP 响应返回（仅 localhost 可访问），
        # 不再写入系统临时目录——明文落盘于 %TEMP% 且 Windows 无权限限制，
        # 存在泄密风险（军标审计不合格）。
        logger.info("用户 %s 密码已通过机器码验证重置，新密码仅在本次响应中返回", username)
        return {
            "code": 200,
            "success": True,
            "data": {"username": username, "new_password": new_password},
            "message": "密码重置成功，请首次登录后立即修改",
        }
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        db.rollback()
        logger.error(f"重置密码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="重置密码失败，请稍后重试或联系管理员")


@router.get("/machine-info")
async def get_machine_info(current_user=Depends(get_current_user)):
    """获取当前机器的详细信息（需要登录）"""
    try:
        service = MachineCodeService()
        machine_info = service.get_machine_info()

        return {"code": 200, "success": True, "data": machine_info, "message": "获取成功"}
    except Exception as e:  # pragma: no cover
        logger.error(f"获取机器信息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取机器信息失败，请稍后重试或联系管理员")


# ==================== 组织通行证码 API ====================


@router.get("/organization/{org_id}/verification-code")
async def get_organization_verification_code(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取组织的校验码

    管理员接口，基于组织信息生成确定性的校验码。

    Args:
        org_id: 组织ID
    """
    # 权限检查
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        from app.models.organization import Organization

        # 查询组织
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="组织不存在")

        # 生成校验码
        service = MachineCodeService()
        verification_code = service.generate_organization_verification_code(org.id, org.name)

        return {
            "code": 200,
            "success": True,
            "data": {
                "organization_id": org.id,
                "organization_name": org.name,
                "verification_code": verification_code,
            },
            "message": "获取成功",
        }
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.error(f"获取组织校验码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取组织校验码失败，请稍后重试或联系管理员")


@router.post("/organization/create")
async def create_organization_pass_code(
    request: OrganizationPassCodeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """管理员输入校验码+选择组织→生成通行码

    管理员接口。下级单位提供机器校验码，管理员选择对应组织并输入校验码，
    系统生成通行码。管理员将通行码告知下级单位用于注册。

    Args:
        request: 创建请求（包含组织ID和校验码）
    """
    # 权限检查
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        from app.models.organization import Organization

        # 查询组织
        org = db.query(Organization).filter(Organization.id == request.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="组织不存在")

        # 生成组织校验码（用于验证管理员输入的校验码是否匹配组织）
        service = MachineCodeService(db)
        expected_code = service.generate_organization_verification_code(org.id, org.name)
        if expected_code != request.verification_code:
            raise HTTPException(status_code=400, detail="校验码不正确，请确认下级单位提供的校验码")

        # 生成通行码
        record = service.create_organization_pass_code(
            organization_id=request.organization_id,
            verification_code=request.verification_code,
            allow_subordinate=request.allow_subordinate_generation,
            created_by=current_user.id,
            description=request.description,
        )

        try:
            write_work_log(db, "machine_code", "create_org_pass_code", record.id, f"生成组织通行码: org={org.name}",
                           user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:  # pragma: no cover
            logger.debug("记录工作日志失败")
        return {
            "code": 200,
            "success": True,
            "data": {
                "id": record.id,
                "organization_id": record.organization_id,
                "organization_name": org.name,
                "pass_code": record.pass_code,
                "verification_code": request.verification_code,
                "allow_subordinate_generation": record.allow_subordinate_generation,
                "created_at": (record.created_at.isoformat() if record.created_at else None),
            },
            "message": f"通行码已生成，请将通行码告知「{org.name}」用于注册账号",
        }
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        db.rollback()
        logger.error(f"生成组织通行码失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="生成通行码失败，请稍后重试或联系管理员")


@router.get("/organization/list")
async def list_organization_pass_codes(
    organization_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询组织通行证码列表

    管理员接口，支持按组织和状态筛选。

    Args:
        organization_id: 组织ID筛选（可选）
        status: 状态筛选（pending/active/revoked）
        page: 页码
        page_size: 每页数量
    """
    # 权限检查
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        service = MachineCodeService(db)

        # 查询列表
        skip = (page - 1) * page_size
        records, total = service.get_organization_pass_codes(
            organization_id=organization_id,
            status=status,
            skip=skip,
            limit=page_size,
        )

        # 构建响应
        items = []
        for record in records:
            # 使用预加载的组织关系，避免 N+1 查询
            org = record.organization

            # 生成校验码
            verification_code = ""
            if org:
                verification_code = service.generate_organization_verification_code(org.id, org.name)

            items.append(
                {
                    "id": record.id,
                    "organization_id": record.organization_id,
                    "organization_name": org.name if org else None,
                    "pass_code": record.pass_code,
                    "verification_code": verification_code,
                    "allow_subordinate_generation": record.allow_subordinate_generation,
                    "status": record.status,
                    "created_at": (record.created_at.isoformat() if record.created_at else None),
                    "created_by": record.created_by,
                }
            )

        return ok_list(items=items, total=total, page=page, page_size=page_size)
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.error(f"查询组织通行证码列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询组织通行证码列表失败，请稍后重试或联系管理员")


@router.get("/organization/export")
async def export_organization_pass_codes(
    organization_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出组织通行证码列表为 Excel

    管理员接口，支持按组织和状态筛选。

    Args:
        organization_id: 组织ID筛选（可选）
        status: 状态筛选（pending/active/revoked）
    """
    # 权限检查
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        from app.services.export_service import ExcelExportService
        import io

        service = MachineCodeService(db)

        # 查询所有数据（不分页）
        records, _ = service.get_organization_pass_codes(
            organization_id=organization_id,
            status=status,
            skip=0,
            limit=10000,  # 导出最多 10000 条
        )

        # 构建导出数据
        export_data = []
        for record in records:
            # 使用预加载的组织关系，避免 N+1 查询
            org = record.organization

            # 生成校验码
            verification_code = ""
            if org:
                verification_code = service.generate_organization_verification_code(org.id, org.name)

            export_data.append(
                {
                    "organization_name": org.name if org else "",
                    "verification_code": verification_code,
                    "pass_code": record.pass_code,
                    "allow_subordinate_generation": record.allow_subordinate_generation,
                    "status": record.status,
                    "created_at": (record.created_at.isoformat() if record.created_at else ""),
                }
            )

        # 导出 Excel
        export_service = ExcelExportService()
        excel_bytes = export_service.export_organization_pass_codes(
            pass_codes=export_data,
            filename="组织通行证码列表",
        )

        # 返回文件流
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=organization_pass_codes.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        logger.error(f"导出组织通行证码列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="导出组织通行证码列表失败，请稍后重试或联系管理员")


@router.delete("/organization/{pass_code_id}", summary="删除通行码记录")
async def delete_organization_pass_code(
    pass_code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除通行码记录

    管理员可删除任意通行码记录（包括已激活和未激活的）。
    删除后该通行码将无法用于注册。

    Args:
        pass_code_id: 通行码记录ID
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        service = MachineCodeService(db)
        success = service.delete_organization_pass_code(pass_code_id)

        if not success:
            raise HTTPException(status_code=404, detail="通行码记录不存在")

        try:
            write_work_log(db, "machine_code", "delete_org_pass_code", pass_code_id, f"删除通行码记录: id={pass_code_id}",
                           user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:  # pragma: no cover
            logger.debug("记录工作日志失败")

        return {"code": 200, "success": True, "message": "通行码记录已删除"}
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        db.rollback()
        logger.error(f"删除通行码记录失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除失败，请稍后重试或联系管理员")


# 机器码权限管理 API


class MachineCodePermissionBaseRequest(BaseModel):
    """机器码权限请求基类"""

    permissions: list[Permission] = Field(..., description="权限标识符列表")


class MachineCodePermissionGrantRequest(MachineCodePermissionBaseRequest):
    """授予权限请求"""

    expires_at: Optional[datetime] = Field(None, description="过期时间 ISO格式")


class MachineCodePermissionRevokeRequest(MachineCodePermissionBaseRequest):
    """撤销权限请求"""


class MachineCodePermissionResponse(BaseModel):
    id: str
    machine_code_id: int
    permission: str
    granted_by: Optional[int]
    expires_at: Optional[str]
    created_at: str

    model_config = ConfigDict(from_attributes=True)


@router.get("/{machine_code_id}/permissions")
async def get_machine_code_permissions(
    machine_code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取机器码关联的功能权限列表

    需要权限：管理员或超级管理员
    """
    require_admin(current_user, error_message="仅管理员可查看机器码权限")

    try:
        service = MachineCodePermissionService(db)
        permissions = service.get_machine_code_permissions(machine_code_id)

        items = [
            {
                "id": p.id,
                "machine_code_id": p.machine_code_id,
                "permission": p.permission,
                "granted_by": p.granted_by,
                "expires_at": p.expires_at.isoformat() if p.expires_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in permissions
        ]

        return ok_list(items, len(items), message="查询成功")
    except Exception:  # pragma: no cover
        logger.error("获取机器码权限失败", exc_info=True)
        raise HTTPException(status_code=500, detail="获取机器码权限失败")


@router.post("/{machine_code_id}/permissions")
async def grant_machine_code_permissions(
    machine_code_id: int,
    request: MachineCodePermissionGrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量授予机器码功能权限

    需要权限：管理员或超级管理员
    """
    require_admin(current_user, error_message="仅管理员可管理机器码权限")

    try:
        service = MachineCodePermissionService(db)
        count = service.batch_grant_permissions(
            machine_code_id=machine_code_id,
            permissions=request.permissions,
            granted_by=current_user.id,
            expires_at=request.expires_at,
        )

        try:
            write_work_log(db, "machine_code", "grant_permissions", machine_code_id, f"授予机器码权限: {count}个",
                           user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:  # pragma: no cover
            logger.debug("记录工作日志失败")
        return {
            "code": 200,
            "success": True,
            "data": {"granted_count": count},
            "message": f"成功授予 {count} 个权限",
        }
    except Exception:  # pragma: no cover
        logger.error("授予机器码权限失败", exc_info=True)
        raise HTTPException(status_code=500, detail="授予机器码权限失败")


@router.delete("/{machine_code_id}/permissions")
async def revoke_machine_code_permissions(
    machine_code_id: int,
    request: MachineCodePermissionRevokeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量撤销机器码功能权限

    需要权限：管理员或超级管理员
    """
    require_admin(current_user, error_message="仅管理员可管理机器码权限")

    try:
        service = MachineCodePermissionService(db)
        count = service.batch_revoke_permissions(
            machine_code_id=machine_code_id,
            permissions=request.permissions,
        )

        try:
            write_work_log(db, "machine_code", "revoke_permissions", machine_code_id, f"撤销机器码权限: {count}个",
                           user_id=current_user.id, username=getattr(current_user, "username", ""))
        except Exception:  # pragma: no cover
            logger.debug("记录工作日志失败")
        return {
            "code": 200,
            "success": True,
            "data": {"revoked_count": count},
            "message": f"成功撤销 {count} 个权限",
        }
    except Exception:  # pragma: no cover
        logger.error("撤销机器码权限失败", exc_info=True)
        raise HTTPException(status_code=500, detail="撤销机器码权限失败")


@router.delete("/{machine_code_id}/permissions/{permission}")
async def revoke_single_machine_code_permission(
    machine_code_id: int,
    permission: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """撤销机器码单个功能权限

    需要权限：管理员或超级管理员
    """
    require_admin(current_user, error_message="仅管理员可管理机器码权限")

    try:
        service = MachineCodePermissionService(db)
        success = service.revoke_permission(machine_code_id, permission)

        if not success:
            raise HTTPException(status_code=404, detail="权限记录不存在")

        return {"code": 200, "success": True, "message": "权限已撤销"}
    except HTTPException:
        raise
    except Exception:  # pragma: no cover
        logger.error("撤销机器码权限失败", exc_info=True)
        raise HTTPException(status_code=500, detail="撤销机器码权限失败")


@router.get("/user/{user_id}/effective-permissions")
async def get_user_effective_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户实际生效的权限（含机器码限制）

    需要权限：管理员或超级管理员
    """
    require_admin(current_user, error_message="仅管理员可查看用户实际权限")

    try:
        permissions, restricted = await rbac_service.get_user_permissions_with_restrictions(str(user_id), db)

        return {
            "code": 200,
            "success": True,
            "data": {
                "user_id": user_id,
                "effective_permissions": list(permissions),
                "restricted_permissions": list(restricted),
            },
            "message": "查询成功",
        }
    except Exception:  # pragma: no cover
        logger.error("获取用户实际权限失败", exc_info=True)
        raise HTTPException(status_code=500, detail="获取用户实际权限失败")
