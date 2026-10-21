"""离线瓦片包校验工具（CI 门禁 / 交付前自检）。

校验内容：
1. 瓦片目录与 MANIFEST.json 是否存在、可解析、字段合法；
2. MANIFEST 的 tileCount / totalBytes / 缩放范围与实际文件是否一致；
3. 缩放级别是否连续（缺层通常意味着切片中断）；
4. 抽样 PNG 是否可解码（Pillow 可用时完整解码，否则只校验 PNG 头/IHDR）；
5. ``--require-min N``：瓦片数下限，供 CI 强制"必须预置瓦片"。

退出码：0 通过；1 校验失败；3 瓦片数不足（含目录缺失且强制要求）；2 参数错误。

示例::

    python scripts/tiles/verify_tiles.py
    python scripts/tiles/verify_tiles.py --dir resources/map-tiles --require-min 0
    python scripts/tiles/verify_tiles.py --require-min 1000 --json
"""

import argparse
import json
import sys
from pathlib import Path

try:  # 直接执行脚本时脚本目录已在 sys.path
    from _common import (  # type: ignore
        DEFAULT_OUT,
        MANIFEST_NAME,
        TileToolError,
        check_png,
        fail,
        human_bytes,
        log,
        read_manifest,
        scan_tiles,
        setup_console,
        warn,
    )
except ImportError:  # pragma: no cover — 脚本直跑与包导入二选一，另一条 import 分支必然不可执行
    from ._common import (  # type: ignore
        DEFAULT_OUT,
        MANIFEST_NAME,
        TileToolError,
        check_png,
        fail,
        human_bytes,
        log,
        read_manifest,
        scan_tiles,
        setup_console,
        warn,
    )

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_INSUFFICIENT = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_tiles.py",
        description="校验离线瓦片包的完整性与覆盖率（供 CI / 交付自检）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "退出码: 0 通过；1 校验失败；3 瓦片数不足（或目录缺失但要求非空）\n"
            "示例:\n"
            "  python scripts/tiles/verify_tiles.py --require-min 0\n"
            "  python scripts/tiles/verify_tiles.py --dir resources/map-tiles --require-min 1000 --json\n"
        ),
    )
    parser.add_argument("--dir", default=DEFAULT_OUT, help=f"瓦片目录（默认 {DEFAULT_OUT}）")
    parser.add_argument("--require-min", type=int, default=0, help="要求的最少瓦片数（默认 0 = 允许未预置）")
    parser.add_argument("--sample", type=int, default=5, help="抽样校验 PNG 的张数（默认 5，0 = 不抽样）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出报告（便于 CI 解析）")
    return parser


def _sample_tiles(root: Path, sample: int) -> list:
    tiles = []
    for z_dir in sorted(root.iterdir()):
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        for x_dir in sorted(z_dir.iterdir()):
            if not x_dir.is_dir():
                continue
            for tile in sorted(x_dir.iterdir()):
                if tile.suffix.lower() == ".png" and tile.is_file():
                    tiles.append(tile)
    if not tiles or sample <= 0:
        return []
    if len(tiles) <= sample:
        return tiles
    step = max(1, len(tiles) // sample)
    return tiles[::step][:sample]


def verify(root: Path, require_min: int, sample: int) -> dict:  # noqa: C901 - 逐项校验清单
    report = {
        "dir": str(root),
        "exists": root.is_dir(),
        "tileCount": 0,
        "totalBytes": 0,
        "zoomLevels": [],
        "manifest": None,
        "manifestPresent": False,
        "sampled": 0,
        "problems": [],
        "exitCode": EXIT_OK,
    }
    if not report["exists"]:
        if require_min > 0:
            report["problems"].append(f"瓦片目录不存在: {root}")
            report["exitCode"] = EXIT_INSUFFICIENT
        return report

    count, total_bytes, levels = scan_tiles(root)
    report["tileCount"] = count
    report["totalBytes"] = total_bytes
    report["zoomLevels"] = levels

    manifest_path = root / MANIFEST_NAME
    report["manifestPresent"] = manifest_path.is_file()
    if report["manifestPresent"]:
        try:
            manifest = read_manifest(root)
            report["manifest"] = manifest
        except TileToolError as exc:
            report["problems"].append(f"MANIFEST 非法: {exc}")
            manifest = None
    else:
        manifest = None
        if count > 0:
            report["problems"].append(f"存在 {count} 张瓦片但缺少 {MANIFEST_NAME}")

    if manifest is not None:
        if manifest["tileCount"] is not None and manifest["tileCount"] != count:
            report["problems"].append(
                f"MANIFEST tileCount({manifest['tileCount']}) 与实际({count}) 不一致"
            )
        if manifest["totalBytes"] is not None and manifest["totalBytes"] != total_bytes:
            report["problems"].append(
                f"MANIFEST totalBytes({manifest['totalBytes']}) 与实际({total_bytes}) 不一致"
            )
        if manifest["zRange"] is not None and levels:
            if [levels[0], levels[-1]] != manifest["zRange"]:
                report["problems"].append(
                    f"MANIFEST 缩放范围({manifest['zRange']}) 与实际({levels[0]}-{levels[-1]}) 不一致"
                )

    if levels:
        expected = list(range(levels[0], levels[-1] + 1))
        missing = [z for z in expected if z not in levels]
        if missing:
            report["problems"].append(f"缩放级别不连续，缺少 z{missing}")

    samples = _sample_tiles(root, sample)
    report["sampled"] = len(samples)
    for tile in samples:
        ok, reason = check_png(tile)
        if not ok:
            report["problems"].append(f"瓦片损坏 {tile.relative_to(root)}: {reason}")

    if count < require_min:
        report["problems"].append(f"瓦片数 {count} 少于要求的下限 {require_min}")
        report["exitCode"] = EXIT_INSUFFICIENT
    elif report["problems"]:
        report["exitCode"] = EXIT_INVALID
    return report


def _print_report(report: dict, require_min: int) -> None:
    log(f"瓦片目录: {report['dir']}")
    if not report["exists"]:
        if require_min > 0:
            log(f"[失败] 目录不存在（--require-min={require_min} 要求至少 {require_min} 张）")
        else:
            log("[通过] 目录不存在，按“未预置瓦片”可选处理（--require-min=0）")
        return
    log(f"瓦片数: {report['tileCount']}  体积: {human_bytes(report['totalBytes'])}")
    log(f"缩放级别: {report['zoomLevels']}  抽样校验: {report['sampled']} 张")
    if report["manifest"]:
        manifest = report["manifest"]
        log(
            "MANIFEST: provider={} zRange={} generatedAt={}".format(
                manifest.get("provider"), manifest.get("zRange"), manifest.get("generatedAt")
            )
        )
    elif report["manifestPresent"]:
        log("MANIFEST: 存在但不可用（见问题列表）")
    else:
        log("MANIFEST: 缺失")
    for problem in report["problems"]:
        log(f"  [问题] {problem}")
    if report["exitCode"] == EXIT_OK:
        log("[通过] 瓦片包校验通过")
    elif report["exitCode"] == EXIT_INSUFFICIENT:
        log(f"[失败] 瓦片数不足（--require-min={require_min}）")
    else:
        log("[失败] 瓦片包校验未通过")


def main(argv=None) -> int:
    setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.dir)
    try:
        report = verify(root, args.require_min, args.sample)
    except TileToolError as exc:
        fail(str(exc), EXIT_INVALID)
        return EXIT_INVALID
    if args.json:
        log(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report, args.require_min)
    if report["tileCount"] == 0 and args.require_min == 0 and report["exists"]:
        warn("本次构建未预置瓦片（--require-min=0）：安装包地图底图为空，需运维导入瓦片包")
    return report["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
