"""
Data Package API
数据包管理接口 - 导入导出功能
"""
import json
import logging
import os
import tempfile
import time
import zipfile
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Query,
                     Request, UploadFile, status)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessError, NotFoundException
from app.core.response import success_response
from app.core.security import get_current_user
from app.core.permission_utils import get_org_with_fallback, is_admin, require_admin
from app.models.import_export_history import OperationResult
from app.models.data_package import PackageType
from app.schemas.data_package import (DataPackageConfirmRequest,
                                      DataPackageConfirmResult,
                                      DataPackageExportRequest,
                                      DataPackageExportResult,
                                      DataPackageImportResult,
                                      DataPackageListResponse,
                                      DataPackagePreviewData,
                                      DataPackageResponse,
                                      DataPackageValidationResult)
from app.services.data_package_service import DataPackageService
from app.services.import_export_history_service import \
    ImportExportHistoryService
from app.core.transaction import safe_commit
from app.services.organization_permission_service import \
    OrganizationPermissionService
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-packages", tags=["数据包管理"])

# ==================== 错误消息常量 ====================
ORG_NOT_BOUND_ERROR = "当前用户未绑定组织，无法执行此操作。请联系管理员在系统管理中为您分配组织。"

# 一键上报默认导出的数据类型
ONE_CLICK_DATA_TYPES = ["villages", "projects", "funds", "schools"]


def get_package_service(db: Session = Depends(get_db)) -> DataPackageService:
    return DataPackageService(db)


def get_history_service(db: Session = Depends(get_db)) -> ImportExportHistoryService:
    return ImportExportHistoryService(db)


def get_permission_service(db: Session = Depends(get_db)) -> OrganizationPermissionService:
    return OrganizationPermissionService(db)


def get_client_ip(request: Request) -> str:
    """获取客户端IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_first_active_org(db: Session) -> Optional[int]:
    """获取第一个活跃组织的ID（内部辅助函数）"""
    from app.models.organization import Organization

    first_org = db.query(Organization).filter(Organization.is_active == True).first()  # noqa: E712
    return first_org.id if first_org else None


def _export_owner_scope(current_user) -> Optional[int]:
    """导出范围：非管理员仅导出本人录入（created_by）的记录；管理员返回 None（全组织，行为不变）"""
    return None if is_admin(current_user) else getattr(current_user, "id", None)


def _user_display_name(current_user) -> str:
    """用户显示名（full_name 优先，回退 username；非字符串属性忽略）"""
    for attr in ("full_name", "username"):
        value = getattr(current_user, attr, None)
        if isinstance(value, str) and value:
            return value
    return ""


def _safe_write_work_log(db: Session, action: str, entity_id, entity_name: str, current_user, detail: str = ""):
    """写数据包审计日志（日志失败不阻断主流程）"""
    try:
        write_work_log(
            db, "data_package", action, entity_id, entity_name,
            user_id=getattr(current_user, "id", None),
            username=_user_display_name(current_user),
            detail=detail,
        )
    except Exception as e:
        logger.warning(f"记录数据包审计日志失败: {e}")


class OneClickReportRequest(BaseModel):
    """一键上报请求体（可选）"""

    year: Optional[int] = None
    data_types: Optional[List[str]] = None
    remarks: Optional[str] = None
    description: Optional[str] = None


@router.post("/one-click-report")
async def one_click_report(
    request: Request,
    body: Optional[OneClickReportRequest] = None,
    description: Optional[str] = None,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
):
    """
    一键生成上报数据包
    自动收集当前用户所属组织的所有数据类型，打包导出并返回下载文件流。
    支持前端发送 JSON body 包含 year/data_types/remarks 字段。
    """
    # 获取组织ID（支持超级管理员回退到第一个可用组织）
    org_id = get_org_with_fallback(
        current_user=current_user,
        requested_org_id=None,
        get_first_org_callback=lambda: _get_first_active_org(service.db),
    )

    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ORG_NOT_BOUND_ERROR
        )

    # 从 body 中提取参数（如果前端发送了 JSON body）
    data_types = ONE_CLICK_DATA_TYPES
    desc = description or "一键上报数据包"
    if body:
        if body.data_types:
            data_types = body.data_types
        if body.remarks:
            desc = body.remarks
        if body.description:
            desc = body.description

    start_time = time.time()

    try:
        result = await service.export_package(
            org_id=org_id,
            data_types=data_types,
            export_by=current_user.id,
            description=desc,
            package_type=PackageType.report,
            owner_id=_export_owner_scope(current_user),
            exported_by_name=_user_display_name(current_user),
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 记录导出历史
        try:
            history_service.record_export(
                package_id=result.package_id,
                org_id=org_id,
                user_id=current_user.id,
                file_name=result.file_name,
                file_size=result.file_size,
                record_count=sum(result.manifest.record_counts.values()) if result.manifest else 0,
                data_types=ONE_CLICK_DATA_TYPES,
                duration_ms=duration_ms,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception as e:
            logger.warning(f"记录一键上报历史失败: {e}")

        # 审计日志
        _safe_write_work_log(
            service.db, "export", result.package_id,
            result.file_name or result.package_code, current_user,
            detail=f"一键上报，记录数: {sum(result.manifest.record_counts.values()) if result.manifest else 0}",
        )

        # 直接返回文件流
        file_path = getattr(result, "file_path", None)
        if file_path and os.path.exists(file_path):
            return FileResponse(
                path=file_path,
                filename=result.file_name or "report_package.zip",
                media_type="application/zip",
                headers={
                    "X-Package-Id": str(result.package_id),
                    "X-Record-Count": str(sum(result.manifest.record_counts.values()) if result.manifest else 0),
                },
            )

        # file_path 不可用时返回元数据（前端走 download 接口）
        return {
            "success": True,
            "package_id": result.package_id,
            "file_name": result.file_name,
            "file_size": result.file_size,
            "download_url": f"/api/v1/data-packages/{result.package_id}/download",
            "manifest": result.manifest.model_dump() if result.manifest else None,
        }

    except Exception as e:
        import traceback

        logger.error(f"一键上报失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成上报数据包失败，请稍后重试或联系管理员")


@router.get("", response_model=DataPackageListResponse)
async def list_data_packages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    org_id: Optional[int] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    type_filter: Optional[str] = Query(None, alias="type"),
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """获取数据包列表"""
    # 确定查询的组织ID（多级回退）
    target_org_id = org_id
    if not target_org_id:
        target_org_id = getattr(current_user, "organization_id", None) or getattr(current_user, "org_id", None)

    if not target_org_id:
        return DataPackageListResponse(total=0, page=page, page_size=page_size, items=[])

    # 检查权限 - 普通用户无权限时返回空列表而不是403，确保页面正常加载
    if not permission_service.can_access_organization(current_user.id, target_org_id):
        return DataPackageListResponse(total=0, page=page, page_size=page_size, items=[])

    packages = service.get_packages_by_org(
        target_org_id, status=status_filter, type_filter=type_filter, skip=(page - 1) * page_size, limit=page_size
    )

    # 真实总数（独立查询，不随分页截断）
    total = service.count_packages_by_org(
        target_org_id, status=status_filter, type_filter=type_filter
    )

    return DataPackageListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[DataPackageResponse.model_validate(pkg) for pkg in packages],
    )


def _received_package_to_dict(package) -> dict:
    """接收记录序列化（manifest/data_types 字段缺失容忍）"""
    import json as _json

    manifest = package.manifest if isinstance(package.manifest, dict) else {}
    data_types = package.data_types
    if isinstance(data_types, str):
        try:
            data_types = _json.loads(data_types)
        except (ValueError, TypeError):
            data_types = [data_types]

    importer = getattr(package, "importer", None)
    imported_by_name = None
    if importer is not None:
        imported_by_name = getattr(importer, "full_name", None) or getattr(importer, "username", None)

    return {
        "id": package.id,
        "package_code": package.package_code,
        "file_name": package.file_name,
        "file_size": package.file_size or 0,
        "record_count": package.record_count or 0,
        "data_types": data_types or [],
        "status": getattr(package.status, "value", package.status),
        "created_at": package.created_at.isoformat() if package.created_at else None,
        "imported_at": package.imported_at.isoformat() if package.imported_at else None,
        "imported_by": imported_by_name,
        "org_code": manifest.get("org_code"),
        "org_name": manifest.get("org_name"),
        "export_scope": manifest.get("export_scope"),
        "exported_by_name": manifest.get("exported_by_name"),
        "validation_summary": manifest.get("validation_summary"),
    }


@router.get("/received")
async def list_received_packages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取已接收的上报数据包列表（仅管理员，按创建时间倒序分页）"""
    require_admin(current_user, error_message="仅管理员可查看接收记录")

    from app.models.data_package import DataPackage

    query = (
        db.query(DataPackage)
        .filter(DataPackage.type == "report")
        .order_by(DataPackage.created_at.desc(), DataPackage.id.desc())
    )
    total = query.count()
    packages = query.offset((page - 1) * page_size).limit(page_size).all()

    return success_response(
        data={
            "items": [_received_package_to_dict(pkg) for pkg in packages],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="成功",
    )


@router.get("/{package_id}", response_model=DataPackageResponse)
async def get_data_package(
    package_id: int,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """获取数据包详情"""
    package = service.get_package(package_id)
    if not package:
        raise NotFoundException("数据包不存在")

    # 检查权限 - 普通用户无权限时抛出404而不是403，避免前端看到错误
    if not permission_service.can_access_organization(current_user.id, package.org_id):
        raise NotFoundException("数据包不存在")

    return DataPackageResponse.model_validate(package)


@router.post("/preview")
async def preview_data_for_export(
    data: DataPackageExportRequest,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
):
    """预览导出数据的统计信息（不生成包，仅返回各数据类型记录数）"""
    # 获取组织ID（支持超级管理员回退到第一个可用组织）
    org_id = get_org_with_fallback(
        current_user=current_user,
        requested_org_id=data.org_id,
        get_first_org_callback=lambda: _get_first_active_org(service.db),
    )

    from app.services.data_package_service import DATA_TYPE_MODELS

    counts = {}
    data_types = data.data_types or ["villages", "projects", "funds", "schools"]
    for dt in data_types:
        model = DATA_TYPE_MODELS.get(dt)
        if model:
            query = service.db.query(model)
            if org_id and hasattr(model, "organization_id"):
                query = query.filter(model.organization_id == org_id)
            counts[dt] = query.count()
        else:
            counts[dt] = 0

    return success_response(data={"counts": counts})


@router.post("/export", response_model=DataPackageExportResult)
async def export_data_package(
    data: DataPackageExportRequest,
    request: Request,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """导出数据包"""
    # 获取组织ID（支持超级管理员回退到第一个可用组织）
    org_id = get_org_with_fallback(
        current_user=current_user,
        requested_org_id=data.org_id,
        get_first_org_callback=lambda: _get_first_active_org(service.db),
    )

    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ORG_NOT_BOUND_ERROR
        )

    # 检查权限
    if not permission_service.can_access_organization(current_user.id, org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限访问该组织的数据。请联系管理员为您分配正确的组织权限。"
        )

    start_time = time.time()

    try:
        result = await service.export_package(
            org_id=org_id,
            data_types=data.data_types,
            export_by=current_user.id,
            description=data.description,
            package_type=data.type,
            incremental=data.incremental,
            since_sync_version=data.since_sync_version if data.incremental else None,
            owner_id=_export_owner_scope(current_user),
            exported_by_name=_user_display_name(current_user),
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 记录导出历史
        try:
            history_service.record_export(
                package_id=result.package_id,
                org_id=org_id,
                user_id=current_user.id,
                file_name=result.file_name,
                file_size=result.file_size,
                record_count=sum(result.manifest.record_counts.values()) if result.manifest else 0,
                data_types=data.data_types,
                duration_ms=duration_ms,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception as e:
            logger.warning(f"记录导出历史失败: {e}")

        # 审计日志
        _safe_write_work_log(
            service.db, "export", result.package_id,
            result.file_name or result.package_code, current_user,
            detail=f"导出数据包，记录数: {sum(result.manifest.record_counts.values()) if result.manifest else 0}",
        )

        return result

    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        import traceback

        logger.error(f"导出数据包失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="导出失败，请稍后重试或联系管理员")


@router.post("/import", response_model=DataPackageImportResult)
async def import_data_package(
    file: UploadFile = File(...),
    org_id: Optional[int] = None,
    request: Request = None,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """导入数据包（仅管理员可接收）"""
    require_admin(current_user, error_message="仅管理员可接收数据包")

    # 验证文件
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未选择文件")

    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="文件格式错误，仅支持 .zip 格式的数据包"
        )

    # 确定组织ID
    target_org_id = org_id
    if not target_org_id and hasattr(current_user, "org_id"):
        target_org_id = current_user.org_id

    if not target_org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未指定目标组织ID")

    # 检查权限
    if not permission_service.can_access_organization(current_user.id, target_org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权向该组织导入数据")

    start_time = time.time()

    # 保存上传文件到临时目录
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        content = await file.read()

        # 检查文件大小
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="文件为空，请选择有效的数据包文件"
            )

        if len(content) > 100 * 1024 * 1024:  # 100MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="文件过大，数据包大小不能超过 100MB"
            )

        temp_file.write(content)
        temp_file.close()

        result = await service.import_package(
            file_path=temp_file.name, file_name=file.filename, org_id=target_org_id, imported_by=current_user.id
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 记录导入历史
        op_result = OperationResult.SUCCESS if result.validation.is_valid else OperationResult.FAILED
        error_msg = None
        if not result.validation.is_valid:
            error_msg = "; ".join([e.message for e in result.validation.errors[:3]])

        history_service.record_import(
            package_id=result.package_id,
            org_id=target_org_id,
            user_id=current_user.id,
            file_name=file.filename,
            file_size=len(content),
            record_count=sum(result.manifest.record_counts.values()) if result.manifest else 0,
            data_types=result.manifest.data_types if result.manifest else [],
            duration_ms=duration_ms,
            ip_address=get_client_ip(request) if request else None,
            user_agent=request.headers.get("User-Agent") if request else None,
            result=op_result,
            error_message=error_msg,
        )

        # 审计日志
        _safe_write_work_log(
            service.db, "import", result.package_id,
            file.filename or result.package_code, current_user,
            detail=f"接收数据包，校验{'通过' if result.validation.is_valid else '未通过'}",
        )

        return result

    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except BusinessError as e:
        # 业务错误转换为友好提示
        error_detail = str(e)
        if "无法解压" in error_detail or "not a zip file" in error_detail.lower():
            error_detail = "数据包文件损坏或格式错误，请重新导出后再试"
        elif "manifest" in error_detail.lower():
            error_detail = "数据包清单文件缺失或格式错误，请使用系统导出的标准数据包"

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)
    except Exception as e:
        logger.error(f"导入数据包失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导入失败，请稍后重试或联系管理员"
        )

    finally:
        # 清理临时文件（先关闭句柄——Windows 不允许删除打开中的文件，
        # 否则早期 raise 路径会以 PermissionError 掩盖原始错误）
        if not temp_file.closed:
            temp_file.close()
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


# ══════════════════════════════════════════════════════════════════════
# 增量数据包端点（前端 IncrementalUpdate.vue 使用）
# ══════════════════════════════════════════════════════════════════════

class IncrementalDetectRequest(BaseModel):
    """增量变更检测请求"""
    org_id: Optional[int] = None
    data_types: List[str] = []
    base_package_id: int


class IncrementalExportRequest(BaseModel):
    """增量包导出请求"""
    org_id: Optional[int] = None
    data_types: List[str] = []
    base_package_id: int
    description: Optional[str] = None


class IncrementalImportRequest(BaseModel):
    """增量包导入请求"""
    package_id: int
    apply_changes: bool = False


def _get_base_package_time(service: DataPackageService, base_package_id: int) -> datetime:
    """获取基准数据包的导出时间（增量基准）"""
    package = service.get_package(base_package_id)
    if not package:
        raise NotFoundException("基准数据包不存在")
    base_time = getattr(package, "created_at", None)
    if not base_time:
        from datetime import datetime as _dt
        from datetime import timezone as _tz

        base_time = _dt.now(_tz.utc)
    return base_time


def _compute_package_diff_stats(service: DataPackageService, file_path: str) -> Dict[str, Dict[str, int]]:
    """对比包内记录与本地库，产出 {added, modified, deleted, total} 明细。

    added=本地不存在的记录ID数；modified=本地已存在（将被覆盖/跳过）的ID数；
    deleted 恒为 0 —— 包内不含删除墓碑，物理删除无法从包推断。

    失败语义（fail-loud）：包损坏/查询失败直接抛出，由调用方转为明确错误——
    绝不返回空统计让管理员把"统计全 0"误读为"无差异"而确认覆盖式导入。
    """
    from sqlalchemy import inspect as sa_inspect

    from app.services.data_package_service import DATA_TYPE_MODELS

    # SQLite 历史版本默认变量上限 999，现代版 32766；分块规避两个上限
    CHUNK_SIZE = 500

    stats: Dict[str, Dict[str, int]] = {}
    with zipfile.ZipFile(file_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        for dtype in manifest.get("data_types", []):
            model = DATA_TYPE_MODELS.get(dtype)
            data_file = f"data/{dtype}.json"
            if not model or data_file not in zf.namelist():
                continue
            records = json.loads(zf.read(data_file).decode("utf-8"))
            pk_name = sa_inspect(model).primary_key[0].name
            pk_col = getattr(model, pk_name)
            ids = [r.get(pk_name) for r in records if r.get(pk_name) is not None]
            existing = 0
            for start in range(0, len(ids), CHUNK_SIZE):
                chunk = ids[start:start + CHUNK_SIZE]
                existing += service.db.query(pk_col).filter(pk_col.in_(chunk)).count()
            added = len(ids) - existing
            stats[dtype] = {"added": added, "modified": existing, "deleted": 0, "total": len(ids)}
    return stats


def _diff_summary(stats: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    """把 per-type 差异统计折叠成 ChangesSummary 汇总"""
    summary = {"total_added": 0, "total_modified": 0, "total_deleted": 0}
    for item in stats.values():
        summary["total_added"] += item.get("added", 0)
        summary["total_modified"] += item.get("modified", 0)
        summary["total_deleted"] += item.get("deleted", 0)
    return summary


@router.post("/incremental/detect-changes", summary="增量变更检测")
async def incremental_detect_changes(
    base_package_id: int = Query(..., description="基准数据包ID"),
    org_id: Optional[int] = Query(None, description="组织ID（缺省用当前用户组织）"),
    data_types: List[str] = Query(default=[], description="数据类型列表"),
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """检测基准包之后各数据类型的变更记录数

    返回 ChangesSummary 结构：total_added/total_modified/total_deleted 汇总 +
    by_type 每类型 {added, modified, deleted, total} 明细。
    统计口径：added=基准时间后新建；deleted=基准时间后软删且基准前已存在；
    modified=其余变更记录。系统无物理删除墓碑，物理删除无法统计。
    """
    org_id = get_org_with_fallback(
        current_user=current_user,
        requested_org_id=org_id,
        get_first_org_callback=lambda: _get_first_active_org(service.db),
    )
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ORG_NOT_BOUND_ERROR)
    if not permission_service.can_access_organization(current_user.id, org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该组织的数据")

    base_time = _get_base_package_time(service, base_package_id)

    from sqlalchemy import func as sa_func
    from app.services.data_package_service import DATA_TYPE_MODELS

    by_type: Dict[str, Dict[str, int]] = {}
    total_added = total_modified = total_deleted = 0
    for dtype in data_types:
        model = DATA_TYPE_MODELS.get(dtype)
        if not model:
            continue
        query = service.db.query(sa_func.count(model.id))
        if hasattr(model, "organization_id"):
            query = query.filter(model.organization_id == org_id)
        elif hasattr(model, "org_id"):
            query = query.filter(model.org_id == org_id)
        if not hasattr(model, "updated_at"):
            by_type[dtype] = {"added": 0, "modified": 0, "deleted": 0, "total": 0}
            continue

        changed = query.filter(model.updated_at > base_time).scalar() or 0
        added_count = 0
        if hasattr(model, "created_at"):
            added_count = query.filter(
                model.updated_at > base_time, model.created_at > base_time
            ).scalar() or 0
        deleted_count = 0
        if hasattr(model, "is_active") and hasattr(model, "created_at"):
            deleted_count = query.filter(
                model.is_active == False,  # noqa: E712
                model.updated_at > base_time,
                model.created_at <= base_time,
            ).scalar() or 0
        modified_count = max(changed - added_count - deleted_count, 0)
        by_type[dtype] = {
            "added": added_count, "modified": modified_count,
            "deleted": deleted_count, "total": changed,
        }
        total_added += added_count
        total_modified += modified_count
        total_deleted += deleted_count

    summary = {
        "total_added": total_added,
        "total_modified": total_modified,
        "total_deleted": total_deleted,
        "by_type": by_type,
    }
    return success_response(
        data={"summary": summary, "base_package_id": base_package_id},
        message="变更检测完成",
    )


@router.post("/incremental/export", summary="导出增量数据包")
async def incremental_export(
    data: IncrementalExportRequest,
    request: Request,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """基于基准包时间导出增量数据包（仅变更记录），返回下载地址"""
    org_id = get_org_with_fallback(
        current_user=current_user,
        requested_org_id=data.org_id,
        get_first_org_callback=lambda: _get_first_active_org(service.db),
    )
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ORG_NOT_BOUND_ERROR)
    if not permission_service.can_access_organization(current_user.id, org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该组织的数据")

    start_time = time.time()
    base_time = _get_base_package_time(service, data.base_package_id)
    try:
        result = await service.export_package(
            org_id=org_id,
            data_types=data.data_types,
            export_by=current_user.id,
            description=data.description or "增量更新包",
            package_type=PackageType.update,
            incremental=True,
            since_time=base_time,
            owner_id=_export_owner_scope(current_user),
            exported_by_name=_user_display_name(current_user),
            base_package_id=data.base_package_id,
        )

        # DataPackageExportResult 无 record_counts/total_records 字段，从 manifest 取
        record_counts = dict(result.manifest.record_counts) if result.manifest else {}
        total_records = sum(record_counts.values())
        duration_ms = int((time.time() - start_time) * 1000)

        try:
            history_service.record_export(
                package_id=result.package_id,
                org_id=org_id,
                user_id=current_user.id,
                file_name=result.file_name,
                file_size=result.file_size,
                record_count=total_records,
                data_types=data.data_types,
                duration_ms=duration_ms,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception as e:
            logger.warning(f"记录增量导出历史失败: {e}")

        _safe_write_work_log(
            service.db, "export", result.package_id,
            result.file_name or result.package_code, current_user,
            detail=f"导出增量更新包(基准包{data.base_package_id})，记录数: {total_records}",
        )

        return success_response(
            data={
                "package_id": result.package_id,
                "download_url": f"/api/v1/data-packages/{result.package_id}/download",
                "filename": result.file_name,
                "record_counts": record_counts,
                "total_records": total_records,
            },
            message="增量包导出成功",
        )
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"导出增量数据包失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出失败，请稍后重试或联系管理员",
        )


@router.post("/incremental/import", summary="导入增量数据包")
async def incremental_import(
    data: IncrementalImportRequest,
    request: Request,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """导入已存在于服务器上的数据包（增量或全量）

    apply_changes=false 仅预览：统计包内记录与本地库的新增/覆盖数，不写业务表；
    apply_changes=true（仅管理员）：注册包并确认导入（覆盖式 upsert，保留原始ID）。
    """
    package = service.get_package(data.package_id)
    if not package:
        raise NotFoundException("数据包不存在")
    if not package.file_path or not os.path.exists(package.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据包文件缺失，无法处理")

    org_id = getattr(package, "org_id", None)
    if org_id and not permission_service.can_access_organization(current_user.id, org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权导入该数据包")

    try:
        stats = _compute_package_diff_stats(service, package.file_path)
    except Exception:
        logger.error("增量包差异统计失败(package_id=%s, file=%s)", data.package_id, package.file_path, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="差异统计失败，无法预览；数据包可能损坏，请重新导出",
        )
    summary = _diff_summary(stats)

    if not data.apply_changes:
        return success_response(
            data={
                "success": True,
                "preview_only": True,
                "stats": stats,
                "summary": summary,
            },
            message="预览完成",
        )

    require_admin(current_user, error_message="仅管理员可应用增量数据导入")

    start_time = time.time()
    try:
        result = await service.import_package(
            file_path=package.file_path,
            file_name=package.file_name or "package.zip",
            org_id=org_id or 0,
            imported_by=current_user.id,
        )
        confirm = await service.confirm_import(
            package_id=result.package_id,
            confirmed_by=current_user.id,
            overwrite_existing=True,
        )
        duration_ms = int((time.time() - start_time) * 1000)

        if not confirm.success:
            _safe_write_work_log(
                service.db, "import", result.package_id,
                package.file_name or "", current_user, detail="增量数据导入失败",
            )
            return success_response(
                data={
                    "success": False,
                    "preview_only": False,
                    "stats": stats,
                    "summary": summary,
                    "message": "导入失败，数据已回滚，请查看服务端日志",
                },
                message="导入失败",
            )

        try:
            history_service.record_import(
                package_id=result.package_id,
                org_id=org_id or 0,
                user_id=current_user.id,
                file_name=package.file_name or "package.zip",
                record_count=summary["total_added"] + summary["total_modified"],
                data_types=list(stats.keys()),
                duration_ms=duration_ms,
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("User-Agent"),
            )
        except Exception as e:
            logger.warning(f"记录增量导入历史失败: {e}")

        _safe_write_work_log(
            service.db, "import", result.package_id,
            package.file_name or "", current_user,
            detail=f"应用增量导入：新增{summary['total_added']}，覆盖{summary['total_modified']}",
        )

        return success_response(
            data={
                "success": True,
                "preview_only": False,
                "stats": stats,
                "summary": summary,
                "package_id": result.package_id,
            },
            message="导入成功",
        )
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"增量导入失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导入失败，请稍后重试或联系管理员",
        )


@router.post("/{package_id}/validate", response_model=DataPackageValidationResult)
async def validate_data_package(
    package_id: int,
    request: Request,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
):
    """验证数据包"""
    package = service.get_package(package_id)
    if not package:
        raise NotFoundException("数据包不存在")

    result = await service.validate_package(package.file_path)

    # 记录验证历史
    op_result = OperationResult.SUCCESS if result.is_valid else OperationResult.FAILED
    history_service.record_validate(
        package_id=package_id,
        org_id=package.org_id,
        user_id=current_user.id,
        result=op_result,
        error_message="; ".join([e.message for e in result.errors]) if result.errors else None,
        ip_address=get_client_ip(request),
    )

    return result


@router.get("/{package_id}/preview", response_model=List[DataPackagePreviewData])
async def preview_data_package(
    package_id: int,
    request: Request,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """预览数据包内容"""
    package = service.get_package(package_id)
    if not package:
        raise NotFoundException("数据包不存在")

    # 检查权限 - 无权限时返回空列表
    if not permission_service.can_access_organization(current_user.id, package.org_id):
        return []

    preview = await service.preview_package_data(package_id)

    # 记录预览历史
    history_service.record_preview(
        package_id=package_id, org_id=package.org_id, user_id=current_user.id, ip_address=get_client_ip(request)
    )

    return preview


@router.post("/{package_id}/confirm", response_model=DataPackageConfirmResult)
async def confirm_import(
    package_id: int,
    data: DataPackageConfirmRequest,
    request: Request,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """确认导入数据（仅管理员可操作）"""
    require_admin(current_user, error_message="仅管理员可接收数据包")

    package = service.get_package(package_id)
    if not package:
        raise NotFoundException("数据包不存在")

    # 检查权限
    if not permission_service.can_access_organization(current_user.id, package.org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权确认该数据包导入")

    start_time = time.time()

    try:
        result = await service.confirm_import(
            package_id=package_id,
            confirmed_by=current_user.id,
            overwrite_existing=data.overwrite_existing,
            selected_types=data.selected_types,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 记录确认历史
        op_result = OperationResult.SUCCESS if result.success else OperationResult.FAILED
        total_imported = sum(result.imported_counts.values())

        history_service.record_confirm(
            package_id=package_id,
            org_id=package.org_id,
            user_id=current_user.id,
            record_count=total_imported,
            data_types=data.selected_types,
            duration_ms=duration_ms,
            result=op_result,
            details={
                "imported_counts": result.imported_counts,
                "skipped_counts": result.skipped_counts,
                "error_counts": result.error_counts,
            },
            ip_address=get_client_ip(request),
        )

        # 审计日志
        _safe_write_work_log(
            service.db, "confirm", package_id,
            package.file_name or package.package_code, current_user,
            detail=f"确认导入，成功 {total_imported} 条，跳过 {sum(result.skipped_counts.values())} 条",
        )

        return result

    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{package_id}/download")
async def download_data_package(
    package_id: int,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """下载数据包"""
    package = service.get_package(package_id)
    if not package:
        raise NotFoundException("数据包不存在")

    # 检查权限 - 无权限时返回404
    if not permission_service.can_access_organization(current_user.id, package.org_id):
        raise NotFoundException("数据包不存在")

    if not package.file_path or not os.path.exists(package.file_path):
        raise NotFoundException("数据包文件不存在")

    return FileResponse(
        path=package.file_path,
        filename=package.file_name or f"{package.package_code}.zip",
        media_type="application/zip",
    )


@router.delete("/{package_id}")
async def delete_data_package(
    package_id: int,
    reason: Optional[str] = None,
    request: Request = None,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
    db: Session = Depends(get_db),
):
    """删除数据包"""
    package = service.get_package(package_id)
    if not package:
        raise NotFoundException("数据包不存在")

    # 检查权限
    if not permission_service.can_access_organization(current_user.id, package.org_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除该数据包")

    org_id = package.org_id

    # 记录删除历史
    history_service.record_delete(
        package_id=package_id,
        org_id=org_id,
        user_id=current_user.id,
        reason=reason,
        ip_address=get_client_ip(request) if request else None,
    )

    # 删除文件
    if package.file_path and os.path.exists(package.file_path):
        os.unlink(package.file_path)

    # 删除数据库记录
    db.delete(package)
    safe_commit(db)

    return success_response(message="删除成功")


@router.get("/{package_id}/history")
async def get_package_history(
    package_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """获取数据包操作历史"""
    package = service.get_package(package_id)
    if not package:
        raise NotFoundException("数据包不存在")

    # 检查权限 - 无权限时返回空历史
    if not permission_service.can_access_organization(current_user.id, package.org_id):
        return success_response(
            data={"package_id": package_id, "items": [], "total": 0},
            message="成功",
        )

    history = history_service.get_history_by_package(package_id, skip=(page - 1) * page_size, limit=page_size)

    return success_response(
        data={
            "package_id": package_id,
            "items": [
                {
                    "id": h.id,
                    "operation_type": h.operation_type,
                    "result": h.result,
                    "user_id": h.user_id,
                    "operation_time": h.operation_time,
                    "duration_ms": h.duration_ms,
                    "error_message": h.error_message,
                }
                for h in history
            ],
            "total": len(history),
        },
        message="成功",
    )


# ========================================================================
# 加密导入导出端点
# ========================================================================


class ExportEncryptedRequest(BaseModel):
    """加密导出请求（密码经请求体传输，避免落入 URL/请求日志）"""

    data_types: List[str]
    password: Optional[str] = None
    description: Optional[str] = None
    package_type: PackageType = PackageType.report


@router.post("/export-encrypted", response_model=DataPackageExportResult)
async def export_encrypted_package(
    request: Request,
    body: ExportEncryptedRequest,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
):
    """
    导出加密数据包

    支持密码加密，使用PBKDF2密钥派生和Fernet加密
    """
    password = body.password
    data_types = body.data_types
    description = body.description
    package_type = body.package_type

    # 获取组织ID（支持超级管理员回退到第一个可用组织）
    org_id = get_org_with_fallback(
        current_user=current_user,
        requested_org_id=None,
        get_first_org_callback=lambda: _get_first_active_org(service.db),
    )

    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ORG_NOT_BOUND_ERROR
        )

    # 验证密码强度
    if password and len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码长度至少8位")

    start_time = time.time()
    client_ip = get_client_ip(request)

    try:
        result = await service.export_encrypted_package(
            org_id=org_id,
            data_types=data_types,
            export_by=current_user.id,
            password=password,
            description=description,
            package_type=package_type,
        )

        # 记录历史
        duration_ms = int((time.time() - start_time) * 1000)
        try:
            history_service.create_history(
                package_id=result.package_id,
                operation_type="export_encrypted" if password else "export",
                result=OperationResult.SUCCESS,
                user_id=current_user.id,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )
        except Exception as e:
            logger.warning(f"记录导出加密历史失败: {e}")

        return result

    except Exception as e:
        logger.error(f"导出加密数据包失败: {str(e)}", exc_info=True)
        duration_ms = int((time.time() - start_time) * 1000)
        try:
            history_service.create_history(
                package_id=None,
                operation_type="export_encrypted" if password else "export",
                result=OperationResult.FAILED,
                user_id=current_user.id,
                duration_ms=duration_ms,
                client_ip=client_ip,
                error_message=str(e),
            )
        except Exception as hist_err:
            logger.warning(f"记录导出加密历史失败: {hist_err}")
        # W1: 错误细节不出站, 仅日志与操作历史保留内部原因
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出加密数据包失败，请稍后重试或联系管理员",
        )


class UploadEncryptedPackageRequest(BaseModel):
    """上传加密包请求"""

    password: Optional[str] = None


@router.post("/upload-encrypted", response_model=DataPackageResponse)
async def upload_encrypted_package(
    request: Request,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
):
    """
    上传加密数据包（第一步：上传并检测加密）

    返回数据包ID和是否需要密码（密码经 multipart 表单字段传输，避免落入 URL/请求日志）
    """
    # 获取组织ID（支持超级管理员回退到第一个可用组织）
    org_id = get_org_with_fallback(
        current_user=current_user,
        requested_org_id=None,
        get_first_org_callback=lambda: _get_first_active_org(service.db),
    )

    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ORG_NOT_BOUND_ERROR
        )

    # 保存上传文件
    temp_dir = tempfile.gettempdir()
    temp_file_path = os.path.join(temp_dir, f"upload_{int(time.time())}_{file.filename}")

    try:
        with open(temp_file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 检测是否加密
        import zipfile

        is_encrypted = False
        try:
            with zipfile.ZipFile(temp_file_path, "r") as zf:
                zf.read("manifest.json")
        except (zipfile.BadZipFile, KeyError):
            is_encrypted = True

        # 创建数据包记录
        from app.models.data_package import PackageStatus

        package = service._create_package_record(
            file_path=temp_file_path,
            file_name=file.filename,
            org_id=org_id,
            created_by=current_user.id,
            status=PackageStatus.pending,
        )

        # 如果检测到加密，更新记录
        if is_encrypted:
            package.is_encrypted = True
            safe_commit(service.db)

        return DataPackageResponse(
            id=package.id,
            package_code=package.package_code,
            org_id=package.org_id,
            file_name=package.file_name,
            file_size=package.file_size,
            status=package.status,
            is_encrypted=is_encrypted,
            created_at=package.created_at,
        )

    except Exception as e:
        logger.error(f"上传加密数据包失败: {str(e)}", exc_info=True)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        # W1: 错误细节不出站, 仅日志保留内部原因
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上传加密数据包失败，请稍后重试或联系管理员",
        )


class DecryptPreviewRequest(BaseModel):
    """解密预览请求（密码经请求体传输，避免落入 URL/请求日志）"""

    password: str


@router.post("/decrypt-preview/{package_id}")
async def decrypt_and_preview_package(
    package_id: int,
    body: DecryptPreviewRequest,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
):
    """
    解密并预览数据包（第二步：提供密码解密）

    返回预览数据和冲突信息
    """
    try:
        result = await service.decrypt_and_preview_package(package_id, body.password)
        return result
    except BusinessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"解密预览失败: {str(e)}", exc_info=True)
        # W1: 错误细节不出站, 仅日志保留内部原因
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="解密预览失败，请检查密码后重试或联系管理员",
        )


class ConfirmImportRequest(BaseModel):
    """确认导入请求"""

    conflict_strategy: str = "KEEP_BOTH"


@router.post("/confirm-import/{package_id}")
async def confirm_import_with_conflict_resolution(
    request: Request,
    package_id: int,
    body: ConfirmImportRequest,
    current_user=Depends(get_current_user),
    service: DataPackageService = Depends(get_package_service),
    history_service: ImportExportHistoryService = Depends(get_history_service),
):
    """
    确认导入并处理冲突（第三步：选择冲突策略并导入）

    支持的策略：SKIP, OVERWRITE, KEEP_BOTH, MERGE
    """
    start_time = time.time()
    client_ip = get_client_ip(request)

    try:
        result = await service.confirm_import_with_conflict_resolution(package_id, body.conflict_strategy)

        # 记录历史
        duration_ms = int((time.time() - start_time) * 1000)
        history_service.create_history(
            package_id=package_id,
            operation_type="import",
            result=OperationResult.SUCCESS,
            user_id=current_user.id,
            duration_ms=duration_ms,
            client_ip=client_ip,
        )

        return result

    except Exception as e:
        logger.error(f"确认导入失败: {str(e)}", exc_info=True)
        duration_ms = int((time.time() - start_time) * 1000)
        history_service.create_history(
            package_id=package_id,
            operation_type="import",
            result=OperationResult.FAILED,
            user_id=current_user.id,
            duration_ms=duration_ms,
            client_ip=client_ip,
            error_message=str(e),
        )
        # W1: 错误细节不出站, 仅日志与操作历史保留内部原因
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="确认导入失败，请稍后重试或联系管理员",
        )


# ==================== 数据包版本管理 ====================


class PackageVersionCreate(BaseModel):
    """创建数据包版本请求体"""

    version: str
    description: Optional[str] = None


def _package_version_changes(package) -> dict:
    """根据数据包信息生成版本变更摘要（各数据类型空变更结构）"""
    data_types = package.data_types or ["villages", "projects", "funds", "schools"]
    return {dt: {"added": [], "modified": [], "deleted": []} for dt in data_types}


def _package_version_to_dict(version) -> dict:
    """将 PackageVersion 模型转为前端兼容的字典"""
    import json as _json

    changes = {}
    if version.changes:
        try:
            changes = _json.loads(version.changes)
        except (ValueError, TypeError):
            changes = {}
    return {
        "id": version.id,
        "version": version.version,
        "description": version.description or "",
        "changes": changes,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


def _get_package_or_404(db: Session, package_id: int):
    """获取数据包，不存在则 404"""
    from app.models.data_package import DataPackage

    package = db.query(DataPackage).filter(DataPackage.id == package_id).first()
    if not package:
        raise HTTPException(status_code=404, detail="数据包不存在")
    return package


def _ensure_package_org_access(permission_service, current_user, package):
    """版本管理组织访问校验：管理员直通；未授权一律 404（不泄露数据包存在性）"""
    if is_admin(current_user):
        return
    org_id = getattr(package, "org_id", None)
    if org_id and not permission_service.can_access_organization(
        getattr(current_user, "id", None), org_id
    ):
        raise HTTPException(status_code=404, detail="数据包不存在")


@router.get("/{package_id}/versions", summary="获取数据包版本列表")
async def list_package_versions(
    package_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """获取指定数据包的所有版本"""
    package = _get_package_or_404(db, package_id)
    _ensure_package_org_access(permission_service, current_user, package)

    from app.models.package_version import PackageVersion

    versions = (
        db.query(PackageVersion)
        .filter(PackageVersion.package_id == package_id)
        .order_by(PackageVersion.created_at.desc(), PackageVersion.id.desc())
        .all()
    )
    return success_response(
        data={
            "versions": [_package_version_to_dict(v) for v in versions],
            "total": len(versions),
        },
        message="获取版本列表成功",
    )


@router.post("/{package_id}/versions", summary="创建数据包版本")
async def create_package_version(
    package_id: int,
    body: PackageVersionCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """为数据包创建新版本记录"""
    package = _get_package_or_404(db, package_id)
    _ensure_package_org_access(permission_service, current_user, package)

    version_text = (body.version or "").strip()
    if not version_text:
        raise HTTPException(status_code=422, detail="版本号不能为空")

    from app.models.package_version import PackageVersion

    existing = (
        db.query(PackageVersion)
        .filter(
            PackageVersion.package_id == package_id,
            PackageVersion.version == version_text,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"版本号 {version_text} 已存在")

    import json as _json

    version = PackageVersion(
        package_id=package_id,
        version=version_text,
        description=body.description,
        changes=_json.dumps(_package_version_changes(package), ensure_ascii=False),
        created_by=current_user.id,
    )
    db.add(version)
    safe_commit(db)
    db.refresh(version)
    _safe_write_work_log(
        db, "version", version.id, f"package:{package_id}/v{version_text}",
        current_user, detail="创建数据包版本",
    )
    return success_response(data=_package_version_to_dict(version), message="版本创建成功")


@router.get("/{package_id}/versions/compare", summary="对比数据包两个版本")
async def compare_package_versions(
    package_id: int,
    version1: str = Query(..., description="第一个版本号"),
    version2: str = Query(..., description="第二个版本号"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """对比数据包两个版本的变更差异"""
    from app.models.package_version import PackageVersion

    package = _get_package_or_404(db, package_id)
    _ensure_package_org_access(permission_service, current_user, package)

    v1 = (
        db.query(PackageVersion)
        .filter(PackageVersion.package_id == package_id, PackageVersion.version == version1)
        .first()
    )
    v2 = (
        db.query(PackageVersion)
        .filter(PackageVersion.package_id == package_id, PackageVersion.version == version2)
        .first()
    )
    if not v1:
        raise HTTPException(status_code=404, detail=f"版本 {version1} 不存在")
    if not v2:
        raise HTTPException(status_code=404, detail=f"版本 {version2} 不存在")

    def _load_changes(version) -> dict:
        import json as _json

        if not version.changes:
            return {}
        try:
            return _json.loads(version.changes)
        except (ValueError, TypeError):
            return {}

    c1 = _load_changes(v1)
    c2 = _load_changes(v2)

    added_in_v2: dict = {}
    removed_in_v2: dict = {}
    modified: dict = {}
    for dtype in sorted(set(list(c1.keys()) + list(c2.keys()))):
        a = c1.get(dtype, {}) or {}
        b = c2.get(dtype, {}) or {}
        a_added = set(a.get("added", []) or [])
        b_added = set(b.get("added", []) or [])
        added_in_v2[dtype] = sorted(b_added - a_added, key=str)
        removed_in_v2[dtype] = sorted(a_added - b_added, key=str)
        modified[dtype] = sorted(set(b.get("modified", []) or []), key=str)

    return success_response(
        data={
            "version1": {"version": v1.version},
            "version2": {"version": v2.version},
            "comparison": {
                "differences": {
                    "added_in_v2": added_in_v2,
                    "modified": modified,
                    "removed_in_v2": removed_in_v2,
                }
            },
        },
        message="版本对比完成",
    )


@router.get("/{package_id}/versions/{version_id}", summary="获取数据包版本详情")
async def get_package_version(
    package_id: int,
    version_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """获取指定版本的详细信息"""
    from app.models.package_version import PackageVersion

    _ensure_package_org_access(permission_service, current_user, _get_package_or_404(db, package_id))

    version = (
        db.query(PackageVersion)
        .filter(
            PackageVersion.id == version_id,
            PackageVersion.package_id == package_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response(data=_package_version_to_dict(version), message="获取版本详情成功")


@router.delete("/{package_id}/versions/{version_id}", summary="删除数据包版本")
async def delete_package_version(
    package_id: int,
    version_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    permission_service: OrganizationPermissionService = Depends(get_permission_service),
):
    """删除指定版本记录"""
    from app.models.package_version import PackageVersion

    package = _get_package_or_404(db, package_id)
    _ensure_package_org_access(permission_service, current_user, package)

    version = (
        db.query(PackageVersion)
        .filter(
            PackageVersion.id == version_id,
            PackageVersion.package_id == package_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    db.delete(version)
    safe_commit(db)
    _safe_write_work_log(
        db, "version", version_id, f"package:{package_id}/v{version.version}",
        current_user, detail="删除数据包版本",
    )
    return success_response(message="删除成功")
