#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「高层级明细瓦片」与「z5–8 全省概览瓦片」合成可独立导入的贵州瓦片包。

背景（2026-10-31 现场问题）：用户只导入 z13/z14 明细包、或安装包内没有内置 z5–12 时，
`tile-info.zoomLevels` 的最低层级被抬到 13/14：
- 前端 `tileZoomLimits` 只能降到 `minNativeZoom - 2`（z13 包 → 11），**看不到全省**；
- `maxBounds` 又被收紧到已导入的市州范围，缩放/拖动都"卡住"。

因此每个交付包都必须自带 **z5–8 全省概览**（31 张 / 约 0.8MB），
使任何单个包导入后都能缩到 z4~z5 看全省；另提供独立 `guizhou-overview_z5-8.zip`
供已经导入旧包的现场补装。

包结构（每个 zip）：`MANIFEST.json` + `{z}/{x}/{y}.png`。

用法：
python scripts/tiles/pack_guizhou_bundles.py \
  --overview-dir .scratch/osm/tiles-v2 \
  --detail-dir .scratch/osm/tiles-z14 --detail-zoom 14 \
  --out-dir deliverables/osm-tiles-20261031 \
  [--only z13,z14,overview] [--no-prefectures]
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

PROVINCE_BBOX = (103.6, 24.6, 109.6, 29.2)
LICENSE_TEXT = "ODbL-1.0 (© OpenStreetMap contributors)"
PROVIDER = "osm-render"
OVERVIEW_ZOOMS = (5, 6, 7, 8)
PADDING = 0.02

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


def tile_range(bbox, z: int, padding: float = PADDING):
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        lon_to_x(min_lon - padding, z),
        lon_to_x(max_lon + padding, z),
        lat_to_y(max_lat + padding, z),
        lat_to_y(min_lat - padding, z),
    )


def collect_dir_zoom(root: Path, z: int, bbox=None) -> list[Path]:
    zdir = root / str(z)
    if not zdir.is_dir():
        return []
    if bbox is None:
        return [p for p in zdir.rglob("*.png") if p.is_file()]
    x0, x1, y0, y1 = tile_range(bbox, z)
    out: list[Path] = []
    for x in range(x0, x1 + 1):
        xdir = zdir / str(x)
        if not xdir.is_dir():
            continue
        for y in range(y0, y1 + 1):
            p = xdir / f"{y}.png"
            if p.is_file():
                out.append(p)
    return out


def build_manifest(bbox, levels, tile_count, total_bytes, region=None) -> dict:
    manifest = {
        "schemaVersion": 1,
        "provider": PROVIDER,
        "license": LICENSE_TEXT,
        "coordinateSystem": "EPSG:3857 XYZ",
        "bbox": list(bbox),
        "zoom": {"min": min(levels), "max": max(levels)},
        "zoomLevels": sorted(levels),
        "tileCount": tile_count,
        "totalBytes": total_bytes,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attribution": "© OpenStreetMap contributors",
    }
    if region:
        manifest["region"] = region
    return manifest


def write_bundle(
    zip_path: Path,
    entries: list[tuple[Path, str]],
    bbox,
    levels,
    region=None,
) -> dict:
    total_bytes = sum(p.stat().st_size for p, _ in entries)
    manifest = build_manifest(bbox, levels, len(entries), total_bytes, region)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path, arcname in entries:
            zf.write(path, arcname)
    return {
        "zip": zip_path.name,
        "tileCount": len(entries),
        "totalBytes": total_bytes,
        "zipBytes": zip_path.stat().st_size,
        "zoomLevels": sorted(levels),
        "bbox": list(bbox),
    }


def main(argv=None) -> int:
    setup_console()
    ap = argparse.ArgumentParser(description="合成带 z5–8 全省概览的贵州瓦片包")
    ap.add_argument("--overview-dir", default=".scratch/osm/tiles-v2")
    ap.add_argument("--detail-dir", default=None, help="明细瓦片目录（z13/z14）")
    ap.add_argument("--detail-zoom", type=int, default=None, help="明细层级（13/14）")
    ap.add_argument("--prefecture-json", default=".scratch/osm/prefecture_bboxes.json")
    ap.add_argument("--out-dir", default="deliverables/osm-tiles-20261031")
    ap.add_argument("--only", default="overview,all", help="overview,all,prefectures 的子集")
    ap.add_argument("--skip-prefectures", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    overview_dir = Path(args.overview_dir)
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    results = []

    # 1) 独立概览包（给已导入旧包的现场补装）
    overview_entries: list[tuple[Path, str]] = []
    for z in OVERVIEW_ZOOMS:
        for p in collect_dir_zoom(overview_dir, z):
            overview_entries.append((p, p.relative_to(overview_dir).as_posix()))
    if not overview_entries:
        print(f"[错误] 概览目录缺少 z{OVERVIEW_ZOOMS[0]}–{OVERVIEW_ZOOMS[-1]}：{overview_dir}")
        return 2
    if "overview" in only:
        results.append(
            write_bundle(
                out_dir / "guizhou-overview_z5-8.zip",
                overview_entries,
                PROVINCE_BBOX,
                list(OVERVIEW_ZOOMS),
            )
        )
        log(
            f"[概览] {len(overview_entries)} 张 → guizhou-overview_z5-8.zip "
            f"({results[-1]['zipBytes'] / 1048576:.1f}MB)"
        )

    detail_dir = Path(args.detail_dir) if args.detail_dir else None
    detail_zoom = args.detail_zoom
    if detail_dir is None or detail_zoom is None:
        print("[提示] 未给 --detail-dir/--detail-zoom，只生成概览包")
        (out_dir / "summary.json").write_text(
            json.dumps({"overview": results}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 0
    if not (detail_dir / str(detail_zoom)).is_dir():
        print(f"[错误] 明细目录缺少 z{detail_zoom}：{detail_dir}")
        return 2

    levels = list(OVERVIEW_ZOOMS) + [detail_zoom]

    # 2) 全省明细包（概览 + 全部明细）
    if "all" in only:
        entries = list(overview_entries)
        for p in collect_dir_zoom(detail_dir, detail_zoom):
            entries.append((p, p.relative_to(detail_dir).as_posix()))
        results.append(
            write_bundle(out_dir / f"guizhou-all_z{detail_zoom}.zip", entries, PROVINCE_BBOX, levels)
        )
        log(
            f"[全省] z{detail_zoom} {len(entries)} 张 → guizhou-all_z{detail_zoom}.zip "
            f"({results[-1]['zipBytes'] / 1048576:.1f}MB)"
        )

    # 3) 市州明细包（概览 + 该市州明细）
    if not args.skip_prefectures:
        prefs = json.loads(Path(args.prefecture_json).read_text(encoding="utf-8"))
        for name, slug in PREFECTURES:
            bbox = prefs.get(name)
            if not bbox:
                log(f"[跳过] 缺少 bbox：{name}")
                continue
            entries = list(overview_entries)
            for p in collect_dir_zoom(detail_dir, detail_zoom, bbox):
                entries.append((p, p.relative_to(detail_dir).as_posix()))
            region = {"name": name, "slug": slug, "bbox": list(bbox)}
            results.append(
                write_bundle(
                    out_dir / f"guizhou-{slug}_z{detail_zoom}.zip",
                    entries,
                    bbox,
                    levels,
                    region,
                )
            )
            log(
                f"[{name}] z{detail_zoom} {len(entries)} 张 → "
                f"guizhou-{slug}_z{detail_zoom}.zip ({results[-1]['zipBytes'] / 1048576:.1f}MB)"
            )

    summary = {
        "detailZoom": detail_zoom,
        "overviewZooms": list(OVERVIEW_ZOOMS),
        "license": LICENSE_TEXT,
        "packages": results,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_zip = sum(r["zipBytes"] for r in results)
    log(f"完成：{len(results)} 个包，合计 {total_zip / 1048576:.1f}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
