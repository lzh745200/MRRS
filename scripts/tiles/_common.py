"""瓦片工具链共享逻辑（仅标准库，Python 3.8+）。

目录结构约定（与后端 ``app/api/v1/map.py``、Electron ``extraResources`` 一致）::

    <tiles>/
      MANIFEST.json
      <z>/<x>/<y>.png

坐标系统：Web Mercator（EPSG:3857）XYZ 瓦片编号，与 Leaflet / OSM 一致。
本模块不触网、不依赖第三方库；PNG 解码校验在 Pillow 可用时增强。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

MANIFEST_NAME = "MANIFEST.json"
SCHEMA_VERSION = 1
# 256x256 PNG 实测 5~50KB；纯色/水体偏小、城区偏大，18KB 作为估算均值
DEFAULT_AVG_TILE_BYTES = 18 * 1024
MAX_TILE_ZOOM = 22
MAX_TILES = 200_000
MAX_TILE_MEMBER_BYTES = 5 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# 默认区域：黔南布依族苗族自治州 bbox（min_lon, min_lat, max_lon, max_lat）
DEFAULT_BBOX = (106.0, 25.1, 108.5, 26.9)
DEFAULT_OUT = "resources/map-tiles"
DEFAULT_ZOOM = "6-12"

TILE_RE = re.compile(r"^(?P<z>\d{1,2})/(?P<x>\d{1,7})/(?P<y>\d{1,7})\.png$")


# ==================== 控制台/输出 ====================


def setup_console() -> None:
    """Windows 控制台（cp936/cp1252）下尽量切 UTF-8，保证中文提示可读。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def log(message: str = "") -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"[警告] {message}", file=sys.stderr, flush=True)


def error(message: str) -> None:
    print(f"[错误] {message}", file=sys.stderr, flush=True)


class TileToolError(Exception):
    """工具链校验失败（message 直接展示给运维）。"""


def fail(message: str, code: int = 1) -> None:
    """打印中文错误并以非零码退出（脚本统一失败出口）。"""
    error(message)
    raise SystemExit(code)


def human_bytes(num: float) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}TB"


# ==================== 参数/几何 ====================


def parse_bbox(text: str) -> Tuple[float, float, float, float]:
    """解析 ``min_lon,min_lat,max_lon,max_lat``（兼容中文逗号）。"""
    raw = str(text or "").replace("，", ",").strip()
    try:
        values = [float(part) for part in raw.split(",")]
    except ValueError as exc:
        raise TileToolError(f"bbox 格式非法: {text}（应为 min_lon,min_lat,max_lon,max_lat）") from exc
    if len(values) != 4:
        raise TileToolError(f"bbox 需要 4 个数值: {text}")
    min_lon, min_lat, max_lon, max_lat = values
    if not (-180.0 <= min_lon < max_lon <= 180.0):
        raise TileToolError(f"bbox 经度非法: {min_lon}..{max_lon}（应 -180≤min<max≤180）")
    if not (-85.05 <= min_lat < max_lat <= 85.05):
        raise TileToolError(f"bbox 纬度非法: {min_lat}..{max_lat}（Web Mercator 限 ±85.05）")
    return min_lon, min_lat, max_lon, max_lat


def parse_zoom(text: str) -> Tuple[int, int]:
    """解析缩放级别范围：``6-12`` / ``10``。"""
    raw = str(text or "").strip().replace("，", ",")
    try:
        if "-" in raw:
            start, end = raw.split("-", 1)
            z_min, z_max = int(start), int(end)
        else:
            z_min = z_max = int(raw)
    except ValueError as exc:
        raise TileToolError(f"缩放级别格式非法: {text}（示例: 6-12 或 10）") from exc
    if not (0 <= z_min <= z_max <= MAX_TILE_ZOOM):
        raise TileToolError(f"缩放级别越界: {text}（应 0≤min≤max≤{MAX_TILE_ZOOM}）")
    return z_min, z_max


def lonlat_to_tile(lon: float, lat: float, z: int) -> Tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def tile_range(bbox: Tuple[float, float, float, float], z: int) -> Tuple[int, int, int, int]:
    """bbox 在缩放级 z 覆盖的瓦片范围 ``(x_min, x_max, y_min, y_max)``。"""
    min_lon, min_lat, max_lon, max_lat = bbox
    x_min, y_min = lonlat_to_tile(min_lon, max_lat, z)
    x_max, y_max = lonlat_to_tile(max_lon, min_lat, z)
    return x_min, x_max, y_min, y_max


def iter_tiles(
    bbox: Tuple[float, float, float, float], z_min: int, z_max: int
) -> Iterable[Tuple[int, int, int]]:
    for z in range(z_min, z_max + 1):
        x_min, x_max, y_min, y_max = tile_range(bbox, z)
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                yield z, x, y


def count_tiles(bbox: Tuple[float, float, float, float], z_min: int, z_max: int) -> int:
    total = 0
    for z in range(z_min, z_max + 1):
        x_min, x_max, y_min, y_max = tile_range(bbox, z)
        total += (x_max - x_min + 1) * (y_max - y_min + 1)
    return total


def count_tiles_by_zoom(
    bbox: Tuple[float, float, float, float], z_min: int, z_max: int
) -> List[Tuple[int, int]]:
    rows = []
    for z in range(z_min, z_max + 1):
        x_min, x_max, y_min, y_max = tile_range(bbox, z)
        rows.append((z, (x_max - x_min + 1) * (y_max - y_min + 1)))
    return rows


# ==================== 路径安全 ====================


def safe_relative(name: str) -> str:
    """规范化包内相对路径；拒绝绝对路径/盘符/``..``（zip-slip 防护）。"""
    raw = str(name or "").replace("\\", "/").strip()
    if not raw:
        raise TileToolError("压缩包内存在空文件名")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise TileToolError(f"压缩包内存在非法绝对路径: {name}")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or ".." in parts:
        raise TileToolError(f"压缩包内存在路径穿越: {name}")
    return "/".join(parts)


def parse_tile_rel(rel: str) -> Tuple[int, int, int]:
    """解析 ``z/x/y.png``；非瓦片或坐标越界抛 TileToolError。"""
    match = TILE_RE.match(rel)
    if not match:
        raise TileToolError(f"非瓦片文件: {rel}")
    z, x, y = int(match["z"]), int(match["x"]), int(match["y"])
    if z > MAX_TILE_ZOOM:
        raise TileToolError(f"缩放级别超出范围: {rel}")
    limit = 1 << z
    if x >= limit or y >= limit:
        raise TileToolError(f"瓦片坐标越界: {rel}")
    return z, x, y


# ==================== MANIFEST ====================


def normalize_manifest(raw: Any) -> Dict[str, Any]:
    """校验并规范化 MANIFEST 内容（与后端 offline_map_service 同口径）。"""
    if not isinstance(raw, dict):
        raise TileToolError("MANIFEST.json 必须是 JSON 对象")

    z_min: Optional[int] = None
    z_max: Optional[int] = None
    declared_levels: Optional[List[int]] = None
    raw_levels = raw.get("zoomLevels")
    if isinstance(raw_levels, list) and raw_levels:
        try:
            declared_levels = sorted({int(level) for level in raw_levels})
        except (TypeError, ValueError) as exc:
            raise TileToolError("MANIFEST.json 的 zoomLevels 字段非法（应为整数列表）") from exc
    zoom = raw.get("zoom")
    if isinstance(zoom, dict):
        try:
            z_min, z_max = int(zoom["min"]), int(zoom["max"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TileToolError("MANIFEST.json 的 zoom 字段非法（应为 {\"min\":a,\"max\":b}）") from exc
        if z_min > z_max:
            raise TileToolError("MANIFEST.json 的 zoom.min 不能大于 zoom.max")
    elif isinstance(zoom, (list, tuple)) and len(zoom) == 2:
        try:
            z_min, z_max = int(zoom[0]), int(zoom[1])
        except (TypeError, ValueError) as exc:
            raise TileToolError("MANIFEST.json 的 zoom 字段非法（应为两个整数）") from exc
    elif declared_levels:
        z_min, z_max = declared_levels[0], declared_levels[-1]

    tile_count = raw.get("tileCount")
    total_bytes = raw.get("totalBytes")
    for field, value in (("tileCount", tile_count), ("totalBytes", total_bytes)):
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise TileToolError(f"MANIFEST.json 的 {field} 字段非法（应为非负整数）")

    if z_min is None and tile_count is None and total_bytes is None:
        raise TileToolError("MANIFEST.json 缺少必要字段（zoom / zoomLevels / tileCount）")

    return {
        "provider": raw.get("provider"),
        "license": raw.get("license"),
        "coordinateSystem": raw.get("coordinateSystem"),
        "zRange": [z_min, z_max] if z_min is not None else None,
        "zoomLevels": declared_levels,
        "generatedAt": raw.get("generatedAt"),
        "tileCount": tile_count,
        "totalBytes": total_bytes,
    }


def load_manifest_text(text: str) -> Dict[str, Any]:
    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise TileToolError(f"MANIFEST.json 不是合法 JSON: {exc}") from exc
    return normalize_manifest(raw)


def read_manifest(root: Path) -> Dict[str, Any]:
    path = Path(root) / MANIFEST_NAME
    if not path.is_file():
        raise TileToolError(f"缺少 {MANIFEST_NAME}: {path}")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise TileToolError(f"{MANIFEST_NAME} 超过 {MAX_MANIFEST_BYTES} 字节上限")
    return load_manifest_text(path.read_text(encoding="utf-8"))


def scan_tiles(root: Path) -> Tuple[int, int, List[int]]:
    """扫描 ``z/x/y.png``，返回 (瓦片数, 总字节, 缩放级别列表)。"""
    total = 0
    total_bytes = 0
    levels = set()
    root = Path(root)
    if not root.is_dir():
        return 0, 0, []
    for z_dir in root.iterdir():
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        levels.add(int(z_dir.name))
        for x_dir in z_dir.iterdir():
            if not x_dir.is_dir():
                continue
            for tile in x_dir.iterdir():
                if tile.suffix.lower() != ".png" or not tile.is_file():
                    continue
                try:
                    total_bytes += tile.stat().st_size
                except OSError:
                    continue
                total += 1
    return total, total_bytes, sorted(levels)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    provider: str,
    license_text: str,
    bbox: Optional[Tuple[float, float, float, float]],
    z_min: int,
    z_max: int,
    tile_count: int,
    total_bytes: int,
    coordinate_system: str = "EPSG:3857 XYZ",
    sources: Optional[List[str]] = None,
    hashes: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "provider": provider,
        "license": license_text,
        "coordinateSystem": coordinate_system,
        "bbox": list(bbox) if bbox else None,
        "zoom": {"min": z_min, "max": z_max},
        "zoomLevels": list(range(z_min, z_max + 1)),
        "tileCount": tile_count,
        "totalBytes": total_bytes,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if sources:
        manifest["sources"] = sources
    if hashes:
        manifest["hashes"] = hashes
    if extra:
        manifest.update(extra)
    return manifest


def write_manifest(root: Path, manifest: Dict[str, Any]) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / MANIFEST_NAME
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def check_png(path: Path) -> Tuple[bool, str]:
    """校验 PNG 文件头/IHDR；Pillow 可用时进一步完整解码。

    Returns:
        (是否通过, 失败原因)
    """
    try:
        with Path(path).open("rb") as handle:
            head = handle.read(64)
    except OSError as exc:
        return False, f"无法读取: {exc}"
    if not head.startswith(PNG_MAGIC):
        return False, "不是 PNG 文件（缺少 PNG 文件头）"
    if b"IHDR" not in head[:33]:
        return False, "PNG 缺少 IHDR 块"
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return True, ""
    try:
        with Image.open(path) as image:
            image.load()
    except Exception as exc:  # Pillow 解码失败：文件损坏
        return False, f"Pillow 解码失败: {exc}"
    return True, ""
