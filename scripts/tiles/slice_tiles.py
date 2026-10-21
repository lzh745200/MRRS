"""完全离线的瓦片切片工具（调用 GDAL 的 gdal2tiles，不触网）。

用于**单位自有或已获授权**的底图（GeoTIFF / 正射影像 / 扫描地图）：
在断网机器上用 GDAL 切出 XYZ 瓦片，生成 ``<out>/<z>/<x>/<y>.png`` + ``MANIFEST.json``。

依赖（仅运维机器需要，不进安装包）：
- OSGeo4W / QGIS 附带的 GDAL：https://trac.osgeo.org/osgeo4w/
- 或 conda：``conda install -c conda-forge gdal``
- 或 apt：``apt install gdal-bin python3-gdal``

示例::

    python scripts/tiles/slice_tiles.py --source 底图.tif --zoom 10-14 --dry-run
    python scripts/tiles/slice_tiles.py --source 底图.tif --zoom 10-14 --out resources/map-tiles
    python scripts/tiles/slice_tiles.py --source ./影像目录 --zoom 12-14

未检测到 GDAL 时以非零码（3）退出并给出安装提示；``--dry-run`` 只检查环境与
切片的参数，不产生任何文件。
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:  # 直接执行脚本时脚本目录已在 sys.path
    from _common import (  # type: ignore
        DEFAULT_OUT,
        DEFAULT_ZOOM,
        TileToolError,
        build_manifest,
        fail,
        human_bytes,
        log,
        parse_bbox,
        parse_zoom,
        scan_tiles,
        setup_console,
        warn,
        write_manifest,
    )
except ImportError:  # pragma: no cover — 脚本直跑与包导入二选一，另一条 import 分支必然不可执行
    from ._common import (  # type: ignore
        DEFAULT_OUT,
        DEFAULT_ZOOM,
        TileToolError,
        build_manifest,
        fail,
        human_bytes,
        log,
        parse_bbox,
        parse_zoom,
        scan_tiles,
        setup_console,
        warn,
        write_manifest,
    )

GDAL_HINT = """未检测到 GDAL 的 gdal2tiles（离线切片必需）。

安装方式（三选一，运维机器安装即可，不需要进安装包）：
  1) Windows：安装 OSGeo4W/QGIS，勾选 GDAL，然后从 "OSGeo4W Shell" 运行本脚本；
  2) conda：conda install -c conda-forge gdal；
  3) Linux：apt install gdal-bin python3-gdal 或 yum install gdal gdal-python-tools。

替代方案：若无法安装 GDAL，请向地图数据提供方索取已切好的 XYZ 瓦片包
（z/x/y.png + MANIFEST.json），再用 import_tiles.py 导入。

注意：本工具只用于**单位自有或已获授权**的底图，禁止用未授权数据切片分发。"""

IMAGE_SUFFIXES = (".tif", ".tiff", ".img", ".vrt", ".jp2", ".png")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slice_tiles.py",
        description="用 gdal2tiles 将本地底图切片为 XYZ 瓦片包（全程离线）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/tiles/slice_tiles.py --source 底图.tif --zoom 10-14 --dry-run\n"
            "  python scripts/tiles/slice_tiles.py --source ./影像目录 --zoom 12-14\n"
        ),
    )
    parser.add_argument("--source", required=True, help="底图 GeoTIFF 文件，或包含影像文件的目录")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"输出目录（默认 {DEFAULT_OUT}）")
    parser.add_argument("--zoom", default=DEFAULT_ZOOM, help=f"缩放范围（默认 {DEFAULT_ZOOM}）")
    parser.add_argument("--bbox", default=None, help="可选裁剪范围 min_lon,min_lat,max_lon,max_lat（记录进 MANIFEST）")
    parser.add_argument("--provider", default="local-gdal2tiles", help="MANIFEST 中的来源标识")
    parser.add_argument("--license", default="单位自有 / 已获授权底图", help="MANIFEST 中的授权说明")
    parser.add_argument("--resume", action="store_true", help="gdal2tiles 断点续切")
    parser.add_argument("--title", default="离线底图", help="gdal2tiles 图层标题")
    parser.add_argument("--dry-run", action="store_true", help="只检查 GDAL 环境与参数，不切片")
    return parser


def find_gdal2tiles() -> str:
    for name in ("gdal2tiles", "gdal2tiles.py", "gdal2tiles-script.py"):
        found = shutil.which(name)
        if found:
            return found
    raise TileToolError(GDAL_HINT)


def _resolve_source(source: Path) -> Path:
    """目录来源：合并为 VRT 再切片；文件来源：直接使用。"""
    if source.is_file():
        return source
    if not source.is_dir():
        raise TileToolError(f"底图不存在: {source}")
    images = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise TileToolError(f"目录内没有可切片的影像文件（支持 {', '.join(IMAGE_SUFFIXES)}）: {source}")
    if len(images) == 1:
        return images[0]
    gdalbuildvrt = shutil.which("gdalbuildvrt")
    if not gdalbuildvrt:
        raise TileToolError(
            "目录内有多个影像文件，需要 gdalbuildvrt 合并（未检测到）。\n"
            "可先手动执行：gdalbuildvrt merged.vrt *.tif 后用 --source merged.vrt 切片。"
        )
    vrt = source / "_merged_tiles_source.vrt"
    log(f"合并 {len(images)} 个影像 → {vrt}")
    completed = subprocess.run(
        [gdalbuildvrt, str(vrt), *[str(p) for p in images]],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise TileToolError(f"gdalbuildvrt 失败: {completed.stderr.strip() or completed.stdout.strip()}")
    return vrt


def main(argv=None) -> int:
    setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        z_min, z_max = parse_zoom(args.zoom)
        bbox = parse_bbox(args.bbox) if args.bbox else None
        source = Path(args.source)
        out = Path(args.out)

        try:
            gdal2tiles = find_gdal2tiles()
        except TileToolError as exc:
            fail(str(exc), 3)

        log(f"gdal2tiles: {gdal2tiles}")
        log(f"底图来源: {source.resolve()}")
        log(f"输出目录: {out.resolve()}  缩放: {z_min}-{z_max}")
        if bbox:
            log(f"记录 bbox: {bbox}")

        if args.dry_run:
            log("")
            log("dry-run 完成：GDAL 环境与参数检查通过，未切片、未写盘。")
            log("去掉 --dry-run 即开始切片（--xyz 保证瓦片为 Leaflet 可用的 XYZ 编号）。")
            return 0

        raster = _resolve_source(source)
        out.mkdir(parents=True, exist_ok=True)
        command = [
            gdal2tiles,
            "--xyz",
            "--profile=mercator",
            "-z",
            f"{z_min}-{z_max}",
            "--title",
            args.title,
            "--webviewer=none",
        ]
        if args.resume:
            command.append("--resume")
        command.extend([str(raster), str(out)])
        log("执行: " + " ".join(command))

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise TileToolError(
                "gdal2tiles 执行失败（退出码 "
                f"{completed.returncode}）: {completed.stderr.strip() or completed.stdout.strip()}"
            )

        count, total_bytes, levels = scan_tiles(out)
        manifest = build_manifest(
            provider=args.provider,
            license_text=args.license,
            bbox=bbox,
            z_min=z_min,
            z_max=z_max,
            tile_count=count,
            total_bytes=total_bytes,
            coordinate_system="EPSG:3857 XYZ（Web Mercator）",
            sources=[str(raster.name)],
            extra={"tool": "gdal2tiles", "title": args.title},
        )
        manifest_path = write_manifest(out, manifest)
        log("")
        log(f"切片完成: {count} 张 / {human_bytes(total_bytes)}，缩放级别 {levels}")
        log(f"MANIFEST: {manifest_path}")
        if not count:
            warn("未生成任何瓦片：请检查底图坐标系是否已定义（gdalinfo 查看 CRS）与缩放范围")
            return 1
        return 0

    except TileToolError as exc:
        fail(str(exc))
    except KeyboardInterrupt:
        fail("已中断", 130)
    return 0


if __name__ == "__main__":
    sys.exit(main())
