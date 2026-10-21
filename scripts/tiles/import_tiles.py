"""离线侧瓦片包导入工具（把 U 盘/内网共享里的瓦片包写入瓦片仓）。

支持两种来源：
- ZIP 瓦片包（``<根>/MANIFEST.json`` + ``z/x/y.png``，允许单一顶层目录）；
- 目录（含 ``MANIFEST.json``，常用于 U 盘直接拷贝的大包）。

校验项与后端 ``POST /api/v1/map/tiles/import`` 完全同口径：
MANIFEST 合法、tileCount/totalBytes/缩放范围与实际文件一致、可选 SHA256、
瓦片数/总体积上限、zip-slip 与符号链接防护。导入为**合并写入**（同名覆盖，
其余保留），可用于瓦片升级。

示例::

    python scripts/tiles/import_tiles.py --source D:\\tiles.zip --dry-run
    python scripts/tiles/import_tiles.py --source D:\\tiles.zip --target resources/map-tiles
    python scripts/tiles/import_tiles.py --source D:\\map-tiles --target %APPDATA%\\...\\map-tiles

失败以非零码退出，且不会留下半成品（先全量校验再落盘）。
"""

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:  # 直接执行脚本时脚本目录已在 sys.path
    from _common import (  # type: ignore
        DEFAULT_OUT,
        MANIFEST_NAME,
        MAX_MANIFEST_BYTES,
        MAX_TILES,
        TILE_RE,
        TileToolError,
        fail,
        human_bytes,
        log,
        normalize_manifest,
        parse_tile_rel,
        safe_relative,
        setup_console,
        sha256_bytes,
    )
except ImportError:  # pragma: no cover — 脚本直跑与包导入二选一，另一条 import 分支必然不可执行
    from ._common import (  # type: ignore
        DEFAULT_OUT,
        MANIFEST_NAME,
        MAX_MANIFEST_BYTES,
        MAX_TILES,
        TILE_RE,
        TileToolError,
        fail,
        human_bytes,
        log,
        normalize_manifest,
        parse_tile_rel,
        safe_relative,
        setup_console,
        sha256_bytes,
    )

DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024
TILE_MEMBER_LIMIT = 5 * 1024 * 1024


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_tiles.py",
        description="校验并导入瓦片包（ZIP 或目录）到瓦片仓",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/tiles/import_tiles.py --source D:\\tiles.zip --dry-run\n"
            "  python scripts/tiles/import_tiles.py --source D:\\tiles.zip --target resources/map-tiles\n"
        ),
    )
    parser.add_argument("--source", required=True, help="瓦片包 ZIP 路径或包含 MANIFEST.json 的目录")
    parser.add_argument("--target", default=DEFAULT_OUT, help=f"瓦片仓目录（默认 {DEFAULT_OUT}）")
    parser.add_argument("--dry-run", action="store_true", help="只校验并统计，不写盘")
    parser.add_argument("--skip-existing", action="store_true", help="目标已存在同名瓦片时跳过（默认覆盖）")
    parser.add_argument("--skip-hashes", action="store_true", help="忽略 MANIFEST 中的 SHA256 校验")
    parser.add_argument("--max-tiles", type=int, default=MAX_TILES, help=f"瓦片数上限（默认 {MAX_TILES}）")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="总体积上限（默认 2GB）")
    return parser


def _load_manifest_bytes(data: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if len(data) > MAX_MANIFEST_BYTES:
        raise TileToolError(f"{MANIFEST_NAME} 超过 {MAX_MANIFEST_BYTES} 字节上限")
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TileToolError(f"{MANIFEST_NAME} 不是合法的 UTF-8 JSON") from exc
    return normalize_manifest(raw), raw


def _check_against(
    manifest: Dict[str, Any],
    entries: List[Tuple[str, int, int, int, int]],
    total_bytes: int,
) -> None:
    levels = sorted({entry[1] for entry in entries})
    if manifest["tileCount"] is not None and manifest["tileCount"] != len(entries):
        raise TileToolError(
            f"MANIFEST 的 tileCount({manifest['tileCount']}) 与实际瓦片数({len(entries)}) 不一致"
        )
    if manifest["totalBytes"] is not None and manifest["totalBytes"] != total_bytes:
        raise TileToolError(
            f"MANIFEST 的 totalBytes({manifest['totalBytes']}) 与实际体积({total_bytes}) 不一致"
        )
    if manifest["zRange"] is not None and [levels[0], levels[-1]] != manifest["zRange"]:
        raise TileToolError(
            f"MANIFEST 缩放范围({manifest['zRange']}) 与实际目录({levels[0]}-{levels[-1]}) 不一致"
        )


def _verify_hash(hashes: Any, rel: str, data: bytes) -> None:
    if not isinstance(hashes, dict):
        return
    expected = hashes.get(rel)
    if expected and str(expected).lower() != sha256_bytes(data):
        raise TileToolError(f"瓦片 {rel} 的 SHA256 校验失败（文件损坏或被篡改）")


def import_zip(source: Path, target: Path, args) -> Dict[str, Any]:  # noqa: C901 - ZIP 解析与落盘分支较多
    try:
        zf = zipfile.ZipFile(source)
    except zipfile.BadZipFile as exc:
        raise TileToolError(f"不是有效的 ZIP 压缩包: {source}") from exc
    with zf:
        entries = [(info, safe_relative(info.filename)) for info in zf.infolist() if not info.is_dir()]
        if not entries:
            raise TileToolError("ZIP 为空")
        manifests = [rel for _info, rel in entries if rel == MANIFEST_NAME or rel.endswith("/" + MANIFEST_NAME)]
        if not manifests:
            raise TileToolError(f"ZIP 内缺少 {MANIFEST_NAME}")
        if len(manifests) > 1:
            raise TileToolError(f"ZIP 内存在多个 {MANIFEST_NAME}")
        prefix = manifests[0][: -len(MANIFEST_NAME)]
        if prefix and (prefix.count("/") != 1 or not prefix.endswith("/")):
            raise TileToolError(f"{MANIFEST_NAME} 必须位于根目录或单一顶层目录下")

        manifest_info = next(info for info, rel in entries if rel == prefix + MANIFEST_NAME)
        if int(getattr(manifest_info, "file_size", 0) or 0) > MAX_MANIFEST_BYTES:
            raise TileToolError(f"{MANIFEST_NAME} 超过 {MAX_MANIFEST_BYTES} 字节上限")
        manifest_bytes = zf.read(manifest_info.filename)
        manifest, raw = _load_manifest_bytes(manifest_bytes)
        hashes = raw.get("hashes")

        plan: List[Tuple[str, str]] = []
        shape: List[Tuple[str, int, int, int, int]] = []
        for info, rel in entries:
            if rel == prefix + MANIFEST_NAME:
                continue
            if not rel.startswith(prefix):
                continue
            sub = rel[len(prefix):]
            if not TILE_RE.match(sub):
                continue
            z, x, y = parse_tile_rel(sub)
            size = int(getattr(info, "file_size", 0) or 0)
            if size > TILE_MEMBER_LIMIT:
                raise TileToolError(f"瓦片 {sub} 超过 {human_bytes(TILE_MEMBER_LIMIT)} 上限")
            plan.append((info.filename, sub))
            shape.append((sub, z, x, y, size))

        if not shape:
            raise TileToolError("ZIP 内没有瓦片文件（目录结构应为 z/x/y.png）")
        if len(shape) > args.max_tiles:
            raise TileToolError(f"瓦片数 {len(shape)} 超过 --max-tiles={args.max_tiles}")
        total_bytes = sum(entry[4] for entry in shape)
        if total_bytes > args.max_bytes:
            raise TileToolError(f"总体积 {human_bytes(total_bytes)} 超过 --max-bytes={human_bytes(args.max_bytes)}")
        _check_against(manifest, shape, total_bytes)

        if args.dry_run:
            return {
                "tileCount": len(shape),
                "totalBytes": total_bytes,
                "manifest": manifest,
                "overwritten": 0,
                "skipped": 0,
                "dryRun": True,
            }

        overwritten = 0
        skipped = 0
        for member, rel in plan:
            data = zf.read(member)
            if not args.skip_hashes:
                _verify_hash(hashes, rel, data)
            z, x, y = parse_tile_rel(rel)
            dest = target / str(z) / str(x) / f"{y}.png"
            if args.skip_existing and dest.is_file():
                skipped += 1
                continue
            overwritten += int(dest.is_file())
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

        target.mkdir(parents=True, exist_ok=True)
        (target / MANIFEST_NAME).write_bytes(manifest_bytes)
        return {
            "tileCount": len(shape),
            "totalBytes": total_bytes,
            "manifest": manifest,
            "overwritten": overwritten,
            "skipped": skipped,
            "dryRun": False,
        }


def _locate_manifest_root(source: Path) -> Tuple[Path, Path]:
    direct = source / MANIFEST_NAME
    if direct.is_file():
        return source, direct
    candidates = [child / MANIFEST_NAME for child in source.iterdir() if child.is_dir()]
    candidates = [path for path in candidates if path.is_file()]
    if len(candidates) == 1:
        return candidates[0].parent, candidates[0]
    raise TileToolError(f"目录内缺少 {MANIFEST_NAME}: {source}")


def import_directory(source: Path, target: Path, args) -> Dict[str, Any]:
    base, manifest_path = _locate_manifest_root(source)
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise TileToolError(f"{MANIFEST_NAME} 超过 {MAX_MANIFEST_BYTES} 字节上限")
    manifest_bytes = manifest_path.read_bytes()
    manifest, raw = _load_manifest_bytes(manifest_bytes)
    hashes = raw.get("hashes")

    plan: List[Tuple[Path, str]] = []
    shape: List[Tuple[str, int, int, int, int]] = []
    for dirpath, dirnames, filenames in os.walk(base):
        for dirname in dirnames:
            if os.path.islink(os.path.join(dirpath, dirname)):
                raise TileToolError(f"目录含符号链接，已拒绝: {dirname}")
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            rel = path.relative_to(base).as_posix()
            if rel == MANIFEST_NAME or not TILE_RE.match(rel):
                continue
            if os.path.islink(path):
                raise TileToolError(f"目录含符号链接，已拒绝: {rel}")
            z, x, y = parse_tile_rel(rel)
            size = path.stat().st_size
            if size > TILE_MEMBER_LIMIT:
                raise TileToolError(f"瓦片 {rel} 超过 {human_bytes(TILE_MEMBER_LIMIT)} 上限")
            plan.append((path, rel))
            shape.append((rel, z, x, y, size))
            if len(shape) > args.max_tiles:
                raise TileToolError(f"瓦片数超过 --max-tiles={args.max_tiles}")

    if not shape:
        raise TileToolError("目录内没有瓦片文件（目录结构应为 z/x/y.png）")
    total_bytes = sum(entry[4] for entry in shape)
    if total_bytes > args.max_bytes:
        raise TileToolError(f"总体积 {human_bytes(total_bytes)} 超过 --max-bytes={human_bytes(args.max_bytes)}")
    _check_against(manifest, shape, total_bytes)

    if args.dry_run:
        return {
            "tileCount": len(shape),
            "totalBytes": total_bytes,
            "manifest": manifest,
            "overwritten": 0,
            "skipped": 0,
            "dryRun": True,
        }

    overwritten = 0
    skipped = 0
    for path, rel in plan:
        data = path.read_bytes()
        if not args.skip_hashes:
            _verify_hash(hashes, rel, data)
        z, x, y = parse_tile_rel(rel)
        dest = target / str(z) / str(x) / f"{y}.png"
        if args.skip_existing and dest.is_file():
            skipped += 1
            continue
        overwritten += int(dest.is_file())
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    target.mkdir(parents=True, exist_ok=True)
    (target / MANIFEST_NAME).write_bytes(manifest_bytes)
    return {
        "tileCount": len(shape),
        "totalBytes": total_bytes,
        "manifest": manifest,
        "overwritten": overwritten,
        "skipped": skipped,
        "dryRun": False,
    }


def main(argv=None) -> int:
    setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        source = Path(args.source)
        target = Path(args.target)
        if not source.exists():
            raise TileToolError(f"来源不存在: {source}")

        if source.is_dir():
            result = import_directory(source, target, args)
        elif source.suffix.lower() == ".zip":
            result = import_zip(source, target, args)
        else:
            raise TileToolError(f"不支持的来源类型（应为目录或 .zip）: {source}")

        log(f"瓦片数: {result['tileCount']}  体积: {human_bytes(result['totalBytes'])}")
        log(f"来源标识: {result['manifest'].get('provider')}  缩放范围: {result['manifest'].get('zRange')}")
        if result["dryRun"]:
            log("")
            log(f"dry-run 校验通过：去掉 --dry-run 即写入 {target.resolve()}")
            return 0
        log(f"导入完成: 覆盖 {result['overwritten']} 张，跳过 {result['skipped']} 张 → {target.resolve()}")
        return 0

    except TileToolError as exc:
        fail(str(exc))
    except KeyboardInterrupt:
        fail("已中断", 130)
    return 0


if __name__ == "__main__":
    sys.exit(main())
