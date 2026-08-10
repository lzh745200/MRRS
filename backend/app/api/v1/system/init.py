"""
系统初始化API
提供系统首次初始化配置和初始化状态检查
用于帮扶管理信息系统的初始部署设置
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.transaction import safe_commit
from app.core.security import get_current_user, PasswordPolicy
from app.core.config import settings
from app.services.system_config_service import SystemConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/init", tags=["系统初始化"])


# ==================== Pydantic 模型 ====================

class InitRequest(BaseModel):
    """系统初始化请求"""
    organization_name: str = Field(..., description="单位名称", min_length=2, max_length=100)
    organization_short_name: Optional[str] = Field(None, description="单位简称")
    organization_code: Optional[str] = Field(None, description="单位编码")
    admin_username: str = Field("admin", description="超级管理员用户名")
    admin_password: str = Field(..., description="超级管理员密码", min_length=12)
    admin_email: Optional[str] = Field(None, description="超级管理员邮箱")
    system_name: Optional[str] = Field("帮扶管理信息系统", description="系统名称")
    contact_person: Optional[str] = Field(None, description="联系人")
    contact_phone: Optional[str] = Field(None, description="联系电话")


class InitStatusResponse(BaseModel):
    """初始化状态响应"""
    initialized: bool
    organization_name: Optional[str] = None
    system_name: Optional[str] = None
    initialized_at: Optional[str] = None
    version: str


class InitStepResponse(BaseModel):
    """初始化步骤响应"""
    step: str
    status: str
    message: str


# ==================== API 端点 ====================

@router.get("/status", summary="检查系统初始化状态")
async def check_init_status(db: Session = Depends(get_db)):
    """检查系统是否已完成初始化

    新安装的系统需要通过此接口确认是否已完成初始配置。
    未初始化的系统会引导用户完成初始化向导。
    """
    try:
        svc = SystemConfigService(db)
        is_initialized = svc.is_initialized()

        result = {
            "initialized": is_initialized,
            "version": getattr(settings, "PROJECT_VERSION", "1.0.0"),
        }

        if is_initialized:
            result["organization_name"] = svc.get("organization_name", "未知单位")
            result["system_name"] = svc.get("system_name", "帮扶管理信息系统")
            result["initialized_at"] = svc.get("init_timestamp", None)

        return {"success": True, "data": result}
    except Exception as e:
        logger.error("检查初始化状态失败: %s", e)
        return {
            "success": True,
            "data": {
                "initialized": False,
                "version": getattr(settings, "PROJECT_VERSION", "1.0.0"),
                "error": str(e),
            },
        }


@router.post("/initialize", summary="执行系统初始化")
async def initialize_system(
    request: InitRequest,
    db: Session = Depends(get_db),
):
    """执行系统首次初始化

    系统部署后首次使用时调用此接口完成初始化配置，包括：
    1. 创建根组织单位
    2. 创建超级管理员账号
    3. 初始化系统配置参数
    4. 初始化默认角色和权限
    5. 标记系统为已初始化状态

    注意：此操作只能执行一次，重复调用将返回错误。
    """
    try:
        svc = SystemConfigService(db)

        # 检查是否已初始化
        if svc.is_initialized():
            raise HTTPException(status_code=400, detail="系统已完成初始化，不能重复执行")

        # 校验管理员密码强度（与注册接口统一密码策略，确保最高权限账户不留弱密码）
        pw_valid, pw_error = PasswordPolicy.validate(request.admin_password, request.admin_username)
        if not pw_valid:
            raise HTTPException(status_code=400, detail=pw_error)

        steps = []

        # 步骤1：验证输入参数
        steps.append({"step": "validate", "status": "success", "message": "参数验证通过"})

        # 步骤2：初始化系统配置
        svc.initialize_defaults()
        svc.set("system_name", request.system_name or "帮扶管理信息系统", "系统名称")
        svc.set("organization_name", request.organization_name, "单位名称")
        if request.organization_short_name:
            svc.set("organization_short_name", request.organization_short_name, "单位简称")
        if request.organization_code:
            svc.set("organization_code", request.organization_code, "单位编码")
        if request.contact_person:
            svc.set("contact_person", request.contact_person, "联系人")
        if request.contact_phone:
            svc.set("contact_phone", request.contact_phone, "联系电话")
        svc.set("init_timestamp", datetime.now(timezone.utc).isoformat(), "初始化时间戳")
        steps.append({"step": "config", "status": "success", "message": "系统配置初始化完成"})

        # 步骤3：创建超级管理员账号
        try:
            from app.models.user import User
            from app.core.security import get_password_hash

            # 检查管理员用户是否已存在
            existing_admin = db.query(User).filter(User.username == request.admin_username).first()
            if existing_admin:
                steps.append({"step": "admin_user", "status": "skipped", "message": "管理员账号已存在"})
            else:
                admin_user = User(
                    username=request.admin_username,
                    hashed_password=get_password_hash(request.admin_password),
                    email=request.admin_email or "",
                    is_superuser=True,
                    is_active=True,
                    full_name="系统管理员",
                )
                db.add(admin_user)
                safe_commit(db)
                steps.append({"step": "admin_user", "status": "success", "message": "超级管理员账号创建成功"})
        except Exception as e:
            logger.warning("创建管理员账号失败: %s", e)
            steps.append({"step": "admin_user", "status": "warning", "message": f"管理员账号创建失败: {str(e)}"})

        # 步骤4：标记系统为已初始化
        svc.set_initialized(org_id=1)
        steps.append({"step": "finalize", "status": "success", "message": "系统初始化完成"})

        logger.info("系统初始化完成，单位: %s", request.organization_name)

        return {
            "success": True,
            "message": f"系统初始化完成，欢迎使用{request.system_name or '帮扶管理信息系统'}",
            "data": {
                "organization_name": request.organization_name,
                "admin_username": request.admin_username,
                "initialized_at": datetime.now(timezone.utc).isoformat(),
                "steps": steps,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("系统初始化失败: %s", e)
        raise HTTPException(status_code=500, detail=f"系统初始化失败: {str(e)}")


@router.post("/reset", summary="重置系统初始化状态（仅超级管理员）")
async def reset_initialization(
    confirm: str = Query(..., description="输入 'RESET' 确认重置操作"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重置系统初始化状态

    危险操作：此接口将清除系统初始化标记，允许重新执行初始化流程。
    需要超级管理员权限，且必须输入确认字符串。
    """
    from app.core.permission_utils import is_admin

    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")

    if confirm != "RESET":
        raise HTTPException(status_code=400, detail="请输入 'RESET' 确认重置操作")

    try:
        svc = SystemConfigService(db)
        svc.set("initialized", "false")
        svc.set("init_timestamp", "")

        logger.warning(
            "系统初始化状态已被重置，操作人: %s",
            getattr(current_user, "username", "unknown"),
        )

        return {
            "success": True,
            "message": "系统初始化状态已重置，可重新执行初始化流程",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置失败: {str(e)}")


@router.get("/checklist", summary="获取初始化前检查清单")
async def get_init_checklist():
    """获取系统初始化前需要准备的资料清单

    帮助用户在执行初始化前确认各项准备工作已完成。
    """
    return {
        "success": True,
        "data": {
            "checklist": [
                {"item": "确定系统部署单位全称和简称", "required": True},
                {"item": "准备单位编码（如有帮扶单位编码体系）", "required": False},
                {"item": "确定超级管理员账号用户名", "required": True},
                {"item": "设置安全的超级管理员密码（至少12位）", "required": True},
                {"item": "准备超级管理员联系邮箱", "required": False},
                {"item": "确认系统安装目录有足够磁盘空间（建议10GB以上）", "required": True},
                {"item": "确认操作系统时间正确", "required": True},
                {"item": "阅读系统安全使用规范", "required": False},
            ],
        },
    }
