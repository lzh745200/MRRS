"""
系统初始化API
提供系统首次初始化配置和初始化状态检查
用于帮扶管理信息系统的初始部署设置
"""

# security-audit: exempt data_scope — 系统初始化引导，创建首个管理员，无数据权限主体

import hmac
import ipaddress
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.transaction import safe_commit
from app.core.security import get_current_user, PasswordPolicy
from app.core.config import settings
from app.core.permission_utils import is_superuser
from app.services.system_config_service import SystemConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/init", tags=["系统初始化"])

# 深审 #82：初始化并发守卫。原实现先 is_initialized() 再写多步配置，两者之间
# 没有任何互斥 —— 两个并发请求（多 worker / 内部调用）会各自创建超管、重复
# 生成 system_id，并把初始化标记与组织/系统 ID 写成互相覆盖的结果。
_INIT_LOCK = threading.Lock()


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


class ResetInitializationRequest(BaseModel):
    """重置初始化状态请求（密码必须走请求体，禁止进入 URL/访问日志）"""
    confirm: str = Field(..., description="输入 RESET 确认")
    admin_password: str = Field(..., min_length=1, description="当前超级管理员密码")


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


def _is_loopback_request(request: Request) -> bool:
    """仅允许本机首次引导；代理转发后的地址不被当作回环。"""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    if not host:
        return False
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return False


def _bootstrap_token_valid(request: Request) -> bool:
    """可选的首次引导令牌；配置后必须提供，未配置时由本机+空库门禁兜底。"""
    expected = os.getenv("INIT_BOOTSTRAP_TOKEN", "").strip()
    if not expected:
        return True
    supplied = request.headers.get("X-Init-Token", "").strip()
    return bool(supplied) and hmac.compare_digest(supplied, expected)


def _ensure_first_run_bootstrap(request: Request, db: Session, svc: SystemConfigService) -> None:
    """匿名初始化只能发生在“本机 + 空库 + 未初始化”状态。

    历史缺陷：本接口仅检查 ``initialized`` 标记。实际安装库经常已有 seed 创建的
    超管但该标记缺失，等于把匿名超管创建入口常开。这里把“存在任何用户/组织”
    也作为硬拒绝条件；已有数据的系统只能由已登录超管走受控流程。
    """
    from app.models.organization import Organization
    from app.models.user import User

    if svc.is_initialized():
        raise HTTPException(status_code=409, detail="系统已完成初始化，不能重复执行")
    if db.query(User.id).first() is not None or db.query(Organization.id).first() is not None:
        raise HTTPException(status_code=409, detail="系统已存在用户或组织，禁止匿名重新初始化")
    if not _is_loopback_request(request):
        raise HTTPException(status_code=403, detail="首次初始化仅允许在本机操作")
    if not _bootstrap_token_valid(request):
        raise HTTPException(status_code=403, detail="首次初始化令牌无效")


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
            "version": getattr(settings, "PROJECT_VERSION", "1.10.0"),
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
                "version": getattr(settings, "PROJECT_VERSION", "1.10.0"),
                # W1-T8：内部异常细节不出站，仅记录日志
                "error": "状态检查失败，请查看服务端日志",
            },
        }


@router.post("/initialize", summary="执行系统初始化")
async def initialize_system(
    request: InitRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """系统首次初始化入口（并发 fail-closed 守卫见 _run_initialization）。"""
    # 非阻塞抢锁：已有初始化在跑时直接 409，绝不并发双跑（fail-closed）
    if not _INIT_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="系统初始化正在进行中，请稍后重试")
    try:
        _ensure_first_run_bootstrap(http_request, db, SystemConfigService(db))
        return await _run_initialization(request, db)
    finally:
        _INIT_LOCK.release()


def _resolve_root_org_code(raw_code: Optional[str]) -> str:
    """校验并规范化根组织编码（6 位行政区划代码）。

    组织编码是 v1.16.4 起的强制契约（跨机匹配唯一依据）；初始化缺失/非法时
    必须给 400 可操作指引，不得让 OrganizationCreate 的校验错误冒泡成 500。

    2026-10-27（P2）：**不再强制省级**。此前面向省本级部署，市州级单位（如黔南州
    522700）首启必然被拒 —— 只能先造一个省本级根再手工建州，既反直觉，又与
    「逐级挂接从本单位起算」矛盾。现按代码实际层级建根（省/市州/县市均可），
    下级组织从该层级逐级挂接；县级根不再允许建下级（业务只有三级）。
    """
    from app.services.admin_division_service import AdminDivisionService
    from app.services.organization_code_service import OrganizationCodeService

    code = (raw_code or "").strip()
    if not code:
        raise HTTPException(
            status_code=400,
            detail="首次初始化必须提供本单位编码（6 位行政区划代码，如 520000 省本级 / 522700 黔南州 / 522701 都匀市）",
        )
    try:
        root_code = OrganizationCodeService.normalize_admin_code(code)
        # 权威区划校验：存在性 + 别名归一（贵州为全量校验，查不到即非法代码）
        root_code = AdminDivisionService.validate_code(root_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if OrganizationCodeService.infer_level(root_code) is None:
        raise HTTPException(
            status_code=400,
            detail="单位编码无法判定层级，请核对 6 位行政区划代码（如 520000 / 522700 / 522701）",
        )
    return root_code


async def _ensure_root_organization(db, request, steps) -> int:
    """创建或复用根组织单位，返回其 id。

    抽成独立函数有两个原因：降低 _run_initialization 的圈复杂度（CI C901=16），
    以及把根组织编码的校验与失败语义收敛在一处。

    注意：2026-10-27（P2）起**不再强制省级** —— 根组织可为省 / 市州 / 县级任一，
    由 _resolve_root_code 按代码实际层级判定（旧注释「根组织必须是省级编码」已过时）。
    """
    from app.models.organization import Organization
    from app.schemas.organization import OrganizationCreate
    from app.services.organization_service import OrganizationService

    try:
        root_org = (
            db.query(Organization)
            .filter(Organization.parent_id.is_(None))
            .order_by(Organization.id.asc())
            .first()
        )
        if root_org is None:
            root_code = _resolve_root_org_code(request.organization_code)
            org_svc = OrganizationService(db)
            root_org = await org_svc.create_organization(
                OrganizationCreate(
                    name=request.organization_name,
                    code=root_code,
                    is_active=True,
                ),
                created_by=0,
            )
            steps.append({"step": "organization", "status": "success", "message": "根组织单位创建成功"})
        else:
            steps.append({"step": "organization", "status": "skipped", "message": "根组织单位已存在，直接复用"})
        return int(root_org.id)
    except HTTPException:
        # 参数类错误（编码缺失/非法/非省级）原样上抛，不能被包成 500
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error("根组织单位创建失败，初始化中止: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="根组织单位创建失败，系统未初始化；请检查数据库可用性后重试，或联系管理员",
        )


async def _run_initialization(
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

        # 步骤1b：创建（或复用）根组织单位
        root_org_id = await _ensure_root_organization(db, request, steps)

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
        # 失败必须中止：若继续走到 set_initialized，系统会被标记为已初始化却
        # 没有任何超级管理员，而 /initialize 不可重入 —— 部署被永久锁死。
        from app.models.user import User
        from app.core.security import get_password_hash

        # 检查管理员用户是否已存在（查询同样纳入守卫：DB 异常也必须中止初始化）
        try:
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
            db.rollback()
            logger.error("创建管理员账号失败，初始化中止: %s", e, exc_info=True)
            # 错误细节不出站（W1-T8）：内部原因只进日志，响应只给可操作提示
            raise HTTPException(
                status_code=500,
                detail="超级管理员账号创建失败，系统未初始化；请检查数据库可用性后重试，或联系管理员",
            )

        # 步骤4：标记系统为已初始化（写入真实根组织 ID，不再硬编码 1）
        svc.set_initialized(org_id=root_org_id)
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
        raise HTTPException(status_code=500, detail="系统初始化失败，请稍后重试或联系管理员")


@router.post("/reset", summary="重置系统初始化状态（仅超级管理员）")
async def reset_initialization(
    body: ResetInitializationRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重置系统初始化状态

    危险操作：此接口将清除系统初始化标记，允许重新执行初始化流程。
    仅超级管理员可执行；密码走请求体，避免被访问日志记录。
    注意：``/initialize`` 还会拒绝“已有用户/组织”的库，因此本接口不能用于
    对已有数据的系统重新创建超管。
    """
    if not is_superuser(current_user):
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")

    if body.confirm != "RESET":
        raise HTTPException(status_code=400, detail="请输入 'RESET' 确认重置操作")

    # T047 加固：confirm 字符串之上增加管理员密码二次校验（fail-closed）
    from app.core.security import verify_password as _verify_pwd

    if not body.admin_password or not _verify_pwd(
        body.admin_password, getattr(current_user, "hashed_password", "") or ""
    ):
        raise HTTPException(status_code=403, detail="管理员密码校验失败")

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
    except Exception:
        raise HTTPException(status_code=500, detail="重置失败，请稍后重试或联系管理员")


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
