#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从一份"全省权威瓦片"打散出「全省总包 + 各市州分包」（纯文件操作，不重新渲染）。

背景：渲染 v2（`render_osm_tiles.py`）已产出全省 z5–12 的权威瓦片集
（`.scratch/osm/tiles-v2`）。本脚本按市州 bbox 从该集合中**取子集**，
保证所有交付包出自同一份、同一版本的瓦片，避免"分包先后渲染导致样式/数据不一致"。

包结构（每个 zip）：
- `guizhou-all_z5-12.zip`           全省 z5–12
- `guizhou-<slug>_z7-12.zip`       该市州 z7–12 + **全省 z5–6 概览（5 张）**
  概览瓦片保证单独导入后在省级缩放不出现"缺瓦片 → 前端回退矢量"。

每个包都写 MANIFEST.json（ODbL 署名、provider、region、bbox、zoom、tileCount、totalBytes），
随后由调用方用 verify_tiles.py / import_tiles.py 校验。

用法：
python scripts/tiles/pack_osm_subsets.py \
  --source .scratch/osm/tiles-v2 \
  --out-dir deliverables/osm-tiles-20261022 \
  [--only guiyang,qiannan] [--no-complete]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    build_manifest,
    human_bytes,
    log,
    read_manifest,
    scan_tiles,
    setup_console,
    warn,
)

PROVINCE_BBOX = (103.6, 24.6, 109.6, 29.2)
OVERVIEW_ZOOMS = (5, 6)          # 每个市州包都带的全省概览层
DETAIL_ZOOMS = (7, 12)           # 市州明细层
COMPLETE_ZOOMS = (5, 12)         # 全省总包
PADDING = 0.02                   # 市州 bbox 外扩（度）

# 中文名 → 交付 slug（顺序即 INDEX 顺序：先省会，再按常用排序）
PREFECTURES = [
    ("贵阳市", "guiyang"),
    ("遵义市", "zunyi"),
    ("六盘水市", "liupanshui"),
    ("安顺市", "anshun"),
    ("毕节市", "bijie"),
    ("铜仁市", "tongren"),
    ("黔东南苗族侗族自治州", "qiandongnan"),
    ("黔南布依族苗族自治州", "qiannan"),
    ("黔西南布依族苗族自治州", "qianxinan"),
]


def project(lon: float, lat: float, z: int) -> tuple[float, float]:
    n = 256 * (2**z)
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def tile_range(bbox, z: int) -> tuple[int, int, int, int]:
    min_lon, min_lat, max_lon, max_lat = bbox
    x0, y0 = project(min_lon, max_lat, z)
    x1, y1 = project(max_lon, min_lat, z)
    return int(x0 // 256), int(y0 // 256), int(x1 // 256), int(y1 // 256)


def iter_tile_files(source: Path, z: int, x_range, y_range):
    zdir = source / str(z)
    if not zdir.is_dir():
        return
    x0, y0, x1, y1 = x_range
    for x in range(x0, x1 + 1):
        xdir = zdir / str(x)
        if not xdir.is_dir():
            continue
        for y in range(y0, y1 + 1):
            p = xdir / f"{y}.png"
            if p.is_file():
                yield p


def collect_package_tiles(source: Path, detail_bbox, zoom_min: int, zoom_max: int):
    """返回相对路径列表：市州包 = 全省 z5-6 概览 + 该市州 z7-12；总包 = 全省 z5-12。"""
    rels = []

    def add_zoom_range(z_lo: int, z_hi: int):
        for z in range(z_lo, z_hi + 1):
            if detail_bbox is None:
                xr = tile_range(PROVINCE_BBOX, z)
            elif z <= max(OVERVIEW_ZOOMS):
                xr = tile_range(PROVINCE_BBOX, z)
            else:
                xr = tile_range(detail_bbox, z)
            for p in iter_tile_files(source, z, xr, (xr[1], xr[3])):
                rels.append(p.relative_to(source).as_posix())

    if detail_bbox is None:
        add_zoom_range(zoom_min, zoom_max)
    else:
        # 概览层（z5-6）无条件带上，保证单独导入时省级缩放不缺瓦片
        add_zoom_range(min(OVERVIEW_ZOOMS), max(OVERVIEW_ZOOMS))
        add_zoom_range(max(zoom_min, max(OVERVIEW_ZOOMS) + 1), zoom_max)
    return sorted(set(rels))


def make_manifest(base_manifest, provider, region_name, region_bbox, zoom_min, zoom_max, count, total_bytes):
    bbox = PROVINCE_BBOX
    # 市州包实际含 z5-6 全省概览 → MANIFEST 的 zoom.min 必须取实际最小层级（5），
    # 否则 verify/前端/后端会认为"声明 7 起、实际有 5 级"不一致。
    manifest_z_min = min(OVERVIEW_ZOOMS) if region_bbox else zoom_min
    m = build_manifest(
        provider=provider,
        license_text=base_manifest.get("license")
        or "ODbL-1.0 (© OpenStreetMap contributors)",
        bbox=bbox,
        z_min=manifest_z_min,
        z_max=zoom_max,
        tile_count=count,
        total_bytes=total_bytes,
        coordinate_system=base_manifest.get("coordinateSystem") or "EPSG:3857 XYZ",
        extra={
            "schemaVersion": 1,
            "attribution": "© OpenStreetMap contributors",
            "style": base_manifest.get("style") or "osm-vector-basemap-light-v2",
            "tilesVersion": base_manifest.get("tilesVersion") or 2,
            "region": {
                "name": region_name,
                "bbox": list(region_bbox) if region_bbox else list(PROVINCE_BBOX),
                "overviewZooms": list(OVERVIEW_ZOOMS) if region_bbox else [],
                "detailZooms": [zoom_min, zoom_max] if region_bbox else [zoom_min, zoom_max],
            },
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    return m


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_package(source: Path, base_manifest, out_dir: Path, name: str, provider: str,
                  region_name: str, region_bbox, zoom_min: int, zoom_max: int):
    rels = collect_package_tiles(source, region_bbox, zoom_min, zoom_max)
    if not rels:
        warn(f"{name}: 没有匹配的瓦片，跳过")
        return None
    tiles_dir = source.parent / "packages" / name.replace(".zip", "") / "tiles"
    if tiles_dir.exists():
        shutil.rmtree(tiles_dir)
    tiles_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for rel in rels:
        dst = tiles_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dst)
        total += dst.stat().st_size
    manifest = make_manifest(
        base_manifest, provider, region_name, region_bbox, zoom_min, zoom_max, len(rels), total
    )
    (tiles_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    zip_path = out_dir / name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        for rel in rels:
            zf.write(tiles_dir / rel, rel)
    size = zip_path.stat().st_size
    log(f"{name}: {len(rels)} 张 / {human_bytes(total)} → zip {human_bytes(size)}")
    return {
        "name": name,
        "region": region_name,
        "slug": provider,
        "zooms": [min(OVERVIEW_ZOOMS) if region_bbox else zoom_min, zoom_max],
        "detailZooms": [zoom_min, zoom_max],
        "tiles": len(rels),
        "bytes": size,
        "sha256": sha256_file(zip_path),
    }


def main(argv=None) -> int:
    setup_console()
    parser = argparse.ArgumentParser(description="从全省瓦片集打散出总包 + 各市州分包")
    parser.add_argument("--source", default=".scratch/osm/tiles-v2", help="权威瓦片目录")
    parser.add_argument("--out-dir", default="deliverables/osm-tiles-20261022", help="交付目录")
    parser.add_argument("--prefecture-json", default=".scratch/osm/prefecture_bboxes.json",
                        help="市州 bbox JSON（中文名 → bbox）")
    parser.add_argument("--only", default="", help="只处理这些 slug（逗号分隔）")
    parser.add_argument("--no-complete", action="store_true", help="跳过全省总包")
    args = parser.parse_args(argv)

    source = Path(args.source)
    if not (source / "MANIFEST.json").is_file():
        print(f"[错误] 源目录缺少 MANIFEST.json: {source}", file=sys.stderr)
        return 2
    base = read_manifest(source) or {}
    # read_manifest 归一化后 bbox 可能丢失，这里补一份原始 MANIFEST
    raw = json.loads((source / "MANIFEST.json").read_text(encoding="utf-8"))
    base.update({k: v for k, v in raw.items() if k not in base})

    bboxes = json.loads(Path(args.prefecture_json).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    results = []
    if not args.no_complete and (not only or "all" in only):
        info = build_package(
            source, base, out_dir, "guizhou-all_z5-12.zip", "osm",
            "贵州省（全省）", None, COMPLETE_ZOOMS[0], COMPLETE_ZOOMS[1],
        )
        if info:
            results.append(info)

    for cn_name, slug in PREFECTURES:
        if only and slug not in only and "all" not in only:
            continue
        bbox = bboxes.get(cn_name)
        if not bbox:
            warn(f"缺少 {cn_name} 的 bbox，跳过")
            continue
        padded = [bbox[0] - PADDING, bbox[1] - PADDING, bbox[2] + PADDING, bbox[3] + PADDING]
        # 夹回全省范围
        padded = [
            max(padded[0], PROVINCE_BBOX[0]), max(padded[1], PROVINCE_BBOX[1]),
            min(padded[2], PROVINCE_BBOX[2]), min(padded[3], PROVINCE_BBOX[3]),
        ]
        info = build_package(
            source, base, out_dir, f"guizhou-{slug}_z7-12.zip",
            f"osm-{slug}", cn_name, padded, DETAIL_ZOOMS[0], DETAIL_ZOOMS[1],
        )
        if info:
            results.append(info)

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(source),
        "source_tiles": scan_tiles(source)[0],
        "license": base.get("license") or "ODbL-1.0 (© OpenStreetMap contributors)",
        "attribution": "© OpenStreetMap contributors",
        "packages": results,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# 贵州离线瓦片包索引（OSM 渲染 v2）",
        "",
        f"> 生成时间：{summary['generated_at']}　数据：OpenStreetMap（ODbL-1.0）"
        f"　渲染：Pillow 纯离线（无 GDAL/Mapnik）",
        ">",
        "> 每个包都含 `MANIFEST.json`，可直接在「系统管理 → 备份与存储 → 地图瓦片 → 导入瓦片包」导入；"
        "各市州包额外内含全省 z5–6 概览（5 张），单独导入也能在省级缩放正常显示。",
        "",
        "| 包名 | 地区 | 缩放 | 瓦片数 | 体积 | SHA256(前16) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| `{r['name']}` | {r['region']} | z{r['zooms'][0]}–{r['zooms'][1]} | "
            f"{r['tiles']:,} | {human_bytes(r['bytes'])} | `{r['sha256'][:16]}` |"
        )
    lines += [
        "",
        "## 导入建议",
        "",
        "- 只要一次到位：导入 `guizhou-all_z5-12.zip`（全省 z5–12）。",
        "- 分单位下发：导入对应 `guizhou-<slug>_z7-12.zip`；多包可叠加导入（同名瓦片覆盖，不会重复占用）。",
        "- 导入后 `GET /api/v1/map/tile-info` 的 `tileCount` 会增加；地图页切到「瓦片底图」即可查看。",
        "- 署名：瓦片右下角与页面 Leaflet 署名控件均显示 `© OpenStreetMap contributors`（ODbL 要求，请勿移除）。",
        "",
        "## 完整包与市州包的关系",
        "",
        "- 全省包按贵州**外接矩形**渲染；市州包按各自 bbox（含 0.02° 边缘余量）取子集，并附带全省 z5–6 概览。",
        "- 市州包并集**完全被全省包包含**；全省包多出的瓦片位于省界之外的邻省边缘（外接矩形所致），不影响使用。",
        "- 只要省界内 → 导入 9 个市州包即可；希望省界边缘不露空白 → 用全省包。两者可叠加导入（同名覆盖）。",
    ]
    (out_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"共 {len(results)} 个包 → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
