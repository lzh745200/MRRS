#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用项目内置 GeoJSON 离线渲染"示意瓦片包"（Web Mercator XYZ）。

用途
----
在没有授权底图、也不能批量抓取公共瓦片服务时，生成一套**完全本地、无外部数据**
的示意底图（省界 + 地州界 + 县市界 + 地名），可直接被本系统导入并在
「地图可视化 → 瓦片底图」中查看。

它与真实底图的差别（务必如实告知使用方）：
- 只有行政边界与地名，没有道路/水系/影像；
- 不能替代授权底图用于正式汇报底图，只作离线示意/联调/验收占位。

数据来源：``frontend/src/assets/geo/guizhou.json``（项目自带，88 个县级 feature）。
输出结构：``<out>/{z}/{x}/{y}.png`` + ``<out>/MANIFEST.json``（与 scripts/tiles
其余工具、后端 import 端点同一口径）。

用法
----
python scripts/tiles/render_schematic_tiles.py --zoom 5-10 --out resources/map-tiles
python scripts/tiles/render_schematic_tiles.py --zoom 5-12 --zip deliverables/guizhou-tiles.zip
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

TILE_SIZE = 256
ROOT = Path(__file__).resolve().parents[2]
GEOJSON = ROOT / "frontend" / "src" / "assets" / "geo" / "guizhou.json"

# 贵州省整体 bbox（含全部 9 个地州 / 88 个县市区）
GUIZHOU_BBOX = [103.6, 24.6, 109.6, 29.2]

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhl.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def project(lon: float, lat: float, z: int) -> tuple[float, float]:
    """经纬度 → 该缩放级下的世界像素坐标（EPSG:3857 Web Mercator）。"""
    world = TILE_SIZE * (2 ** z)
    x = (lon + 180.0) / 360.0 * world
    lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * world
    return x, y


def tile_range(bbox, z):
    min_lon, min_lat, max_lon, max_lat = bbox
    x0, y0 = project(min_lon, max_lat, z)
    x1, y1 = project(max_lon, min_lat, z)
    return (
        int(x0 // TILE_SIZE),
        int(y0 // TILE_SIZE),
        int(x1 // TILE_SIZE),
        int(y1 // TILE_SIZE),
    )


def iter_polygons(geom):
    """统一产出 ring 列表（Polygon / MultiPolygon）。"""
    if geom["type"] == "Polygon":
        yield geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly


def load_features():
    data = json.loads(GEOJSON.read_text(encoding="utf-8"))
    feats = []
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        name = str(props.get("name") or "").strip()
        if not name:
            continue
        feats.append(
            {
                "name": name,
                "prefecture": str(props.get("prefecture") or "").strip(),
                "pref_adcode": str(props.get("pref_adcode") or ""),
                "center": props.get("center"),
                "geom": feature.get("geometry"),
            }
        )
    return data.get("features", []), feats


def load_font(size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None


def prefecture_centers(feats):
    """按地州聚合县级 center，得到地州标签锚点。"""
    buckets: dict[str, list] = {}
    for feat in feats:
        center = feat.get("center")
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            buckets.setdefault(feat["prefecture"], []).append((float(center[0]), float(center[1])))
    out = {}
    for pref, pts in buckets.items():
        if not pts:
            continue
        out[pref] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return out


def draw_tile(z, tx, ty, features, feats, pref_centers, license_note):  # noqa: C901
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (247, 250, 247))
    draw = ImageDraw.Draw(img)

    origin_x, origin_y = tx * TILE_SIZE, ty * TILE_SIZE

    def to_px(lon, lat):
        wx, wy = project(lon, lat, z)
        return (wx - origin_x, wy - origin_y)

    palette = {}
    base_colors = [
        (232, 241, 233), (226, 238, 229), (238, 243, 231), (231, 240, 236),
        (240, 238, 230), (230, 237, 241), (237, 234, 241), (234, 241, 234),
        (238, 236, 228),
    ]

    # 县级面（浅色区分地州）
    for feat in feats:
        pref_key = feat["pref_adcode"] or feat["prefecture"]
        if pref_key not in palette:
            palette[pref_key] = base_colors[len(palette) % len(base_colors)]
        fill = palette[pref_key]
        geom = feat["geom"]
        if not geom:
            continue
        for poly in iter_polygons(geom):
            for ring in poly:
                pts = [to_px(p[0], p[1]) for p in ring if len(p) >= 2]
                if len(pts) < 3:
                    continue
                if max(p[0] for p in pts) < -8 or min(p[0] for p in pts) > TILE_SIZE + 8:
                    continue
                if max(p[1] for p in pts) < -8 or min(p[1] for p in pts) > TILE_SIZE + 8:
                    continue
                draw.polygon(pts, fill=fill)

    # 县界 + 结合部线
    for feat in feats:
        geom = feat["geom"]
        if not geom:
            continue
        for poly in iter_polygons(geom):
            for ring in poly:
                pts = [to_px(p[0], p[1]) for p in ring if len(p) >= 2]
                if len(pts) < 3:
                    continue
                if (
                    max(p[0] for p in pts) < -8
                    or min(p[0] for p in pts) > TILE_SIZE + 8
                    or max(p[1] for p in pts) < -8
                    or min(p[1] for p in pts) > TILE_SIZE + 8
                ):
                    continue
                draw.line(pts + [pts[0]], fill=(150, 168, 152), width=1)

    # 地名（z>=7 地州；z>=10 县市）
    if z >= 7:
        font = load_font(15 if z < 9 else 17)
        if font is not None:
            for pref, (lon, lat) in pref_centers.items():
                px, py = to_px(lon, lat)
                if -60 <= px <= TILE_SIZE + 60 and -20 <= py <= TILE_SIZE + 20:
                    text = pref.replace("布依族苗族自治州", "").replace("苗族侗族自治州", "")
                    text = text.replace("自治州", "").replace("地区", "")
                    draw.text((px, py), text, fill=(70, 92, 74), font=font, anchor="mm")
    if z >= 10:
        font = load_font(11)
        if font is not None:
            for feat in feats:
                center = feat.get("center")
                if not (isinstance(center, (list, tuple)) and len(center) >= 2):
                    continue
                px, py = to_px(float(center[0]), float(center[1]))
                if 0 <= px <= TILE_SIZE and 0 <= py <= TILE_SIZE:
                    draw.text((px, py), feat["name"], fill=(96, 112, 98), font=font, anchor="mm")

    if z <= 6:
        font = load_font(20)
        if font is not None:
            draw.text(
                (TILE_SIZE - 8, TILE_SIZE - 8),
                "示意底图",
                fill=(176, 190, 178),
                font=font,
                anchor="rs",
            )
    return img


def main(argv=None) -> int:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="用项目内置 GeoJSON 离线渲染示意瓦片包（无外部数据、可离线）"
    )
    parser.add_argument("--zoom", default="5-10", help="缩放范围，如 5-10（默认 5-10）")
    parser.add_argument("--bbox", default=",".join(str(v) for v in GUIZHOU_BBOX),
                        help="经纬度范围 min_lon,min_lat,max_lon,max_lat（默认贵州省全域）")
    parser.add_argument("--out", default="resources/map-tiles", help="输出目录")
    parser.add_argument("--zip", dest="zip_path", default=None, help="同时打包为 ZIP（可选）")
    parser.add_argument("--hashes", action="store_true", help="在 MANIFEST 记录每瓦片 SHA256")
    parser.add_argument("--dry-run", action="store_true", help="只统计数量，不渲染")
    args = parser.parse_args(argv)

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("[错误] 需要 Pillow：backend/.venv/Scripts/python.exe -m pip install pillow", file=sys.stderr)
        return 3

    if not GEOJSON.is_file():
        print(f"[错误] 找不到 GeoJSON：{GEOJSON}", file=sys.stderr)
        return 2

    try:
        zoom_min, zoom_max = (int(x) for x in args.zoom.split("-", 1))
    except ValueError:
        print("[错误] --zoom 需形如 5-10", file=sys.stderr)
        return 2
    if zoom_min > zoom_max or zoom_min < 0 or zoom_max > 18:
        print("[错误] 缩放范围非法（0<=min<=max<=18）", file=sys.stderr)
        return 2

    try:
        bbox = [float(x) for x in args.bbox.split(",")]
        if len(bbox) != 4:
            raise ValueError
    except ValueError:
        print("[错误] --bbox 需为 min_lon,min_lat,max_lon,max_lat", file=sys.stderr)
        return 2

    _, feats = load_features()
    if not feats:
        print("[错误] GeoJSON 中没有任何 feature", file=sys.stderr)
        return 2

    plan = []
    for z in range(zoom_min, zoom_max + 1):
        x0, y0, x1, y1 = tile_range(bbox, z)
        plan.append((z, x0, y0, x1, y1, (x1 - x0 + 1) * (y1 - y0 + 1)))

    total_tiles = sum(item[5] for item in plan)
    print(f"数据源: 项目内置 GeoJSON（{len(feats)} 个县级要素）")
    print(f"bbox: {tuple(bbox)}  缩放: {zoom_min}-{zoom_max}  瓦片总数: {total_tiles}")
    for z, x0, y0, x1, y1, n in plan:
        print(f"  z{z:<2} {n:5d} 张（x {x0}-{x1}, y {y0}-{y1}）")
    if args.dry_run:
        print("dry-run 完成：未渲染、未写盘。")
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    pref_centers = prefecture_centers(feats)

    total_bytes = 0
    hashes: dict[str, str] = {}
    rendered = 0
    for z, x0, y0, x1, y1, _ in plan:
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                img = draw_tile(z, tx, ty, None, feats, pref_centers, "")
                target = out_dir / str(z) / str(tx) / f"{ty}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                img.save(target, "PNG", optimize=True)
                size = target.stat().st_size
                total_bytes += size
                rendered += 1
                if args.hashes:
                    import hashlib

                    hashes[f"{z}/{tx}/{ty}.png"] = hashlib.sha256(target.read_bytes()).hexdigest()

    manifest = {
        "schemaVersion": 1,
        "provider": "local-schematic",
        "license": "项目内置 GeoJSON 本地渲染，无外部数据；仅作离线示意底图",
        "coordinateSystem": "EPSG:3857 XYZ",
        "bbox": bbox,
        "zoom": {"min": zoom_min, "max": zoom_max},
        "zoomLevels": [z for z in range(zoom_min, zoom_max + 1)],
        "tileCount": rendered,
        "totalBytes": total_bytes,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if hashes:
        manifest["hashes"] = hashes
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"渲染完成: {rendered} 张 / {total_bytes / 1024 / 1024:.2f}MB → {out_dir}"
    )

    if args.zip_path:
        zip_path = Path(args.zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(out_dir / "MANIFEST.json", "MANIFEST.json")
            for z, x0, y0, x1, y1, _ in plan:
                for tx in range(x0, x1 + 1):
                    for ty in range(y0, y1 + 1):
                        rel = f"{z}/{tx}/{ty}.png"
                        zf.write(out_dir / rel, rel)
        print(f"已打包: {zip_path}  ({zip_path.stat().st_size / 1024 / 1024:.2f}MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
