"""影像库服务层（W22 · 契约 §1.4 / §2）

职责：
- 从上传目录内的图片解析 EXIF（拍摄时间 / GPS，Pillow）；
- GPS 就近匹配帮扶村（Haversine ≤ 5km，取最近且需在数据域内）；
- ``spot_key`` 默认取 GPS 量化串（保留 4 位小数）；
- 列表筛选 / 软删 / 多期对比查询；
- 对比图合成（Pillow：≤3 张横排，≥4 张 2 列网格，每张下方标注拍摄日期）。

**路径安全**：只允许 ``/uploads/...`` 且禁止 ``..`` 段，解析一律落在
``paths.get_runtime_uploads_path()`` 上传根目录内，杜绝任意路径读取。
"""

import io
import logging
import math
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.data_permission import OrgScopeFilter, require_data_permission
from app.core.transaction import safe_commit
from app.models.media import PhotoArchive
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.schemas.media import PhotoArchiveOut
from app.services.work_log_service import write_work_log
from app.utils.paths import get_runtime_uploads_path
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)

# 地球平均半径（km）
EARTH_RADIUS_KM = 6371.0088
# GPS 就近匹配村的半径（契约 §2：≤5km）
GPS_MATCH_RADIUS_KM = 5.0
# 通用上传 URL 前缀（复用 /files/upload）
UPLOAD_URL_PREFIX = "/uploads/"
# 对比图最大张数（2 列网格，6 行以内）
MAX_COMPARE_IMAGES = 9
# 对比图单元格图片高度 / 日期标注条高度（像素）
COMPARE_CELL_HEIGHT = 360
COMPARE_LABEL_HEIGHT = 40

_EXIF_TAG_DATETIME_ORIGINAL = 36867
_EXIF_TAG_DATETIME = 306
_EXIF_TAG_GPS_INFO = 34853
_EXIF_DATETIME_FORMATS = ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S")


# ==================== EXIF 解析 ====================


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两点球面距离（km）"""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _gps_ref(value: Any) -> str:
    """EXIF GPS 半球引用（N/S/E/W）归一化为大写字符串"""
    if isinstance(value, bytes):
        text = value.decode("ascii", errors="ignore")
    else:
        text = str(value or "")
    return text.strip().upper()


def _decimal_degrees(values: Any, ref: Any) -> Optional[float]:
    """EXIF GPS 度/分/秒三分量 → 十进制度；非法值返回 None"""
    if not values:
        return None
    try:
        degrees = [float(part) for part in values[:3]]
    except (TypeError, ValueError):
        return None
    if len(degrees) < 3:
        return None
    decimal = degrees[0] + degrees[1] / 60.0 + degrees[2] / 3600.0
    if _gps_ref(ref) in ("S", "W"):
        decimal = -decimal
    return decimal


def _parse_exif_datetime(raw: Any) -> Optional[datetime]:
    """解析 EXIF 时间字符串（``YYYY:MM:DD HH:MM:SS`` / ``YYYY-MM-DD HH:MM:SS``）"""
    if not raw:
        return None
    text = raw.decode("ascii", errors="ignore") if isinstance(raw, bytes) else str(raw)
    for fmt in _EXIF_DATETIME_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_exif(image_bytes: Optional[bytes]) -> dict:
    """解析图片 EXIF，返回 ``{taken_at, gps_lat, gps_lng, shot_source}``

    无 EXIF / 非法图片 / 非法 GPS 时对应字段为 None，``shot_source='manual'``。
    """
    meta: dict[str, Any] = {
        "taken_at": None,
        "gps_lat": None,
        "gps_lng": None,
        "shot_source": "manual",
    }
    if not image_bytes:
        return meta
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            exif = image.getexif()
    except (OSError, UnidentifiedImageError, ValueError):
        return meta

    meta["taken_at"] = _parse_exif_datetime(
        exif.get(_EXIF_TAG_DATETIME_ORIGINAL) or exif.get(_EXIF_TAG_DATETIME)
    )
    gps_info = exif.get_ifd(_EXIF_TAG_GPS_INFO) or {}
    latitude = _decimal_degrees(gps_info.get(2), gps_info.get(1))
    longitude = _decimal_degrees(gps_info.get(4), gps_info.get(3))
    if latitude is not None and -90 <= latitude <= 90:
        meta["gps_lat"] = round(latitude, 6)
    if longitude is not None and -180 <= longitude <= 180:
        meta["gps_lng"] = round(longitude, 6)
    if meta["taken_at"] is not None or meta["gps_lat"] is not None or meta["gps_lng"] is not None:
        meta["shot_source"] = "exif"
    return meta


# ==================== 上传目录 / 路径安全 ====================


def resolve_upload_file(file_url: str) -> Path:
    """把 ``/uploads/...`` URL 解析为上传根目录内的物理路径（防路径穿越）

    Raises:
        HTTPException 400: 非 ``/uploads/`` 地址 / 含空段或 ``..`` 穿越段
    """
    if not isinstance(file_url, str) or not file_url.startswith(UPLOAD_URL_PREFIX):
        raise HTTPException(status_code=400, detail="非法的文件地址（仅支持 /uploads/ 下的文件）")
    relative = unquote(file_url[len(UPLOAD_URL_PREFIX):]).replace("\\", "/")
    segments = [segment for segment in relative.split("/") if segment not in ("", ".")]
    if not segments or any(segment == ".." for segment in segments):
        raise HTTPException(status_code=400, detail="非法的文件地址（禁止路径穿越）")
    return get_runtime_uploads_path().resolve().joinpath(*segments).resolve()


def read_upload_bytes(file_url: str) -> Optional[bytes]:
    """读取上传目录内文件字节；文件不存在/不可读返回 None（路径非法仍抛 400）"""
    path = resolve_upload_file(file_url)
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        logger.warning("读取上传文件失败: %s", path, exc_info=True)
        return None


def load_image(file_url: str) -> Image.Image:
    """读取并解码上传目录内的图片为 RGB（404 文件缺失 / 400 非图片）"""
    content = read_upload_bytes(file_url)
    if content is None:
        raise HTTPException(status_code=404, detail="图片文件不存在")
    try:
        image = Image.open(io.BytesIO(content))
        return image.convert("RGB")
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="图片文件无法解析") from exc


# ==================== GPS → 帮扶村匹配 ====================


def match_village_by_gps(
    db: Session,
    data_scope: OrgScopeFilter,
    gps_lat: Optional[float],
    gps_lng: Optional[float],
) -> Optional[int]:
    """GPS 就近匹配帮扶村（≤5km 取最近；无坐标/无命中返回 None；受数据域约束）"""
    if gps_lat is None or gps_lng is None:
        return None
    query = db.query(SupportedVillage).filter(
        SupportedVillage.is_active.is_(True),
        SupportedVillage.latitude.isnot(None),
        SupportedVillage.longitude.isnot(None),
    )
    query = data_scope.filter_by_org_ids(
        query,
        SupportedVillage.organization_id,
        created_by_column=SupportedVillage.created_by,
    )
    best_id: Optional[int] = None
    best_km: Optional[float] = None
    for village in query.all():
        distance = haversine_km(gps_lat, gps_lng, float(village.latitude), float(village.longitude))
        if distance <= GPS_MATCH_RADIUS_KM and (best_km is None or distance < best_km):
            best_id = village.id
            best_km = distance
    return best_id


def _default_spot_key(gps_lat: Optional[float], gps_lng: Optional[float]) -> Optional[str]:
    """默认拍摄点标识：GPS 量化串（保留 4 位小数）"""
    if gps_lat is None or gps_lng is None:
        return None
    return f"{gps_lat:.4f},{gps_lng:.4f}"


# ==================== 归档写入 / 读取 ====================


def _write_log(db: Session, action: str, photo: PhotoArchive, current_user: Any) -> None:
    """写操作日志（失败不阻断主流程由 write_work_log 内部行为保证）"""
    write_work_log(
        db,
        "media",
        action,
        photo.id,
        photo.file_name or photo.file_url,
        user_id=getattr(current_user, "id", None),
        username=getattr(current_user, "username", "系统"),
    )


def create_photo_archive(
    db: Session,
    payload: Any,
    current_user: Any,
    data_scope: OrgScopeFilter,
) -> PhotoArchive:
    """注册影像归档：补 EXIF 时间/GPS、GPS 匹配村、生成 spot_key、落库"""
    content = read_upload_bytes(payload.file_url)
    exif = parse_exif(content)
    gps_lat = payload.gps_lat if payload.gps_lat is not None else exif["gps_lat"]
    gps_lng = payload.gps_lng if payload.gps_lng is not None else exif["gps_lng"]
    taken_at = payload.taken_at if payload.taken_at is not None else exif["taken_at"]
    shot_source = payload.shot_source or exif["shot_source"]
    village_id = payload.village_id
    if village_id is None:
        village_id = match_village_by_gps(db, data_scope, gps_lat, gps_lng)
    spot_key = payload.spot_key or _default_spot_key(gps_lat, gps_lng)

    photo = PhotoArchive(
        file_url=payload.file_url,
        file_name=payload.file_name,
        file_size=payload.file_size,
        mime_type=payload.mime_type,
        village_id=village_id,
        school_id=payload.school_id,
        project_id=payload.project_id,
        tag=payload.tag,
        spot_key=spot_key,
        taken_at=taken_at,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        uploader_id=getattr(current_user, "id", None),
        shot_source=shot_source,
        organization_id=getattr(current_user, "organization_id", None),
        created_by=getattr(current_user, "id", None),
    )
    db.add(photo)
    safe_commit(db)
    db.refresh(photo)
    _write_log(db, "create", photo, current_user)
    return photo


def _base_query(db: Session, data_scope: OrgScopeFilter):
    """软删过滤 + 数据域过滤的查询基座"""
    query = db.query(PhotoArchive).filter(PhotoArchive.is_active.is_(True))
    return data_scope.filter_by_org_ids(
        query,
        PhotoArchive.organization_id,
        created_by_column=PhotoArchive.created_by,
    )


def _resolve_names(db: Session, model: Any, name_column: Any, ids: set[int]) -> dict[int, str]:
    """批量解析关联对象名称（村/校/项目），软删对象不返回名称"""
    if not ids:
        return {}
    rows = (
        db.query(model.id, name_column)
        .filter(model.id.in_(ids), model.is_active.is_(True))
        .all()
    )
    return {row[0]: row[1] for row in rows}


def build_photo_payloads(db: Session, photos: list[PhotoArchive]) -> list[dict]:
    """ORM 归档列表 → 响应 dict 列表（附 village_name / school_name / project_name）"""
    payloads = [
        PhotoArchiveOut.model_validate(photo).model_dump(mode="json") for photo in photos
    ]
    village_ids = {photo.village_id for photo in photos if photo.village_id is not None}
    school_ids = {photo.school_id for photo in photos if photo.school_id is not None}
    project_ids = {photo.project_id for photo in photos if photo.project_id is not None}
    village_names = _resolve_names(db, SupportedVillage, SupportedVillage.village_name, village_ids)
    school_names = _resolve_names(db, School, School.name, school_ids)
    project_names = _resolve_names(db, Project, Project.name, project_ids)
    for payload in payloads:
        payload["village_name"] = village_names.get(payload["village_id"])
        payload["school_name"] = school_names.get(payload["school_id"])
        payload["project_name"] = project_names.get(payload["project_id"])
    return payloads


def get_photo(db: Session, photo_id: int, current_user: Any) -> PhotoArchive:
    """按 ID 取未软删归档；不存在 404，越权 403"""
    photo = (
        db.query(PhotoArchive)
        .filter(PhotoArchive.id == photo_id, PhotoArchive.is_active.is_(True))
        .first()
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="影像归档不存在")
    require_data_permission(
        current_user,
        photo.organization_id,
        photo.created_by,
        error_message="无权访问该影像归档",
    )
    return photo


def list_photos(
    db: Session,
    data_scope: OrgScopeFilter,
    *,
    page: int = 1,
    page_size: int = 20,
    village_id: Optional[int] = None,
    school_id: Optional[int] = None,
    project_id: Optional[int] = None,
    tag: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> tuple[list[PhotoArchive], int]:
    """影像归档列表（软删 + 数据域 + 多条件筛选 + 分页）"""
    query = _base_query(db, data_scope)
    if village_id is not None:
        query = query.filter(PhotoArchive.village_id == village_id)
    if school_id is not None:
        query = query.filter(PhotoArchive.school_id == school_id)
    if project_id is not None:
        query = query.filter(PhotoArchive.project_id == project_id)
    if tag is not None:
        query = query.filter(PhotoArchive.tag == tag)
    if date_from is not None:
        query = query.filter(
            PhotoArchive.taken_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        query = query.filter(
            PhotoArchive.taken_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc)
        )
    total = query.count()
    items = (
        query.order_by(PhotoArchive.taken_at.desc(), PhotoArchive.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_photo(db: Session, photo_id: int, payload: Any, current_user: Any) -> PhotoArchive:
    """部分更新影像归档（仅更新显式传入字段）"""
    photo = get_photo(db, photo_id, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(photo, field, value)
    safe_commit(db)
    db.refresh(photo)
    _write_log(db, "update", photo, current_user)
    return photo


def delete_photo(db: Session, photo_id: int, current_user: Any) -> PhotoArchive:
    """软删除影像归档（is_active=False + deleted_at）"""
    photo = get_photo(db, photo_id, current_user)
    photo.is_active = False
    photo.deleted_at = utcnow()
    safe_commit(db)
    _write_log(db, "delete", photo, current_user)
    return photo


# ==================== 多期对比 ====================


def compare_photos(db: Session, data_scope: OrgScopeFilter, spot_key: Optional[str]) -> list[dict]:
    """同一拍摄点的多期照片（按拍摄时间升序；契约 §2 返回字段 id/file_url/taken_at）"""
    key = (spot_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="缺少拍摄点标识 spot_key")
    photos = (
        _base_query(db, data_scope)
        .filter(PhotoArchive.spot_key == key)
        .order_by(PhotoArchive.taken_at.asc(), PhotoArchive.id.asc())
        .all()
    )
    return [
        {"id": photo.id, "file_url": photo.file_url, "taken_at": photo.taken_at}
        for photo in photos
    ]


def _format_taken_at(value: Optional[datetime]) -> str:
    """对比图日期标注文案"""
    if value is None:
        return "未知日期"
    return value.strftime("%Y-%m-%d")


def _resize_to_height(image: Image.Image, height: int) -> Image.Image:
    """等比缩放到指定高度（宽度按原比例）"""
    width, source_height = image.size
    target_width = max(1, round(width * height / source_height))
    return image.resize((target_width, height))


def _compose_grid(cells: list[tuple[Image.Image, str]]) -> bytes:
    """把图片与日期标注合成为 PNG 网格（≤3 张横排；≥4 张 2 列多行）"""
    count = len(cells)
    columns = count if count <= 3 else 2
    rows = 1 if count <= 3 else (count + 1) // 2
    resized = [_resize_to_height(image, COMPARE_CELL_HEIGHT) for image, _label in cells]
    cell_width = max(image.width for image in resized)
    cell_height = COMPARE_CELL_HEIGHT + COMPARE_LABEL_HEIGHT
    canvas = Image.new("RGB", (cell_width * columns, cell_height * rows), "white")
    drawer = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=20)
    for index, (image, label) in enumerate(cells):
        cell = resized[index]
        row, column = divmod(index, columns)
        x = column * cell_width + (cell_width - cell.width) // 2
        y = row * cell_height
        canvas.paste(cell, (x, y))
        text_width = drawer.textlength(label, font=font)
        drawer.text(
            (column * cell_width + (cell_width - text_width) / 2, y + COMPARE_CELL_HEIGHT + 6),
            label,
            fill="black",
            font=font,
        )
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def compose_compare_image(
    db: Session,
    data_scope: OrgScopeFilter,
    photo_ids: list[int],
) -> bytes:
    """按传入顺序拼接多张影像为对比图 PNG；缺图 404、越权/不存在 404"""
    unique_ids = list(dict.fromkeys(photo_ids))
    if not unique_ids:
        raise HTTPException(status_code=400, detail="请至少选择一张图片")
    if len(unique_ids) > MAX_COMPARE_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"最多支持 {MAX_COMPARE_IMAGES} 张图片拼接",
        )
    photos = _base_query(db, data_scope).filter(PhotoArchive.id.in_(unique_ids)).all()
    by_id = {photo.id: photo for photo in photos}
    if len(by_id) != len(unique_ids):
        raise HTTPException(status_code=404, detail="部分图片不存在或无权访问")
    cells = [
        (load_image(by_id[photo_id].file_url), _format_taken_at(by_id[photo_id].taken_at))
        for photo_id in unique_ids
    ]
    return _compose_grid(cells)
