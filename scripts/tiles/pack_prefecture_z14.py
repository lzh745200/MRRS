#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把权威 z14 全省瓦片集打散为「各市州 z14 分包」（纯文件操作，不重新渲染）。

背景：贵州 z14 全省约 6.5 万张、合计约 0.7~0.8GB，**单个 zip 超过 512MB 导入上限**
（`offline_map_service.MAX_TILE_UPLOAD_BYTES`），因此按市州拆分；每包 30~140MB，
可分别导入、互不覆盖（同 zoom 同名瓦片按需覆盖）。

包结构（每个 zip）：
- `MANIFEST.json`（provider/bbox/zoom=[14,14]/tileCount/totalBytes/ODbL 署名/region）
- `14/<x>/<y>.png`

用法：
python scripts/tiles/pack_prefecture_z14.py \
  --source .scratch/osm/tiles-z14 \
  --prefecture-json .scratch/osm/prefecture_bboxes.json \
  --out-dir deliverables/osm-tiles-z14-20261026 \
  [--padding 0.02] [--only guiyang,zunyi]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import log, setup_console  # noqa: E402

ZOOM = 14
LICENSE_TEXT = "ODbL-1.0 (© OpenStreetMap contributors)"
PROVIDER = "osm-render"

PREFECTURES = [
    ("贵阳市", "guiyang"),
    ("遵义市", "zunyi"),
    ("六盘水市", "liupanshui"),
    ("安顺市", "anshun"),
    ("毕节市", "bijie"),
    ("铜仁市", "tongren"),
    ("黔西南布依族苗族自治州", "qianxinan"),
    ("黔东南苗族侗族自治州", "qiandongnan"),
    ("黔南布依族苗族自治州", "qiannan"),
]


def lon_to_x(lon: float, z: int) -> int:
    return int((lon + 180.0) / 360.0 * (1 << z))


def lat_to_y(lat: float, z: int) -> int:
    rad = math.radians(lat)
    return int((1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * (1 << z))


def tile_range(bbox, z: int, padding: float):
    min_lon, min_lat, max_lon, max_lat = bbox
    min_lon -= padding
    min_lat -= padding
    max_lon += padding
    max_lat += padding
    return (
        lon_to_x(min_lon, z),
        lon_to_x(max_lon, z),
        lat_to_y(max_lat, z),
        lat_to_y(min_lat, z),
    )


def load_prefectures(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for name, value in raw.items():
        if isinstance(value, dict):
            bbox = value.get("bbox") or [
                value.get("min_lon"),
                value.get("min_lat"),
                value.get("max_lon"),
                value.get("max_lat"),
            ]
        else:
            bbox = value
        out[name] = [float(v) for v in bbox]
    return out


def build_manifest(bbox, tile_count: int, total_bytes: int, slug: str, name: str) -> dict:
    return {
        "schemaVersion": 1,
        "provider": PROVIDER,
        "license": LICENSE_TEXT,
        "coordinateSystem": "EPSG:3857 XYZ",
        "bbox": [min(bbox[0], 103.6), max(bbox[1], 24.6), min(bbox[2], 109.6), max(bbox[3], 29.2)],
        "zoom": {"min": ZOOM, "max": ZOOM},
        "zoomLevels": [ZOOM],
        "tileCount": tile_count,
        "totalBytes": total_bytes,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "region": {"name": name, "slug": slug, "bbox": list(bbox)},
        "attribution": "© OpenStreetMap contributors",
    }


def pack_one(source: Path, out_dir: Path, name: str, slug: str, bbox, padding: float) -> dict:
    x0, x1, y0, y1 = tile_range(bbox, ZOOM, padding)
    tiles = []
    for x in range(x0, x1 + 1):
        xdir = source / str(ZOOM) / str(x)
        if not xdir.is_dir():
            continue
        for y in range(y0, y1 + 1):
            p = xdir / f"{y}.png"
            if p.is_file():
                tiles.append(p)
    if not tiles:
        raise SystemExit(f"{name}: 该 bbox 在 z{ZOOM} 没有瓦片（检查 --source）")

    total_bytes = sum(p.stat().st_size for p in tiles)
    manifest = build_manifest(bbox, len(tiles), total_bytes, slug, name)
    zip_path = out_dir / f"guizhou-{slug}_z{ZOOM}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for p in tiles:
            rel = p.relative_to(source).as_posix()
            zf.write(p, rel)
    log(
        f"[{name}] z{ZOOM} 瓦片 {len(tiles)} 张 / {total_bytes / 1048576:.1f}MB "
        f"→ {zip_path.name} ({zip_path.stat().st_size / 1048576:.1f}MB)"
    )
    return {
        "name": name,
        "slug": slug,
        "bbox": bbox,
        "tileCount": len(tiles),
        "totalBytes": total_bytes,
        "zip": zip_path.name,
        "zipBytes": zip_path.stat().st_size,
    }


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="打散贵州 z14 全省瓦片为各市州分包")
    ap.add_argument("--source", default=".scratch/osm/tiles-z14")
    ap.add_argument("--prefecture-json", default=".scratch/osm/prefecture_bboxes.json")
    ap.add_argument("--out-dir", default="deliverables/osm-tiles-z14-20261026")
    ap.add_argument("--padding", type=float, default=0.02)
    ap.add_argument("--only", default=None, help="只处理这些 slug（逗号分隔）")
    args = ap.parse_args(argv)

    source = Path(args.source)
    if not (source / str(ZOOM)).is_dir():
        print(f"[错误] 源目录缺少 z{ZOOM}：{source}")
        return 2
    prefs = load_prefectures(Path(args.prefecture_json))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    only = {s.strip() for s in args.only.split(",")} if args.only else None

    results = []
    for name, slug in PREFECTURES:
        if only and slug not in only:
            continue
        bbox = prefs.get(name)
        if not bbox:
            print(f"[跳过] 缺少 bbox：{name}")
            continue
        results.append(pack_one(source, out_dir, name, slug, bbox, args.padding))

    summary = {
        "zoom": ZOOM,
        "provider": PROVIDER,
        "license": LICENSE_TEXT,
        "totalTiles": sum(r["tileCount"] for r in results),
        "totalZipBytes": sum(r["zipBytes"] for r in results),
        "packages": results,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(
        f"完成：{len(results)} 个市州包，合计 {summary['totalTiles']} 张 / "
        f"{summary['totalZipBytes'] / 1048576:.1f}MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
