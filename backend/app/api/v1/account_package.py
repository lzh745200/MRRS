"""账号开通包 API（P1-b）。

- 导出/下载/撤销：super_admin；
- 预览/确认：出厂首装允许本机匿名，已初始化机器要求管理员 + X-Confirm-Password；
- 所有响应统一 ``success_response``，错误映射为稳定 AP_* 码。
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.permission_package import _client_is_loopback, _optional_current_user
from app.core.account_package import MAX_PACKAGE_BYTES, AccountPackageError
from app.core.database import get_db
from app.core.permission_utils import is_superuser, require_admin, require_superuser
from app.core.security import get_current_user
from app.core.response import success_response
from app.models.organization import Organization
from app.models.user import User
from app.services.account_package_service import (
    AccountPackageBusinessError,
    AccountPackageService,
)
from app.services.first_run_service import is_pristine_first_run
from app.services.machine_code_service import MachineCodeService
from app.utils.audit_logger import AuditAction, AuditLogger

router = APIRouter(prefix="/account-packages", tags=["账号开通包"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    require_admin(current_user)
    return current_user


def _require_superuser(current_user: User = Depends(get_current_user)) -> User:
    require_superuser(current_user)
    return current_user


class ExportAccountPackageRequest(BaseModel):
    organization_code: str = Field(..., min_length=6, max_length=6)
    organization_name: str = Field("", max_length=100)
    parent_code: str = Field("", max_length=6)
    admin_username: str = Field("", max_length=20)
    admin_full_name: str = Field("", max_length=50)
    accounts: list[dict[str, str]] = Field(default_factory=list)
    target_machine_code: str = Field(..., min_length=8, max_length=64)
    package_password: str = Field(..., min_length=12, max_length=128)
    grants: dict[str, str] = Field(default_factory=dict)
    valid_days: int = Field(7, ge=1, le=30)


class RevokeAccountPackageRequest(BaseModel):
    reason: str = Field("", max_length=500)


def _fail(exc: Exception) -> AccountPackageBusinessError:
    if isinstance(exc, AccountPackageBusinessError):
        return exc
    if isinstance(exc, AccountPackageError):
        code = getattr(exc, "code", "AP_BAD_PACKAGE")
        status = 403 if "SIGNATURE" in code or "UNSIGNED" in code else 400
        return AccountPackageBusinessError(str(exc), code=code, status=status)
    return AccountPackageBusinessError("账号包处理失败", code="AP_ROLLBACK", status=500)


def _assert_import_principal(
    request: Request,
    current_user: Optional[User],
    db: Session,
    confirm_password: str,
    *,
    require_confirm: bool,
):
    if current_user is not None:
        require_admin(current_user)
        if require_confirm:
            from app.api.v1.deps import verify_confirm_password_value

            verify_confirm_password_value(request, confirm_password, current_user)
        return
    if not _client_is_loopback(request):
        _raise_http_error(
            AccountPackageBusinessError("仅允许本机导入账号包", code="AP_PREREQUISITE", status=403)
        )
    # 真·空库（一个用户都没有）直接放行；仅出厂种子账号未使用时复用共享判定。
    if db.query(User.id).first() is not None and not is_pristine_first_run(db):
        _raise_http_error(
            AccountPackageBusinessError(
                "系统已初始化，请登录管理员账号后导入", code="AP_PREREQUISITE", status=403
            )
        )


@router.post("/export")
def export_account_package(
    body: ExportAccountPackageRequest,
    current_user: User = Depends(_require_superuser),
    db: Session = Depends(get_db),
):
    service = AccountPackageService(db)
    package_id = str(uuid.uuid4())
    try:
        result = service.export_package(
            package_id=package_id,
            organization_code=body.organization_code,
            organization_name=body.organization_name,
            parent_code=body.parent_code,
            admin_username=body.admin_username,
            admin_full_name=body.admin_full_name,
            target_machine_code=body.target_machine_code,
            grants=body.grants,
            password=body.package_password,
            issued_by=current_user,
            valid_days=body.valid_days,
            accounts=body.accounts or None,
        )
    except (AccountPackageBusinessError, AccountPackageError) as exc:  # 统一映射稳定错误码
        _raise_http_error(_fail(exc))
    AuditLogger.log(
        action=AuditAction.ACCOUNT_PACKAGE_EXPORT,
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", None),
        resource_type="account_package",
        resource_id=package_id,
        details={"target_org": body.organization_code},
    )
    return success_response(data=result)


@router.get("/{package_id}/download")
def download_account_package(
    package_id: str,
    _current_user: User = Depends(_require_superuser),
):
    path = AccountPackageService.package_path(package_id)
    if not path.exists():
        _raise_http_error(AccountPackageBusinessError("账号包文件不存在", code="AP_NOT_FOUND", status=404))
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=f"account-package-{package_id}.apkg",
    )


@router.get("")
def list_account_packages(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    issuer_org = None
    if not is_superuser(current_user):
        org = db.query(Organization).filter(
            Organization.id == getattr(current_user, "organization_id", None)
        ).first()
        issuer_org = getattr(org, "code", None) or "__none__"
    rows = AccountPackageService(db).list_exports(issuer_org, limit=limit)
    return success_response(data={"items": [row.to_dict() for row in rows], "total": len(rows)})


@router.get("/receipts")
def list_account_package_receipts(
    _current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    rows = AccountPackageService(db).list_receipts()
    return success_response(data={"items": [row.to_dict() for row in rows], "total": len(rows)})


@router.post("/{package_id}/revoke")
def revoke_account_package(
    package_id: str,
    body: RevokeAccountPackageRequest,
    current_user: User = Depends(_require_superuser),
    db: Session = Depends(get_db),
):
    try:
        row = AccountPackageService(db).revoke(package_id, body.reason)
    except (AccountPackageBusinessError, AccountPackageError) as exc:
        _raise_http_error(_fail(exc))
    AuditLogger.log(
        action=AuditAction.ACCOUNT_PACKAGE_REVOKE,
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", None),
        resource_type="account_package",
        resource_id=package_id,
        details={"reason": body.reason[:200]},
    )
    return success_response(data=row.to_dict())


@router.post("/preview")
async def preview_account_package(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(...),
    current_user: Optional[User] = Depends(_optional_current_user),
    db: Session = Depends(get_db),
):
    _assert_import_principal(request, current_user, db, "", require_confirm=False)
    raw = await file.read(MAX_PACKAGE_BYTES + 1)
    if len(raw) > MAX_PACKAGE_BYTES:
        _raise_http_error(AccountPackageBusinessError("账号包超过大小上限", code="AP_FILE_TOO_LARGE", status=413))
    try:
        data = AccountPackageService(db).preview(
            raw, password=password, machine_code=MachineCodeService().get_machine_code()
        )
    except (AccountPackageBusinessError, AccountPackageError) as exc:
        _raise_http_error(_fail(exc))
    return success_response(data=data)


@router.post("/confirm")
async def confirm_account_package(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(...),
    current_user: Optional[User] = Depends(_optional_current_user),
    confirm_password: str = Header("", alias="X-Confirm-Password"),
    db: Session = Depends(get_db),
):
    _assert_import_principal(request, current_user, db, confirm_password, require_confirm=True)
    raw = await file.read(MAX_PACKAGE_BYTES + 1)
    if len(raw) > MAX_PACKAGE_BYTES:
        _raise_http_error(AccountPackageBusinessError("账号包超过大小上限", code="AP_FILE_TOO_LARGE", status=413))
    try:
        data = AccountPackageService(db).confirm(
            raw, password=password, machine_code=MachineCodeService().get_machine_code()
        )
    except (AccountPackageBusinessError, AccountPackageError) as exc:
        err = _fail(exc)
        AuditLogger.log_safely(
            action=AuditAction.ACCOUNT_PACKAGE_IMPORT_FAILED,
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", None),
            resource_type="account_package",
            details={"error_code": err.code},
        )
        _raise_http_error(err)
    AuditLogger.log(
        action=AuditAction.ACCOUNT_PACKAGE_CONFIRM,
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", None),
        resource_type="account_package",
        resource_id=data["package_id"],
        details={"usernames": [u["username"] for u in data.get("users", [])]},
    )
    return success_response(data=data)


def _raise_http_error(exc: AccountPackageBusinessError) -> None:
    from fastapi import HTTPException

    raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)})
