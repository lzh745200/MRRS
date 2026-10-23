"""在线侧瓦片抓取工具（运维在**联网**机器运行，产出离线瓦片包）。

生成 ``<out>/<z>/<x>/<y>.png`` + ``MANIFEST.json``；把 ``<out>`` 目录（或打包成
ZIP）拷入内网机器后，用 ``POST /api/v1/map/tiles/import`` 或
``import_tiles.py`` 导入。

三种来源与授权提示：
- osm      ：OpenStreetMap 标准瓦片，ODbL；批量下载受 tile usage policy 限制
             （默认限速 2 req/s，请勿大规模爬取）；
- tianditu ：天地图在线服务，需单位申请授权 ``--key``（tk），按服务条款缓存；
- amap     ：高德瓦片，**GCJ-02 火星坐标**，与系统 WGS-84 标注不一致，前端
             必须做坐标转换，否则标记偏移数百米；商用/批量使用须获授权。

示例::

    python scripts/tiles/fetch_tiles.py --provider osm --dry-run
    python scripts/tiles/fetch_tiles.py --provider tianditu --key <tk> \\
        --bbox 106.0,25.1,108.5,26.9 --zoom 6-11 --out resources/map-tiles
    python scripts/tiles/fetch_tiles.py --provider amap --zoom 11-12 --hashes

失败时以非零码退出，失败清单写入 ``<out>/failed.txt``（断点续跑：已存在的
瓦片默认跳过）。
"""

import argparse
import sys
import time
import urllib.request
from pathlib import Path

try:  # 直接执行脚本时脚本目录已在 sys.path；作为包导入时走相对导入
    from _common import (  # type: ignore
        DEFAULT_AVG_TILE_BYTES,
        DEFAULT_BBOX,
        DEFAULT_OUT,
        DEFAULT_ZOOM,
        MAX_TILE_MEMBER_BYTES,
        MAX_TILES,
        PNG_MAGIC,
        TileToolError,
        build_manifest,
        count_tiles_by_zoom,
        fail,
        human_bytes,
        iter_tiles,
        log,
        parse_bbox,
        parse_zoom,
        scan_tiles,
        setup_console,
        sha256_bytes,
        sha256_file,
        warn,
        write_manifest,
    )
except ImportError:  # pragma: no cover - 包内导入兜底
    from ._common import (  # type: ignore
        DEFAULT_AVG_TILE_BYTES,
        DEFAULT_BBOX,
        DEFAULT_OUT,
        DEFAULT_ZOOM,
        MAX_TILE_MEMBER_BYTES,
        MAX_TILES,
        PNG_MAGIC,
        TileToolError,
        build_manifest,
        count_tiles_by_zoom,
        fail,
        human_bytes,
        iter_tiles,
        log,
        parse_bbox,
        parse_zoom,
        scan_tiles,
        setup_console,
        sha256_bytes,
        sha256_file,
        warn,
        write_manifest,
    )

USER_AGENT = "MRRS-offline-tiles-fetch/1.0 (offline deployment; operator-run)"

# provider → 默认 URL 模板 / 授权说明 / 坐标系
PROVIDERS = {
    "osm": {
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "license": "OpenStreetMap contributors, ODbL 1.0；批量下载受 OSM tile usage policy 限制",
        "coordinate": "WGS-84 / EPSG:3857 XYZ",
    },
    "tianditu": {
        "url": (
            "https://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile"
            "&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles"
            "&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk={key}"
        ),
        "license": "天地图（需单位申请授权 key）；按天地图服务条款使用与缓存",
        "coordinate": "CGCS2000 / EPSG:3857 XYZ（TILEMATRIX 层级以天地图 WMTS 为准）",
        "requires_key": True,
    },
    "amap": {
        "url": (
            "https://webrd0{s}.is.autonavi.com/appmaptile"
            "?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
        ),
        "license": "高德地图；批量/商用须获授权，受其服务条款限制",
        "coordinate": "GCJ-02（火星坐标，非 WGS-84；前端必须坐标转换，否则标记偏移）",
        "gcj02": True,
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_tiles.py",
        description="按 bbox + 缩放范围抓取在线瓦片，生成离线瓦片包（联网机器运行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/tiles/fetch_tiles.py --provider osm --dry-run\n"
            "  python scripts/tiles/fetch_tiles.py --provider tianditu --key <tk> --zoom 6-11\n"
            "  python scripts/tiles/fetch_tiles.py --provider amap --zoom 11-12 --hashes\n"
        ),
    )
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="osm", help="瓦片来源（默认 osm）")
    parser.add_argument("--url-template", default=None, help="自定义 URL 模板（占位符 {z}/{x}/{y}/{key}/{s}）")
    parser.add_argument(
        "--bbox",
        default=",".join(str(v) for v in DEFAULT_BBOX),
        help=f"经纬度范围 min_lon,min_lat,max_lon,max_lat（默认黔南州 {DEFAULT_BBOX}）",
    )
    parser.add_argument("--zoom", default=DEFAULT_ZOOM, help=f"缩放范围（默认 {DEFAULT_ZOOM}）")
    parser.add_argument("--out", default=DEFAULT_OUT, help=f"输出目录（默认 {DEFAULT_OUT}）")
    parser.add_argument("--key", default="", help="天地图 tk（provider=tianditu 必填）")
    parser.add_argument(
        "--header",
        action="append",
        default=[],
        metavar="NAME:VALUE",
        help="附加请求头（可重复），如 --header 'Authorization: Bearer xxx'；内网瓦片服务用",
    )
    parser.add_argument("--zoom-offset", type=int, default=0, help="URL 中 z 的偏移量（天地图 WMTS 层级校准）")
    parser.add_argument(
        "--scheme",
        choices=("xyz", "tms"),
        default="xyz",
        help="瓦片编号方案：xyz（默认，y 自北向南）或 tms（y 自南向北，部分内网/GeoServer 服务用）",
    )
    parser.add_argument("--rate", type=float, default=2.0, help="限速 req/s（默认 2）")
    parser.add_argument("--retries", type=int, default=3, help="单瓦片重试次数（默认 3）")
    parser.add_argument("--timeout", type=float, default=15.0, help="单请求超时秒数（默认 15）")
    parser.add_argument("--avg-bytes", type=int, default=DEFAULT_AVG_TILE_BYTES, help="dry-run 单瓦片体积估算（默认 18KB）")
    parser.add_argument("--dry-run", action="store_true", help="只统计瓦片数与预估体积，不联网、不写盘")
    parser.add_argument("--hashes", action="store_true", help="在 MANIFEST 中记录每瓦片 SHA256（导入时校验）")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在瓦片（默认断点续跑跳过）")
    parser.add_argument("--max-tiles", type=int, default=MAX_TILES, help=f"单次抓取瓦片数上限（默认 {MAX_TILES}）")
    return parser


def _tile_url(
    template: str, z: int, x: int, y: int, key: str, zoom_offset: int, scheme: str = "xyz"
) -> str:
    url_z = z + zoom_offset
    url_y = y
    if scheme == "tms":
        # TMS 的 y 轴自南向北，与 XYZ 相反：同级别总行数 - 1 - y
        url_y = (1 << url_z) - 1 - y
    return (
        template.replace("{z}", str(url_z))
        .replace("{x}", str(x))
        .replace("{y}", str(url_y))
        .replace("{-y}", str((1 << url_z) - 1 - y))
        .replace("{key}", key)
        .replace("{s}", str((x + y) % 4 + 1))
    )


def _parse_headers(raw_headers) -> dict:
    """把 ``--header NAME:VALUE`` 列表解析为请求头字典（供内网瓦片服务鉴权）。"""
    headers = {"User-Agent": USER_AGENT}
    for item in raw_headers or []:
        if ":" not in item:
            raise TileToolError(f"--header 格式应为 NAME:VALUE，收到: {item!r}")
        name, value = item.split(":", 1)
        name = name.strip()
        if not name:
            raise TileToolError(f"--header 缺少头名称，收到: {item!r}")
        headers[name] = value.strip()
    return headers


def fetch_one(url: str, timeout: float, retries: int, headers: dict = None) -> bytes:
    """抓取单张瓦片（带重试）；失败抛 TileToolError。"""
    last_error = "unknown"
    request_headers = dict(headers or {"User-Agent": USER_AGENT})
    for attempt in range(1, max(1, retries) + 1):
        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(MAX_TILE_MEMBER_BYTES + 1)
            if len(data) > MAX_TILE_MEMBER_BYTES:
                raise TileToolError(f"单张瓦片超过 {human_bytes(MAX_TILE_MEMBER_BYTES)} 上限")
            if not data.startswith(PNG_MAGIC):
                raise TileToolError("返回内容不是 PNG（可能被服务端拒绝、鉴权失败或超出配额）")
            return data
        except Exception as exc:  # 网络/协议/内容错误统一重试
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(2**attempt, 10))
    raise TileToolError(f"抓取失败: {last_error}")


def main(argv=None) -> int:  # noqa: C901 - CLI 编排（参数校验/限速/重试/清单）集中在此，拆分收益低
    setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        bbox = parse_bbox(args.bbox)
        z_min, z_max = parse_zoom(args.zoom)
        profile = PROVIDERS[args.provider]
        template = args.url_template or profile["url"]
        request_headers = _parse_headers(args.header)
        if profile.get("requires_key") and not args.key:
            if args.dry_run:
                warn("provider=tianditu 缺少 --key，实际抓取会全部失败（dry-run 仅统计）")
            else:
                raise TileToolError("provider=tianditu 必须提供 --key（天地图授权 tk）")

        rows = count_tiles_by_zoom(bbox, z_min, z_max)
        total = sum(count for _z, count in rows)
        estimate = total * args.avg_bytes
        out = Path(args.out)

        log(f"数据源: {args.provider}  坐标系: {profile['coordinate']}")
        log(f"授权/使用限制: {profile['license']}")
        log(f"bbox: {bbox}  缩放: {z_min}-{z_max}  总数: {total} 张")
        for z, count in rows:
            log(f"  z{z:<2} {count:>7} 张")
        log(f"预估体积: {human_bytes(estimate)}（按 {args.avg_bytes}B/张 估算，实际以抓取结果为准）")
        log(f"输出目录: {out.resolve()}")

        if args.dry_run:
            log("")
            log("dry-run 完成：未联网、未写盘。去掉 --dry-run 即开始抓取。")
            if profile.get("gcj02"):
                warn("高德为 GCJ-02 坐标，系统标注为 WGS-84：前端必须转换坐标，否则标记偏移数百米")
            return 0

        if total > args.max_tiles:
            raise TileToolError(f"瓦片总数 {total} 超过 --max-tiles={args.max_tiles}，请缩小 bbox/缩放范围")
        if total == 0:
            raise TileToolError("瓦片总数为 0，请检查 bbox/缩放范围")

        interval = 1.0 / args.rate if args.rate > 0 else 0.0
        last_request = 0.0
        fetched = 0
        skipped = 0
        failures = []
        hashes = {}
        out.mkdir(parents=True, exist_ok=True)

        for z, x, y in iter_tiles(bbox, z_min, z_max):
            rel = f"{z}/{x}/{y}.png"
            path = out / str(z) / str(x) / f"{y}.png"
            if path.is_file() and path.stat().st_size > 0 and not args.overwrite:
                skipped += 1
                if args.hashes:
                    hashes[rel] = sha256_file(path)
                continue
            wait = interval - (time.monotonic() - last_request)
            if wait > 0:
                time.sleep(wait)
            last_request = time.monotonic()
            try:
                data = fetch_one(
                    _tile_url(template, z, x, y, args.key, args.zoom_offset, args.scheme),
                    args.timeout,
                    args.retries,
                    request_headers,
                )
            except TileToolError as exc:
                failures.append(f"{rel}\t{exc}")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            fetched += 1
            if args.hashes:
                hashes[rel] = sha256_bytes(data)
            done = fetched + skipped
            if done % 50 == 0:
                log(f"进度: {done}/{total}（新增 {fetched}，跳过 {skipped}，失败 {len(failures)}）")

        failed_path = out / "failed.txt"
        if failures:
            failed_path.write_text("\n".join(failures) + "\n", encoding="utf-8")
        elif failed_path.is_file():
            failed_path.unlink()

        count, total_bytes, levels = scan_tiles(out)
        manifest = build_manifest(
            provider=args.provider,
            license_text=profile["license"],
            bbox=bbox,
            z_min=z_min,
            z_max=z_max,
            tile_count=count,
            total_bytes=total_bytes,
            coordinate_system=profile["coordinate"],
            hashes=hashes or None,
            extra={
                "url": template,
                "zoomOffset": args.zoom_offset,
                "failed": len(failures),
                "note": (
                    "GCJ-02 坐标：前端显示前必须转换为 WGS-84，否则标记偏移"
                    if profile.get("gcj02")
                    else None
                ),
            },
        )
        manifest_path = write_manifest(out, manifest)
        log("")
        log(f"完成: 新增 {fetched} 张，跳过 {skipped} 张，失败 {len(failures)} 张")
        log(f"目录内现有 {count} 张 / {human_bytes(total_bytes)}，缩放级别 {levels}")
        log(f"MANIFEST: {manifest_path}")
        if failures:
            warn(f"有 {len(failures)} 张瓦片失败，清单见 {failed_path}（重跑本命令可断点续跑）")
            return 1
        return 0

    except TileToolError as exc:
        fail(str(exc))
    except KeyboardInterrupt:
        fail("已中断（已抓取的瓦片保留，重跑可续传）", 130)
    return 0


if __name__ == "__main__":
    sys.exit(main())
