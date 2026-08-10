"""
地图可视化API
提供帮扶村和学校的地图标注数据，以及离线地图瓦片服务
"""

import hashlib
import logging
import math
import os
import random
import sys
from pathlib import Path
from typing import Optional

from app.utils.helpers import safe_json_loads

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.response import ok_list
from ...core.security import get_current_user
from ...models.school import School
from ...models.supported_village import SupportedVillage
from app.core.unified_data_scope import OrgScopeFilter, get_org_scope
from app.core.transaction import safe_commit
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/map", tags=["地图可视化"])

# ==================== diskcache 缓存 ====================
try:
    import diskcache as _dc

    from app.core.config import settings as _settings

    _map_cache_dir = _settings.CACHE_DIR
    os.makedirs(_map_cache_dir, exist_ok=True)
    _map_cache = _dc.Cache(
        os.path.join(_map_cache_dir, "map"),
        size_limit=10 * 1024 * 1024,  # 10MB
    )
except ImportError:  # pragma: no cover
    _map_cache = None
    logger.warning("diskcache 未安装，地图距离缓存已禁用")
except Exception as e:
    _map_cache = None
    logger.warning("diskcache 初始化失败: %s，使用内存缓存", e)
    # 删除损坏的缓存文件
    import shutil
    _bad_dir = os.path.join(_settings.CACHE_DIR, "map")
    try:
        shutil.rmtree(_bad_dir, ignore_errors=True)
    except Exception as e:
        logger.warning("清理损坏的地图缓存目录失败: %s", e)

_DISTANCES_TTL = 600  # 10 分钟


def invalidate_map_cache() -> None:
    """公开函数：清除地图模块缓存（供 admin.py 调用）"""
    if _map_cache is not None:
        _map_cache.clear()


# --------------- 离线瓦片目录 ---------------


def _resolve_tiles_dir() -> Path:
    """解析瓦片存储目录，兼容 PyInstaller / 开发模式"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "resources" / "map-tiles"
        if p.exists():
            return p
    env_path = os.environ.get("MAP_TILES_DIR")
    if env_path:
        return Path(env_path)
    # 开发模式：项目根目录/resources/map-tiles
    return Path(__file__).resolve().parent.parent.parent.parent / "resources" / "map-tiles"


TILES_DIR = _resolve_tiles_dir()

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
            "map_type": "gaode",
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

    return result


@router.get("/county-coords")
async def get_county_coordinates():
    """获取铴南州12县市坐标（前端地图选点参考用）"""
    return {
        "center": {"lng": QIANNAN_CENTER[0], "lat": QIANNAN_CENTER[1]},
        "counties": {
            name: {"lng": coords[0], "lat": coords[1]}
            for name, coords in QIANNAN_COUNTY_COORDS.items()
            if "县" in name or "市" in name  # 只返回全称
        },
    }


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
        record = db.query(SupportedVillage).filter(SupportedVillage.id == marker_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="帮扶村不存在")
        record.latitude = coords.latitude
        record.longitude = coords.longitude
    elif marker_type == "school":
        record = db.query(School).filter(School.id == marker_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="学校不存在")
        record.latitude = coords.latitude
        record.longitude = coords.longitude
    else:
        raise HTTPException(status_code=400, detail="marker_type 必须为 'village' 或 'school'")

    safe_commit(db)
    try:
        write_work_log(db, "map", "update_coordinates", marker_id, f"更新{marker_type}坐标",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))
    except Exception:
        logger.debug("记录工作日志失败")
    if _map_cache is not None:
        try:
            _map_cache.clear()
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
    if _map_cache is not None:
        try:
            cached = _map_cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            logger.debug("读取地图距离缓存失败")

    result = {
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

    if _map_cache is not None:
        try:
            _map_cache.set(cache_key, result, expire=_DISTANCES_TTL)
        except Exception:
            logger.debug("写入地图距离缓存失败")

    return result


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


@router.get("/tile-info")
async def get_tile_info():
    """获取离线瓦片信息：是否可用、缩放级别范围、瓦片数量"""
    if not TILES_DIR.exists():
        return {
            "available": False,
            "tileCount": 0,
            "zoomLevels": [],
            "dir": str(TILES_DIR),
        }

    zoom_levels = sorted(int(d.name) for d in TILES_DIR.iterdir() if d.is_dir() and d.name.isdigit())
    if not zoom_levels:
        return {
            "available": False,
            "tileCount": 0,
            "zoomLevels": [],
            "dir": str(TILES_DIR),
        }

    # 统计 .png 文件数量
    tile_count = sum(1 for _ in TILES_DIR.rglob("*.png"))
    return {
        "available": tile_count > 0,
        "tileCount": tile_count,
        "zoomLevels": zoom_levels,
        "minZoom": zoom_levels[0],
        "maxZoom": zoom_levels[-1],
        "dir": str(TILES_DIR),
    }


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
