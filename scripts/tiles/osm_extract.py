#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 OSM PBF 提取包（贵州省）抽取可离线渲染的矢量图层，落盘为单个 pickle。

schema v3（向后兼容 v1/v2）：在 v2（multipolygon 关系 + 洞）基础上新增 **POI 图层**
（学校/幼儿园/学院/大学），供 z13 瓦片绘制"村子与学校名称"。v2/v1 的 pkl 仍可被
渲染器读取（`pois` 缺失按空列表处理）。

输出契约（渲染器按此消费）
--------------------------
```
{
  "meta": {
     "schema_version": 3,
     "source_file": "guizhou.osm.pbf", "source_bytes": int,
     "license": "ODbL-1.0", "attribution": "© OpenStreetMap contributors",
     "bbox": [min_lon, min_lat, max_lon, max_lat],   # 保留要素的实际包围盒
     "generated_at": "2026-10-22T...+08:00",
     "relation_fail_sample_ids": [int, ...],        # 缝合失败的关系样例（最多 10 个）
     "counts": {
        "lines": {...by class...}, "polys": {...by class...}, "places": {...by class...},
        "pois": {"school": int, "kindergarten": int, "college": int, "university": int},
        "skipped": {...by reason...},
        "relations_total": int, "relations_assembled": int, "relations_failed": int,
        "holes_total": int
     }
  },
  "lines": [{"cls": "motorway|trunk|primary|secondary|tertiary|residential|service|
                     unclassified|living_street|track|rail|river|stream|canal",
             "name": str, "coords": [(lon, lat), ...]}],
  "polys": [{"cls": "water|reservoir|riverbank|wetland|park|forest|farmland|grass|urban|industrial",
             "name": str, "rings": [[(lon, lat), ...], ...],
             "holes": [[(lon, lat), ...], ...]}],   # 无洞时必须为 []（不要省略该键）
  "places":[{"name": str, "name_zh": str, "cls": "city|town|village|hamlet|suburb|district",
             "lon": float, "lat": float, "population": int|None}],
  "pois":  [{"name": str, "name_zh": str, "cls": "school|kindergarten|college|university",
             "lon": float, "lat": float, "amenity": str}]   # v3 新增；node + way 质心
}
```
- 坐标统一 `round(..., 5)`；线/环保留首尾端点；环闭合（首尾同点）。
- `polys[*].rings` 目前恒为 1 个外环（多面关系已拆成多条），`holes` 为该外环内的内环（岛屿）。
- POI：`amenity ∈ {school, kindergarten, college, university}` 的 node 与 way；
  way 取其节点坐标的**质心**（relation 暂不做）；名称取 `name:zh` → `name`，无名称不输出，
  截断 100（`NAME_MAX_LEN`）。

分类规则（tag 白名单）
----------------------
- 线：`highway` ∈ motorway/trunk/primary/secondary/tertiary/residential/service/unclassified/
      living_street/track；`highway=*_link` 归并到父类（primary_link → primary）；
      `railway` ∈ rail/subway → rail；`waterway` ∈ river/stream/canal。
- 面（单 way 闭合 + multipolygon 关系共用同一套规则）：
      `natural=water` → water；`waterway=riverbank` → riverbank；`landuse=reservoir` → reservoir；
      `natural=wetland` → wetland；`landuse=forest`/`natural=wood`/`natural=scrub` → forest；
      `landuse=farmland` → farmland；`landuse=grass` → grass；`landuse=industrial` → industrial；
      `landuse=residential` → urban；`leisure=park` → park；
      `place=city_block|neighbourhood` → urban。
- 点：`place` ∈ city/town/village/hamlet/suburb；`place=district|quarter|borough` → district。
      名称优先 `name:zh` 再 `name`。
- **不**抽行政边界（省/州/县界由渲染器用 frontend/src/assets/geo/guizhou.json 负责），
  **不**抽建筑物/POI/detail 标签。

multipolygon 处理（两遍扫描）
-----------------------------
1. **pass1**（不带 locations，只读 relation）：收集 `type=multipolygon` 且 tag 命中面白名单的
   关系 → 记录 relation id、类别、名称、成员 way id + role（outer/inner），得到成员 way 集合。
2. **pass2**（`apply_file(locations=True)`，全内存）：正常抽取线/点/单 way 面，同时把"成员 way"
   的 node id 序列与坐标记下来（成员 way 不再单独作为面输出，交给关系拼接）。
3. **环拼接**：按 **node id** 缝合成环（支持多段、首尾倒序、端点相接），role 齐全时按 role
   分 outer/inner；role 缺失时按"面积 + 包含关系"奇偶判定。开链容错：端点缺口 ≤0.01°（约 1km）
   时补闭合，否则丢弃并计数。
4. 每个 outer 环输出一条 poly，`holes` 为其内部 inner 环；多 outer 关系拆成多条。
5. 稳健性：任何关系异常只计数不崩溃；缝合失败的关系 id 抽样写入 `meta.relation_fail_sample_ids`。
   v1 时代被整体跳过的 635 个 multipolygon 在此补齐。

内存策略（为什么两遍而不是先攒 refs）
-------------------------------------
pass1 只读 relation，几乎不占内存；pass2 才是主扫描。若单次扫描，relation 在 PBF 中排在 way
之后，读到 relation 时 way 已过去，必须缓存全部 way 的 node refs（229k 条）才能补，代价比多读一遍
30MB 文件大。故采用"pass1 收关系 → pass2 收几何"，峰值内存 ≈ pyosmium 节点索引
（500 万节点）+ 成员 way 几何（仅数百个关系涉及的 way），实测 <1GB。

已知限制
--------
- 不做多边形裁剪：只要有一个点在过滤框内就整条保留（渲染端按瓦片裁剪）。
- 不做拓扑校验（自相交环仅做面积阈值过滤）。
- 关系成员 way 若在提取包内缺失/坐标不可解析，会导致该关系缝合失败（计入 relations_failed）。

用法
----
python scripts/tiles/osm_extract.py --input .scratch/osm/guizhou.osm.pbf \
    --output .scratch/osm/layers.pkl --stats
python scripts/tiles/osm_extract.py --input guizhou.osm.pbf --no-relations   # 快速回归 v1 行为
python scripts/tiles/osm_extract.py --help
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量：schema 版本、tag 白名单与输出类别
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 3

LICENSE = "ODbL-1.0"
ATTRIBUTION = "© OpenStreetMap contributors"

# 贵州全境包围盒（约 103.6~109.6E, 24.6~29.2N）再留约 10km 缓冲。
# 作用：pbf 若带邻省缓冲，用它把省外要素挡掉；不是精确省界（省界由 GeoJSON 负责）。
DEFAULT_FILTER_BBOX = (103.5, 24.5, 109.7, 29.3)

HIGHWAY_CLASSES = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "service",
    "unclassified",
    "living_street",
    "track",
)
# `highway=*_link` 归并到父类，避免渲染端为匝道单独配色
HIGHWAY_LINK_MAP = {
    "motorway_link": "motorway",
    "trunk_link": "trunk",
    "primary_link": "primary",
    "secondary_link": "secondary",
    "tertiary_link": "tertiary",
}
RAILWAY_CLASSES = {"rail": "rail", "subway": "rail"}
WATERWAY_LINE_CLASSES = ("river", "stream", "canal")

LINE_CLASSES = HIGHWAY_CLASSES + ("rail",) + WATERWAY_LINE_CLASSES
POLY_CLASSES = (
    "water",
    "reservoir",
    "riverbank",
    "wetland",
    "park",
    "forest",
    "farmland",
    "grass",
    "urban",
    "industrial",
)

# 面要素 tag → 类别。顺序即优先级（先命中先返回）。单 way 闭合与 multipolygon 关系共用。
POLY_TAG_RULES = (
    (("natural", "water"), "water"),
    (("waterway", "riverbank"), "riverbank"),
    (("landuse", "reservoir"), "reservoir"),
    (("natural", "wetland"), "wetland"),
    (("landuse", "forest"), "forest"),
    (("natural", "wood"), "forest"),
    (("natural", "scrub"), "forest"),
    (("landuse", "farmland"), "farmland"),
    (("landuse", "grass"), "grass"),
    (("landuse", "industrial"), "industrial"),
    (("landuse", "residential"), "urban"),
    (("leisure", "park"), "park"),
    (("place", "city_block"), "urban"),
    (("place", "neighbourhood"), "urban"),
)

# 地名节点：place 值 → 输出类别（district 覆盖 district/quarter/borough）
PLACE_NODE_MAP = {
    "city": "city",
    "town": "town",
    "village": "village",
    "hamlet": "hamlet",
    "suburb": "suburb",
    "district": "district",
    "quarter": "district",
    "borough": "district",
}
PLACE_CLASSES = tuple(dict.fromkeys(PLACE_NODE_MAP.values()))

# POI（v3）：`amenity` 白名单。渲染端据此在 z12（大学/学院）/z13（学校/幼儿园）画名称。
POI_AMENITIES = ("school", "kindergarten", "college", "university")

# 简化容差（度）：z11 级别约 30m，面略放宽以压体积
LINE_TOLERANCE = 0.0003
RING_TOLERANCE = 0.0005
# 洞（岛屿）容差单独收紧：小岛在 0.0005° 下常被简化成 <4 点而整块丢失，
# 用 0.0002°（约 22m）能保住绝大多数湖中岛屿，体积代价很小（洞都是小环）。
HOLE_TOLERANCE = 0.0002

# 环面积下限（度²）：1e-10 度² ≈ 1.2 m²。只用 `= 0` 判断挡不住"自相交细条环"——
# 鞋带公式的浮点抵消会给出 3e-18 这种非零残值，故必须用绝对阈值。
MIN_RING_AREA = 1e-10

# 关系开链容错：端点缺口在经纬度上都不超过该值时补闭合（约 1km）
RELATION_MAX_GAP_DEG = 0.01

# 关系缝合失败样例最多记录多少个 relation id（便于排查，不写全量）
RELATION_FAIL_SAMPLE_LIMIT = 10

DEFAULT_MAX_BYTES = 60 * 1024 * 1024  # v2 体积目标上限
NAME_MAX_LEN = 100                    # 名称截断，防个别超长 detail 值

EXIT_OK = 0
EXIT_ENV = 2       # 环境/参数问题（未装 pyosmium、输入不存在等）
EXIT_DATA = 3      # 数据解析失败
EXIT_OUTPUT = 4    # 落盘/体积门禁失败


# ---------------------------------------------------------------------------
# 几何工具
# ---------------------------------------------------------------------------

def _perp_dist2(p, a, b):
    """点 p 到线段 ab 的平方距离（经纬度平面近似；贵州纬度范围内误差可忽略）。"""
    ax, ay = a
    bx, by = b
    px, py = p
    dx = bx - ax
    dy = by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0.0:
        ddx = px - ax
        ddy = py - ay
        return ddx * ddx + ddy * ddy
    t = ((px - ax) * dx + (py - ay) * dy) / seg2
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    qx = ax + t * dx
    qy = ay + t * dy
    ddx = px - qx
    ddy = py - qy
    return ddx * ddx + ddy * ddy


def douglas_peucker(points, tolerance):
    """迭代版 Douglas-Peucker（避免递归深度限制），保留首尾端点。"""
    n = len(points)
    if n < 3 or tolerance <= 0.0:
        return list(points)
    tol2 = tolerance * tolerance
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        best = -1.0
        best_k = -1
        a = points[i]
        b = points[j]
        for k in range(i + 1, j):
            d = _perp_dist2(points[k], a, b)
            if d > best:
                best = d
                best_k = k
        if best > tol2 and best_k > 0:
            keep[best_k] = True
            stack.append((i, best_k))
            stack.append((best_k, j))
    return [p for p, k in zip(points, keep) if k]


def simplify_ring(points, tolerance):
    """闭合环简化：以"离首点最远的顶点"为切分点拆两段分别 DP，再拼回闭合环。

    闭合环首尾同点，直接用 DP 会得到零长度基准线（退化），故先切分。
    """
    n = len(points)
    if n < 4:
        return list(points)
    first = points[0]
    far = 0
    best = -1.0
    for idx in range(1, n - 1):
        dx = points[idx][0] - first[0]
        dy = points[idx][1] - first[1]
        d = dx * dx + dy * dy
        if d > best:
            best = d
            far = idx
    if far <= 0:
        return list(points)
    head = douglas_peucker(points[: far + 1], tolerance)
    tail = douglas_peucker(points[far:], tolerance)
    ring = head[:-1] + tail
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def ring_area(ring):
    """有向面积绝对值（度²），以首点为原点做扇形累加，避免大坐标相消误差。"""
    if len(ring) < 4:
        return 0.0
    x0, y0 = ring[0]
    s = 0.0
    for i in range(1, len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        s += (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    return abs(s) * 0.5


def point_in_ring(point, ring):
    """射线法判断点是否在环内（含边界近似；用于 hole 归属，不追求边界严格性）。"""
    x, y = point
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def simplify_and_round_ring(ring, tolerance):
    """简化 + 5 位小数 + 去重复点 + 闭合；返回环（可能退化）。"""
    simplified = simplify_ring(ring, tolerance)
    out = []
    for lon, lat in simplified:
        pt = (round(lon, 5), round(lat, 5))
        if not out or out[-1] != pt:
            out.append(pt)
    if len(out) >= 3 and out[0] != out[-1]:
        out.append(out[0])
    return out


def round_line(coords):
    out = []
    for lon, lat in coords:
        pt = (round(lon, 5), round(lat, 5))
        if not out or out[-1] != pt:
            out.append(pt)
    return out


def bbox_of(points, box=None):
    """返回 [min_lon, min_lat, max_lon, max_lat] 或 None；传 box 时做增量扩展。"""
    if not points:
        return None
    if box is None:
        lons = [p[0] for p in points]
        lats = [p[1] for p in points]
        return [min(lons), min(lats), max(lons), max(lats)]
    min_lon, min_lat, max_lon, max_lat = box
    for lon, lat in points:
        if lon < min_lon:
            min_lon = lon
        elif lon > max_lon:
            max_lon = lon
        if lat < min_lat:
            min_lat = lat
        elif lat > max_lat:
            max_lat = lat
    return [min_lon, min_lat, max_lon, max_lat]


def bbox_intersects(box_a, box_b):
    return not (
        box_a[0] > box_b[2]
        or box_a[2] < box_b[0]
        or box_a[1] > box_b[3]
        or box_a[3] < box_b[1]
    )


def intersect_bbox(a, b):
    box = [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]
    if box[0] > box[2] or box[1] > box[3]:
        return None
    return box


def clamp_name(value):
    if not value:
        return ""
    value = " ".join(str(value).split())
    if len(value) > NAME_MAX_LEN:
        value = value[:NAME_MAX_LEN]
    return value


def parse_population(value):
    """把 OSM population 标签解析为整数；无法解析返回 None。"""
    if not value:
        return None
    digits = []
    matched = False
    for ch in str(value):
        if ch.isdigit():
            digits.append(ch)
            matched = True
        elif matched and ch in " ,":
            continue
        elif matched:
            break
    if not digits:
        return None
    try:
        pop = int("".join(digits))
    except ValueError:
        return None
    if pop <= 0 or pop > 100_000_000:
        return None
    return pop


def valid_lonlat(lon, lat):
    """坐标合法性：范围、非空、非明显占位值 (0,0)。"""
    if lon is None or lat is None:
        return False
    if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
        return False
    if abs(lon) < 1e-9 and abs(lat) < 1e-9:
        return False
    return True


# ---------------------------------------------------------------------------
# multipolygon：环拼接
# ---------------------------------------------------------------------------

def assemble_rings(segments, node_coords, max_gap=RELATION_MAX_GAP_DEG):
    """把成员 way 的 node id 段缝合成环。

    segments: [[node_id, ...], ...]（每段 ≥2 点，允许首尾倒序、多段相接）
    返回 (rings, gaps_closed, dropped)：rings 为 node id 环（闭合），
    gaps_closed 为"端点缺口补闭合"的环数，dropped 为无法成环的链数。
    """
    pool = [list(s) for s in segments if len(s) >= 2]
    rings = []
    gaps_closed = 0
    dropped = 0
    while pool:
        cur = pool.pop(0)
        progressed = True
        while cur[0] != cur[-1] and progressed:
            progressed = False
            for i, seg in enumerate(pool):
                if seg[0] == cur[-1]:
                    cur = cur + seg[1:]
                elif seg[-1] == cur[-1]:
                    cur = cur + seg[::-1][1:]
                elif seg[-1] == cur[0]:
                    cur = seg + cur[1:]
                elif seg[0] == cur[0]:
                    cur = seg[::-1] + cur[1:]
                else:
                    continue
                pool.pop(i)
                progressed = True
                break
        if cur[0] == cur[-1]:
            rings.append(cur)
            continue
        # 开链容错：端点距离足够近时补闭合（OSM 里常见几米的缝隙）
        head = node_coords.get(cur[0])
        tail = node_coords.get(cur[-1])
        if (
            head is not None
            and tail is not None
            and abs(head[0] - tail[0]) <= max_gap
            and abs(head[1] - tail[1]) <= max_gap
        ):
            cur.append(cur[0])
            rings.append(cur)
            gaps_closed += 1
        else:
            dropped += 1
    return rings, gaps_closed, dropped


def refs_to_coords(refs, node_coords):
    """node id 环 → 坐标环；任一节点缺坐标则返回 None。"""
    coords = []
    for ref in refs:
        pt = node_coords.get(ref)
        if pt is None:
            return None
        coords.append(pt)
    return coords


def classify_rings_by_containment(rings):
    """无 role 时的奇偶回退：按面积降序，被包含次数为偶数的环当 outer。

    返回 (outer_rings, inner_rings)。
    """
    if not rings:
        return [], []
    ordered = sorted(rings, key=ring_area, reverse=True)
    contained_in = [[] for _ in ordered]
    for i, ring in enumerate(ordered):
        probe = ring[0]
        for j in range(i):
            if point_in_ring(probe, ordered[j]):
                contained_in[i].append(j)
    outers = []
    inners = []
    for i, ring in enumerate(ordered):
        if len(contained_in[i]) % 2 == 0:
            outers.append(ring)
        else:
            inners.append(ring)
    return outers, inners


def assign_holes(outers, inners):
    """把内环挂到包含它的最小 outer 上；返回 ([(outer, [inner...])...], 未挂上的 inner 数)。"""
    pairs = [[outer, []] for outer in outers]
    outer_areas = [ring_area(outer) for outer in outers]
    unassigned = 0
    for inner in inners:
        probe = inner[0]
        inner_area = ring_area(inner)
        best_idx = -1
        best_area = None
        for idx, outer in enumerate(outers):
            if outer_areas[idx] <= inner_area:
                continue
            if not point_in_ring(probe, outer):
                continue
            if best_area is None or outer_areas[idx] < best_area:
                best_area = outer_areas[idx]
                best_idx = idx
        if best_idx >= 0:
            pairs[best_idx][1].append(inner)
        else:
            unassigned += 1
    return pairs, unassigned


def rotate_ring_into_outer(outer, hole):
    """把闭合洞环旋转到"某顶点严格落在外环内"的起点；找不到返回 None。

    环简化（0.0005°）会把外环/洞的边界各自移动几十米，个别洞的起点可能被挤到
    简化后的外环之外。旋转起点既不改几何，又能保证消费方"洞在外环内"的判定成立。
    """
    base = hole[:-1]
    n = len(base)
    for idx in range(n):
        if point_in_ring(base[idx], outer):
            seq = base[idx:] + base[:idx]
            return seq + [seq[0]]
    return None


def relation_rings(plan, way_geoms, node_coords, skipped):
    """把一条 multipolygon 关系的成员 way 拼成 (outer, holes) 组。

    role 齐全 → 按 role 分 outer/inner；role 缺失或 outer 拼不出 → 按面积+包含奇偶回退。
    返回 [(outer_coords, [inner_coords...]), ...]（坐标环，已含首尾同点）。
    """
    outer_segs = []
    inner_segs = []
    all_segs = []
    has_explicit_role = False
    for way_id, role in plan["members"]:
        refs = way_geoms.get(way_id)
        if refs is None:
            skipped["relation_member_missing"] += 1
            continue
        all_segs.append(refs)
        if role == "inner":
            inner_segs.append(refs)
            has_explicit_role = True
        else:
            outer_segs.append(refs)
            if role == "outer":
                has_explicit_role = True

    outer_rings, gaps, dropped = assemble_rings(outer_segs, node_coords)
    inner_rings, gaps2, dropped2 = assemble_rings(inner_segs, node_coords)
    skipped["relation_open_chains_closed"] += gaps + gaps2
    skipped["relation_rings_dropped"] += dropped + dropped2

    outer_coords = [refs_to_coords(r, node_coords) for r in outer_rings]
    inner_coords = [refs_to_coords(r, node_coords) for r in inner_rings]
    outer_coords = [r for r in outer_coords if r]
    inner_coords = [r for r in inner_coords if r]

    if not has_explicit_role or not outer_coords:
        # 奇偶回退：忽略 role，重新拼全部段。这是"再试一次"的探索性拼接，
        # 缺口/丢弃已由上面的 role 分拼统计过，此处不再重复计数，避免统计虚高。
        all_rings, _gaps, _dropped = assemble_rings(all_segs, node_coords)
        coords = [refs_to_coords(r, node_coords) for r in all_rings]
        coords = [r for r in coords if r]
        outer_coords, inner_coords = classify_rings_by_containment(coords)

    if not outer_coords:
        return []
    pairs, unassigned = assign_holes(outer_coords, inner_coords)
    skipped["relation_inner_unassigned"] += unassigned
    return pairs


# ---------------------------------------------------------------------------
# pyosmium 处理句柄
# ---------------------------------------------------------------------------

def _import_osmium():
    try:
        import osmium  # noqa: F401
    except ImportError as exc:  # pragma: no cover - 环境问题
        sys.stderr.write(
            "[错误] 无法导入 pyosmium：%s\n"
            "       本机 pyosmium 安装在 .scratch/osm/pylibs，请先设置环境变量再运行：\n"
            "       PowerShell:  $env:PYTHONPATH = \"<项目根>\\.scratch\\osm\\pylibs\"\n"
            "       Bash:        export PYTHONPATH=\"<项目根>/.scratch/osm/pylibs\"\n" % exc
        )
        raise
    return osmium


def _classify_poly_tags(tags):
    """按面白名单判定类别；未命中返回 None。"""
    for (key, value), cls in POLY_TAG_RULES:
        if tags.get(key) == value:
            return cls
    return None


def _classify_tags(tags):
    """按 tag 白名单判定线/面类别；返回 (poly_cls, line_cls)，未命中均为 None。"""
    poly_cls = _classify_poly_tags(tags)
    if poly_cls is not None:
        return poly_cls, None
    hw = tags.get("highway")
    if hw in HIGHWAY_LINK_MAP:
        return None, HIGHWAY_LINK_MAP[hw]
    if hw in HIGHWAY_CLASSES:
        return None, hw
    rw = tags.get("railway")
    if rw in RAILWAY_CLASSES:
        return None, RAILWAY_CLASSES[rw]
    ww = tags.get("waterway")
    if ww in WATERWAY_LINE_CLASSES:
        return None, ww
    return None, None


def _way_segments(w):
    """把 way 的节点序列转成坐标段列表（可能多段），返回 (segments, bad_node_count)。

    遇到无法解析坐标的节点（悬空引用 / 越界补丁）不整条丢弃，而是切成多段有效折线，
    这样跨省界道路只损失缺口处，不会被误连成跨缺口的假线段。
    """
    segments = []
    cur = []
    bad = 0
    for nd in w.nodes:
        try:
            # pyosmium 4.x：NodeRef 直接暴露 ref/lon/lat；无坐标时抛 InvalidLocationError
            lon = nd.lon
            lat = nd.lat
        except Exception:
            bad += 1
            if len(cur) >= 2:
                segments.append(cur)
            cur = []
            continue
        if not valid_lonlat(lon, lat):
            bad += 1
            if len(cur) >= 2:
                segments.append(cur)
            cur = []
            continue
        cur.append((lon, lat))
    if len(cur) >= 2:
        segments.append(cur)
    return segments, bad


def _way_member_geometry(w):
    """成员 way → (node id 列表, 坐标列表)；任一节点无坐标则返回 (None, bad 数)。"""
    refs = []
    coords = []
    bad = 0
    for nd in w.nodes:
        try:
            lon = nd.lon
            lat = nd.lat
            ref = nd.ref
        except Exception:
            bad += 1
            continue
        if not valid_lonlat(lon, lat):
            bad += 1
            continue
        refs.append(ref)
        coords.append((lon, lat))
    if bad or len(refs) < 2:
        return None, bad
    return (refs, coords), 0


def _encode_place(tags, lon, lat):
    """place 节点 → 输出结构；返回 (payload, no_name)。"""
    place = PLACE_NODE_MAP.get(tags.get("place"))
    if place is None:
        return None, False
    name_zh = clamp_name(tags.get("name:zh") or tags.get("name:zh-Hans"))
    name = name_zh or clamp_name(tags.get("name"))
    if not name:
        return None, True
    payload = {
        "name": name,
        "name_zh": name_zh,
        "cls": place,
        "lon": round(lon, 5),
        "lat": round(lat, 5),
        "population": parse_population(tags.get("population")),
    }
    return payload, False


def _amenity_class(tags):
    """POI 的 `amenity` 白名单归一（大小写/空白容忍）；非白名单返回 None。"""
    amenity = str((tags or {}).get("amenity") or "").strip().lower()
    return amenity if amenity in POI_AMENITIES else None


def _encode_poi(tags, lon, lat, cls):
    """POI（学校/幼儿园/学院/大学）→ 输出结构；无名称返回 None。

    名称优先级与 places 一致：`name:zh`（含 `name:zh-Hans`）→ `name`，截断 100。
    `cls` 与 `amenity` 同值（渲染端按 cls 判断最小缩放与优先级）。
    """
    name_zh = clamp_name(tags.get("name:zh") or tags.get("name:zh-Hans"))
    name = name_zh or clamp_name(tags.get("name"))
    if not name:
        return None
    return {
        "name": name,
        "name_zh": name_zh,
        "cls": cls,
        "lon": round(lon, 5),
        "lat": round(lat, 5),
        "amenity": cls,
    }


def _way_centroid(segments):
    """way 的节点坐标质心（顶点均值）；无点返回 None。

    way 的 POI（学校/大学常以闭合面表示）用质心作为标签落点；顶点均值对
    凸/凹多边形都足够（仅用于注记定位，不参与几何计算）。
    """
    points = [point for segment in segments for point in segment]
    if not points:
        return None
    count = float(len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
    )


def scan_relations(osmium, in_path):
    """pass1：收集 multipolygon 关系。返回 (plans, member_way_ids)。

    plans: {relation_id: {"cls", "name", "members": [(way_id, role)]}}
    """
    plans = {}
    member_ways = set()

    class RelationHandler(osmium.SimpleHandler):
        def relation(self, r):
            tags = r.tags
            if tags.get("type") != "multipolygon":
                return
            cls = _classify_poly_tags(tags)
            if cls is None:
                return
            members = []
            for m in r.members:
                if m.type != "w":
                    continue
                role = "inner" if m.role == "inner" else ("outer" if m.role == "outer" else "")
                members.append((m.ref, role))
            if not members:
                return
            plans[r.id] = {
                "cls": cls,
                "name": clamp_name(tags.get("name:zh") or tags.get("name")),
                "members": members,
            }
            for way_id, _role in members:
                member_ways.add(way_id)

    handler = RelationHandler()
    handler.apply_file(str(in_path))
    return plans, member_ways


def build_handler(osmium, member_ways):  # noqa: C901 - 回调式分类逻辑集中在此，拆开反而难读
    """构造 pass2 用的 SimpleHandler（内部类继承 pyosmium 的 SimpleHandler）。"""

    class ExtractHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.raw_lines = []   # (cls, name, [(lon, lat), ...])
            self.raw_polys = []   # (cls, name, [(lon, lat), ...])  单 way 环
            self.raw_places = []  # dict
            self.raw_pois = []    # dict（v3：学校/幼儿园/学院/大学）
            self.way_geoms = {}   # way_id -> [node_id, ...]（仅 multipolygon 成员 way）
            self.node_coords = {}  # node_id -> (lon, lat)（仅成员 way 用到的节点）
            self.node_bbox = None
            self.node_count = 0
            self.way_count = 0
            self.relation_count = 0
            self.member_way_hits = 0
            self.skipped = {
                "node_bad_coord": 0,
                "place_no_name": 0,
                "poi_no_name": 0,
                "way_no_geometry": 0,
                "way_bad_coord": 0,
                "way_no_class": 0,
                "way_member_bad_geometry": 0,
                "line_too_short": 0,
                "ring_not_closed": 0,
                "ring_too_short": 0,
                "ring_zero_area": 0,
                "relation_member_missing": 0,
                "relation_open_chains_closed": 0,
                "relation_rings_dropped": 0,
                "relation_hole_dropped": 0,
                "relation_hole_too_short": 0,
                "relation_hole_area_invalid": 0,
                "relation_hole_outside": 0,
                "relation_inner_unassigned": 0,
                "relation_no_outer": 0,
                "relation_all_filtered": 0,
                "out_of_bbox": 0,
            }

        # -- 节点：地名点 + 数据范围 ----------------------------------------
        def node(self, n):
            self.node_count += 1
            try:
                lon = n.lon
                lat = n.lat
            except Exception:  # osmium 对无坐标节点抛 InvalidLocationError
                self.skipped["node_bad_coord"] += 1
                return
            if not valid_lonlat(lon, lat):
                self.skipped["node_bad_coord"] += 1
                return
            # 数据实际范围必须覆盖**所有**节点（含无 tag 的几何点），否则会被误判越界
            self.node_bbox = bbox_of(((lon, lat),), self.node_bbox)

            tags = n.tags
            if not tags:
                return
            payload, no_name = _encode_place(tags, lon, lat)
            if no_name:
                self.skipped["place_no_name"] += 1
            elif payload is not None:
                self.raw_places.append(payload)
            # v3 POI：学校/幼儿园/学院/大学节点（与 place 互斥，amenity 挂在独立 tag 上）
            poi_cls = _amenity_class(tags)
            if poi_cls is not None:
                poi = _encode_poi(tags, lon, lat, poi_cls)
                if poi is None:
                    self.skipped["poi_no_name"] += 1
                else:
                    self.raw_pois.append(poi)

        # -- way：线 / 面 / multipolygon 成员几何 ----------------------------
        def way(self, w):
            self.way_count += 1
            way_id = w.id
            tags = w.tags
            is_member = way_id in member_ways
            if is_member:
                self.member_way_hits += 1
                geom, bad = _way_member_geometry(w)
                if geom is None:
                    self.skipped["way_member_bad_geometry"] += 1
                    self.skipped["way_bad_coord"] += bad
                else:
                    refs, coords = geom
                    self.way_geoms[way_id] = refs
                    for ref, pt in zip(refs, coords):
                        self.node_coords[ref] = pt
            if not tags:
                return
            poly_cls, line_cls = _classify_tags(tags)
            poi_cls = _amenity_class(tags)
            if poly_cls is None and line_cls is None and poi_cls is None:
                self.skipped["way_no_class"] += 1
                return

            segments, bad = _way_segments(w)
            self.skipped["way_bad_coord"] += bad
            if not segments:
                self.skipped["way_no_geometry"] += 1
                return

            # v3 POI：way（多为闭合面，如学校/大学）用节点坐标质心作为标签落点
            if poi_cls is not None:
                centroid = _way_centroid(segments)
                if centroid is None:
                    self.skipped["way_no_geometry"] += 1
                else:
                    poi = _encode_poi(tags, centroid[0], centroid[1], poi_cls)
                    if poi is None:
                        self.skipped["poi_no_name"] += 1
                    else:
                        self.raw_pois.append(poi)
            if poly_cls is None and line_cls is None:
                # 纯 POI way（如 amenity=school 的边界），不进入线/面图层
                return

            name = clamp_name(tags.get("name:zh") or tags.get("name"))

            if poly_cls is not None:
                # 成员 way 的面交给关系拼接，避免与关系结果重复
                if is_member:
                    return
                # 只有"无缺口且首尾同点"的 way 才能当环；被切断的环直接丢弃
                coords = segments[0]
                if len(segments) != 1 or len(coords) < 4 or coords[0] != coords[-1]:
                    self.skipped["ring_not_closed"] += 1
                    return
                self.raw_polys.append((poly_cls, name, coords))
            else:
                for coords in segments:
                    self.raw_lines.append((line_cls, name, coords))

        # -- relation：只计数（关系在 pass1 已收集） -------------------------
        def relation(self, r):
            self.relation_count += 1

    return ExtractHandler()


# ---------------------------------------------------------------------------
# 后处理：bbox 过滤 + 简化 + 关系拼接
# ---------------------------------------------------------------------------

def build_layers(handler, filter_bbox, line_tol, ring_tol):
    """单 way 要素：过滤、简化、舍入成输出结构。"""
    skipped = handler.skipped
    lines = []
    line_counts = {c: 0 for c in LINE_CLASSES}
    out_bbox = None

    for cls, name, coords in handler.raw_lines:
        box = bbox_of(coords)
        if filter_bbox is not None and not bbox_intersects(box, filter_bbox):
            skipped["out_of_bbox"] += 1
            continue
        simplified = douglas_peucker(coords, line_tol)
        rounded = round_line(simplified)
        if len(rounded) < 2:
            skipped["line_too_short"] += 1
            continue
        lines.append({"cls": cls, "name": name, "coords": rounded})
        line_counts[cls] += 1
        out_bbox = bbox_of(rounded, out_bbox)
    handler.raw_lines = []  # 及时释放原始几何，降低出包时的峰值内存

    polys = []
    poly_counts = {c: 0 for c in POLY_CLASSES}
    for cls, name, coords in handler.raw_polys:
        box = bbox_of(coords)
        if filter_bbox is not None and not bbox_intersects(box, filter_bbox):
            skipped["out_of_bbox"] += 1
            continue
        rounded = simplify_and_round_ring(coords, ring_tol)
        if len(rounded) < 4:
            skipped["ring_too_short"] += 1
            continue
        if ring_area(rounded) <= MIN_RING_AREA:
            skipped["ring_zero_area"] += 1
            continue
        polys.append({"cls": cls, "name": name, "rings": [rounded], "holes": []})
        poly_counts[cls] += 1
        out_bbox = bbox_of(rounded, out_bbox)
    handler.raw_polys = []

    places = []
    place_counts = {c: 0 for c in PLACE_CLASSES}
    seen_places = set()
    for place in handler.raw_places:
        if filter_bbox is not None and not (
            filter_bbox[0] <= place["lon"] <= filter_bbox[2]
            and filter_bbox[1] <= place["lat"] <= filter_bbox[3]
        ):
            skipped["out_of_bbox"] += 1
            continue
        key = (place["name"], place["cls"], place["lon"], place["lat"])
        if key in seen_places:
            continue
        seen_places.add(key)
        places.append(place)
        place_counts[place["cls"]] += 1
        out_bbox = bbox_of(((place["lon"], place["lat"]),), out_bbox)
    handler.raw_places = []

    return lines, line_counts, polys, poly_counts, places, place_counts, out_bbox


def build_pois(handler, filter_bbox):
    """v3 POI 后处理：bbox 过滤 + 去重 + 分类计数；返回 (pois, counts, bbox)。

    与 places 同口径：点必须在过滤框内才保留；同名同类同坐标视为重复（节点+way
    质心可能重合）。处理完清空 handler.raw_pois 及时释放内存。
    """
    skipped = handler.skipped
    pois = []
    counts = {cls: 0 for cls in POI_AMENITIES}
    seen = set()
    out_bbox = None
    for poi in handler.raw_pois:
        if filter_bbox is not None and not (
            filter_bbox[0] <= poi["lon"] <= filter_bbox[2]
            and filter_bbox[1] <= poi["lat"] <= filter_bbox[3]
        ):
            skipped["out_of_bbox"] += 1
            continue
        key = (poi["name"], poi["cls"], poi["lon"], poi["lat"])
        if key in seen:
            continue
        seen.add(key)
        pois.append(poi)
        counts[poi["cls"]] += 1
        out_bbox = bbox_of(((poi["lon"], poi["lat"]),), out_bbox)
    handler.raw_pois = []
    return pois, counts, out_bbox


def _relation_poly_entry(plan, outer_ring, holes):
    return {"cls": plan["cls"], "name": plan["name"], "rings": [outer_ring], "holes": holes}


def build_relation_layers(plans, way_geoms, node_coords, filter_bbox, ring_tol, hole_tol, skipped):
    """把 multipolygon 关系拼成 polys 条目；返回 (polys, counts, fail_ids, bbox)。"""
    polys = []
    poly_counts = {c: 0 for c in POLY_CLASSES}
    fail_ids = []
    holes_total = 0
    assembled = 0
    out_bbox = None

    for rel_id, plan in plans.items():
        groups = relation_rings(plan, way_geoms, node_coords, skipped)
        if not groups:
            skipped["relation_no_outer"] += 1
            if len(fail_ids) < RELATION_FAIL_SAMPLE_LIMIT:
                fail_ids.append(rel_id)
            continue
        emitted = 0
        for outer_coords, hole_coords in groups:
            outer_bbox = bbox_of(outer_coords)
            if filter_bbox is not None and not bbox_intersects(outer_bbox, filter_bbox):
                skipped["out_of_bbox"] += 1
                continue
            outer_ring = simplify_and_round_ring(outer_coords, ring_tol)
            if len(outer_ring) < 4:
                skipped["ring_too_short"] += 1
                continue
            outer_area = ring_area(outer_ring)
            if outer_area <= MIN_RING_AREA:
                skipped["ring_zero_area"] += 1
                continue
            holes = []
            for hole in hole_coords:
                hole_ring = simplify_and_round_ring(hole, hole_tol)
                if len(hole_ring) < 4:
                    skipped["relation_hole_too_short"] += 1
                    skipped["relation_hole_dropped"] += 1
                    continue
                hole_area = ring_area(hole_ring)
                if hole_area <= MIN_RING_AREA or hole_area >= outer_area:
                    skipped["relation_hole_area_invalid"] += 1
                    skipped["relation_hole_dropped"] += 1
                    continue
                rotated = rotate_ring_into_outer(outer_ring, hole_ring)
                if rotated is None:
                    skipped["relation_hole_outside"] += 1
                    skipped["relation_hole_dropped"] += 1
                    continue
                holes.append(rotated)
            polys.append(_relation_poly_entry(plan, outer_ring, holes))
            poly_counts[plan["cls"]] += 1
            holes_total += len(holes)
            emitted += 1
            out_bbox = bbox_of(outer_ring, out_bbox)
        if emitted:
            assembled += 1
        else:
            # 关系拼出了环，但全部被「越界 / 退化几何」过滤掉
            skipped["relation_all_filtered"] += 1
            if len(fail_ids) < RELATION_FAIL_SAMPLE_LIMIT:
                fail_ids.append(rel_id)
    counts = {
        "relations_total": len(plans),
        "relations_assembled": assembled,
        "relations_failed": len(plans) - assembled,
        "holes_total": holes_total,
    }
    return polys, poly_counts, counts, fail_ids, out_bbox


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------

def atomic_write_pickle(path, payload):
    """先写 <out>.tmp 再 os.replace 原子替换，避免渲染端读到半个文件。"""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "wb") as fh:
        pickle.dump(payload, fh, protocol=4)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def atomic_write_json(path, payload):
    """统计 JSON 同样原子落盘（先 .tmp 再 os.replace）。"""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def force_utf8_stdio():
    """Windows 控制台/管道默认 cp936，遇到 '©' 会 UnicodeEncodeError；统一按 UTF-8 输出。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def human_bytes(n):
    return "%.2f MB" % (n / 1024.0 / 1024.0) if n >= 1024 else "%d B" % n


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

class _CliError(Exception):
    """参数/环境问题（退出码 2）。"""


class _DataError(Exception):
    """PBF 解析失败（退出码 3）。"""


class _OutputError(Exception):
    """落盘或体积门禁失败（退出码 4）。"""


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="osm_extract.py",
        description="从贵州省 OSM PBF 提取包抽取离线渲染图层（道路/水系/面状地物/地名/POI + "
                    "multipolygon 关系拼接），原子写出 layers.pkl（schema v3）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/tiles/osm_extract.py --input .scratch/osm/guizhou.osm.pbf "
            "--output .scratch/osm/layers-v3.pkl --stats\n"
            "  python scripts/tiles/osm_extract.py --input guizhou.osm.pbf --no-relations\n"
            "\n退出码: 0 成功 / 2 环境或参数错误 / 3 数据解析失败 / 4 落盘或体积门禁失败\n"
        ),
    )
    parser.add_argument("--input", "-i", required=True, help="输入 .osm.pbf 路径")
    parser.add_argument(
        "--output",
        "-o",
        default=".scratch/osm/layers.pkl",
        help="输出 pickle 路径（默认 .scratch/osm/layers.pkl）",
    )
    parser.add_argument(
        "--stats", action="store_true", help="结束时把统计信息以 JSON 打到 stdout"
    )
    parser.add_argument(
        "--stats-json",
        default=None,
        help="统计 JSON 落盘路径（默认在 --output 同目录写 extract_stats.json）",
    )
    parser.add_argument(
        "--bbox",
        default=None,
        help="过滤范围 min_lon,min_lat,max_lon,max_lat（默认 %s；与数据实际范围取交集）"
        % (",".join("%g" % v for v in DEFAULT_FILTER_BBOX),),
    )
    parser.add_argument(
        "--line-tolerance",
        type=float,
        default=LINE_TOLERANCE,
        help="线要素 Douglas-Peucker 容差（度，默认 %g ≈ 30m）" % LINE_TOLERANCE,
    )
    parser.add_argument(
        "--ring-tolerance",
        type=float,
        default=RING_TOLERANCE,
        help="面要素环简化容差（度，默认 %g ≈ 50m）" % RING_TOLERANCE,
    )
    parser.add_argument(
        "--hole-tolerance",
        type=float,
        default=HOLE_TOLERANCE,
        help="面要素内环（岛屿）简化容差（度，默认 %g ≈ 22m；比外环细以保住小岛）"
        % HOLE_TOLERANCE,
    )
    parser.add_argument(
        "--no-simplify", action="store_true", help="关闭几何简化（体积会明显变大，仅排错用）"
    )
    parser.add_argument(
        "--no-relations",
        action="store_true",
        help="跳过 multipolygon 关系（不做 pass1/pass2 关系拼接，退回 v1 行为，仅排错用）",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="输出体积上限（默认 %d MB），超过则非零退出（0 表示不限制）"
        % (DEFAULT_MAX_BYTES // 1024 // 1024),
    )
    parser.add_argument("--quiet", action="store_true", help="只输出错误与最终统计")
    return parser, parser.parse_args(argv)


def _parse_bbox(text):
    try:
        box = tuple(float(x) for x in text.split(","))
    except ValueError:
        raise _CliError("[错误] --bbox 需要 4 个逗号分隔的数字，例如 103.5,24.5,109.7,29.3")
    if len(box) != 4 or box[0] >= box[2] or box[1] >= box[3]:
        raise _CliError("[错误] --bbox 需满足 min_lon<max_lon 且 min_lat<max_lat")
    return box


def _prepare_inputs(args):
    """校验输入文件与过滤框；返回 (in_path, in_bytes, filter_bbox)，失败抛 _CliError。"""
    in_path = Path(args.input)
    if not in_path.is_file():
        raise _CliError("[错误] 输入文件不存在：%s" % in_path)
    in_bytes = in_path.stat().st_size
    if in_bytes <= 0:
        raise _CliError("[错误] 输入文件为空（可能仍在下载）：%s" % in_path)
    if in_bytes < 1024:
        raise _CliError("[错误] 输入文件过小，疑似下载不完整：%s（%d B）" % (in_path, in_bytes))
    return in_path, in_bytes, (_parse_bbox(args.bbox) if args.bbox else DEFAULT_FILTER_BBOX)


def _header_bbox(osmium, in_path, log):
    """读文件头 bbox（仅日志信息；OpenStreetMap.fr 提取包常不带 header bbox）。"""
    try:
        header = osmium.FileProcessor(str(in_path)).header
        if callable(header):  # 兼容把 header 实现为方法的 pyosmium 版本
            header = header()
        hb = header.box()
        if not hb.valid():
            return None
        box = [hb.bottom_left.lon, hb.bottom_left.lat, hb.top_right.lon, hb.top_right.lat]
        log("      文件头 bbox：%s" % ", ".join("%.4f" % v for v in box))
        return box
    except Exception as exc:  # 头信息不可用不影响主流程
        log("      （文件头信息不可用：%s）" % exc)
        return None


def _scan_relations(osmium, in_path, log):
    """pass1：只读 relation。返回 (plans, member_ways)。失败抛 _DataError。"""
    log("[2/5] pass1：扫描 multipolygon 关系（不带 locations）…")
    try:
        plans, member_ways = scan_relations(osmium, in_path)
    except Exception as exc:
        raise _DataError("[错误] pass1 解析失败：%s" % exc) from exc
    log("      关系 %d 个，涉及成员 way %d 条" % (len(plans), len(member_ways)))
    return plans, member_ways


def _scan(osmium, in_path, member_ways, log, t_start):
    """pass2：主扫描（线/点/单 way 面 + 成员 way 几何）。返回 (handler, 耗时秒)。"""
    handler = build_handler(osmium, member_ways)
    log("[3/5] pass2：单次扫描 + 分类抽取（locations=True，全内存）…")
    try:
        # pyosmium 4.x 入口：apply_file(locations=True) 会先建"节点 id → 坐标"索引，
        # 随后 way 回调里可直接读 node 坐标。
        handler.apply_file(str(in_path), locations=True)
    except Exception as exc:
        raise _DataError(
            "[错误] PBF 解析失败：%s\n       常见原因：文件下载不完整 / 不是有效 .osm.pbf。" % exc
        ) from exc
    t_scan = time.time() - t_start
    log(
        "      节点 %d、way %d、relation %d；成员 way 命中 %d 条；节点 bbox=%s"
        % (
            handler.node_count,
            handler.way_count,
            handler.relation_count,
            handler.member_way_hits,
            ("[%.4f, %.4f, %.4f, %.4f]" % tuple(handler.node_bbox)) if handler.node_bbox else "无",
        )
    )
    return handler, t_scan


def _used_filter_bbox(handler, filter_bbox):
    """数据实际范围 ∩ 过滤框；pbf 若带邻省缓冲，省外要素在此被挡掉。"""
    if handler.node_bbox is None:
        return filter_bbox
    used = intersect_bbox(handler.node_bbox, filter_bbox)
    if used is None:
        sys.stderr.write(
            "[警告] 数据范围与 --bbox 不相交，输出可能为空；数据 bbox=%s\n"
            % ("%.4f, %.4f, %.4f, %.4f" % tuple(handler.node_bbox))
        )
        return filter_bbox
    return used


def _build_payload(in_path, in_bytes, data_bbox, counts, lines, polys, places, pois, fail_ids):
    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "source_file": in_path.name,
            "source_bytes": in_bytes,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "bbox": [round(v, 5) for v in data_bbox],
            "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
            "relation_fail_sample_ids": fail_ids,
            "counts": counts,
        },
        "lines": lines,
        "polys": polys,
        "places": places,
        "pois": pois,
    }


def _fmt_counts(counts):
    return "、".join("%s %d" % (k, v) for k, v in counts.items() if v) or "无"


def _write_output(out_path, payload, max_bytes, log):
    """原子写出 pkl 并做体积门禁；返回字节数，失败抛 _OutputError。"""
    log("[5/5] 原子写出：%s" % out_path)
    try:
        atomic_write_pickle(out_path, payload)
    except OSError as exc:
        raise _OutputError("[错误] 写入失败：%s" % exc) from exc
    out_bytes = out_path.stat().st_size
    if max_bytes and out_bytes > max_bytes:
        raise _OutputError(
            "[错误] 输出体积 %s 超过上限 %s；可调大 --line-tolerance/--ring-tolerance 或加 --max-bytes 0"
            % (human_bytes(out_bytes), human_bytes(max_bytes))
        )
    return out_bytes


def _log_report(log, out_path, out_bytes, data_bbox, counts, skipped, t_scan, t_total):
    log("")
    log("=== 提取完成（schema v%d）===" % SCHEMA_VERSION)
    log("输出：%s（%s）" % (out_path, human_bytes(out_bytes)))
    log("bbox：%s" % ", ".join("%.5f" % v for v in data_bbox))
    log("线 %d 条：%s" % (sum(counts["lines"].values()), _fmt_counts(counts["lines"])))
    log("面 %d 个：%s" % (sum(counts["polys"].values()), _fmt_counts(counts["polys"])))
    log("点 %d 个：%s" % (sum(counts["places"].values()), _fmt_counts(counts["places"])))
    log("POI %d 个：%s" % (sum(counts["pois"].values()), _fmt_counts(counts["pois"])))
    log(
        "关系：总计 %d、成功 %d、失败 %d、洞 %d"
        % (
            counts.get("relations_total", 0),
            counts.get("relations_assembled", 0),
            counts.get("relations_failed", 0),
            counts.get("holes_total", 0),
        )
    )
    log("跳过 %d：%s" % (sum(skipped.values()), _fmt_counts(skipped)))
    log("耗时：扫描 %.1fs / 合计 %.1fs" % (t_scan, t_total))
    log("许可：%s（%s）" % (LICENSE, ATTRIBUTION))


def _write_stats(
    args,
    payload,
    in_path,
    in_bytes,
    out_path,
    out_bytes,
    counts,
    skipped,
    t_scan,
    t_total,
    header_bbox,
    log,
):
    """--stats：统计 JSON 落盘 + 打到 stdout；未启用时返回 None。"""
    if not args.stats:
        return None
    stats_path = (
        Path(args.stats_json) if args.stats_json else Path(args.output).parent / "extract_stats.json"
    )
    stats = {
        "schema_version": SCHEMA_VERSION,
        "output": str(out_path),
        "output_bytes": out_bytes,
        "input": str(in_path),
        "input_bytes": in_bytes,
        "bbox": payload["meta"]["bbox"],
        "counts": counts,
        "totals": {
            "lines": sum(counts["lines"].values()),
            "polys": sum(counts["polys"].values()),
            "places": sum(counts["places"].values()),
            "pois": sum(counts["pois"].values()),
            "skipped": sum(skipped.values()),
        },
        "relation_fail_sample_ids": payload["meta"]["relation_fail_sample_ids"],
        "scan_seconds": round(t_scan, 2),
        "total_seconds": round(t_total, 2),
        "header_bbox": header_bbox,
        "stats_json": str(stats_path),
    }
    try:
        atomic_write_json(stats_path, stats)
        log("统计 JSON：%s" % stats_path)
    except OSError as exc:
        sys.stderr.write("[警告] 统计 JSON 写入失败：%s\n" % exc)
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)
    return stats


def main(argv=None):
    force_utf8_stdio()
    parser, args = parse_args(argv)
    t_start = time.time()

    def log(msg):
        if not args.quiet:
            print(msg, flush=True)

    try:
        osmium = _import_osmium()
        in_path, in_bytes, filter_bbox = _prepare_inputs(args)
    except ImportError:
        return EXIT_ENV
    except _CliError as exc:
        sys.stderr.write("%s\n" % exc)
        return EXIT_ENV

    log("[1/5] 读取 PBF：%s（%s），schema v%d" % (in_path, human_bytes(in_bytes), SCHEMA_VERSION))
    header_bbox = _header_bbox(osmium, in_path, log)

    plans = {}
    member_ways = set()
    try:
        if args.no_relations:
            log("[2/5] 已指定 --no-relations，跳过 multipolygon 关系")
        else:
            plans, member_ways = _scan_relations(osmium, in_path, log)
        handler, t_scan = _scan(osmium, in_path, member_ways, log, t_start)
    except _DataError as exc:
        sys.stderr.write("%s\n" % exc)
        return EXIT_DATA

    line_tol = 0.0 if args.no_simplify else args.line_tolerance
    ring_tol = 0.0 if args.no_simplify else args.ring_tolerance
    hole_tol = 0.0 if args.no_simplify else args.hole_tolerance
    used_bbox = _used_filter_bbox(handler, filter_bbox)
    log(
        "[3/5] 过滤/简化（线容差 %g、环容差 %g；过滤框 %s）…"
        % (line_tol, ring_tol, ", ".join("%.4f" % v for v in used_bbox))
    )
    lines, line_counts, polys, poly_counts, places, place_counts, data_bbox = build_layers(
        handler, used_bbox, line_tol, ring_tol
    )
    pois, poi_counts, poi_bbox = build_pois(handler, used_bbox)
    if poi_bbox is not None:
        data_bbox = bbox_of(((poi_bbox[0], poi_bbox[1]), (poi_bbox[2], poi_bbox[3])), data_bbox)

    log("[4/5] 拼接 multipolygon 关系（按 node id 缝合，role/包含关系判定内外环）…")
    rel_polys, rel_poly_counts, relation_counts, fail_ids, rel_bbox = build_relation_layers(
        plans,
        handler.way_geoms,
        handler.node_coords,
        used_bbox,
        ring_tol,
        hole_tol,
        handler.skipped,
    )
    for cls, cnt in rel_poly_counts.items():
        poly_counts[cls] = poly_counts.get(cls, 0) + cnt
    if rel_bbox is not None:
        data_bbox = bbox_of(((rel_bbox[0], rel_bbox[1]), (rel_bbox[2], rel_bbox[3])), data_bbox)
    polys.extend(rel_polys)
    handler.way_geoms = {}
    handler.node_coords = {}

    if data_bbox is None:
        data_bbox = [round(v, 5) for v in used_bbox]
    counts = {
        "lines": line_counts,
        "polys": poly_counts,
        "places": place_counts,
        "pois": poi_counts,
        "skipped": handler.skipped,
    }
    counts.update(relation_counts)
    payload = _build_payload(
        in_path, in_bytes, data_bbox, counts, lines, polys, places, pois, fail_ids
    )

    out_path = Path(args.output)
    try:
        out_bytes = _write_output(out_path, payload, args.max_bytes, log)
    except _OutputError as exc:
        sys.stderr.write("%s\n" % exc)
        return EXIT_OUTPUT

    t_total = time.time() - t_start
    _log_report(
        log, out_path, out_bytes, payload["meta"]["bbox"], counts, handler.skipped, t_scan, t_total
    )
    _write_stats(
        args,
        payload,
        in_path,
        in_bytes,
        out_path,
        out_bytes,
        counts,
        handler.skipped,
        t_scan,
        t_total,
        header_bbox,
        log,
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
