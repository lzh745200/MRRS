"""
权限配置包 API 路由

提供权限配置包的导出/导入功能，用于离线多机协作场景下的权限同步。
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Form, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.core.permission_utils import is_admin
from app.models.user import User
from app.schemas.permission_package import (
    PermissionPackageConfirmRequest,
    PermissionPackageConfirmResult,
    PermissionPackageExportRequest,
    PermissionPackageExportResult,
    PermissionPackageImportResult,
)
from app.services.permission_package_service import PermissionPackageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permission-packages", tags=["权限配置包"])

_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def _client_is_loopback(request: Request) -> bool:
    """判断请求是否来自本机回环地址（基于 TCP 对端地址，不信任可伪造头）。"""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return host in _LOOPBACK_HOSTS


def _resolve_package_upload_path(file_name: str) -> str:
    """净化权限包文件名并解析到上传目录内（路径遍历防护）。

    供 /import 与 /confirm 复用：basename 等价校验 + 反斜杠拒绝 +
    realpath 越界校验。与 download 端点的防护策略保持一致。
    """
    if (
        not file_name
        or "\\" in file_name
        or os.path.basename(file_name) != file_name
        or file_name in (".", "..")
    ):
        raise HTTPException(status_code=400, detail="非法文件名")
    from app.utils.paths import get_runtime_uploads_path

    upload_dir = str(get_runtime_uploads_path("permission_packages"))
    real_dir = os.path.realpath(upload_dir)
    file_path = os.path.realpath(os.path.join(real_dir, file_name))
    if not file_path.startswith(real_dir + os.sep):
        raise HTTPException(status_code=400, detail="非法文件路径")
    return file_path


def _optional_current_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """可选认证：未登录时返回 None（登录前离线导入权限包场景）。

    与 get_current_user 不同，本依赖不抛 401，供全新系统登录前导入权限包使用。
    """
    token = None
    if authorization:
        parts = authorization.split(" ", 1)
        token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else parts[0]
    if not token:
        return None
    try:
        from app.core.security import decode_token
        from app.core.database import SessionLocal

        payload = decode_token(token)
        if not payload or not payload.get("sub"):
            return None
        db = SessionLocal()
        try:
            return db.query(User).filter(User.username == payload["sub"]).first()
        finally:
            db.close()
    except HTTPException:
        return None


@router.post("/export", response_model=PermissionPackageExportResult, summary="导出权限配置包")
def export_permission_package(
    body: PermissionPackageExportRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    导出完整权限配置为 ZIP 包。

    包含: RBAC 角色、角色权限、用户-角色关联、用户直接权限、
    用户菜单覆盖、用户遗留权限字段。
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    service = PermissionPackageService(db)
    result = service.export_package(
        password=body.password if body else None,
        description=body.description if body else None,
        role_names=body.role_names if body else None,
        bind_machine_code=bool(getattr(body, "bind_machine_code", False)) if body else False,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "导出失败"))

    return JSONResponse(content=result)


@router.get("/download/{file_name}", summary="下载权限配置包文件")
def download_permission_package(
    file_name: str,
    current_user: User = Depends(get_current_user),
):
    """
    下载已导出的权限配置包 ZIP 文件。
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    from app.utils.paths import get_runtime_uploads_path

    upload_dir = str(get_runtime_uploads_path("permission_packages"))
    # 路径遍历防护: 仅允许合法文件名(不允许 ../ 或绝对路径)
    safe_name = os.path.basename(file_name)
    if safe_name != file_name:
        raise HTTPException(status_code=400, detail="非法文件名")
    file_path = os.path.join(upload_dir, safe_name)
    # 二次校验: realpath 必须在 upload_dir 内
    real_path = os.path.realpath(file_path)
    real_dir = os.path.realpath(upload_dir)
    if not real_path.startswith(real_dir):
        raise HTTPException(status_code=400, detail="非法文件路径")

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="文件不存在或已被清理")

    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.post("/import", response_model=PermissionPackageImportResult, summary="导入权限配置包（验证预览）")
async def import_permission_package(
    request: Request,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    上传权限配置包 ZIP 文件，进行验证并返回预览数据。

    此步骤不实际修改数据库，让管理员确认后再执行导入。

    **离线导入场景**: 全新系统在登录前即可导入权限包（管理员在
    其他机器导出,新机器导入后获得页面访问权限）。此步骤仅做
    验证预览,不写入数据,因此允许未登录调用——但仅限本机来源,
    与 /confirm 门禁一致（W1-T2）。
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的权限配置包文件")

    # 未认证调用仅允许本机（桌面应用场景），防止远程未授权上传
    if not current_user or not is_admin(current_user):
        if not _client_is_loopback(request):
            raise HTTPException(status_code=403, detail="仅允许本机导入权限包")

    # 路径遍历防护：净化文件名并解析到上传目录内
    from app.utils.paths import get_runtime_uploads_path

    file_path = _resolve_package_upload_path(file.filename)
    upload_dir = str(get_runtime_uploads_path("permission_packages"))
    os.makedirs(upload_dir, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    tmp_path = file_path
    try:
        service = PermissionPackageService(db)
        # Phase E：解密口令 + 本机机器码（用于绑定校验）
        _machine_code = ""
        try:
            from app.services.machine_code_service import MachineCodeService

            _s = SessionLocal()
            try:
                _machine_code = MachineCodeService(_s).get_machine_code() or ""
            finally:
                _s.close()
        except Exception:
            _machine_code = ""
        result = service.import_package(
            tmp_path, password=password, current_machine_code=_machine_code
        )
        # 契约：返回服务端保存的文件名，前端两步导入（import → confirm）必需。
        # 旧版前端缺陷即因响应缺失该字段导致 confirm 永不执行、导入不落库。
        saved_name = os.path.basename(file_path)
        if isinstance(result, dict):
            result["saved_file_name"] = saved_name
            result["file_name"] = saved_name
        return JSONResponse(content=result)
    except Exception as e:
        logger.error("权限配置包导入预览失败: %s", e, exc_info=True)
        # Clean up on error since confirm won't need it
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail="导入预览失败，请稍后重试或联系管理员")


@router.post("/confirm/{file_name}", response_model=PermissionPackageConfirmResult, summary="确认导入权限配置包")
def confirm_import_permission_package(
    file_name: str,
    body: PermissionPackageConfirmRequest = PermissionPackageConfirmRequest(),
    current_user: Optional[User] = Depends(_optional_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """
    确认导入权限配置包，将所有权限配置写入数据库。

    导入策略: 完全替换（mirror mode）。
    警告: 此操作会删除目标电脑上的现有 RBAC 权限配置（系统角色除外）。

    **离线导入场景**: 与 /import 配套,全新系统登录前即可应用权限包
    （管理员在其他机器导出,新机器导入后获得页面访问权限）。
    未登录调用时仅允许本机来源(127.0.0.1/::1),防止远程未授权导入。
    """
    if not current_user or not is_admin(current_user):
        # 登录前离线导入: 仅允许本机来源（桌面应用场景）
        if not _client_is_loopback(request):
            raise HTTPException(status_code=403, detail="仅允许本机导入权限包")

    # 路径遍历防护：净化 file_name（历史缺陷可致任意文件删除）
    file_path = _resolve_package_upload_path(file_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="导入文件不存在，请先通过 /import 上传")

    service = PermissionPackageService(db)
    try:
        result = service.confirm_import(
            file_path,
            overwrite_existing=body.overwrite_existing,
            mode=body.mode,
        )
    finally:
        # Clean up the uploaded file after import (success or failure)
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except OSError:
            pass

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "导入失败"))

    return JSONResponse(content=result)
