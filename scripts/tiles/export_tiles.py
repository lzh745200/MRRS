#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把已有瓦片仓导出为可交付的 .zip 瓦片包（离线）。

典型用途
--------
1. 上级单位/兄弟单位已经装好系统并预置了瓦片（``resources/map-tiles`` 或
   ``<安装目录>/resources/map-tiles`` / Electron 的 ``MAP_TILES_DIR``），
   把他们的瓦片仓导出成一个 zip，拷给其它离线机器导入；
2. 自己用 fetch/slice/render 生成后，统一打包交付（带 MANIFEST 与可选 SHA256）。

为什么需要它
------------
交付物必须是"zip 内含 MANIFEST.json + z/x/y.png"这一结构，直接压缩目录容易
多套一层目录名（``map-tiles/8/...``），导入端会判为非瓦片文件而拒绝。
本脚本按标准结构重新打包，并可选补写/刷新 MANIFEST（缺失时按实际扫描结果生成）。

用法
----
python scripts/tiles/export_tiles.py --from resources/map-tiles --zip deliverables/guizhou-tiles.zip
python scripts/tiles/export_tiles.py --from D:/tiles --zip out.zip --hashes --require-min 1
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    TILE_RE,
    build_manifest,
    check_png,
    error,
    human_bytes,
    log,
    read_manifest,
    scan_tiles,
    setup_console,
    sha256_file,
    warn,
    write_manifest,
)


def collect(root: Path):
    """扫描根目录下所有 z/x/y.png，返回 (相对路径列表, 抽样校验失败数)。"""
    if not root.is_dir():
        raise FileNotFoundError(f"瓦片目录不存在: {root}")
    rels = []
    for path in sorted(root.rglob("*.png")):
        rel = path.relative_to(root).as_posix()
        if TILE_RE.match(rel):
            rels.append(rel)
    return rels


def load_raw_manifest(root: Path):
    """读取源目录 MANIFEST.json 的**原始 schema**（保留 zoom/zoomLevels 字段）。

    不用 ``_common.read_manifest``：它返回归一化后的 ``zRange``，写回 zip 后
    导入端/后端不认（只认 zoom / zoomLevels），会出现"缩放范围: None"。
    """
    path = Path(root) / "MANIFEST.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        warn(f"源 MANIFEST.json 无法解析（{exc}），将重新生成")
        return None
    if not isinstance(raw, dict):
        warn("源 MANIFEST.json 不是 JSON 对象，将重新生成")
        return None
    return raw


def main(argv=None) -> int:
    setup_console()
    parser = argparse.ArgumentParser(
        description="把已有瓦片仓导出为 .zip 瓦片包（结构：MANIFEST.json + z/x/y.png）"
    )
    parser.add_argument("--from", dest="source", default="resources/map-tiles", help="源瓦片目录")
    parser.add_argument("--zip", dest="zip_path", required=True, help="输出 ZIP 路径")
    parser.add_argument("--hashes", action="store_true", help="在 MANIFEST 中写入每瓦片 SHA256")
    parser.add_argument("--require-min", type=int, default=1, help="最少瓦片数（默认 1；0 允许空包）")
    parser.add_argument("--refresh-manifest", action="store_true", help="重写源目录 MANIFEST.json")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写 zip")
    args = parser.parse_args(argv)

    root = Path(args.source)
    try:
        rels = collect(root)
    except FileNotFoundError as exc:
        error(str(exc))
        return 3

    total_tiles, total_bytes, levels = scan_tiles(root)
    if total_tiles != len(rels):
        warn(f"目录中 .png 文件 {len(rels)} 张，但统计到合法 z/x/y 瓦片 {total_tiles} 张（其余忽略）")

    log(f"源目录: {root.resolve()}")
    log(f"瓦片数: {total_tiles}  体积: {human_bytes(total_bytes)}  缩放级别: {levels or '无'}")

    if total_tiles < args.require_min:
        error(f"瓦片数 {total_tiles} 少于 --require-min={args.require_min}")
        return 3
    if total_tiles == 0:
        error("没有可导出的瓦片（目录为空或结构不是 z/x/y.png）")
        return 3

    # MANIFEST：优先沿用源目录的“原始 schema”（zoom/zoomLevels）；缺失/损坏则按实际扫描生成。
    # 注意：zip 里必须写原始 schema，不能写归一化后的 zRange —— 导入端/后端
    # normalize_manifest 只认 zoom / zoomLevels / tileCount / totalBytes。
    raw_manifest = load_raw_manifest(root)
    normalized = read_manifest(root) or {}
    bbox = normalized.get("bbox") if isinstance(normalized.get("bbox"), (list, tuple)) else None
    if raw_manifest is not None:
        log(
            "沿用源 MANIFEST: provider=%s zRange=%s tileCount=%s"
            % (normalized.get("provider"), normalized.get("zRange"), normalized.get("tileCount"))
        )
        declared = normalized.get("tileCount")
        if declared not in (None, total_tiles):
            warn(
                f"MANIFEST 声明 tileCount={declared} 与实际 {total_tiles} 不一致，"
                "建议加 --refresh-manifest 重写"
            )
    else:
        warn("源目录没有可用的 MANIFEST.json，将按实际扫描结果生成")

    if args.refresh_manifest or raw_manifest is None:
        z_min, z_max = (levels[0], levels[-1]) if levels else (0, 0)
        hashes = None
        if args.hashes:
            hashes = {rel: sha256_file(root / rel) for rel in rels}
        raw_manifest = build_manifest(
            provider=normalized.get("provider") or "exported",
            license_text=normalized.get("license")
            or "由运维从既有瓦片仓导出；使用前请确认底图授权",
            bbox=bbox,
            z_min=z_min,
            z_max=z_max,
            tile_count=total_tiles,
            total_bytes=total_bytes,
            coordinate_system=normalized.get("coordinateSystem") or "EPSG:3857 XYZ",
            hashes=hashes,
            extra={"exportedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        )
        if args.refresh_manifest:
            write_manifest(root, raw_manifest)
            log("已刷新源目录 MANIFEST.json")

    if args.dry_run:
        log("dry-run 完成：未写 zip。")
        return 0

    zip_path = Path(args.zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(
            "MANIFEST.json",
            json.dumps(raw_manifest, ensure_ascii=False, indent=2) + "\n",
        )
        for rel in rels:
            zf.write(root / rel, rel)

    ok_count, bad = 0, 0
    for rel in rels[: min(5, len(rels))]:
        valid, _msg = check_png(root / rel)
        ok_count += 1 if valid else 0
        bad += 0 if valid else 1

    log(f"已导出: {zip_path}  ({human_bytes(zip_path.stat().st_size)})")
    log(f"抽样 PNG 校验: 通过 {ok_count} / 失败 {bad}")
    log("导入方式: 管理页「导入瓦片包」上传，或 python scripts/tiles/import_tiles.py --source <zip>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
