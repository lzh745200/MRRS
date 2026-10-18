"""影像库 API（W22 · 契约 §1.4 / §2 ``/media/photos``）

- 归档列表 / 注册 / 更新 / 软删；
- 多期对比查询（同 ``spot_key``）与对比图合成（PNG，≤3 张横排、≥4 张 2 列网格）；
- 数据域：列表 / 对比 / 合图走 ``get_org_scope``（``filter_by_org_ids``），
  点查写操作走 ``require_data_permission``（越权 403 / 不存在 404）；
- 归档文件只允许读取上传目录内文件（``media_service.resolve_upload_file`` 防穿越）。
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.data_permission import OrgScopeFilter, get_org_scope
from app.core.database import get_db
from app.core.response import ok_list, success_response
from app.core.security import get_current_user
from app.schemas.media import (
    CompareImageRequest,
    PhotoArchiveCreate,
    PhotoArchiveUpdate,
)
from app.services import media_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["影像库"])

# 对比图下载文件名（GET/POST 两个入口统一）
COMPARE_IMAGE_FILENAME = "compare.png"


def _compare_image_response(png: bytes) -> Response:
    """对比图统一响应：image/png + 附件名（前端 responseType=blob 可直接下载）"""
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{COMPARE_IMAGE_FILENAME}"'},
    )


@router.get("/photos", summary="影像归档列表")
async def list_photos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    village_id: Optional[int] = Query(None, description="按帮扶村筛选"),
    school_id: Optional[int] = Query(None, description="按帮扶学校筛选"),
    project_id: Optional[int] = Query(None, description="按帮扶项目筛选"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    date_from: Optional[date] = Query(None, description="拍摄日期起（含）"),
    date_to: Optional[date] = Query(None, description="拍摄日期止（含）"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """影像归档列表（数据域 + 软删过滤 + 筛选 + 分页）"""
    items, total = media_service.list_photos(
        db,
        data_scope,
        page=page,
        page_size=page_size,
        village_id=village_id,
        school_id=school_id,
        project_id=project_id,
        tag=tag,
        date_from=date_from,
        date_to=date_to,
    )
    rows = media_service.build_photo_payloads(db, items)
    return ok_list(items=rows, total=total, page=page, page_size=page_size)


@router.post("/photos", summary="注册影像归档")
async def create_photo(
    payload: PhotoArchiveCreate,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """注册影像归档：后端读取上传文件 EXIF 补全拍摄时间/GPS 并尽力匹配帮扶村"""
    photo = media_service.create_photo_archive(db, payload, current_user, data_scope)
    return success_response(
        data=media_service.build_photo_payloads(db, [photo])[0], message="归档成功"
    )


@router.get("/photos/compare", summary="同拍摄点多期对比列表")
async def compare_photos(
    spot_key: str = Query(..., description="拍摄点标识（默认由 GPS 量化生成）"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """同一拍摄点的多期影像（按拍摄时间升序）"""
    return success_response(data=media_service.compare_photos(db, data_scope, spot_key), message="成功")


@router.post("/photos/compare-image", summary="生成多期对比图（PNG）")
async def compose_compare_image(
    payload: CompareImageRequest,
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """按传入顺序合成对比图 PNG（≤3 张横排；≥4 张 2 列网格，每张标注日期）"""
    png = media_service.compose_compare_image(db, data_scope, payload.ids)
    return _compare_image_response(png)


@router.get("/photos/compare-image", summary="下载多期对比图（PNG）")
async def download_compare_image(
    ids: str = Query(..., description="逗号分隔的影像 ID，如 1,2,3"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """GET 版本便于浏览器直接下载（逻辑与 POST 版一致）"""
    photo_ids: list[int] = []
    for raw in ids.split(","):
        chunk = raw.strip()
        if not chunk:
            continue
        try:
            photo_ids.append(int(chunk))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="ids 参数必须为逗号分隔的整数") from exc
    png = media_service.compose_compare_image(db, data_scope, photo_ids)
    return _compare_image_response(png)


@router.put("/photos/{photo_id}", summary="更新影像归档")
async def update_photo(
    photo_id: int,
    payload: PhotoArchiveUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """部分更新影像归档（越权 403 / 不存在 404）"""
    photo = media_service.update_photo(db, photo_id, payload, current_user)
    return success_response(
        data=media_service.build_photo_payloads(db, [photo])[0], message="更新成功"
    )


@router.delete("/photos/{photo_id}", summary="删除影像归档（软删）")
async def delete_photo(
    photo_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """软删除影像归档（is_active=False，可回收）"""
    photo = media_service.delete_photo(db, photo_id, current_user)
    return success_response(data={"id": photo.id}, message="删除成功")
