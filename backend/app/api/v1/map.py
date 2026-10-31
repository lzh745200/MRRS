"""
地图可视化API
提供帮扶村和学校的地图标注数据，以及离线地图瓦片服务
"""

import asyncio
import hashlib
import logging
import math
import os
import random
import sys
import threading
from pathlib import Path
from typing import Any, Optional, Sequence, TypeGuard

from app.core.config import settings as _settings
from app.utils.helpers import safe_json_loads

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.response import ok_list
from ...core.security import get_current_user, require_admin
from ...models.school import School
from ...models.supported_village import SupportedVillage
from app.core.data_permission import OrgScopeFilter, get_org_scope
from app.core.transaction import safe_commit
from app.services.offline_map_service import (
    MAX_TILE_UPLOAD_BYTES,
    TilePackageError,
    import_tile_directory,
    import_tile_zip_bytes,
    read_manifest_file,
    scan_tiles_dir,
)
from app.services.work_log_service import write_work_log
from app.core.response import success_response
from app.utils.audit_logger import AuditAction, AuditLogger
from app.utils.upload_helper import read_upload_with_limit

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/map", tags=["地图可视化"])

# ==================== diskcache 缓存（惰性初始化，P2-4 启动优化） ====================
# diskcache.Cache(...) 构造会在磁盘上创建缓存目录并建立索引（实测中位 ~130ms），
# 属于应用冷启动（import app.main）路径上的可推迟开销。此处仅保留廉价的模块级
# import；真正的 Cache 构造推迟到首次使用（见 _get_map_cache），避免拖慢冷启动。
try:
    import diskcache as _dc
except ImportError:  # pragma: no cover - 可选依赖缺失（功能降级为无缓存）
    _dc = None

# 惰性单例哨兵：_UNSET 表示"尚未初始化"；None 表示"不可用/已禁用"。
_UNSET = object()
# 三种状态：哨兵（未初始化）/ None（不可用）/ diskcache.Cache 实例。
_map_cache: Any = _UNSET
_map_cache_lock = threading.Lock()

_DISTANCES_TTL = 600  # 10 分钟


def _build_map_cache():
    """构造地图 diskcache 缓存实例（仅由 _get_map_cache 首次调用时执行）。

    Returns:
        diskcache.Cache | None: 缓存实例；diskcache 不可用或初始化失败时为 None。
    """
    if _dc is None:
        logger.warning("diskcache 未安装，地图距离缓存已禁用")
        return None
    try:
        cache_dir = _settings.CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        return _dc.Cache(
            os.path.join(cache_dir, "map"),
            size_limit=10 * 1024 * 1024,  # 10MB
            # JSON 序列化替代 pickle（CVE-2025-69872 / PYSEC-2026-2447，上游无修复版本）：
            # 缓存内容为纯 JSON 结构（距离/时长的 dict/list/float），换 JSONDisk 无行为差异。
            disk=_dc.JSONDisk,
        )
    except Exception as e:
        logger.warning("diskcache 初始化失败: %s，使用内存缓存", e)
        # 删除损坏的缓存文件
        import shutil
        bad_dir = os.path.join(_settings.CACHE_DIR, "map")
        try:
            shutil.rmtree(bad_dir, ignore_errors=True)
        except Exception as e:
            logger.warning("清理损坏的地图缓存目录失败: %s", e)
        return None


def _get_map_cache():
    """惰性获取地图缓存单例（线程安全，首次调用时才构造）。

    - 若外部已把 ``_map_cache`` 设为 mock / None（测试用），直接沿用，不触发构造；
    - 仅当仍为 ``_UNSET`` 哨兵时才真正构造缓存。

    Returns:
        diskcache.Cache | None: 缓存实例；diskcache 不可用时为 None。
    """
    global _map_cache
    if _map_cache is _UNSET:
        with _map_cache_lock:
            if _map_cache is _UNSET:
                _map_cache = _build_map_cache()
    return None if _map_cache is _UNSET else _map_cache


def _clear_map_cache_if_ready() -> None:
    """仅当缓存已初始化（非哨兵、非 None）时清空；不触发惰性构造。"""
    cache = _map_cache
    if cache is not _UNSET and cache is not None:
        cache.clear()


def invalidate_map_cache() -> None:
    """公开函数：清除地图模块缓存（供 admin.py 调用）"""
    _clear_map_cache_if_ready()


# --------------- 离线瓦片目录 ---------------

# 贵州全省 bbox（minLon, minLat, maxLon, maxLat）：
# 前端用它把瓦片视图限制在"有覆盖"的范围内，避免视野越界后大量 404 被误判为
# "瓦片加载失败"而整体回退矢量视图（2026-10-25 现场问题根因）。
PROVINCE_BBOX = [103.6, 24.6, 109.6, 29.2]

# 瓦片目录解析来源（诊断用）：env / meipass / dev
_TILES_DIR_SOURCE = "dev"


def _resolve_tiles_dir() -> Path:
    """解析瓦片存储目录，兼容 PyInstaller / Electron / 开发模式。

    优先级（F 区约定，与打包接线严格一致）：

    1. ``MAP_TILES_DIR`` 环境变量 —— Electron 主进程注入（安装包内即
       ``<resources>/map-tiles``，也允许运维指向可写的自定义瓦片仓，
       导入升级写入的就是该目录）；
    2. PyInstaller 冻结态 ``sys._MEIPASS/resources/map-tiles``
       （``assistance-backend.spec`` 的 datas 目标目录）；
    3. 开发/源码态仓库根 ``resources/map-tiles``（与根 package.json 的
       extraResources 源目录同一份）。

    注意：环境变量即使指向尚不存在的目录也直接采信 —— 运维首次导入瓦片
    时由导入端点创建目录，不能因为"目录还没建"就悄悄回退到别处。

    同时记录 ``_TILES_DIR_SOURCE`` 供 ``/map/tile-info`` 诊断（现场排查
    "装了包但瓦片目录没生效"时，能直接看到走的是 env 还是打包内置）。
    """
    global _TILES_DIR_SOURCE
    env_path = os.environ.get("MAP_TILES_DIR")
    if env_path:
        _TILES_DIR_SOURCE = "env"
        return Path(env_path)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "resources" / "map-tiles"
        if p.exists():
            _TILES_DIR_SOURCE = "meipass"
            return p
    # 开发模式：仓库根目录/resources/map-tiles（源码树为 backend/app/api/v1/map.py）
    _TILES_DIR_SOURCE = "dev"
    return Path(__file__).resolve().parents[4] / "resources" / "map-tiles"


TILES_DIR = _resolve_tiles_dir()


def _valid_bbox(value: object) -> TypeGuard[Sequence[float]]:
    """bbox 必须是「4 个有限数值」的序列。

    只校验长度是不够的：["x", 1, 2, 3] 这类非法值会被当作 Leaflet bounds 传给
    前端，地图初始化拿到含字符串的角点后表现为不显示 / 异常缩放。
    bool 是 int 子类，需显式排除（true / false 不能当坐标）。
    """
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    for item in value:
        if isinstance(item, bool):
            return False
        if not isinstance(item, (int, float)):
            return False
        if item != item:  # NaN
            return False
        if item in (float("inf"), float("-inf")):
            return False
    return True


def _manifest_bbox(manifest) -> Optional[list]:
    """从 MANIFEST 取覆盖 bbox：region.bbox 优先，其次顶层 bbox。"""
    if not isinstance(manifest, dict):
        return None
    region = manifest.get("region")
    if isinstance(region, dict):
        bbox = region.get("bbox")
        if _valid_bbox(bbox):
            return list(bbox)
    bbox = manifest.get("bbox")
    if _valid_bbox(bbox):
        return list(bbox)
    return None


# 黔南州12县市中心坐标
QIANNAN_COUNTY_COORDS = {
    "都匀市": (107.5187, 26.2594),
    "福泉市": (107.5133, 26.6868),
    "荔波县": (107.8860, 25.4220),
    "贵定县": (107.2326, 26.5573),
    "瓮安县": (107.4716, 27.0785),
    "独山县": (107.5451, 25.8224),
    "平塘县": (107.3224, 25.8313),
    "罗甸县": (106.7518, 25.4271),
    "长顺县": (106.4472, 26.0227),
    "龙里县": (106.9793, 26.4530),
    "惠水县": (106.6571, 26.1341),
    "三都水族自治县": (107.8696, 25.9835),
    "丹寨县": (107.8887, 26.1989),
    # 简称兼容
    "都匀": (107.5187, 26.2594),
    "福泉": (107.5133, 26.6868),
    "荔波": (107.8860, 25.4220),
    "贵定": (107.2326, 26.5573),
    "瓮安": (107.4716, 27.0785),
    "独山": (107.5451, 25.8224),
    "平塘": (107.3224, 25.8313),
    "罗甸": (106.7518, 25.4271),
    "长顺": (106.4472, 26.0227),
    "龙里": (106.9793, 26.4530),
    "惠水": (106.6571, 26.1341),
    "三都": (107.8696, 25.9835),
    "丹寨": (107.8887, 26.1989),
}

# 黔南州中心坐标（默认回退）
QIANNAN_CENTER = (107.5, 26.3)


def _get_coords(lat, lng, county_or_district, record_id=None, name=""):
    """获取坐标：优先使用已有坐标，否则根据县市名自动分配

    匹配优先级：精确匹配 > 包含匹配
    使用确定性偏移（基于 record_id + name 的 hash）确保位置稳定可重现

    Returns:
        tuple: (lng, lat, is_estimated)
        is_estimated=True 表示坐标是根据县市估算的，非数据库中存储的真实坐标
    """
    if lat is not None and lng is not None:
        return (lng, lat, False)

    MAX_OFFSET = 0.008  # ±0.9km，不会跨越县界

    # 确定性随机种子：相同记录始终得到相同偏移
    raw = hashlib.md5(f"{record_id}:{name}:{county_or_district}".encode(), usedforsecurity=False)
    seed = int(raw.hexdigest()[:8], 16)
    rng = random.Random(seed)

    if county_or_district:
        matched_coords = None
        if county_or_district in QIANNAN_COUNTY_COORDS:
            matched_coords = QIANNAN_COUNTY_COORDS[county_or_district]
        else:
            for key, coords in QIANNAN_COUNTY_COORDS.items():
                if key in county_or_district or county_or_district in key:
                    matched_coords = coords
                    break
        if matched_coords:
            offset_lng = rng.uniform(-MAX_OFFSET, MAX_OFFSET)
            offset_lat = rng.uniform(-MAX_OFFSET, MAX_OFFSET)
            return (matched_coords[0] + offset_lng, matched_coords[1] + offset_lat, True)

    logger.warning("无法匹配县市坐标: county_or_district=%s", county_or_district)
    offset_lng = rng.uniform(-0.05, 0.05)
    offset_lat = rng.uniform(-0.05, 0.05)
    return (QIANNAN_CENTER[0] + offset_lng, QIANNAN_CENTER[1] + offset_lat, True)


@router.get("/config")
async def get_map_config(
    current_user=Depends(get_current_user),
):
    """
    获取地图配置
    """
    return {
        "success": True,
        "data": {
            "center": {"lng": QIANNAN_CENTER[0], "lat": QIANNAN_CENTER[1]},
            "zoom": 9,
            # 前端实际渲染的是 ECharts 离线矢量地图（components/map/OfflineMap.vue），
            # 从无高德在线底图；对外声明 vector 才与离线事实一致（审计 A 区 A8 关联）。
            "map_type": "vector",
            "offline_enabled": True,
            "tiles_url": "/api/v1/map/tiles",
        },
    }


@router.get("/markers")
async def get_map_markers(
    marker_type: Optional[str] = Query(default="all", description="标注类型: all, villages, schools"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """获取地图标注数据（根据用户权限过滤）"""
    result = {}

    if marker_type in ("all", "villages"):
        v_query = db.query(SupportedVillage).filter(
            SupportedVillage.is_active == True  # noqa: E712 — 过滤软删除
        )
        v_query = data_scope.filter_by_org_ids(
            v_query,
            SupportedVillage.organization_id,
            created_by_column=SupportedVillage.created_by,
        )
        villages = v_query.all()
        village_list = []
        for v in villages:
            coords = _get_coords(v.latitude, v.longitude, v.county, v.id, v.village_name)
            village_list.append(
                {
                    "id": v.id,
                    "name": v.village_name,
                    "lng": coords[0],
                    "lat": coords[1],
                    "isEstimated": coords[2],
                    "county": v.county,
                    "department": v.department,
                    "supportUnit": v.support_unit,
                    "regionScope": v.region_scope,
                    "isThreeRegions": v.is_three_regions,
                    "isKeyCounty": v.is_key_county,
                    "isBorderArea": v.is_border_area,
                    "isProvincialDemo": v.is_provincial_demo,
                    "isHundredVillageDemo": v.is_hundred_village_demo,
                    "isRevitalizationTier": v.is_revitalization_tier,
                }
            )
        result["villages"] = village_list

    if marker_type in ("all", "schools"):
        s_query = db.query(School).filter(School.is_active == True)  # noqa: E712
        s_query = data_scope.filter_by_org_ids(s_query, School.organization_id, created_by_column=School.created_by)
        schools = s_query.all()
        school_list = []
        for s in schools:
            coords = _get_coords(s.latitude, s.longitude, s.district, s.id, s.name)
            school_list.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "lng": coords[0],
                    "lat": coords[1],
                    "isEstimated": coords[2],
                    "district": s.district,
                    "type": s.type.value if s.type else None,
                    "supportStatus": (s.support_status.value if s.support_status else None),
                    "supportUnit": s.support_unit,
                    "studentCount": s.student_count,
                    "teacherCount": s.teacher_count,
                }
            )
        result["schools"] = school_list

    return success_response(data=result)


@router.get("/county-coords")
async def get_county_coordinates():
    """获取铴南州12县市坐标（前端地图选点参考用）"""
    return success_response(data={
        "center": {"lng": QIANNAN_CENTER[0], "lat": QIANNAN_CENTER[1]},
        "counties": {
            name: {"lng": coords[0], "lat": coords[1]}
            for name, coords in QIANNAN_COUNTY_COORDS.items()
            if "县" in name or "市" in name  # 只返回全称
        },
    })


@router.get("/regions")
async def get_regions(
    level: Optional[str] = Query(None, description="层级: province/prefecture/county"),
    parent_code: Optional[str] = Query(None, description="上级区划编码"),
    db: Session = Depends(get_db),
):
    """获取行政区划数据（含 GeoJSON geometry），用于地图边界渲染和多级下钻"""
    from app.models.region import Region

    query = db.query(Region)
    if level:
        query = query.filter(Region.level == level)
    if parent_code:
        query = query.filter(Region.parent_code == parent_code)
    regions = query.all()

    items_list = [
        {
            "code": r.code,
            "name": r.name,
            "level": r.level,
            "parentCode": r.parent_code,
            "centerLng": r.center_lng,
            "centerLat": r.center_lat,
            "geometry": safe_json_loads(r.geometry_text, default=None),
        }
        for r in regions
    ]
    return ok_list(items=items_list, total=len(items_list))


# --------------- 距离与车程计算 ---------------

# 区域中心坐标（都匀市）
MILITARY_BASE = (107.518871, 26.259379)


def _haversine(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """计算两点之间的 Haversine 直线距离 (km)"""
    R = 6371.0  # 地球半径 km
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# 山区路况修正参数
ROAD_FACTOR = 1.4  # 山区弯道系数（直线距离 × 系数 ≈ 公路距离）
AVG_SPEED_KMH = 45.0  # 黔南山区平均行驶时速


def _estimate_travel(straight_km: float):
    """根据直线距离估算山区公路距离和车程"""
    road_km = straight_km * ROAD_FACTOR
    travel_hours = road_km / AVG_SPEED_KMH
    if travel_hours >= 1:
        display = f"{int(travel_hours)}h{int((travel_hours % 1) * 60)}min"
    else:
        display = f"{int(travel_hours * 60)}min"
    return round(road_km, 1), round(travel_hours, 2), display


class CoordinateUpdate(BaseModel):
    """坐标更新请求体"""

    latitude: float
    longitude: float


@router.put("/markers/{marker_type}/{marker_id}/coordinates")
async def update_marker_coordinates(
    marker_type: str,
    marker_id: int,
    coords: CoordinateUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """管理员手动设置帮扶村/学校坐标

    Args:
        marker_type: 'village' 或 'school'
        marker_id: 记录 ID
        coords: 经纬度
    """
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可编辑坐标")

    if not (-90 <= coords.latitude <= 90 and -180 <= coords.longitude <= 180):
        raise HTTPException(status_code=400, detail="经纬度超出合法范围")

    if marker_type == "village":
        village = db.query(SupportedVillage).filter(SupportedVillage.id == marker_id).first()
        if not village:
            raise HTTPException(status_code=404, detail="帮扶村不存在")
        village.latitude = coords.latitude
        village.longitude = coords.longitude
    elif marker_type == "school":
        school = db.query(School).filter(School.id == marker_id).first()
        if not school:
            raise HTTPException(status_code=404, detail="学校不存在")
        school.latitude = coords.latitude
        school.longitude = coords.longitude
    else:
        raise HTTPException(status_code=400, detail="marker_type 必须为 'village' 或 'school'")

    safe_commit(db)
    try:
        write_work_log(db, "map", "update_coordinates", marker_id, f"更新{marker_type}坐标",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败")
    try:
        _clear_map_cache_if_ready()
    except Exception:
        logger.debug("地图缓存失效失败")
    return {
        "success": True,
        "message": "坐标已更新",
        "latitude": coords.latitude,
        "longitude": coords.longitude,
    }


@router.get("/distances")
async def get_distances(
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """计算区域中心到每个帮扶点的距离和预估车程

    以区域中心坐标(107.518871, 26.259379)为起点
    山区公路修正系数: 1.4, 平均时速: 45km/h
    """
    user_id = getattr(current_user, "id", 0)
    cache_key = f"map_distances:{user_id}"
    # 惰性获取缓存：首次访问 /distances 时才构造 diskcache，避免拖慢应用冷启动
    map_cache = _get_map_cache()
    if map_cache is not None:
        try:
            cached = map_cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            logger.debug("读取地图距离缓存失败")

    result: dict[str, Any] = {
        "base": {"lng": MILITARY_BASE[0], "lat": MILITARY_BASE[1], "name": "区域中心"},
        "villages": [],
        "schools": [],
        "county_distances": [],
    }

    # 批量查询帮扶村，避免 N+1
    v_query = db.query(SupportedVillage).filter(
        SupportedVillage.is_active == True  # noqa: E712 — 过滤软删除
    )
    v_query = data_scope.filter_by_org_ids(
        v_query,
        SupportedVillage.organization_id,
        created_by_column=SupportedVillage.created_by,
    )
    villages = v_query.all()

    for v in villages:
        lng, lat, _estimated = _get_coords(v.latitude, v.longitude, v.county)
        straight_km = _haversine(MILITARY_BASE[0], MILITARY_BASE[1], lng, lat)
        road_km, travel_hours, travel_display = _estimate_travel(straight_km)
        result["villages"].append(
            {
                "id": v.id,
                "name": v.village_name,
                "lng": lng,
                "lat": lat,
                "county": v.county,
                "distance_km": round(straight_km, 1),
                "road_distance_km": road_km,
                "travel_hours": travel_hours,
                "travel_display": travel_display,
            }
        )

    # 批量查询学校，避免 N+1
    s_query = db.query(School).filter(School.is_active == True)  # noqa: E712
    s_query = data_scope.filter_by_org_ids(s_query, School.organization_id, created_by_column=School.created_by)
    schools = s_query.all()

    for s in schools:
        lng, lat, _estimated = _get_coords(s.latitude, s.longitude, s.district, s.id, s.name)
        straight_km = _haversine(MILITARY_BASE[0], MILITARY_BASE[1], lng, lat)
        road_km, travel_hours, travel_display = _estimate_travel(straight_km)
        result["schools"].append(
            {
                "id": s.id,
                "name": s.name,
                "lng": lng,
                "lat": lat,
                "district": s.district,
                "distance_km": round(straight_km, 1),
                "road_distance_km": road_km,
                "travel_hours": travel_hours,
                "travel_display": travel_display,
            }
        )

    # 按距离排序
    result["villages"].sort(key=lambda x: x["distance_km"])
    result["schools"].sort(key=lambda x: x["distance_km"])

    # 到各县距离汇总
    for county_name, (clng, clat) in QIANNAN_COUNTY_COORDS.items():
        if "县" not in county_name and "市" not in county_name:
            continue  # 跳过简称
        straight_km = _haversine(MILITARY_BASE[0], MILITARY_BASE[1], clng, clat)
        road_km, travel_hours, travel_display = _estimate_travel(straight_km)
        result["county_distances"].append(
            {
                "county": county_name,
                "lng": clng,
                "lat": clat,
                "distance_km": round(straight_km, 1),
                "road_distance_km": road_km,
                "travel_hours": travel_hours,
                "travel_display": travel_display,
            }
        )
    result["county_distances"].sort(key=lambda x: x["distance_km"])

    if map_cache is not None:
        try:
            map_cache.set(cache_key, result, expire=_DISTANCES_TTL)
        except Exception:
            logger.debug("写入地图距离缓存失败")

    return success_response(data=result)


# --------------- 离线瓦片服务 ---------------


@router.get("/search")
async def search_map_markers(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词（村名/学校名/区县）"),
    marker_type: Optional[str] = Query(default="all", description="搜索类型: all, villages, schools"),
    current_user=Depends(get_current_user),
    data_scope: OrgScopeFilter = Depends(get_org_scope),
    db: Session = Depends(get_db),
):
    """
    离线地图搜索：按关键词搜索帮扶村和学校

    支持模糊搜索村名、学校名、区县等字段。
    返回匹配的标注列表（含坐标），前端可直接在地图上定位。
    """
    keyword = f"%{q}%"
    results: dict = {"villages": [], "schools": [], "total": 0}

    # 搜索帮扶村
    if marker_type in ("all", "villages"):
        v_query = db.query(SupportedVillage).filter(
            SupportedVillage.is_active == True,  # noqa: E712
            SupportedVillage.village_name.ilike(keyword)
            | SupportedVillage.county.ilike(keyword)
            | SupportedVillage.department.ilike(keyword)
            | SupportedVillage.support_unit.ilike(keyword),
        )
        v_query = data_scope.filter_by_org_ids(
            v_query,
            SupportedVillage.organization_id,
            created_by_column=SupportedVillage.created_by,
        )
        villages = v_query.limit(50).all()
        for v in villages:
            coords = _get_coords(v.latitude, v.longitude, v.county, v.id, v.village_name)
            results["villages"].append({
                "id": v.id,
                "name": v.village_name,
                "lng": coords[0],
                "lat": coords[1],
                "type": "village",
                "county": v.county,
                "department": v.department,
                "supportUnit": v.support_unit,
            })

    # 搜索学校
    if marker_type in ("all", "schools"):
        s_query = db.query(School).filter(
            School.is_active == True,  # noqa: E712
            School.name.ilike(keyword)
            | School.district.ilike(keyword)
            | School.support_unit.ilike(keyword),
        )
        s_query = data_scope.filter_by_org_ids(s_query, School.organization_id, created_by_column=School.created_by)
        schools = s_query.limit(50).all()
        for s in schools:
            coords = _get_coords(s.latitude, s.longitude, s.district, s.id, s.name)
            results["schools"].append({
                "id": s.id,
                "name": s.name,
                "lng": coords[0],
                "lat": coords[1],
                "type": "school",
                "district": s.district,
                "supportUnit": s.support_unit,
            })

    results["total"] = len(results["villages"]) + len(results["schools"])
    return results


def _tiles_dir_public_name() -> str:
    """瓦片目录的公开名（仅最后一级目录名）。

    安全口径：瓦片端点保持匿名可访问（Leaflet ``<img>`` 直接请求，无法携带
    JWT），因此响应里**不得**回显完整磁盘路径 —— 只暴露 ``map-tiles`` 这类
    目录名；需要完整路径的运维操作使用 ``POST /map/tiles/import`` 的响应
    （管理员端点）。
    """
    return TILES_DIR.name or "map-tiles"


@router.get("/tile-info")
async def get_tile_info():
    """获取离线瓦片信息：是否可用、缩放级别、瓦片数量、体积、覆盖 bbox 与 MANIFEST 元数据。

    诊断字段（2026-10-25 现场排障新增，均为只读、只增不删）：
    - ``source``：瓦片目录来源 ``env`` / ``meipass`` / ``dev``；
    - ``reason``：不可用原因 ``dir_missing`` / ``no_tiles``，可用时为 ``None``；
    - ``bbox``：瓦片覆盖范围 ``[minLon, minLat, maxLon, maxLat]``，优先级为
      **扫描实测 bounds → MANIFEST 的 ``region.bbox`` / ``bbox`` → 贵州全省兜底**。
      前端据此把视图限制在有覆盖的范围内，避免边缘 404 被误判为"瓦片加载失败"。

      为什么实测优先（P0，2026-10-25）：多包叠加导入时 MANIFEST 只是**最后导入的那个
      包**。若先导贵阳、再导遵义，MANIFEST.region.bbox 只剩遵义，前端 ``maxBounds``
      会把贵阳瓦片挡在视野外（数据在库却看不到）。实测 bounds 来自磁盘上真实存在的
      瓦片集合，天然等于"多包并集"，与 MANIFEST 无关。
    """
    dir_name = _tiles_dir_public_name()
    source = _TILES_DIR_SOURCE
    if not TILES_DIR.exists():
        return success_response(data={
            "available": False,
            "tileCount": 0,
            "zoomLevels": [],
            "totalBytes": 0,
            "dir": dir_name,
            "manifest": None,
            "source": source,
            "reason": "dir_missing",
            "bbox": list(PROVINCE_BBOX),
        })

    # 7 万张瓦片的目录扫描在本机实测 ~8.6s：必须走线程池，否则会阻塞事件循环，
    # 同一时刻的瓦片图片请求/其它 API 全部排队（现场表现为"地图转圈卡住"）。
    stats = await asyncio.to_thread(scan_tiles_dir, TILES_DIR)
    zoom_levels = stats["zoom_levels"]
    tile_count = stats["total_tiles"]
    manifest = read_manifest_file(TILES_DIR / "MANIFEST.json")
    data = {
        "available": tile_count > 0,
        "tileCount": tile_count,
        "zoomLevels": zoom_levels,
        "totalBytes": stats["total_bytes"],
        "dir": dir_name,
        # MANIFEST.json 缺失/损坏 → None（不影响瓦片服务本身）
        "manifest": manifest,
        "source": source,
        "reason": None if tile_count > 0 else "no_tiles",
        # 实测 bounds（多包并集）优先；取不到时才用 MANIFEST 元数据；
        # 都没有则回退贵州全省 bbox。
        "bbox": stats.get("bounds") or _manifest_bbox(manifest) or list(PROVINCE_BBOX),
    }
    if zoom_levels:
        data["minZoom"] = zoom_levels[0]
        data["maxZoom"] = zoom_levels[-1]
    return success_response(data=data)


@router.post("/tiles/import")
async def import_tiles(
    file: UploadFile = File(default=None, description="瓦片包 ZIP（含 MANIFEST.json 与 z/x/y.png）"),
    source_dir: str = Form(default=None, description="本机瓦片目录路径（U 盘导入，与 file 二选一）"),
    current_user=Depends(require_admin()),
):
    """导入离线瓦片包（管理员）。

    两条导入路径（二选一）：

    - ``file``：multipart 上传 ZIP 瓦片包（适合 ≤512MB 的常规包）；
    - ``source_dir``：服务端本机目录（适合 U 盘上的大包，免上传）。

    两条路径共用同一套校验：MANIFEST 合法性、tileCount/totalBytes/缩放范围
    与实际文件一致性、可选 SHA256、瓦片数与总体积上限、zip-slip 与符号链接
    防护。导入为**合并**写入（既有瓦片保留，同名覆盖），可用于瓦片升级。
    """
    if file is None and not source_dir:
        raise HTTPException(status_code=400, detail="请上传瓦片包 ZIP（file）或指定本机瓦片目录（source_dir）")
    if file is not None and source_dir:
        raise HTTPException(status_code=400, detail="file 与 source_dir 只能二选一")

    dest = TILES_DIR
    origin = "upload" if file is not None else "local-directory"
    try:
        if file is not None:
            content = await read_upload_with_limit(
                file, MAX_TILE_UPLOAD_BYTES, limit_label="瓦片包"
            )
            result = import_tile_zip_bytes(content, dest)
        else:
            result = import_tile_directory(Path(source_dir), dest)
    except TilePackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except OSError as exc:
        logger.error("瓦片包写入失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="瓦片包写入失败，请检查瓦片目录写入权限或磁盘空间")
    except Exception as exc:  # 兜底：解析类异常一律 400，不把堆栈透给调用方
        logger.error("瓦片包处理失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail="瓦片包解析失败，请确认文件完整且格式正确")

    stats = await asyncio.to_thread(scan_tiles_dir, dest)
    try:
        AuditLogger.log(
            action=AuditAction.IMPORT,
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", None),
            resource_type="map_tiles",
            details={
                "origin": origin,
                "tileCount": result["tileCount"],
                "totalBytes": result["totalBytes"],
                "overwritten": result["overwritten"],
                "zoomLevels": result["zoomLevels"],
                "ignored": result["ignored"],
                "provider": result["manifest"].get("provider"),
            },
        )
    except Exception:  # 审计失败不得回滚已完成的导入
        logger.warning("瓦片导入审计日志写入失败", exc_info=True)

    return success_response(
        message="瓦片包导入完成",
        data={
            "tileCount": result["tileCount"],
            "totalBytes": result["totalBytes"],
            "overwritten": result["overwritten"],
            "zoomLevels": result["zoomLevels"],
            "ignored": result["ignored"],
            "source": origin,
            "dir": str(dest),
            "manifest": result["manifest"],
            "store": {
                "tileCount": stats["total_tiles"],
                "totalBytes": stats["total_bytes"],
                "zoomLevels": stats["zoom_levels"],
            },
        },
    )


@router.get("/tiles/{z}/{x}/{y}.png")
async def serve_tile(z: int, x: int, y: int):
    """提供离线瓦片文件

    URL 格式与标准 OSM 瓦片一致: /tiles/{z}/{x}/{y}.png
    Leaflet TileLayer 可直接使用。
    """
    tile_path = TILES_DIR / str(z) / str(x) / f"{y}.png"

    # 安全检查：确保解析后的路径仍在 TILES_DIR 下
    try:
        resolved = tile_path.resolve()
        if not str(resolved).startswith(str(TILES_DIR.resolve())):
            raise HTTPException(status_code=400, detail="Invalid tile coordinates")
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid tile coordinates")

    if not tile_path.is_file():
        raise HTTPException(status_code=404, detail="Tile not found")

    return FileResponse(
        str(tile_path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
