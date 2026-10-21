"""
离线地图服务

提供离线地图瓦片能力：
- 单张瓦片缓存读写（``data/offline_tiles``，历史缓存）
- 瓦片目录扫描（安装包预置瓦片 / 导入瓦片包共用的 ``<tiles>/<z>/<x>/<y>.png`` 布局）
- 瓦片包（ZIP / 本机目录）校验与导入（MANIFEST + SHA256 + 数量/体积上限 + zip-slip 防护）

瓦片包 MANIFEST.json 约定（与 ``scripts/tiles/*`` 工具链一致）::

    {
      "schemaVersion": 1,
      "provider": "osm | tianditu | amap | local-gdal2tiles | import",
      "license": "授权/使用限制说明",
      "coordinateSystem": "EPSG:3857 XYZ",
      "bbox": [min_lon, min_lat, max_lon, max_lat],
      "zoom": {"min": 5, "max": 12},
      "zoomLevels": [5, 6, ..., 12],
      "tileCount": 1215,
      "totalBytes": 23500000,
      "generatedAt": "2026-10-21T04:00:00Z",
      "hashes": {"5/1/2.png": "<sha256>"}
    }

本模块只做纯文件/内存处理，不触网；在线抓取由运维在联网机器上用
``scripts/tiles/fetch_tiles.py`` 生成瓦片包。
"""

import hashlib
import io
import json
import logging
import math
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from app.utils.paths import get_data_path
from app.utils.upload_helper import ensure_zip_within_limit, read_zip_member

logger = logging.getLogger(__name__)

# 单张瓦片 PNG 的读取上限（256x256 瓦片实测 5~50KB；上限只为把"文件被替换成
# 巨型文件"这类异常挡在内存之外，见 P-1 check_unbounded_read 门禁）
MAX_TILE_BYTES = 5 * 1024 * 1024

# ── 瓦片包导入上限（单机离线部署，全部可在测试中按模块属性替换）──
# 上传 ZIP 容器上限（与 body_size_limit 的 multipart 默认 512MB 对齐）
MAX_TILE_UPLOAD_BYTES = 512 * 1024 * 1024
# 解压后总体积上限（防压缩炸弹；与 tools/scripts 的 verify 口径一致）
MAX_TILES_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
# 单次导入瓦片数上限（200k ≈ 省域 z5-13 量级）
MAX_TILES_PER_IMPORT = 200_000
# 单个瓦片解压后上限
MAX_TILE_MEMBER_BYTES = 5 * 1024 * 1024
# MANIFEST.json 解压后上限
MAX_MANIFEST_BYTES = 1024 * 1024
# Web Mercator 瓦片最大缩放级别（超过 22 视为异常数据）
MAX_TILE_ZOOM = 22

_TILE_REL_RE = re.compile(r"^(?P<z>\d{1,2})/(?P<x>\d{1,7})/(?P<y>\d{1,7})\.png$")
_MANIFEST_NAME = "MANIFEST.json"

# 模块级别获取瓦片缓存目录。
# 使用 try/except 防护：如果 get_data_path() 因权限问题失败，
# 回退到用户临时目录，避免整个路由模块加载失败（crash log 中曾导致 41/42 路由加载）。
try:
    TILE_CACHE_DIR = get_data_path("offline_tiles")
except Exception as _e:
    import tempfile
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "离线地图缓存目录初始化失败，回退到临时目录: %s", _e
    )
    TILE_CACHE_DIR = Path(tempfile.gettempdir()) / "bumofu_offline_tiles"


class TilePackageError(ValueError):
    """瓦片包校验失败（message 为面向用户的中文提示，端点直接透传）。"""


# ==================== 目录扫描 / MANIFEST ====================


def scan_tiles_dir(root: Path) -> Dict[str, Any]:
    """扫描瓦片目录（``<z>/<x>/<y>.png`` 布局），返回计数/体积/缩放级别。

    目录不存在、扫描中被删除、或某个文件 ``stat`` 失败时跳过而不是抛异常，
    保证 ``/map/tile-info`` 与 ``/offline-map/status`` 在瓦片仓未就绪时也返回零值。
    """
    total_tiles = 0
    total_bytes = 0
    zoom_levels: set = set()

    if not root.is_dir():
        return {
            "total_tiles": 0,
            "total_bytes": 0,
            "total_size_mb": 0.0,
            "zoom_levels": [],
        }

    for z_dir in root.iterdir():
        if not z_dir.is_dir():
            continue
        try:
            zoom_level = int(z_dir.name)
        except ValueError:
            # 非缩放层目录（如 tmp/、README）直接跳过
            continue
        zoom_levels.add(zoom_level)
        for x_dir in z_dir.iterdir():
            if not x_dir.is_dir():
                continue
            for tile_file in x_dir.iterdir():
                if tile_file.suffix != ".png":
                    continue
                try:
                    total_bytes += tile_file.stat().st_size
                except OSError:
                    # 扫描期间文件被并发删除/占用：跳过该文件而非中断统计
                    continue
                total_tiles += 1

    return {
        "total_tiles": total_tiles,
        "total_bytes": total_bytes,
        "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        "zoom_levels": sorted(zoom_levels),
    }


def normalize_manifest(raw: Any) -> Dict[str, Any]:
    """规范化并校验 MANIFEST.json 内容。

    Raises:
        TilePackageError: 不是 JSON 对象 / 字段类型非法 / 缺少全部关键字段
    """
    if not isinstance(raw, dict):
        raise TilePackageError("MANIFEST.json 必须是 JSON 对象")

    z_range: Optional[List[int]] = None
    zoom = raw.get("zoom")
    if isinstance(zoom, dict):
        try:
            z_min = int(zoom["min"])
            z_max = int(zoom["max"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TilePackageError("MANIFEST.json 的 zoom 字段非法（应为 {\"min\":a,\"max\":b}）") from exc
        if z_min > z_max:
            raise TilePackageError("MANIFEST.json 的 zoom.min 不能大于 zoom.max")
        z_range = [z_min, z_max]
    elif isinstance(zoom, (list, tuple)) and len(zoom) == 2:
        try:
            z_range = [int(zoom[0]), int(zoom[1])]
        except (TypeError, ValueError) as exc:
            raise TilePackageError("MANIFEST.json 的 zoom 字段非法（应为两个整数）") from exc
    else:
        levels = raw.get("zoomLevels")
        if isinstance(levels, list) and levels:
            try:
                int_levels = [int(level) for level in levels]
            except (TypeError, ValueError) as exc:
                raise TilePackageError("MANIFEST.json 的 zoomLevels 字段非法（应为整数列表）") from exc
            z_range = [min(int_levels), max(int_levels)]

    tile_count = raw.get("tileCount")
    total_bytes = raw.get("totalBytes")
    for field, value in (("tileCount", tile_count), ("totalBytes", total_bytes)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise TilePackageError(f"MANIFEST.json 的 {field} 字段非法（应为非负整数）")

    if z_range is None and tile_count is None and total_bytes is None:
        raise TilePackageError("MANIFEST.json 缺少必要字段（zoom / zoomLevels / tileCount）")

    return {
        "provider": raw.get("provider"),
        "license": raw.get("license"),
        "coordinateSystem": raw.get("coordinateSystem"),
        "zRange": z_range,
        "generatedAt": raw.get("generatedAt"),
        "tileCount": tile_count,
        "totalBytes": total_bytes,
    }


def read_manifest_file(path: Path) -> Optional[Dict[str, Any]]:
    """读取并规范化 MANIFEST.json；不存在/不可解析/内容非法时返回 ``None``。

    ``/map/tile-info`` 用宽松语义：元数据损坏不应让瓦片服务整体 500，
    真实瓦片计数始终由目录扫描得到。
    """
    try:
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return normalize_manifest(raw)
    except (OSError, ValueError, TypeError, UnicodeDecodeError) as exc:
        logger.warning("读取瓦片 MANIFEST.json 失败: %s", exc)
        return None


def _check_manifest_against(
    manifest: Dict[str, Any],
    tile_entries: List[Tuple[str, int, int, int]],
    total_bytes: int,
) -> None:
    """把 MANIFEST 声明值与实际瓦片集合交叉校验（声明缺省则跳过该项）。"""
    levels = sorted({entry[1] for entry in tile_entries})
    declared_count = manifest["tileCount"]
    if declared_count is not None and declared_count != len(tile_entries):
        raise TilePackageError(
            f"MANIFEST.json 的 tileCount({declared_count}) 与实际瓦片数({len(tile_entries)}) 不一致"
        )
    declared_bytes = manifest["totalBytes"]
    if declared_bytes is not None and declared_bytes != total_bytes:
        raise TilePackageError(
            f"MANIFEST.json 的 totalBytes({declared_bytes}) 与实际体积({total_bytes}) 不一致"
        )
    declared_range = manifest["zRange"]
    if declared_range is not None and [levels[0], levels[-1]] != declared_range:
        raise TilePackageError(
            f"MANIFEST.json 的缩放范围({declared_range[0]}-{declared_range[1]}) "
            f"与实际目录({levels[0]}-{levels[-1]}) 不一致"
        )


# ==================== 路径安全（zip-slip / 符号链接） ====================


def _safe_relative(name: str) -> str:
    """规范化包内相对路径；拒绝绝对路径、盘符与 ``..`` 穿越。"""
    raw = str(name or "").replace("\\", "/").strip()
    if not raw:
        raise TilePackageError("瓦片包内存在空文件名")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise TilePackageError(f"瓦片包内存在非法绝对路径: {name}")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or ".." in parts:
        raise TilePackageError(f"瓦片包内存在路径穿越: {name}")
    return "/".join(parts)


def _parse_tile_rel(rel: str) -> Tuple[int, int, int]:
    """解析 ``z/x/y.png`` 相对路径并校验坐标范围。"""
    match = _TILE_REL_RE.match(rel)
    if not match:
        raise TilePackageError(f"瓦片包内存在非瓦片文件: {rel}")
    z = int(match["z"])
    x = int(match["x"])
    y = int(match["y"])
    if z > MAX_TILE_ZOOM:
        raise TilePackageError(f"瓦片缩放级别超出范围: {rel}")
    limit = 1 << z
    if x >= limit or y >= limit:
        raise TilePackageError(f"瓦片坐标越界: {rel}")
    return z, x, y


def _write_tile(target: Path, dest: Path, data: bytes) -> int:
    """写入单张瓦片（二次校验不含目录穿越），返回 1 表示覆盖已有文件。"""
    try:
        target.resolve().relative_to(dest.resolve())
    except ValueError as exc:
        raise TilePackageError(f"瓦片写入路径越界: {target}") from exc
    existed = int(target.is_file())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return existed


def _verify_tile_hash(hashes: Any, rel: str, data: bytes) -> None:
    """若 MANIFEST 声明了该瓦片的 SHA256，则校验内容（未声明则跳过）。"""
    if not isinstance(hashes, dict):
        return
    expected = hashes.get(rel)
    if not expected:
        return
    actual = hashlib.sha256(data).hexdigest()
    if str(expected).lower() != actual:
        raise TilePackageError(f"瓦片 {rel} 的 SHA256 校验失败（文件可能被篡改或损坏）")


def _manifest_prefix(rel_names: List[str]) -> str:
    """定位 MANIFEST.json，返回其所在前缀（``""`` 或 ``"tiles/``）。

    只允许根目录或单一顶层目录，避免压缩包把 MANIFEST 与瓦片放在不同根下。
    """
    candidates = [
        name for name in rel_names if name == _MANIFEST_NAME or name.endswith("/" + _MANIFEST_NAME)
    ]
    if not candidates:
        raise TilePackageError(f"瓦片包缺少 {_MANIFEST_NAME}")
    if len(candidates) > 1:
        raise TilePackageError(f"瓦片包内存在多个 {_MANIFEST_NAME}")
    prefix = candidates[0][: -len(_MANIFEST_NAME)]
    if prefix and (prefix.count("/") != 1 or not prefix.endswith("/")):
        raise TilePackageError(f"{_MANIFEST_NAME} 必须位于压缩包根目录或单一顶层目录下")
    return prefix


def _manifest_from_bytes(manifest_bytes: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """解析 MANIFEST 字节流，返回 (规范化元数据, 原始 dict)。

    Raises:
        TilePackageError: 非 UTF-8 JSON / 字段非法
    """
    try:
        raw = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TilePackageError("MANIFEST.json 不是合法的 UTF-8 JSON 文件") from exc
    return normalize_manifest(raw), raw


def _collect_zip_tiles(zf: zipfile.ZipFile) -> Tuple[str, List[Dict[str, Any]], int]:
    """遍历 ZIP，返回 (manifest 原始成员名, 瓦片元数据列表, 忽略文件数)。

    - 绝对路径 / ``..`` / 盘符：直接拒绝（zip-slip）；
    - 与 MANIFEST 不同根目录的文件、非 ``z/x/y.png`` 文件：忽略并计数。
    """
    entries: List[Tuple[Any, str]] = [
        (info, _safe_relative(info.filename)) for info in zf.infolist() if not info.is_dir()
    ]
    if not entries:
        raise TilePackageError("瓦片包为空（没有任何文件）")

    prefix = _manifest_prefix([rel for _info, rel in entries])
    manifest_rel = prefix + _MANIFEST_NAME
    manifest_member = next(info.filename for info, rel in entries if rel == manifest_rel)

    metas: List[Dict[str, Any]] = []
    ignored = 0
    for info, rel in entries:
        if rel == manifest_rel:
            continue
        if not rel.startswith(prefix):
            ignored += 1
            continue
        sub = rel[len(prefix):]
        if not _TILE_REL_RE.match(sub):
            ignored += 1
            continue
        z, x, y = _parse_tile_rel(sub)
        metas.append(
            {
                "member": info.filename,
                "rel": sub,
                "z": z,
                "x": x,
                "y": y,
                "size": int(getattr(info, "file_size", 0) or 0),
            }
        )
    return manifest_member, metas, ignored


def import_tile_zip(zf: zipfile.ZipFile, dest: Path) -> Dict[str, Any]:
    """校验并导入一个已打开的瓦片 ZIP 包到 ``dest``（合并写入，不删除既有瓦片）。

    Raises:
        TilePackageError: 包结构/MANIFEST/数量/体积/SHA256 任一项不合规
        HTTPException: 解压后超限（由 upload_helper 抛 413）
    """
    ensure_zip_within_limit(zf, MAX_TILES_TOTAL_BYTES)

    manifest_member, metas, ignored = _collect_zip_tiles(zf)
    manifest_bytes = read_zip_member(zf, manifest_member, MAX_MANIFEST_BYTES)
    manifest, raw_manifest = _manifest_from_bytes(manifest_bytes)
    hashes = raw_manifest.get("hashes")

    if not metas:
        raise TilePackageError("瓦片包内没有瓦片文件（目录结构应为 z/x/y.png）")
    if len(metas) > MAX_TILES_PER_IMPORT:
        raise TilePackageError(
            f"瓦片包内瓦片数 {len(metas)} 超过单次导入上限 {MAX_TILES_PER_IMPORT}"
        )

    total_bytes = sum(meta["size"] for meta in metas)

    tile_entries = [(meta["rel"], meta["z"], meta["x"], meta["y"]) for meta in metas]
    _check_manifest_against(manifest, tile_entries, total_bytes)

    overwritten = 0
    for meta in metas:
        data = read_zip_member(zf, meta["member"], MAX_TILE_MEMBER_BYTES)
        _verify_tile_hash(hashes, meta["rel"], data)
        target = dest / str(meta["z"]) / str(meta["x"]) / f"{meta['y']}.png"
        overwritten += _write_tile(target, dest, data)

    dest.mkdir(parents=True, exist_ok=True)
    (dest / _MANIFEST_NAME).write_bytes(manifest_bytes)

    return {
        "tileCount": len(metas),
        "totalBytes": total_bytes,
        "overwritten": overwritten,
        "zoomLevels": sorted({meta["z"] for meta in metas}),
        "manifest": manifest,
        "ignored": ignored,
    }


def import_tile_zip_bytes(data: bytes, dest: Path) -> Dict[str, Any]:
    """从 ZIP 字节流导入瓦片包（端点上传路径）。"""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise TilePackageError("上传的文件不是有效的 ZIP 压缩包") from exc
    with zf:
        return import_tile_zip(zf, dest)


def _locate_manifest_root(src: Path) -> Tuple[Path, Path]:
    """定位本机目录中的瓦片包根（支持根目录或单一子目录）。"""
    direct = src / _MANIFEST_NAME
    if direct.is_file():
        return src, direct
    candidates = [child / _MANIFEST_NAME for child in src.iterdir() if child.is_dir()]
    candidates = [path for path in candidates if path.is_file()]
    if len(candidates) == 1:
        return candidates[0].parent, candidates[0]
    raise TilePackageError(f"瓦片目录缺少 {_MANIFEST_NAME}: {src}")


def _collect_directory_tiles(base: Path) -> Tuple[List[Tuple[Path, str, int, int, int, int]], int]:
    """遍历本机瓦片目录，返回 ``[(路径, 相对路径, z, x, y, 字节数)], 忽略文件数``。

    安全：符号链接一律拒绝（避免导入指向瓦片仓外的文件）；非瓦片文件忽略。
    """
    entries: List[Tuple[Path, str, int, int, int, int]] = []
    ignored = 0
    for dirpath, dirnames, filenames in os.walk(base):
        for dirname in dirnames:
            if os.path.islink(os.path.join(dirpath, dirname)):
                raise TilePackageError(f"瓦片目录含符号链接，已拒绝: {dirname}")
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            rel = path.relative_to(base).as_posix()
            if rel == _MANIFEST_NAME:
                continue
            if not _TILE_REL_RE.match(rel):
                ignored += 1
                continue
            if os.path.islink(path):
                raise TilePackageError(f"瓦片目录含符号链接，已拒绝: {rel}")
            z, x, y = _parse_tile_rel(rel)
            try:
                size = path.stat().st_size
            except OSError as exc:
                raise TilePackageError(f"读取瓦片失败: {rel}") from exc
            if size > MAX_TILE_MEMBER_BYTES:
                raise TilePackageError(f"瓦片 {rel} 超过 {MAX_TILE_MEMBER_BYTES} 字节上限")
            entries.append((path, rel, z, x, y, size))
            if len(entries) > MAX_TILES_PER_IMPORT:
                raise TilePackageError(
                    f"瓦片目录内瓦片数超过单次导入上限 {MAX_TILES_PER_IMPORT}"
                )
    return entries, ignored


def _copy_directory_tiles(
    entries: List[Tuple[Path, str, int, int, int, int]], hashes: Any, dest: Path
) -> int:
    """把本机目录条目写入瓦片仓，返回覆盖数量。"""
    overwritten = 0
    for path, rel, z, x, y, _size in entries:
        data = path.read_bytes()
        _verify_tile_hash(hashes, rel, data)
        overwritten += _write_tile(dest / str(z) / str(x) / f"{y}.png", dest, data)
    return overwritten


def import_tile_directory(src: Path, dest: Path) -> Dict[str, Any]:
    """校验并导入本机目录中的瓦片包（U 盘导入路径，免上传大包）。

    与 ZIP 路径共用 MANIFEST/数量/体积/SHA256 校验；额外拒绝符号链接。
    """
    source = Path(src)
    if not source.is_dir():
        raise TilePackageError(f"瓦片目录不存在: {source}")

    base, manifest_path = _locate_manifest_root(source)
    try:
        manifest_size = manifest_path.stat().st_size
    except OSError as exc:
        raise TilePackageError(f"读取 MANIFEST.json 失败: {exc}") from exc
    if manifest_size > MAX_MANIFEST_BYTES:
        raise TilePackageError(f"MANIFEST.json 超过 {MAX_MANIFEST_BYTES} 字节上限")
    manifest_bytes = manifest_path.read_bytes()
    manifest, raw_manifest = _manifest_from_bytes(manifest_bytes)
    hashes = raw_manifest.get("hashes")

    file_entries, ignored = _collect_directory_tiles(base)
    if not file_entries:
        raise TilePackageError("瓦片目录内没有瓦片文件（目录结构应为 z/x/y.png）")

    total_bytes = sum(entry[5] for entry in file_entries)
    if total_bytes > MAX_TILES_TOTAL_BYTES:
        raise TilePackageError(
            f"瓦片目录总体积 {total_bytes} 字节超过上限 {MAX_TILES_TOTAL_BYTES} 字节"
        )

    tile_entries = [(entry[1], entry[2], entry[3], entry[4]) for entry in file_entries]
    _check_manifest_against(manifest, tile_entries, total_bytes)

    overwritten = _copy_directory_tiles(file_entries, hashes, dest)

    dest.mkdir(parents=True, exist_ok=True)
    (dest / _MANIFEST_NAME).write_bytes(manifest_bytes)

    return {
        "tileCount": len(file_entries),
        "totalBytes": total_bytes,
        "overwritten": overwritten,
        "zoomLevels": sorted({entry[2] for entry in file_entries}),
        "manifest": manifest,
        "ignored": ignored,
    }


class OfflineMapService:
    """
    离线地图服务

    管理离线地图的下载和使用
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or TILE_CACHE_DIR
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"创建离线地图缓存目录失败: {e}")
        self._map_data = {}
        self._coverage_cache: Optional[Dict[str, Any]] = None

    def get_tile_path(self, z: int, x: int, y: int) -> Path:
        """获取瓦片文件路径"""
        return self.cache_dir / f"{z}/{x}/{y}.png"

    async def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        """获取瓦片数据"""
        tile_path = self.get_tile_path(z, x, y)
        if not tile_path.exists():
            return None
        try:
            async with aiofiles.open(tile_path, "rb") as f:
                data = await f.read(MAX_TILE_BYTES)
            return data
        except Exception:
            logger.warning("离线地图瓦片读取失败: %s", tile_path, exc_info=True)
            return None

    async def save_tile(self, z: int, x: int, y: int, data: bytes) -> bool:
        """保存瓦片数据"""
        try:
            tile_path = self.get_tile_path(z, x, y)
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(tile_path, "wb") as f:
                await f.write(data)
            self._coverage_cache = None  # 覆盖范围变更，刷新缓存
            return True
        except Exception as e:
            logger.error(f"Failed to save tile: {e}")
            return False

    async def get_coverage(self) -> Dict[str, Any]:
        """获取瓦片缓存覆盖统计（带缓存）。

        cache_dir 在 __init__ 中创建失败或事后被外部删除时，扫描会得到零值；
        此时应返回"零覆盖"而非 500。
        """
        if self._coverage_cache is not None:
            return self._coverage_cache

        stats = scan_tiles_dir(self.cache_dir)
        self._coverage_cache = {
            "total_tiles": stats["total_tiles"],
            "total_size_mb": stats["total_size_mb"],
            "zoom_levels": stats["zoom_levels"],
        }
        return self._coverage_cache

    def tile_to_lat_lon(self, x: int, y: int, z: int) -> Tuple[float, float]:
        """将瓦片坐标转换为经纬度"""
        n = 2.0**z
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)
        return (lat_deg, lon_deg)

    def lat_lon_to_tile(self, lat: float, lon: float, z: int) -> Tuple[int, int]:
        """将经纬度转换为瓦片坐标"""
        lat_rad = math.radians(lat)
        n = 2.0**z
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x, y)

    def clear_cache(self):
        """清除地图缓存"""
        self._map_data.clear()
        self._coverage_cache = None


# 全局单例
offline_map_service = OfflineMapService()
