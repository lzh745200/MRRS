#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Pillow 纯 Python 把 OSM 提取图层离线渲染成 XYZ 瓦片（Web Mercator / EPSG:3857）。

v2 能力（相对 v1 的增量）
------------------------
- **multipolygon 洞**：面条目支持 ``holes``（缺省当空），洞按背景色回填；水面/湖泊
  再描 1px 岸线（``#a9c8e0``）提升水体辨识度。
- **更接近真实地图的样式**：河流 casing、湖泊描边、wetland/park/riverbank 面、
  森林描边、道路路面高光、z≥8 铁路虚线、行政边界虚线/点线（省界长虚线、地州短虚线、
  县界点线）。
- **z12**：道路阈值表补齐（含 unclassified / living_street / track；``*_link`` 按父类画）。
- **并行**：``--jobs N``（multiprocessing spawn 池，worker 各自加载 pkl 与索引）。
- **注记**：优先级排序 + 碰撞避让（city > district > county > town > village > water >
  park > 道路名），单瓦片上限 14 条；水面名 z≥10 画在面内；主干道路名 z≥10 画在线段中点
  （截断 8 字）。
- **比例尺**（右下角）+ 署名（左下角 ``© OpenStreetMap contributors``，ODbL 强制）。

输入
----
``--input`` 指向 osm 提取产物（pickle），v1/v2 均兼容::

    {"meta": {...},
     "lines": [{"cls": "motorway|trunk|primary|secondary|tertiary|residential|service|
                        unclassified|living_street|track|rail|river|stream|canal",
                "name": str, "coords": [(lon, lat), ...]}],
     "polys": [{"cls": "water|reservoir|riverbank|wetland|forest|farmland|grass|park|
                        urban|industrial",
                "name": str, "rings": [[(lon, lat), ...]],
                "holes": [[(lon, lat), ...], ...]}],       # v2 新增，v1 缺省
     "places": [{"name": str, "name_zh": str, "cls": "city|district|town|village|hamlet|suburb",
                 "lon": float, "lat": float, "population": int|null, "district": str}]}

输入坐标为 WGS-84；输出为标准 Web Mercator XYZ 瓦片（无 GCJ-02 偏移）。

行政边界
--------
``frontend/src/assets/geo/guizhou.json``（项目自带 88 个县级面，WGS-84）。省级/地州级
边界用**边对消（edge cancellation）**求并集外边界：相邻县共享的同一条边计数为 2 被抵消，
留计数为 1 的边再串成折线——几何精确、无需 shapely；县界取全部边去重后的网络。三条
边网络都带全局弧长，虚线相位按弧长计算，跨瓦片连续。绘制时在 2x 掩膜上描线再降采样，
得到抗锯齿细线。

署名
----
ODbL 强制：每张瓦片左下角绘制 ``© OpenStreetMap contributors``（9px 半透明），
MANIFEST 的 ``license`` 写 ``ODbL-1.0 (© OpenStreetMap contributors)``。

用法
----
    python scripts/tiles/render_osm_tiles.py --selftest
    python scripts/tiles/render_osm_tiles.py --dry-run
    python scripts/tiles/render_osm_tiles.py --zoom 12 --jobs 4 --skip-existing
    python scripts/tiles/render_osm_tiles.py --bbox 106.0,25.1,108.5,26.9 --zoom 9-10
    python scripts/tiles/verify_tiles.py --dir .scratch/osm/tiles --require-min 1000

退出码：0 成功；1 渲染/校验失败；2 参数或输入错误；3 缺少 Pillow。
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import pickle
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

TILE_SIZE = 256
SS = 2  # 行政边界掩膜超采样倍数（2x 描线后降采样 → 抗锯齿）
ROOT = Path(__file__).resolve().parents[2]
GEOJSON = ROOT / "frontend" / "src" / "assets" / "geo" / "guizhou.json"

DEFAULT_INPUT = ".scratch/osm/layers.pkl"
DEFAULT_OUT = ".scratch/osm/tiles-v2"
DEFAULT_PREVIEW_DIR = ".scratch/osm/preview-v2"
DEFAULT_BBOX = "103.6,24.6,109.6,29.2"
DEFAULT_ZOOM = "5-12"
DEFAULT_ATTRIBUTION = "© OpenStreetMap contributors"
LICENSE_TEXT = "ODbL-1.0 (© OpenStreetMap contributors)"
PROVIDER = "osm-render"
STYLE_NAME = "osm-vector-basemap-light-v2"
MAX_LABELS = 14
ROAD_NAME_MAX_CHARS = 8

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

# ── 面/水配色（v2：更接近真实底图，层次更明显）──
COLOR_BACKGROUND = (247, 246, 242)  # #f7f6f2
COLOR_WATER = (207, 227, 243)  # #cfe3f3
COLOR_WATER_OUTLINE = (169, 200, 224)  # #a9c8e0
COLOR_FOREST = (223, 234, 216)  # #dfead8
COLOR_FOREST_OUTLINE = (201, 220, 194)  # #c9dcc2
COLOR_FARMLAND = (242, 239, 219)  # #f2efdb
COLOR_GRASS = (232, 241, 224)  # #e8f1e0
COLOR_URBAN = (239, 234, 226)  # #efeae2
COLOR_INDUSTRIAL = (232, 230, 236)  # #e8e6ec
COLOR_WETLAND = (223, 238, 227)  # #dfeee3
COLOR_PARK = (227, 240, 220)  # #e3f0dc
COLOR_RIVER_CORE = (143, 189, 224)  # #8fbde0
COLOR_RIVER_CASING = (207, 227, 243)  # #cfe3f3
COLOR_RAIL = (184, 184, 184)
COLOR_RAIL_DARK = (107, 107, 107)  # #6b6b6b

CASING_WARM = (216, 201, 168)  # #d8c9a8
CASING_GRAY = (201, 201, 201)  # #c9c9c9
ROAD_FILL = {
    "motorway": (246, 162, 74),  # #f6a24a
    "trunk": (246, 162, 74),
    "primary": (249, 200, 90),  # #f9c85a
    "secondary": (251, 224, 138),  # #fbe08a
    "tertiary": (255, 255, 255),
    "residential": (238, 238, 238),
    "service": (242, 242, 242),
    "unclassified": (245, 245, 245),
    "living_street": (240, 240, 240),
    "track": (236, 230, 220),
}
ROAD_CASING = {
    "motorway": CASING_WARM,
    "trunk": CASING_WARM,
    "primary": CASING_WARM,
    "secondary": CASING_WARM,
    "tertiary": CASING_GRAY,
    "residential": CASING_GRAY,
    "service": CASING_GRAY,
    "unclassified": CASING_GRAY,
    "living_street": CASING_GRAY,
    "track": (222, 214, 200),
}
# 低 → 高绘制顺序：先画支路，干道压在上面
ROAD_DRAW_ORDER = (
    "track",
    "service",
    "living_street",
    "unclassified",
    "residential",
    "tertiary",
    "secondary",
    "primary",
    "trunk",
    "motorway",
)
ROAD_HIGHLIGHT_CLASSES = ("motorway", "trunk", "primary")

COLOR_BOUND_COUNTY = (185, 196, 184)  # #b9c4b8
COLOR_BOUND_PREF = (143, 163, 143)  # #8fa38f
COLOR_BOUND_PROVINCE = (95, 122, 99)  # #5f7a63

BOUND_ZOOM_COUNTY = 9
BOUND_ZOOM_PREF = 7
BOUND_ZOOM_PROVINCE = 5
# 边界线型：(宽度px, 实线段px, 间隔px)
BOUND_STYLE_COUNTY = (1.0, 1.0, 2.0)  # 点线
BOUND_STYLE_PREF = (1.5, 5.0, 3.0)  # 短虚线
BOUND_STYLE_PROVINCE = (2.5, 11.0, 5.0)  # 长虚线

LABEL_COLOR_PREF = (74, 94, 76)
LABEL_COLOR_COUNTY = (96, 112, 98)
LABEL_COLOR_PLACE = (70, 70, 70)
LABEL_COLOR_WATER = (58, 108, 148)
LABEL_COLOR_PARK = (62, 112, 68)
LABEL_COLOR_ROAD = (120, 92, 52)
LABEL_HALO = (255, 255, 255)

# 允许的输入类别（未知类别静默忽略，避免脏数据中断整批渲染）
ROAD_CLASSES = frozenset(ROAD_FILL)
LINK_SUFFIX = "_link"
LINE_CLASSES = frozenset(
    set(ROAD_CLASSES)
    | {"rail", "river", "stream", "canal"}
)
POLY_CLASSES = frozenset(
    {
        "water",
        "reservoir",
        "riverbank",
        "wetland",
        "forest",
        "farmland",
        "grass",
        "park",
        "urban",
        "industrial",
    }
)
WATER_POLY_CLASSES = frozenset({"water", "reservoir", "riverbank"})
# 填充绘制顺序（先大面积植被，再水体/湿地，最后建成区）
POLY_FILL_ORDER = (
    "forest",
    "farmland",
    "grass",
    "park",
    "wetland",
    "water",
    "reservoir",
    "riverbank",
    "urban",
    "industrial",
)
POLY_FILL_COLOR = {
    "forest": COLOR_FOREST,
    "farmland": COLOR_FARMLAND,
    "grass": COLOR_GRASS,
    "park": COLOR_PARK,
    "wetland": COLOR_WETLAND,
    "water": COLOR_WATER,
    "reservoir": COLOR_WATER,
    "riverbank": COLOR_WATER,
    "urban": COLOR_URBAN,
    "industrial": COLOR_INDUSTRIAL,
}
POLY_OUTLINE = {
    "forest": (COLOR_FOREST_OUTLINE, 10),
    "park": (COLOR_FOREST_OUTLINE, 10),
    "water": (COLOR_WATER_OUTLINE, 8),
    "reservoir": (COLOR_WATER_OUTLINE, 8),
    "riverbank": (COLOR_WATER_OUTLINE, 9),
}

ROAD_WIDTH_TABLE: Dict[str, Dict[int, int]] = {
    "motorway": {5: 2, 6: 2, 7: 3, 8: 4, 9: 5, 10: 6, 11: 8, 12: 9},
    "trunk": {5: 2, 6: 2, 7: 3, 8: 4, 9: 5, 10: 6, 11: 7, 12: 8},
    "primary": {5: 2, 6: 2, 7: 3, 8: 4, 9: 4, 10: 5, 11: 6, 12: 7},
    "secondary": {7: 2, 8: 3, 9: 4, 10: 4, 11: 5, 12: 6},
    "tertiary": {10: 3, 11: 4, 12: 4},
    "residential": {11: 3, 12: 3},
    "service": {11: 2, 12: 1},
    "unclassified": {12: 2},
    "living_street": {12: 2},
    "track": {12: 1},
}

PREFECTURE_SUFFIXES = (
    "布依族苗族自治州",
    "苗族侗族自治州",
    "土家族自治州",
    "自治州",
    "地区",
)

# 注记优先级（数值越小越优先）
LABEL_PRIORITY = {
    "city": 0,
    "district": 1,
    "suburb": 1,
    "pref": 1.5,
    "county": 2,
    "town": 3,
    "village": 4,
    "hamlet": 4,
    "water": 5,
    "park": 6,
    "road": 7,
}

try:  # 直接执行脚本时脚本目录已在 sys.path
    from _common import (  # type: ignore
        TileToolError,
        build_manifest,
        count_tiles_by_zoom,
        fail,
        human_bytes,
        iter_tiles,
        log,
        lonlat_to_tile,
        parse_bbox,
        parse_zoom,
        scan_tiles,
        setup_console,
        tile_range,
        warn,
        write_manifest,
    )
except ImportError:  # pragma: no cover — 包导入与脚本直跑二选一，另一条分支不可执行
    from ._common import (  # type: ignore
        TileToolError,
        build_manifest,
        count_tiles_by_zoom,
        fail,
        human_bytes,
        iter_tiles,
        log,
        lonlat_to_tile,
        parse_bbox,
        parse_zoom,
        scan_tiles,
        setup_console,
        tile_range,
        warn,
        write_manifest,
    )


# ==================== 投影 ====================


def project(lon: float, lat: float, z: int) -> Tuple[float, float]:
    """经纬度 → 该缩放级下的世界像素坐标（EPSG:3857 Web Mercator）。"""
    world = float(TILE_SIZE) * (2 ** z)
    x = (lon + 180.0) / 360.0 * world
    clamped = max(min(lat, 85.05112878), -85.05112878)
    y = (1.0 - math.asinh(math.tan(math.radians(clamped))) / math.pi) / 2.0 * world
    return x, y


def unproject(px: float, py: float, z: int) -> Tuple[float, float]:
    """世界像素坐标 → 经纬度（自检用）。"""
    world = float(TILE_SIZE) * (2 ** z)
    lon = px / world * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * py / world
    lat = math.degrees(math.atan(math.sinh(n)))
    return lon, lat


def tile_of(lon: float, lat: float, z: int) -> Tuple[int, int, float, float]:
    """经纬度 → (瓦片 x, 瓦片 y, 瓦片内像素 x, 瓦片内像素 y)。"""
    px, py = project(lon, lat, z)
    tx = int(px // TILE_SIZE)
    ty = int(py // TILE_SIZE)
    return tx, ty, px - tx * TILE_SIZE, py - ty * TILE_SIZE


# ==================== 几何工具 ====================


def _clean_coords(raw: Any) -> List[Tuple[float, float]]:
    """把输入坐标规整为 [(lon, lat), ...]，剔除非法点与连续重复点。"""
    out: List[Tuple[float, float]] = []
    if not isinstance(raw, (list, tuple)):
        return out
    for point in raw:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            lon = float(point[0])
            lat = float(point[1])
        except (TypeError, ValueError):
            continue
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            continue
        if out and abs(out[-1][0] - lon) < 1e-9 and abs(out[-1][1] - lat) < 1e-9:
            continue
        out.append((lon, lat))
    return out


def bbox_of(coords: Sequence[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def _boxes_intersect(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _seg_len(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    return math.hypot(q[0] - p[0], q[1] - p[1])


def _lighten(color: Tuple[int, int, int], factor: float = 0.45) -> Tuple[int, int, int]:
    return tuple(int(c + (255 - c) * factor) for c in color)  # type: ignore[return-value]


def _clip_segment(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    rect: Tuple[float, float, float, float],
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Liang-Barsky 线段裁剪；完全在矩形外返回 None。"""
    xmin, ymin, xmax, ymax = rect
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, p0[0] - xmin),
        (dx, xmax - p0[0]),
        (-dy, p0[1] - ymin),
        (dy, ymax - p0[1]),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return None
            if t > t0:
                t0 = t
        else:
            if t < t0:
                return None
            if t < t1:
                t1 = t
    if t0 > t1:
        return None
    return (
        (p0[0] + t0 * dx, p0[1] + t0 * dy),
        (p0[0] + t1 * dx, p0[1] + t1 * dy),
    )


def polyline_runs(
    points: Sequence[Tuple[float, float]], rect: Tuple[float, float, float, float]
) -> List[List[Tuple[float, float]]]:
    """把像素折线裁到矩形内，返回若干条连续子折线（用于 draw.line）。"""
    if len(points) < 2:
        return []
    xmin, ymin, xmax, ymax = rect
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if min(xs) >= xmin and max(xs) <= xmax and min(ys) >= ymin and max(ys) <= ymax:
        return [list(points)]

    runs: List[List[Tuple[float, float]]] = []
    current: List[Tuple[float, float]] = []
    for index in range(len(points) - 1):
        seg = _clip_segment(points[index], points[index + 1], rect)
        if seg is None:
            if len(current) >= 2:
                runs.append(current)
            current = []
            continue
        start, end = seg
        if not current:
            current = [start, end]
            continue
        gap = abs(current[-1][0] - start[0]) > 0.01 or abs(current[-1][1] - start[1]) > 0.01
        if gap:
            if len(current) >= 2:
                runs.append(current)
            current = [start, end]
        else:
            current.append(end)
    if len(current) >= 2:
        runs.append(current)
    return runs


def clip_ring(
    points: Sequence[Tuple[float, float]], rect: Tuple[float, float, float, float]
) -> List[Tuple[float, float]]:
    """Sutherland-Hodgman 把多边形环裁到矩形内（返回顶点列表）。"""
    xmin, ymin, xmax, ymax = rect

    def _clip(poly: List[Tuple[float, float]], inside, intersect) -> List[Tuple[float, float]]:
        if not poly:
            return []
        out: List[Tuple[float, float]] = []
        prev = poly[-1]
        prev_in = inside(prev)
        for cur in poly:
            cur_in = inside(cur)
            if cur_in:
                if not prev_in:
                    out.append(intersect(prev, cur))
                out.append(cur)
            elif prev_in:
                out.append(intersect(prev, cur))
            prev, prev_in = cur, cur_in
        return out

    def _ix_min(a, b):
        t = (xmin - a[0]) / (b[0] - a[0])
        return (xmin, a[1] + t * (b[1] - a[1]))

    def _ix_max(a, b):
        t = (xmax - a[0]) / (b[0] - a[0])
        return (xmax, a[1] + t * (b[1] - a[1]))

    def _iy_min(a, b):
        t = (ymin - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), ymin)

    def _iy_max(a, b):
        t = (ymax - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), ymax)

    poly = list(points)
    poly = _clip(poly, lambda p: p[0] >= xmin, _ix_min)
    poly = _clip(poly, lambda p: p[0] <= xmax, _ix_max)
    poly = _clip(poly, lambda p: p[1] >= ymin, _iy_min)
    poly = _clip(poly, lambda p: p[1] <= ymax, _iy_max)
    return poly


def dash_polyline_into(
    draw,
    points: Sequence[Tuple[float, float]],
    s0: float,
    dash: float,
    gap: float,
    rect: Tuple[float, float, float, float],
    fill,
    width: float,
) -> None:
    """沿像素折线画虚线/点线；``s0`` 为该折线起点的全局弧长，保证跨瓦片相位连续。"""
    if len(points) < 2 or dash <= 0:
        return
    period = dash + gap
    if period <= 0:
        return
    s = s0
    for index in range(len(points) - 1):
        p = points[index]
        q = points[index + 1]
        seg_len = _seg_len(p, q)
        if seg_len <= 1e-9:
            continue
        clipped = _clip_segment(p, q, rect)
        if clipped is None:
            s += seg_len
            continue
        a, b = clipped
        la = _seg_len(p, a)
        lb = _seg_len(p, b)
        run = lb - la
        if run <= 1e-9:
            s += seg_len
            continue
        s_a = s + la
        steps = max(1, int(run / 0.7))
        current: List[Tuple[float, float]] = []
        for k in range(steps + 1):
            frac = k / steps
            pos = la + run * frac
            along = pos / seg_len
            point = (p[0] + (q[0] - p[0]) * along, p[1] + (q[1] - p[1]) * along)
            if (s_a + run * frac) % period < dash:
                current.append(point)
            else:
                if len(current) >= 2:
                    draw.line(current, fill=fill, width=max(1, int(round(width))))
                current = []
        if len(current) >= 2:
            draw.line(current, fill=fill, width=max(1, int(round(width))))
        s += seg_len


# ==================== 空间索引 ====================


class GridIndex:
    """0.05° 网格空间索引：按 bbox 把要素挂到网格单元，避免每瓦片全量遍历。"""

    CELL = 0.05
    MAX_CELLS_PER_ITEM = 2048

    def __init__(self, boxes: Sequence[Tuple[float, float, float, float]]):
        self._grid: Dict[Tuple[int, int], List[int]] = {}
        self._large: List[int] = []
        for idx, box in enumerate(boxes):
            keys = self._keys_for(box)
            if keys is None:
                self._large.append(idx)
                continue
            for key in keys:
                self._grid.setdefault(key, []).append(idx)
        self.total = len(boxes)

    @classmethod
    def _range(cls, low: float, high: float) -> range:
        return range(int(math.floor(low / cls.CELL)), int(math.floor(high / cls.CELL)) + 1)

    def _keys_for(self, box: Tuple[float, float, float, float]) -> Optional[List[Tuple[int, int]]]:
        cols = list(self._range(box[0], box[2]))
        rows = list(self._range(box[1], box[3]))
        if len(cols) * len(rows) > self.MAX_CELLS_PER_ITEM:
            return None
        return [(col, row) for col in cols for row in rows]

    def query(self, box: Tuple[float, float, float, float]) -> Iterable[int]:
        cols = list(self._range(box[0], box[2]))
        rows = list(self._range(box[1], box[3]))
        if len(cols) * len(rows) > 4096:
            return range(self.total)
        found: set = set(self._large)
        grid = self._grid
        for col in cols:
            for row in rows:
                bucket = grid.get((col, row))
                if bucket:
                    found.update(bucket)
        return found


# ==================== 输入加载 ====================


class LineItem(object):
    __slots__ = ("cls", "name", "coords", "bbox")

    def __init__(self, cls: str, name: str, coords: List[Tuple[float, float]]):
        self.cls = cls
        self.name = name
        self.coords = coords
        self.bbox = bbox_of(coords)


class PolyItem(object):
    __slots__ = ("cls", "name", "rings", "holes", "bbox", "label_point")

    def __init__(
        self,
        cls: str,
        name: str,
        rings: List[List[Tuple[float, float]]],
        holes: Optional[List[List[Tuple[float, float]]]] = None,
    ):
        self.cls = cls
        self.name = name
        self.rings = rings
        self.holes = holes or []
        all_points = [point for ring in rings for point in ring]
        self.bbox = bbox_of(all_points)
        self.label_point = _centroid_of(all_points)


class PlaceItem(object):
    __slots__ = ("name", "cls", "lon", "lat", "population")

    def __init__(self, name: str, cls: str, lon: float, lat: float, population: Optional[int]):
        self.name = name
        self.cls = cls
        self.lon = lon
        self.lat = lat
        self.population = population


def _centroid_of(points: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    """粗糙质心（顶点均值）：只用于水面名定位，无需精确。"""
    if not points:
        return (0.0, 0.0)
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


def _normalize_line_class(raw: str) -> str:
    """归一化线类别：``motorway_link`` 等按父类画（宽 −1，最小 1px）。"""
    cls = str(raw or "").strip().lower()
    if cls.endswith(LINK_SUFFIX):
        base = cls[: -len(LINK_SUFFIX)]
        if base in ROAD_CLASSES:
            return base
    return cls


def _normalize_lines(raw_items: Any) -> Tuple[List["LineItem"], int]:
    lines: List[LineItem] = []
    skipped = 0
    for item in raw_items or []:
        if not isinstance(item, dict):
            skipped += 1
            continue
        cls = _normalize_line_class(item.get("cls"))
        if cls not in LINE_CLASSES:
            skipped += 1
            continue
        coords = _clean_coords(item.get("coords"))
        if len(coords) < 2:
            skipped += 1
            continue
        lines.append(LineItem(cls, str(item.get("name") or ""), coords))
    return lines, skipped


def _normalize_polys(raw_items: Any) -> Tuple[List["PolyItem"], int, int]:
    polys: List[PolyItem] = []
    skipped = 0
    hole_count = 0
    for item in raw_items or []:
        if not isinstance(item, dict):
            skipped += 1
            continue
        cls = str(item.get("cls") or "").strip().lower()
        if cls not in POLY_CLASSES:
            skipped += 1
            continue
        rings: List[List[Tuple[float, float]]] = []
        rings_raw = item.get("rings")
        if isinstance(rings_raw, (list, tuple)):
            for ring_raw in rings_raw:
                ring = _clean_coords(ring_raw)
                if len(ring) >= 3:
                    rings.append(ring)
        if not rings:
            skipped += 1
            continue
        holes: List[List[Tuple[float, float]]] = []
        holes_raw = item.get("holes")
        if isinstance(holes_raw, (list, tuple)):
            for hole_raw in holes_raw:
                hole = _clean_coords(hole_raw)
                if len(hole) >= 3:
                    holes.append(hole)
        hole_count += len(holes)
        polys.append(PolyItem(cls, str(item.get("name") or ""), rings, holes))
    return polys, skipped, hole_count


def _normalize_places(raw_items: Any) -> List["PlaceItem"]:
    places: List[PlaceItem] = []
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        try:
            lon = float(item.get("lon"))
            lat = float(item.get("lat"))
        except (TypeError, ValueError):
            continue
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            continue
        name = str(item.get("name_zh") or item.get("name") or "").strip()
        if not name:
            continue
        cls = str(item.get("cls") or "").strip().lower()
        population = item.get("population")
        if not isinstance(population, int):
            population = None
        places.append(PlaceItem(name, cls, lon, lat, population))
    return places


def load_layers(path: Path) -> Dict[str, Any]:
    """读取并规范化 layers.pkl；v1（无 holes）与 v2 均兼容。"""
    if not path.is_file():
        raise TileToolError(f"找不到输入文件: {path}")
    try:
        raw = pickle.loads(path.read_bytes())
    except Exception as exc:  # noqa: BLE001 - pickle 损坏/半写入统一转中文错误
        raise TileToolError(f"读取 {path} 失败（pickle 解析错误）: {exc}") from exc
    if not isinstance(raw, dict):
        raise TileToolError(f"{path} 结构非法：顶层应为 dict")

    lines, skipped_lines = _normalize_lines(raw.get("lines"))
    polys, skipped_polys, hole_count = _normalize_polys(raw.get("polys"))
    places = _normalize_places(raw.get("places"))
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    return {
        "meta": meta,
        "lines": lines,
        "polys": polys,
        "places": places,
        "skipped_lines": skipped_lines,
        "skipped_polys": skipped_polys,
        "hole_count": hole_count,
    }


def wait_for_input(path: Path, timeout: float, interval: float = 5.0) -> bool:
    """轮询等待输入文件出现且大小稳定（原子替换写入完成后才使用）。"""
    if timeout <= 0:
        return path.is_file()
    deadline = time.time() + timeout
    last_size = -1
    log(f"等待输入就绪（最多 {int(timeout)} 秒）: {path}")
    while time.time() < deadline:
        if path.is_file():
            size = path.stat().st_size
            if size > 0 and size == last_size:
                return True
            last_size = size
        time.sleep(interval)
    return path.is_file()


# ==================== 行政边界（边对消并集） ====================


def _iter_geometry_polys(geom: Any) -> Iterable[List[List[List[float]]]]:
    if not isinstance(geom, dict):
        return
    kind = geom.get("type")
    coords = geom.get("coordinates")
    if kind == "Polygon" and isinstance(coords, list):
        yield coords
    elif kind == "MultiPolygon" and isinstance(coords, list):
        for poly in coords:
            if isinstance(poly, list):
                yield poly


def _quantized_edges(rings: Sequence[Sequence[Tuple[float, float]]]) -> Dict[Tuple[Any, Any], int]:
    """统计无向边出现次数（量化到 1e-6°，相邻面共享边因此可比对）。"""
    counts: Dict[Tuple[Any, Any], int] = {}
    for ring in rings:
        pts = [(round(p[0], 6), round(p[1], 6)) for p in ring]
        if len(pts) >= 2 and pts[0] == pts[-1]:
            pts = pts[:-1]
        total = len(pts)
        for i in range(total):
            a = pts[i]
            b = pts[(i + 1) % total]
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _edge_adjacency(
    edge_counts: Dict[Tuple[Any, Any], int], keep_odd: bool
) -> Dict[Any, List[Any]]:
    """构建无向邻接表；``keep_odd=True`` 时丢弃偶数次（内部共享）的边。"""
    adjacency: Dict[Any, List[Any]] = {}
    for (a, b), count in edge_counts.items():
        if keep_odd and count % 2 == 0:
            continue
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
    return adjacency


def _walk_edge_path(adjacency: Dict[Any, List[Any]], used: set, start, first=None) -> List[Tuple[float, float]]:
    """沿未使用的边从 ``start`` 走出一条折线（到端点/闭环为止）。"""
    path = [start]
    prev = None
    cur = start
    nxt = first
    while True:
        if nxt is None:
            nxt = None
            for cand in adjacency.get(cur, ()):
                if cand == prev:
                    continue
                key = (cur, cand) if cur < cand else (cand, cur)
                if key not in used:
                    nxt = cand
                    break
            if nxt is None:
                break
        key = (cur, nxt) if cur < nxt else (nxt, cur)
        if key in used:
            break
        used.add(key)
        path.append(nxt)
        prev, cur, nxt = cur, nxt, None
        if cur == start:
            break
    return path


def _chain_edges(edge_counts: Dict[Tuple[Any, Any], int], keep_odd: bool) -> List[List[Tuple[float, float]]]:
    """把边串成折线。``keep_odd=True`` 只保留计数为奇数的边（并集外边界）。"""
    adjacency = _edge_adjacency(edge_counts, keep_odd)
    if not adjacency:
        return []
    used: set = set()
    paths: List[List[Tuple[float, float]]] = []
    # 先处理奇点（度数非 2 的顶点，如三县交界），再处理剩余闭环
    for vertex, neighbours in adjacency.items():
        if len(neighbours) % 2 == 1:
            for neighbour in neighbours:
                key = (vertex, neighbour) if vertex < neighbour else (neighbour, vertex)
                if key in used:
                    continue
                path = _walk_edge_path(adjacency, used, vertex, neighbour)
                if len(path) >= 2:
                    paths.append(path)
    for vertex, neighbours in adjacency.items():
        for neighbour in neighbours:
            key = (vertex, neighbour) if vertex < neighbour else (neighbour, vertex)
            if key in used:
                continue
            path = _walk_edge_path(adjacency, used, vertex, neighbour)
            if len(path) >= 2:
                paths.append(path)
    return paths


class BoundaryPath(object):
    """一条边界折线 + 分块索引（含全局累计弧长，供跨瓦片连续虚线使用）。"""

    __slots__ = ("pts", "chunks", "bbox")

    CHUNK = 16

    def __init__(self, pts: List[Tuple[float, float]]):
        self.pts = pts
        self.bbox = bbox_of(pts)
        self.chunks: List[Tuple[int, int, Tuple[float, float, float, float], float]] = []
        cum = 0.0
        index = 0
        total = len(pts)
        while index < total - 1:
            end = min(index + self.CHUNK, total - 1)
            segment = pts[index : end + 1]
            self.chunks.append((index, end, bbox_of(segment), cum))
            for k in range(index, end):
                cum += _seg_len(pts[k], pts[k + 1])
            index = end


def build_admin_boundaries(
    all_rings: Sequence[Sequence[Tuple[float, float]]],
    pref_rings: Dict[str, List[List[Tuple[float, float]]]],
) -> Dict[str, Any]:
    """用边对消生成省/地州/县三级边界折线网络。"""
    all_counts = _quantized_edges(all_rings)
    province_pts = _chain_edges(all_counts, keep_odd=True)
    county_pts = _chain_edges(all_counts, keep_odd=False)
    pref_outer: List[Dict[str, Any]] = []
    for pref, rings in pref_rings.items():
        if not pref:
            continue
        pts = _chain_edges(_quantized_edges(rings), keep_odd=True)
        if pts:
            pref_outer.append({"pref": pref, "paths": [BoundaryPath(p) for p in pts]})
    return {
        "province": [BoundaryPath(p) for p in province_pts],
        "county": [BoundaryPath(p) for p in county_pts],
        "pref": pref_outer,
    }


def load_admin_geo(path: Path) -> Dict[str, Any]:
    """读取县级 GeoJSON：注记锚点 + 三级边界折线网络。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    features = data.get("features") or []
    counties: List[Dict[str, Any]] = []
    pref_rings: Dict[str, List[List[Tuple[float, float]]]] = {}
    pref_points: Dict[str, List[Tuple[float, float]]] = {}
    all_rings: List[List[Tuple[float, float]]] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        name = str(props.get("name") or "").strip()
        geometry = feature.get("geometry")
        if not name or not geometry:
            continue
        rings: List[List[Tuple[float, float]]] = []
        for poly in _iter_geometry_polys(geometry):
            for ring_raw in poly:
                pts = _clean_coords(ring_raw)
                if len(pts) >= 3:
                    rings.append(pts)
        if not rings:
            continue
        pref = str(props.get("prefecture") or "").strip()
        label = props.get("centroid") or props.get("center")
        try:
            label_lon = float(label[0])
            label_lat = float(label[1])
        except (TypeError, ValueError, IndexError):
            label_lon, label_lat = rings[0][0]
        counties.append({"name": name, "pref": pref, "label": (label_lon, label_lat)})
        pref_rings.setdefault(pref, []).extend(rings)
        pref_points.setdefault(pref, []).append((label_lon, label_lat))
        all_rings.extend(rings)

    pref_labels: List[Tuple[str, float, float]] = []
    for pref, points in pref_points.items():
        if not pref:
            continue
        lon = sum(p[0] for p in points) / len(points)
        lat = sum(p[1] for p in points) / len(points)
        pref_labels.append((short_pref_name(pref), lon, lat))

    boundaries = build_admin_boundaries(all_rings, pref_rings)
    return {
        "counties": counties,
        "pref_labels": pref_labels,
        "province": boundaries["province"],
        "county": boundaries["county"],
        "pref": boundaries["pref"],
    }


def short_pref_name(name: str) -> str:
    for suffix in PREFECTURE_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


# ==================== 字体 ====================


class FontBook:
    """按字号缓存字体；找不到中文字体时只警告一次并跳过中文注记。"""

    def __init__(self) -> None:
        self._path: Optional[str] = None
        self._cache: Dict[int, Any] = {}
        self._warned = False
        self.available = False
        for candidate in FONT_CANDIDATES:
            if os.path.exists(candidate):
                self._path = candidate
                self.available = True
                break

    def get(self, size: int):
        if not self.available:
            if not self._warned:
                warn("未找到中文字体（msyh/simhei/Noto CJK），本次跳过中文注记")
                self._warned = True
            return None
        font = self._cache.get(size)
        if font is None:
            from PIL import ImageFont

            try:
                font = ImageFont.truetype(str(self._path), size)
            except OSError:
                self.available = False
                if not self._warned:
                    warn(f"中文字体加载失败: {self._path}，跳过中文注记")
                    self._warned = True
                return None
            self._cache[size] = font
        return font


# ==================== 渲染器 ====================


class LabelCandidate(object):
    __slots__ = ("priority", "importance", "text", "x", "y", "size", "color")

    def __init__(self, priority: float, importance: float, text: str,
                 x: float, y: float, size: int, color):
        self.priority = priority
        self.importance = importance
        self.text = text
        self.x = x
        self.y = y
        self.size = size
        self.color = color


class Renderer:
    def __init__(self, layers: Dict[str, Any], admin: Optional[Dict[str, Any]], attribution: str):
        self.lines: List[LineItem] = layers["lines"]
        self.polys: List[PolyItem] = layers["polys"]
        self.places: List[PlaceItem] = layers["places"]
        self.admin = admin
        self.attribution = attribution
        self.fonts = FontBook()
        self.line_index = GridIndex([item.bbox for item in self.lines]) if self.lines else None
        self.poly_index = GridIndex([item.bbox for item in self.polys]) if self.polys else None
        self._decimated: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
        self._decimated_zoom: Optional[int] = None

    # ---------- 样式 ----------

    @staticmethod
    def road_width(cls: str, z: int) -> int:
        table = ROAD_WIDTH_TABLE.get(cls)
        if not table:
            return 0
        if z in table:
            return table[z]
        levels = sorted(table)
        if z < levels[0]:
            return 0
        return min(24, table[levels[-1]] + (z - levels[-1]))

    @staticmethod
    def rail_width(z: int) -> int:
        if z < 6:
            return 0
        return 1 if z < 10 else 2

    @staticmethod
    def river_width(z: int) -> int:
        if z < 8:
            return 1
        return 2 if z < 10 else 3

    def _line_width(self, cls: str, z: int) -> int:
        if cls in ("river", "stream", "canal"):
            return self.river_width(z)
        if cls == "rail":
            return self.rail_width(z)
        return self.road_width(cls, z)

    # ---------- 几何预处理 ----------

    def _decimate(self, index: int, coords: List[Tuple[float, float]], z: int) -> List[Tuple[float, float]]:
        """按当前缩放级像素精度抽稀折线（缓存），避免低缩放级别投影海量点。"""
        key = (z, index)
        cached = self._decimated.get(key)
        if cached is not None:
            return cached
        world = float(TILE_SIZE) * (2 ** z)
        min_deg = 2.0 * 360.0 / world  # ≈2px
        out: List[Tuple[float, float]] = []
        last_lon = last_lat = None
        for lon, lat in coords:
            if last_lon is None or abs(lon - last_lon) >= min_deg or abs(lat - last_lat) >= min_deg:
                out.append((lon, lat))
                last_lon, last_lat = lon, lat
        if len(out) < 2:
            out = coords[:2]
        elif out[-1] != coords[-1]:
            out.append(coords[-1])
        self._decimated[key] = out
        return out

    # ---------- 单瓦片渲染 ----------

    def render_tile(self, z: int, tx: int, ty: int):
        from PIL import Image, ImageDraw

        # 抽稀缓存只保留当前缩放级：全量 OSM 下跨多级缓存会占用数 GB 内存
        if self._decimated_zoom != z:
            self._decimated.clear()
            self._decimated_zoom = z

        img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), COLOR_BACKGROUND)
        draw = ImageDraw.Draw(img)

        origin_x = tx * TILE_SIZE
        origin_y = ty * TILE_SIZE
        margin = 6
        rect = (float(-margin), float(-margin), float(TILE_SIZE + margin), float(TILE_SIZE + margin))

        world = float(TILE_SIZE) * (2 ** z)
        scale = world / 360.0
        half_world = world / 2.0
        asinh = math.asinh
        tan = math.tan
        radians = math.radians
        pi = math.pi
        clamp = 85.05112878

        def to_px(lon: float, lat: float) -> Tuple[float, float]:
            clamped = lat if -clamp < lat < clamp else (clamp if lat > 0 else -clamp)
            wx = (lon + 180.0) * scale - origin_x
            wy = half_world - world * asinh(tan(radians(clamped))) / (2.0 * pi) - origin_y
            return wx, wy

        lon_min, lat_max = unproject(origin_x - margin, origin_y - margin, z)
        lon_max, lat_min = unproject(origin_x + TILE_SIZE + margin, origin_y + TILE_SIZE + margin, z)
        query_box = (lon_min, lat_min, lon_max, lat_max)

        self._draw_polys(draw, to_px, z, query_box, rect)
        line_data = self._collect_line_runs(to_px, z, query_box, rect)
        self._paint_lines(draw, z, line_data)
        self._draw_admin(img, to_px, z, query_box, rect)
        self._draw_labels(draw, to_px, z, query_box, rect, line_data["road_names"])
        self._draw_scalebar(img, z, ty)
        if self.attribution:
            self._draw_attribution(img, draw)
        return img

    # ---------- 面填充（含 holes） ----------

    def _draw_polys(self, draw, to_px, z: int, query_box, rect) -> None:
        if self.poly_index is None:
            return
        buckets: Dict[str, List[int]] = {}
        for idx in self.poly_index.query(query_box):
            item = self.polys[idx]
            if not _boxes_intersect(item.bbox, query_box):
                continue
            bucket = buckets.get(item.cls)
            if bucket is None:
                bucket = []
                buckets[item.cls] = bucket
            bucket.append(idx)
        for cls in POLY_FILL_ORDER:
            indexes = buckets.get(cls)
            if not indexes:
                continue
            color = POLY_FILL_COLOR[cls]
            outline = POLY_OUTLINE.get(cls)
            for idx in indexes:
                self._draw_poly_item(draw, to_px, z, self.polys[idx], color, outline, rect)

    def _draw_poly_item(self, draw, to_px, z: int, item: "PolyItem", color, outline, rect) -> None:
        """填充单个面：外环填色 → 洞回填背景色 → 必要时描边。"""
        outer_rings: List[List[Tuple[float, float]]] = []
        for ring in item.rings:
            clipped = clip_ring([to_px(lon, lat) for lon, lat in ring], rect)
            if len(clipped) >= 3:
                draw.polygon(clipped, fill=color)
                outer_rings.append(clipped)
        if not outer_rings and not item.holes:
            return
        # 洞：按背景色回填（v2 输入才有；v1 缺省为空）
        hole_rings: List[List[Tuple[float, float]]] = []
        for hole in item.holes:
            clipped_hole = clip_ring([to_px(lon, lat) for lon, lat in hole], rect)
            if len(clipped_hole) >= 3:
                draw.polygon(clipped_hole, fill=COLOR_BACKGROUND)
                hole_rings.append(clipped_hole)
        if outline is not None and z >= outline[1]:
            self._stroke_poly(draw, outline[0], outer_rings, hole_rings)

    @staticmethod
    def _stroke_poly(draw, stroke, outer_rings, hole_rings) -> None:
        for clipped in outer_rings:
            draw.line(clipped + [clipped[0]], fill=stroke, width=1)
        for clipped_hole in hole_rings:
            # 细小的湖中岛（<6px）不描边，否则 1px 岸线会把整个岛盖住
            hole_box = bbox_of(clipped_hole)
            if hole_box[2] - hole_box[0] < 6 or hole_box[3] - hole_box[1] < 6:
                continue
            draw.line(clipped_hole + [clipped_hole[0]], fill=stroke, width=1)

    # ---------- 线要素 ----------

    def _collect_line_runs(self, to_px, z: int, query_box, rect) -> Dict[str, Any]:
        """把候选线要素按类别收集为像素折线段（含抽稀、裁剪与道路名候选）。"""
        rivers: List[List[Tuple[float, float]]] = []
        rails: List[List[Tuple[float, float]]] = []
        roads: Dict[str, List[List[Tuple[float, float]]]] = {}
        road_names: List[Tuple[str, List[Tuple[float, float]], float]] = []
        if self.line_index is None:
            return {"rivers": rivers, "rails": rails, "roads": roads, "road_names": road_names}

        for idx in self.line_index.query(query_box):
            item = self.lines[idx]
            if not _boxes_intersect(item.bbox, query_box):
                continue
            if self._line_width(item.cls, z) <= 0:
                continue
            coords = self._decimate(idx, item.coords, z)
            runs = polyline_runs([to_px(lon, lat) for lon, lat in coords], rect)
            if not runs:
                continue
            if item.cls in ("river", "stream", "canal"):
                rivers.extend(runs)
            elif item.cls == "rail":
                rails.extend(runs)
            else:
                roads.setdefault(item.cls, []).extend(runs)
                if item.name and z >= 10 and item.cls in (
                    "motorway",
                    "trunk",
                    "primary",
                    "secondary",
                ):
                    best = max(runs, key=_run_length)
                    road_names.append((item.name, best, _run_length(best)))
        return {"rivers": rivers, "rails": rails, "roads": roads, "road_names": road_names}

    def _paint_lines(self, draw, z: int, line_data: Dict[str, Any]) -> None:
        self._paint_water_and_rail(draw, z, line_data)
        self._paint_roads(draw, z, line_data["roads"])

    def _paint_water_and_rail(self, draw, z: int, line_data: Dict[str, Any]) -> None:
        rivers = line_data["rivers"]
        core_width = self.river_width(z)
        if rivers:
            casing_width = core_width + 2
            for run in rivers:
                draw.line(run, fill=COLOR_RIVER_CASING, width=casing_width, joint="curve")
            for run in rivers:
                draw.line(run, fill=COLOR_RIVER_CORE, width=core_width, joint="curve")

        rails = line_data["rails"]
        rail_width = self.rail_width(z)
        if not rails or rail_width <= 0:
            return
        if z >= 8:
            rect = (0.0, 0.0, float(TILE_SIZE), float(TILE_SIZE))
            for run in rails:
                dash_polyline_into(draw, run, 0.0, 5.0, 4.0, rect, COLOR_RAIL_DARK, rail_width)
        else:
            for run in rails:
                draw.line(run, fill=COLOR_RAIL, width=rail_width, joint="curve")

    def _paint_roads(self, draw, z: int, roads: Dict[str, List[List[Tuple[float, float]]]]) -> None:
        for cls in ROAD_DRAW_ORDER:
            runs = roads.get(cls)
            if not runs:
                continue
            width = self.road_width(cls, z)
            casing = ROAD_CASING[cls]
            for run in runs:
                draw.line(run, fill=casing, width=width + 2, joint="curve")
        for cls in ROAD_DRAW_ORDER:
            runs = roads.get(cls)
            if not runs:
                continue
            width = self.road_width(cls, z)
            fill = ROAD_FILL[cls]
            for run in runs:
                draw.line(run, fill=fill, width=width, joint="curve")
        # 主干道路面高光（z≥10）：细内芯（≈路宽 1/3，1~3px），避免整条路被冲淡
        if z < 10:
            return
        for cls in ROAD_HIGHLIGHT_CLASSES:
            runs = roads.get(cls)
            if not runs:
                continue
            highlight_width = max(1, min(3, self.road_width(cls, z) // 3))
            highlight = _lighten(ROAD_FILL[cls], 0.5)
            for run in runs:
                draw.line(run, fill=highlight, width=highlight_width, joint="curve")

    # ---------- 行政边界（边对消网络 + 虚线/点线 + 2x 抗锯齿） ----------

    def _draw_admin(self, img, to_px, z: int, query_box, rect) -> None:
        admin = self.admin
        if not admin:
            return
        from PIL import Image, ImageDraw as _ImageDraw

        world = float(TILE_SIZE) * (2 ** z)
        px_per_deg = world / 360.0
        layers: List[Tuple[List[BoundaryPath], Tuple[float, float, float], Tuple[int, int, int]]] = []
        if z >= BOUND_ZOOM_PROVINCE and admin.get("province"):
            layers.append((admin["province"], BOUND_STYLE_PROVINCE, COLOR_BOUND_PROVINCE))
        if z >= BOUND_ZOOM_PREF and admin.get("pref"):
            merged: List[BoundaryPath] = []
            for group in admin["pref"]:
                merged.extend(group["paths"])
            layers.append((merged, BOUND_STYLE_PREF, COLOR_BOUND_PREF))
        if z >= BOUND_ZOOM_COUNTY and admin.get("county"):
            layers.append((admin["county"], BOUND_STYLE_COUNTY, COLOR_BOUND_COUNTY))

        size = TILE_SIZE * SS
        rect_ss = (-4.0 * SS, -4.0 * SS, (TILE_SIZE + 4.0) * SS, (TILE_SIZE + 4.0) * SS)
        for paths, (width, dash, gap), color in layers:
            mask = Image.new("L", (size, size), 0)
            pen = _ImageDraw.Draw(mask)
            painted = False
            for path in paths:
                if not _boxes_intersect(path.bbox, query_box):
                    continue
                for i0, i1, chunk_box, cum_deg in path.chunks:
                    if not _boxes_intersect(chunk_box, query_box):
                        continue
                    pts = [
                        (x * SS, y * SS)
                        for x, y in (to_px(lon, lat) for lon, lat in path.pts[i0 : i1 + 1])
                    ]
                    if len(pts) < 2:
                        continue
                    dash_polyline_into(
                        pen,
                        pts,
                        cum_deg * px_per_deg * SS,
                        dash * SS,
                        gap * SS,
                        rect_ss,
                        255,
                        width * SS,
                    )
                    painted = True
            if not painted:
                continue
            small = mask.resize((TILE_SIZE, TILE_SIZE), Image.BILINEAR)
            img.paste(color, (0, 0), small)

    # ---------- 注记（优先级 + 碰撞避让） ----------

    def _label_candidates(self, to_px, z: int, query_box, rect, road_names) -> List[LabelCandidate]:
        candidates: List[LabelCandidate] = []
        self._admin_labels(candidates, to_px, z, rect)
        self._place_labels(candidates, to_px, z, query_box, rect)
        self._poly_labels(candidates, to_px, z, query_box, rect)
        self._road_labels(candidates, z, rect, road_names)
        return candidates

    @staticmethod
    def _push_label(
        candidates: List[LabelCandidate],
        to_px,
        rect,
        priority: float,
        importance: float,
        text: str,
        lon: float,
        lat: float,
        size: int,
        color,
    ) -> None:
        if not text:
            return
        x, y = to_px(lon, lat)
        if not (rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]):
            return
        candidates.append(LabelCandidate(priority, importance, text, x, y, size, color))

    def _admin_labels(self, candidates: List[LabelCandidate], to_px, z: int, rect) -> None:
        admin = self.admin
        if not admin:
            return
        if z >= 7:
            size = 12 if z <= 8 else (14 if z <= 10 else 16)
            for name, lon, lat in admin["pref_labels"]:
                self._push_label(candidates, to_px, rect, LABEL_PRIORITY["pref"], 1e9,
                                 name, lon, lat, size, LABEL_COLOR_PREF)
        if z >= 9:
            size = 10 if z <= 10 else 11
            for county in admin["counties"]:
                self._push_label(candidates, to_px, rect, LABEL_PRIORITY["county"], 5e8,
                                 county["name"], county["label"][0], county["label"][1],
                                 size, LABEL_COLOR_COUNTY)

    def _place_labels(self, candidates: List[LabelCandidate], to_px, z: int, query_box, rect) -> None:
        place_min_zoom = {"city": 8, "district": 9, "suburb": 9, "town": 10,
                          "village": 11, "hamlet": 11}
        for place in self.places:
            min_zoom = place_min_zoom.get(place.cls)
            if min_zoom is None or z < min_zoom:
                continue
            if not (query_box[0] <= place.lon <= query_box[2]
                    and query_box[1] <= place.lat <= query_box[3]):
                continue
            size = 13 if place.cls == "city" else (11 if place.cls in ("district", "town") else 10)
            self._push_label(candidates, to_px, rect, LABEL_PRIORITY.get(place.cls, 4),
                             float(place.population or 0), place.name, place.lon, place.lat,
                             size, LABEL_COLOR_PLACE)

    def _poly_labels(self, candidates: List[LabelCandidate], to_px, z: int, query_box, rect) -> None:
        if z < 10 or self.poly_index is None:
            return
        for idx in self.poly_index.query(query_box):
            item = self.polys[idx]
            if not item.name or not _boxes_intersect(item.bbox, query_box):
                continue
            lon, lat = item.label_point
            if item.cls in WATER_POLY_CLASSES:
                self._push_label(candidates, to_px, rect, LABEL_PRIORITY["water"],
                                 1e5, item.name, lon, lat, 10, LABEL_COLOR_WATER)
            elif item.cls == "park" and z >= 11:
                self._push_label(candidates, to_px, rect, LABEL_PRIORITY["park"],
                                 1e4, item.name, lon, lat, 9, LABEL_COLOR_PARK)

    def _road_labels(self, candidates: List[LabelCandidate], z: int, rect, road_names) -> None:
        if z < 10:
            return
        for name, run, length in road_names:
            if len(run) < 2:
                continue
            mid = _run_midpoint(run)
            if not (rect[0] <= mid[0] <= rect[2] and rect[1] <= mid[1] <= rect[3]):
                continue
            candidates.append(
                LabelCandidate(
                    LABEL_PRIORITY["road"], length, name[:ROAD_NAME_MAX_CHARS], mid[0], mid[1],
                    9 if z < 12 else 10, LABEL_COLOR_ROAD,
                )
            )

    def _draw_labels(self, draw, to_px, z: int, query_box, rect, road_names) -> None:
        candidates = self._label_candidates(to_px, z, query_box, rect, road_names)
        if not candidates:
            return
        candidates.sort(key=lambda c: (c.priority, -c.importance))
        placed: List[Tuple[float, float, float, float]] = []
        drawn: set = set()
        for candidate in candidates:
            if len(placed) >= MAX_LABELS:
                break
            if candidate.text in drawn:
                continue
            font = self.fonts.get(candidate.size)
            if font is None:
                return
            left, top, right, bottom = draw.textbbox(
                (candidate.x, candidate.y), candidate.text, font=font, anchor="mm"
            )
            box = (left - 1, top - 1, right + 1, bottom + 1)
            if any(
                not (box[2] < other[0] or box[0] > other[2] or box[3] < other[1] or box[1] > other[3])
                for other in placed
            ):
                continue
            placed.append(box)
            drawn.add(candidate.text)
            draw.text(
                (candidate.x, candidate.y),
                candidate.text,
                font=font,
                fill=candidate.color,
                anchor="mm",
                stroke_width=2,
                stroke_fill=LABEL_HALO,
            )

    # ---------- 比例尺 / 署名 ----------

    def _draw_scalebar(self, img, z: int, ty: int) -> None:
        from PIL import ImageDraw

        lat = unproject(0.0, ty * TILE_SIZE + TILE_SIZE / 2.0, z)[1]
        meters_per_pixel = 156543.03392 * max(0.05, math.cos(math.radians(lat))) / (2 ** z)
        target_m = meters_per_pixel * 62.0
        nice_m = _nice_distance(target_m)
        bar_px = nice_m / meters_per_pixel
        if bar_px > TILE_SIZE - 24:
            return
        x2 = TILE_SIZE - 6.0
        x1 = x2 - bar_px
        y = TILE_SIZE - 16.0
        pen = ImageDraw.Draw(img)
        pen.line([(x1, y), (x2, y)], fill=(90, 90, 90), width=3)
        pen.line([(x1, y), (x2, y)], fill=(255, 255, 255), width=1)
        for x in (x1, x2):
            pen.line([(x, y - 4), (x, y + 2)], fill=(255, 255, 255), width=3)
            pen.line([(x, y - 4), (x, y + 2)], fill=(90, 90, 90), width=1)
        font = self.fonts.get(9)
        label = _format_distance(nice_m)
        if font is None:
            from PIL import ImageFont

            font = ImageFont.load_default(size=9)
        pen.text(
            ((x1 + x2) / 2.0, y - 9), label, font=font, fill=(70, 70, 70), anchor="mm",
            stroke_width=1, stroke_fill=(255, 255, 255),
        )

    def _draw_attribution(self, img, draw) -> None:
        from PIL import Image, ImageDraw

        font = self.fonts.get(9)
        if font is None:
            from PIL import ImageFont

            font = ImageFont.load_default(size=9)
        text = self.attribution
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        height = bottom - top
        x = 4
        y = TILE_SIZE - height - 5
        overlay = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
        pen = ImageDraw.Draw(overlay)
        pen.text(
            (x, y),
            text,
            font=font,
            fill=(60, 60, 60, 170),
            stroke_width=1,
            stroke_fill=(255, 255, 255, 120),
        )
        composed = Image.alpha_composite(img.convert("RGBA"), overlay)
        img.paste(composed.convert("RGB"), (0, 0))


# ==================== 工具函数 ====================


def _run_length(run: Sequence[Tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(run) - 1):
        total += _seg_len(run[i], run[i + 1])
    return total


def _run_midpoint(run: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    """折线按长度取中点。"""
    total = _run_length(run)
    if total <= 0:
        return run[0]
    half = total / 2.0
    walked = 0.0
    for i in range(len(run) - 1):
        seg = _seg_len(run[i], run[i + 1])
        if walked + seg >= half:
            ratio = (half - walked) / seg if seg > 0 else 0.0
            return (
                run[i][0] + (run[i + 1][0] - run[i][0]) * ratio,
                run[i][1] + (run[i + 1][1] - run[i][1]) * ratio,
            )
        walked += seg
    return run[-1]


def _nice_distance(target_m: float) -> float:
    """取 1/2/5×10^n 中离目标最近的"整数"距离（米）。"""
    candidates = [
        1, 2, 5, 10, 20, 50, 100, 200, 500,
        1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
    ]
    best = candidates[-1]
    best_delta = None
    for value in candidates:
        delta = abs(value - target_m)
        if best_delta is None or delta < best_delta:
            best, best_delta = value, delta
    return float(best)


def _format_distance(meters: float) -> str:
    if meters < 1000:
        return f"{int(meters)} m"
    return f"{int(meters / 1000)} km"


# ==================== 自检 ====================


def run_selftest() -> int:
    """投影/边界/洞/注记/比例尺/署名自检（不依赖 layers.pkl）。"""
    problems: List[str] = []
    z = 9
    tile_x, tile_y = _selftest_projection(problems, z)
    admin = _selftest_admin(problems)
    renderer = _selftest_holes(problems, admin, z)
    _selftest_labels(problems, renderer)
    _selftest_overlays(problems, renderer, z, tile_x, tile_y)
    _selftest_road_widths(problems)
    if problems:
        for problem in problems:
            log(f"  [问题] {problem}")
        fail("自检失败", 1)
    log("[自检通过] 投影、边界、洞、注记、比例尺、署名与 z12 阈值均正常")
    return 0


def _selftest_projection(problems: List[str], z: int) -> Tuple[int, int]:
    log("== 自检 1/6：Web Mercator 投影与 XYZ 编号 ==")
    lon, lat = 107.517021, 26.258205  # 都匀市中心
    tx, ty, px_in, py_in = tile_of(lon, lat, z)
    cx, cy = lonlat_to_tile(lon, lat, z)
    if (tx, ty) != (cx, cy):
        problems.append(f"瓦片编号不一致: project={tx},{ty} _common={cx},{cy}")
    if not (0.0 <= px_in < TILE_SIZE and 0.0 <= py_in < TILE_SIZE):
        problems.append(f"落点越界: ({px_in:.2f},{py_in:.2f})")
    rlon, rlat = unproject(tx * TILE_SIZE + px_in, ty * TILE_SIZE + py_in, z)
    if abs(rlon - lon) > 1e-6 or abs(rlat - lat) > 1e-6:
        problems.append(f"正反投影不一致: {(rlon, rlat)} != {(lon, lat)}")
    log(f"  都匀 (107.517021, 26.258205) @ z{z} → 瓦片 ({tx},{ty})，落点 ({px_in:.2f},{py_in:.2f})")
    return tx, ty


def _selftest_admin(problems: List[str]) -> Optional[Dict[str, Any]]:
    log("== 自检 2/6：行政边界（边对消） ==")
    if not GEOJSON.is_file():
        warn(f"缺少行政边界 GeoJSON: {GEOJSON}（渲染将不含边界）")
        return None
    admin = load_admin_geo(GEOJSON)
    province_pts = sum(len(p.pts) for p in admin["province"])
    county_pts = sum(len(p.pts) for p in admin["county"])
    pref_count = len(admin["pref"])
    log(
        f"  县 {len(admin['counties'])} / 地州 {pref_count} / 省界折线 {len(admin['province'])} 条"
        f"（{province_pts} 点） / 县界网络 {len(admin['county'])} 条（{county_pts} 点）"
    )
    if len(admin["counties"]) < 80:
        problems.append(f"GeoJSON 县级要素过少: {len(admin['counties'])}")
    if not admin["province"] or province_pts < 100:
        problems.append("省级边界折线为空或过短（边对消失败）")
    if pref_count < 8:
        problems.append(f"地州边界数量异常: {pref_count}")
    return admin


def _selftest_holes(problems: List[str], admin: Optional[Dict[str, Any]], z: int) -> "Renderer":
    log("== 自检 3/6：洞渲染（multipolygon holes） ==")
    prepared = {
        "lines": [],
        "polys": [
            PolyItem(
                "water",
                "测试湖",
                [[(107.40, 26.20), (107.60, 26.20), (107.60, 26.35), (107.40, 26.35)]],
                [[(107.46, 26.24), (107.54, 26.24), (107.54, 26.31), (107.46, 26.31)]],
            )
        ],
        "places": [],
    }
    renderer = Renderer(prepared, admin, DEFAULT_ATTRIBUTION)
    hole_tx, hole_ty, _, _ = tile_of(107.50, 26.275, z)
    img = renderer.render_tile(z, hole_tx, hole_ty)
    hole_px = int(project(107.50, 26.275, z)[0] - hole_tx * TILE_SIZE)
    hole_py = int(project(107.50, 26.275, z)[1] - hole_ty * TILE_SIZE)
    hole_pixel = img.getpixel((hole_px, hole_py))
    if hole_pixel != COLOR_BACKGROUND:
        problems.append(f"洞中心像素未被回填为背景色: {hole_pixel}")
    ring_px = int(project(107.43, 26.21, z)[0] - hole_tx * TILE_SIZE)
    ring_py = int(project(107.43, 26.21, z)[1] - hole_ty * TILE_SIZE)
    ring_pixel = img.getpixel((ring_px, ring_py))
    if ring_pixel != COLOR_WATER:
        problems.append(f"湖面未使用水色: {ring_pixel}")
    log(f"  洞中心像素 {hole_pixel}（期望背景色） / 湖面像素 {ring_pixel}（期望水色）")
    return renderer


def _selftest_labels(problems: List[str], renderer: "Renderer") -> None:
    log("== 自检 4/6：注记优先级与碰撞避让 ==")
    placed, overlaps = _probe_label_placement(renderer)
    if placed > MAX_LABELS:
        problems.append(f"单瓦片注记超过上限: {placed}")
    if overlaps > 0:
        problems.append(f"注记框存在重叠: {overlaps}")
    log(f"  合成 40 条重叠候选 → 放置 {placed} 条（上限 {MAX_LABELS}），重叠 {overlaps} 处")


def _selftest_overlays(problems: List[str], renderer: "Renderer", z: int,
                       tile_x: int, tile_y: int) -> None:
    log("== 自检 5/6：比例尺 / 署名 ==")
    tile_img = renderer.render_tile(z, tile_x, tile_y)
    right_dark = sum(
        1
        for y in range(TILE_SIZE - 24, TILE_SIZE)
        for x in range(TILE_SIZE - 90, TILE_SIZE)
        if all(v < 200 for v in tile_img.getpixel((x, y)))
    )
    left_dark = sum(
        1
        for y in range(TILE_SIZE - 20, TILE_SIZE)
        for x in range(0, 180)
        if all(v < 200 for v in tile_img.getpixel((x, y)))
    )
    if right_dark < 20:
        problems.append(f"右下角比例尺疑似缺失（暗像素 {right_dark}）")
    if left_dark < 20:
        problems.append(f"左下角署名疑似缺失（暗像素 {left_dark}）")
    log(f"  比例尺区域暗像素 {right_dark} / 署名区域暗像素 {left_dark}")
    if tile_img.size != (TILE_SIZE, TILE_SIZE):
        problems.append(f"瓦片尺寸异常: {tile_img.size}")


def _selftest_road_widths(problems: List[str]) -> None:
    log("== 自检 6/6：z12 道路阈值 ==")
    expectations = {
        "motorway": 9, "trunk": 8, "primary": 7, "secondary": 6,
        "tertiary": 4, "residential": 3, "unclassified": 2, "service": 1,
    }
    for cls, expect in expectations.items():
        actual = Renderer.road_width(cls, 12)
        if actual != expect:
            problems.append(f"z12 {cls} 宽度 {actual} != 期望 {expect}")
    log(f"  z12 阈值: {expectations}")


def _probe_label_placement(renderer: "Renderer") -> Tuple[int, int]:
    """用 40 条重叠候选验证注记上限与碰撞剔除（不落盘）。"""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(img)
    font = renderer.fonts.get(10)
    if font is None:
        return (0, 0)
    placed: List[Tuple[float, float, float, float]] = []
    drawn: set = set()
    candidates = [
        LabelCandidate(0, 40 - i, f"测{i}", 128 + (i % 5) * 3, 128 + (i % 7) * 3, 10, LABEL_COLOR_PLACE)
        for i in range(40)
    ]
    candidates.sort(key=lambda c: (c.priority, -c.importance))
    for candidate in candidates:
        if len(placed) >= MAX_LABELS or candidate.text in drawn:
            continue
        left, top, right, bottom = draw.textbbox(
            (candidate.x, candidate.y), candidate.text, font=font, anchor="mm"
        )
        box = (left - 1, top - 1, right + 1, bottom + 1)
        if any(
            not (box[2] < other[0] or box[0] > other[2] or box[3] < other[1] or box[1] > other[3])
            for other in placed
        ):
            continue
        placed.append(box)
        drawn.add(candidate.text)
    overlaps = 0
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = placed[i], placed[j]
            if not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3]):
                overlaps += 1
    return (len(placed), overlaps)


# ==================== 并行渲染 ====================

_WORKER_RENDERER: Optional["Renderer"] = None
_WORKER_STATE: Dict[str, Any] = {}


def _worker_init(
    input_path: str,
    geo_path: Optional[str],
    attribution: str,
    out_dir: str,
    skip_existing: bool,
) -> None:
    """并行 worker 初始化：各自加载图层与索引（Windows spawn 下每进程独立）。"""
    global _WORKER_RENDERER, _WORKER_STATE
    layers = load_layers(Path(input_path))
    admin = load_admin_geo(Path(geo_path)) if geo_path else None
    _WORKER_RENDERER = Renderer(layers, admin, attribution)
    _WORKER_STATE = {"out": Path(out_dir), "skip": bool(skip_existing)}


def _worker_render(tile: Tuple[int, int, int]) -> Tuple[str, Tuple[int, int, int]]:
    """渲染一个瓦片并写盘；返回 (状态, 瓦片坐标)。"""
    z, tx, ty = tile
    target = _WORKER_STATE["out"] / str(z) / str(tx) / f"{ty}.png"
    try:
        if _WORKER_STATE["skip"] and target.is_file() and target.stat().st_size > 0:
            return ("skip", tile)
        assert _WORKER_RENDERER is not None
        image = _WORKER_RENDERER.render_tile(z, tx, ty)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "PNG", optimize=True)
        return ("ok", tile)
    except Exception:  # noqa: BLE001 - 单瓦片失败不应终止整批
        return ("fail", tile)


# ==================== 主流程 ====================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render_osm_tiles.py",
        description="用 Pillow 纯 Python 把 OSM 提取图层离线渲染为 Web Mercator XYZ 瓦片（v2）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/tiles/render_osm_tiles.py --selftest\n"
            "  python scripts/tiles/render_osm_tiles.py --dry-run\n"
            "  python scripts/tiles/render_osm_tiles.py --zoom 12 --jobs 4 --skip-existing\n"
            "  python scripts/tiles/render_osm_tiles.py --bbox 106.0,25.1,108.5,26.9 --zoom 9-10\n"
        ),
    )
    parser.add_argument("--selftest", action="store_true", help="只跑投影/边界/洞/注记/比例尺自检，不读 layers.pkl、不写盘")
    parser.add_argument("--input", default=DEFAULT_INPUT, help=f"OSM 图层 pickle 路径（默认 {DEFAULT_INPUT}）")
    parser.add_argument("--wait-input", type=float, default=0.0, metavar="SECONDS",
                        help="输入不存在时最多等待的秒数（轮询到大小稳定，默认 0 = 不等待）")
    parser.add_argument("--bbox", default=DEFAULT_BBOX,
                        help=f"经纬度范围 min_lon,min_lat,max_lon,max_lat（默认贵州全域 {DEFAULT_BBOX}）")
    parser.add_argument("--zoom", default=DEFAULT_ZOOM, help=f"缩放范围，如 5-12（默认 {DEFAULT_ZOOM}）")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"输出瓦片目录（默认 {DEFAULT_OUT}）")
    parser.add_argument("--jobs", type=int, default=1, metavar="N",
                        help="并行进程数（默认 1；4 进程约 3~4 倍吞吐，建议 ≤ CPU 核数）")
    parser.add_argument("--skip-existing", action="store_true", help="已存在且非空的瓦片跳过（断点续跑）")
    parser.add_argument("--dry-run", action="store_true", help="只统计瓦片数量与图层规模，不渲染")
    parser.add_argument("--attribution", default=DEFAULT_ATTRIBUTION,
                        help=f"瓦片左下角署名文案（默认 {DEFAULT_ATTRIBUTION}；空串 = 不绘制）")
    parser.add_argument("--preview", type=int, default=0, metavar="N",
                        help="渲染完成后复制 N 张抽样瓦片到预览目录（默认 0）")
    parser.add_argument("--preview-dir", default=DEFAULT_PREVIEW_DIR,
                        help=f"预览目录（默认 {DEFAULT_PREVIEW_DIR}）")
    parser.add_argument("--geojson", default=None, help="行政边界 GeoJSON（默认项目内置 guizhou.json）")
    return parser


def _print_plan(bbox, z_min: int, z_max: int) -> int:
    plan = count_tiles_by_zoom(bbox, z_min, z_max)
    total = sum(count for _, count in plan)
    log(f"bbox: {bbox}  缩放: {z_min}-{z_max}  瓦片总数: {total}")
    for z, count in plan:
        x_min, x_max, y_min, y_max = tile_range(bbox, z)
        log(f"  z{z:<2} {count:6d} 张（x {x_min}-{x_max}, y {y_min}-{y_max}）")
    return total


def _write_manifest(out_dir: Path, bbox, z_min: int, z_max: int, attribution: str,
                    input_path: Path, geo_path: Optional[Path], meta: Dict[str, Any]) -> Dict[str, Any]:
    count, total_bytes, levels = scan_tiles(out_dir)
    sources = [str(input_path)]
    if geo_path is not None:
        try:
            sources.append(str(geo_path.resolve().relative_to(ROOT)))
        except ValueError:
            sources.append(str(geo_path))
    manifest = build_manifest(
        provider=PROVIDER,
        license_text=LICENSE_TEXT,
        bbox=bbox,
        z_min=z_min,
        z_max=z_max,
        tile_count=count,
        total_bytes=total_bytes,
        sources=sources,
        extra={
            "attribution": attribution,
            "renderer": "scripts/tiles/render_osm_tiles.py",
            "style": STYLE_NAME,
            "tilesVersion": 2,
            "sourceMeta": meta or {},
        },
    )
    write_manifest(out_dir, manifest)
    return {"count": count, "bytes": total_bytes, "levels": levels}


def _copy_preview(files: List[Path], out_dir: Path, preview_dir: Path, count: int) -> List[Path]:
    if count <= 0 or not files:
        return []
    preview_dir.mkdir(parents=True, exist_ok=True)
    step = max(1, len(files) // count)
    picked = files[::step][:count]
    copied = []
    for source in picked:
        rel = source.relative_to(out_dir)
        target = preview_dir / f"sample-z{rel.parent.parent.name}-x{rel.parent.name}-y{rel.name}"
        target.write_bytes(source.read_bytes())
        copied.append(target)
    return copied


def _render_sequential(
    renderer: "Renderer",
    tiles: List[Tuple[int, int, int]],
    out_dir: Path,
    skip_existing: bool,
    started: float,
    total_plan: int,
) -> Tuple[int, int, int, bool, List[Tuple[int, int, int]]]:
    rendered = 0
    skipped = 0
    failures = 0
    interrupted = False
    done_tiles: List[Tuple[int, int, int]] = []
    last_report = started
    try:
        for tile in tiles:
            z, tx, ty = tile
            target = out_dir / str(z) / str(tx) / f"{ty}.png"
            if skip_existing and target.is_file() and target.stat().st_size > 0:
                skipped += 1
                continue
            try:
                image = renderer.render_tile(z, tx, ty)
                target.parent.mkdir(parents=True, exist_ok=True)
                image.save(target, "PNG", optimize=True)
                rendered += 1
                done_tiles.append(tile)
            except OSError as exc:
                failures += 1
                warn(f"瓦片 {z}/{tx}/{ty} 写入失败: {exc}")
                if failures > 50:
                    fail("连续写入失败过多，已中止", 1)
                    break
            last_report = _report_progress(rendered + skipped, total_plan, started, last_report,
                                           rendered, skipped)
    except KeyboardInterrupt:
        interrupted = True
        warn("收到中断：已渲染部分已落盘，可用 --skip-existing 续跑")
    return rendered, skipped, failures, interrupted, done_tiles


def _render_parallel(
    tiles: List[Tuple[int, int, int]],
    jobs: int,
    out_dir: Path,
    input_path: Path,
    geo_path: Optional[Path],
    attribution: str,
    skip_existing: bool,
    started: float,
    total_plan: int,
) -> Tuple[int, int, int, bool, List[Tuple[int, int, int]]]:
    rendered = 0
    skipped = 0
    failures = 0
    done_tiles: List[Tuple[int, int, int]] = []
    last_report = started
    ctx = multiprocessing.get_context("spawn")
    try:
        with ctx.Pool(
            processes=jobs,
            initializer=_worker_init,
            initargs=(str(input_path), str(geo_path) if geo_path else None,
                      attribution, str(out_dir), skip_existing),
        ) as pool:
            for status, tile in pool.imap_unordered(_worker_render, tiles, chunksize=8):
                if status == "ok":
                    rendered += 1
                    done_tiles.append(tile)
                elif status == "skip":
                    skipped += 1
                else:
                    failures += 1
                    if failures <= 20:
                        warn(f"瓦片 {tile[0]}/{tile[1]}/{tile[2]} 渲染失败")
                last_report = _report_progress(rendered + skipped, total_plan, started,
                                               last_report, rendered, skipped)
    except KeyboardInterrupt:
        warn("收到中断：已渲染部分已落盘，可用 --skip-existing 续跑")
        return rendered, skipped, failures, True, done_tiles
    return rendered, skipped, failures, False, done_tiles


def _report_progress(done: int, total: int, started: float, last_report: float,
                     rendered: int, skipped: int) -> float:
    now = time.time()
    if now - last_report < 15:
        return last_report
    speed = done / max(now - started, 1e-6)
    remaining = max(total - done, 0)
    log(
        f"进度 {done}/{total}（{done / max(total, 1) * 100:.1f}%）"
        f" 已渲染 {rendered} 跳过 {skipped}  {speed:.1f} 张/秒"
        f" 预计剩余 {remaining / max(speed, 1e-6):.0f}s"
    )
    return now


def main(argv: Optional[Sequence[str]] = None) -> int:
    setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        fail("需要 Pillow：backend/.venv/Scripts/python.exe -m pip install pillow", 3)
        return 3

    if args.selftest:
        return run_selftest()
    if args.jobs < 1:
        fail("--jobs 必须 >= 1", 2)
        return 2
    return _execute(args)


def _execute(args) -> int:
    try:
        bbox = parse_bbox(args.bbox)
        z_min, z_max = parse_zoom(args.zoom)
    except TileToolError as exc:
        fail(str(exc), 2)
        return 2

    input_path = Path(args.input)
    out_dir = Path(args.out)
    geo_path = Path(args.geojson) if args.geojson else GEOJSON
    if not geo_path.is_file():
        warn(f"缺少行政边界 GeoJSON: {geo_path}（本次渲染不含行政边界）")
        geo_path = None

    started = time.time()
    if not wait_for_input(input_path, args.wait_input):
        fail(f"输入文件不存在: {input_path}（可用 --wait-input 等待 osm 提取产物）", 2)
        return 2

    try:
        layers = load_layers(input_path)
        admin = load_admin_geo(geo_path) if geo_path is not None else None
    except (TileToolError, OSError, ValueError) as exc:
        fail(str(exc), 2)
        return 2

    _log_inputs(input_path, layers, admin)
    total_plan = _print_plan(bbox, z_min, z_max)
    tiles = list(iter_tiles(bbox, z_min, z_max))
    if args.dry_run:
        log("dry-run 完成：未渲染、未写盘。")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    if args.jobs > 1:
        log(f"并行渲染: {args.jobs} 进程（spawn）")
        result = _render_parallel(
            tiles, args.jobs, out_dir, input_path, geo_path, args.attribution,
            args.skip_existing, started, total_plan,
        )
    else:
        result = _render_sequential(
            Renderer(layers, admin, args.attribution), tiles, out_dir,
            args.skip_existing, started, total_plan,
        )
    return _finish(args, result, bbox, z_min, z_max, input_path, out_dir, geo_path,
                   layers, started)


def _log_inputs(input_path: Path, layers: Dict[str, Any], admin: Optional[Dict[str, Any]]) -> None:
    log(f"输入: {input_path}  ({human_bytes(input_path.stat().st_size)})")
    log(
        f"图层: 线 {len(layers['lines'])}（跳过 {layers['skipped_lines']}）"
        f"  面 {len(layers['polys'])}（跳过 {layers['skipped_polys']}，洞 {layers['hole_count']}）"
        f"  注记点 {len(layers['places'])}"
    )
    if admin:
        log(f"行政边界: {len(admin['counties'])} 县 / {len(admin['pref'])} 地州 / "
            f"省界折线 {len(admin['province'])} 条")


def _finish(args, result, bbox, z_min: int, z_max: int, input_path: Path, out_dir: Path,
            geo_path: Optional[Path], layers: Dict[str, Any], started: float) -> int:
    rendered, skipped, failures, interrupted, done_tiles = result
    elapsed = time.time() - started
    stats = _write_manifest(out_dir, bbox, z_min, z_max, args.attribution, input_path, geo_path,
                            layers.get("meta") or {})
    speed = (rendered + skipped) / max(elapsed, 1e-6)
    log(
        f"完成: 渲染 {rendered} 张 / 跳过 {skipped} / 失败 {failures}；目录现有 {stats['count']} 张，"
        f"共 {human_bytes(stats['bytes'])}；耗时 {elapsed:.1f}s（{speed:.1f} 张/秒）"
    )
    log(f"输出: {out_dir}  缩放级别: {stats['levels']}")
    log(f"MANIFEST: provider={PROVIDER} license={LICENSE_TEXT} style={STYLE_NAME}")

    if args.preview > 0:
        files = [out_dir / str(z) / str(x) / f"{y}.png" for z, x, y in done_tiles]
        files = [f for f in files if f.is_file()]
        for path in _copy_preview(files, out_dir, Path(args.preview_dir), args.preview):
            log(f"预览: {path}")

    if interrupted:
        return 130
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
