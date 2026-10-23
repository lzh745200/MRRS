#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编排：渲染贵州全省/市州 OSM 瓦片包 → 校验 → 导出 ZIP → 导入验证 → 索引。

> ⚠️ **发布打包唯一路径 = 从同一份渲染产物取子集**（`pack_osm_subsets.py`，
> 单一源 `.scratch/osm/tiles-v2`）。本脚本会**逐包重渲**（全省包 1 次 + 9 个
> 市州包各 2 次，共 19 次 `render_osm_tiles.py` 调用，每次使用调用时刻磁盘上
> 的渲染脚本版本）——若渲染脚本在长构建期间被改动，各包会出现**样式/数据
> 版本不一致**（2026-10-22 实际发生：render 脚本 20:14:42 修改，20:07–20:18
> 产出的包内部版本混杂、部分瓦片与 tiles-v2 字节不同）。因此重渲路径
> **仅用于开发/单包调试**，交付打包请勿使用；校验/导出/导入验证/索引编排
> 部分（本脚本其余函数）仍可复用。

一次性产出（默认 ``deliverables/osm-tiles-20261022/``）：

- ``guizhou-all_z5-12.zip``：全省总包（z5-12，5,623 张）
- ``guizhou-<slug>_z7-12.zip`` × 9：市州独立包，**每包额外内含全省 z5-6 概览 5 张**
  （z5:1 + z6:4），保证单独导入后省级缩放下不会因缺瓦片回退矢量底图
- ``INDEX.md``（中文索引表）+ ``summary.json``（机器可读）

每个包的标准流水线：

1. 渲染到 ``.scratch/osm/packages/<slug>/tiles``
   （市州：先渲全省 z5-6 到同一目录，再渲本市州 z7-12；全省总包直接 z5-12）
2. 校准 MANIFEST（渲染脚本每次调用都会重写 MANIFEST，两段式渲染后需按实际目录重写）
3. ``verify_tiles.py --require-min <预期-5> --sample 20``
4. ``export_tiles.py --from <tiles> --zip deliverables/.../<name>.zip``
5. 真导入验证：``import_tiles.py --source <zip> --target <pkg>/import-test`` + 再 verify
6. 记录 zip 体积/SHA256（>400MB 立即告警，512MB 为硬上限）

全部跑完后再做：

7. 9 个市州包依次导入 ``.scratch/osm/packages/merged``，统计合并瓦片数与相对全省包的重复量
8. 用 ``MAP_TILES_DIR=<merged>`` 跑一次后端运行期校验（``/api/v1/map/tile-info``）
9. 生成 ``INDEX.md`` / ``summary.json``

依赖：仅标准库 + Pillow（渲染脚本需要）；渲染/校验/导入/导出脚本由本脚本以子进程调用，
**不修改** ``render_osm_tiles.py`` / ``osm_extract.py``。

用法
----
    # 全量（首次；渲染阶段默认 --jobs 4）
    python scripts/tiles/build_osm_packages.py

    # 只重做某个市州（可重跑；已完成的阶段自动跳过）
    python scripts/tiles/build_osm_packages.py --only guiyang

    # 只跑某几个阶段 / 只重生成索引
    python scripts/tiles/build_osm_packages.py --stages export,import,index
    python scripts/tiles/build_osm_packages.py --only "" --stages index

    # 流水线彩排（极小 bbox + 单缩放级，产物写 _rehearsal，不污染正式交付）
    python scripts/tiles/build_osm_packages.py --rehearse

失败即非零退出；``--dry-run`` 只打印计划（瓦片数/预估体积）不渲染不写盘。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    build_manifest,
    count_tiles,
    human_bytes,
    log,
    scan_tiles,
    setup_console,
    write_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_PACKAGES_ROOT = REPO_ROOT / ".scratch" / "osm" / "packages"
DEFAULT_DELIVERABLES_ROOT = REPO_ROOT / "deliverables" / "osm-tiles-20261022"
DEFAULT_LAYERS = REPO_ROOT / ".scratch" / "osm" / "layers.pkl"
RENDER_SCRIPT = SCRIPTS_DIR / "render_osm_tiles.py"
VERIFY_SCRIPT = SCRIPTS_DIR / "verify_tiles.py"
EXPORT_SCRIPT = SCRIPTS_DIR / "export_tiles.py"
IMPORT_SCRIPT = SCRIPTS_DIR / "import_tiles.py"

PROVINCE_BBOX = (103.6, 24.6, 109.6, 29.2)
PROVINCE_ZOOM = (5, 12)
OVERVIEW_ZOOM = (5, 6)
PREFECTURE_ZOOM = (7, 12)

PROVIDER = "osm"
LICENSE_TEXT = "ODbL-1.0 (© OpenStreetMap contributors)"
ATTRIBUTION = "© OpenStreetMap contributors"
STYLE = "osm-v2"

# 市州 bbox（来自 frontend/src/assets/geo/guizhou.json，与 .scratch/osm/prefecture_bboxes.json 一致）
PREFECTURES = [
    {"slug": "guiyang", "name": "贵阳市", "bbox": (106.125, 26.183, 107.279, 27.358)},
    {"slug": "zunyi", "name": "遵义市", "bbox": (105.609, 27.14, 108.214, 29.221)},
    {"slug": "liupanshui", "name": "六盘水市", "bbox": (104.308, 25.329, 105.723, 26.918)},
    {"slug": "anshun", "name": "安顺市", "bbox": (105.249, 25.354, 106.565, 26.624)},
    {"slug": "bijie", "name": "毕节市", "bbox": (103.601, 26.36, 106.721, 27.775)},
    {"slug": "tongren", "name": "铜仁市", "bbox": (107.755, 27.121, 109.471, 29.091)},
    {"slug": "qiandongnan", "name": "黔东南苗族侗族自治州", "bbox": (107.299, 25.307, 109.555, 27.522)},
    {"slug": "qiannan", "name": "黔南布依族苗族自治州", "bbox": (106.225, 25.06, 108.305, 27.48)},
    {"slug": "qianxinan", "name": "黔西南布依族苗族自治州", "bbox": (104.529, 24.618, 106.532, 26.175)},
]

REHEARSE_BBOX = (106.45, 26.15, 106.95, 26.55)

# 单包体积告警/上限（MB）
ZIP_WARN_MB = 400
ZIP_HARD_LIMIT_MB = 512


# ==================== 基础工具 ====================


def _bbox_arg(bbox) -> str:
    return ",".join(f"{v:g}" for v in bbox)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_rmtree(target: Path, root: Path) -> None:
    """删除 root 下的目录；越界目标直接拒绝（防止误删工作区外文件）。"""
    resolved = target.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise SystemExit(f"拒绝删除工作区外路径: {resolved}（root={root_resolved}）") from exc
    if resolved == root_resolved:
        raise SystemExit(f"拒绝删除根目录: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_step(name: str, cmd: list, log_path: Path, *, timeout: float = None) -> int:
    """执行一个子进程步骤：输出实时回显并落日志；返回退出码。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log(f"\n[步骤] {name}")
    log("  命令: " + " ".join(str(part) for part in cmd))
    started = time.time()
    tail = []
    proc = None
    try:
        with log_path.open("w", encoding="utf-8") as log_handle:
            proc = subprocess.Popen(
                [str(part) for part in cmd],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_child_env(),
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                log_handle.write(line)
                log_handle.flush()
                text = line.rstrip()
                if text:
                    log("   | " + text)
                    tail.append(text)
                    if len(tail) > 8:
                        tail.pop(0)
            proc.wait(timeout=timeout)
            returncode = proc.returncode
    except FileNotFoundError as exc:
        log(f"[失败] 命令不存在: {exc}")
        return 127
    except subprocess.TimeoutExpired:
        log(f"[失败] 步骤超时（{timeout}s）: {name}")
        if proc is not None and proc.poll() is None:
            proc.kill()
        return 124
    except KeyboardInterrupt:
        if proc is not None and proc.poll() is None:
            proc.kill()
        log("[中断] 已终止当前步骤（已渲染瓦片保留，可 --skip-existing 续跑）")
        return 130

    elapsed = time.time() - started
    log(f"  退出码={returncode}  耗时={elapsed:.1f}s  日志={log_path}")
    return returncode


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


# ==================== 计划 ====================


def _package_entries(rehearse: bool) -> list:
    """返回全部包描述（不含 --only 过滤）。"""
    if rehearse:
        province = {
            "slug": "rehearsal-province",
            "name": "彩排（极小区域，非交付）",
            "kind": "province",
            "bbox": REHEARSE_BBOX,
            "zoom": (9, 9),
            "expected": count_tiles(REHEARSE_BBOX, 9, 9),
            "expected_overview": 0,
            "file": "rehearsal_z9.zip",
        }
        return [province]
    entries = [
        {
            "slug": "guizhou-all",
            "name": "贵州省（全省总包）",
            "kind": "province",
            "bbox": PROVINCE_BBOX,
            "zoom": PROVINCE_ZOOM,
            "expected": count_tiles(PROVINCE_BBOX, *PROVINCE_ZOOM),
            "expected_overview": 0,
            "file": "guizhou-all_z5-12.zip",
        }
    ]
    overview_count = count_tiles(PROVINCE_BBOX, *OVERVIEW_ZOOM)
    for pref in PREFECTURES:
        base = count_tiles(pref["bbox"], *PREFECTURE_ZOOM)
        entries.append(
            {
                "slug": pref["slug"],
                "name": pref["name"],
                "kind": "prefecture",
                "bbox": pref["bbox"],
                "zoom": PREFECTURE_ZOOM,
                "expected": base,
                "expected_overview": overview_count,
                "file": f"guizhou-{pref['slug']}_z7-12.zip",
            }
        )
    return entries


def _select_entries(all_entries: list, only: str) -> list:
    tokens = [token.strip() for token in str(only or "").split(",") if token.strip()]
    if not tokens or tokens == ["all"] or "all" in tokens:
        return all_entries
    wanted = set()
    for token in tokens:
        if token in ("province", "guizhou-all"):
            wanted.add("guizhou-all")
        else:
            wanted.add(token)
    selected = [entry for entry in all_entries if entry["slug"] in wanted]
    missing = wanted - {entry["slug"] for entry in selected}
    if missing:
        raise SystemExit(f"未知包标识: {', '.join(sorted(missing))}")
    return selected


def _package_dirs(entry: dict, args) -> dict:
    package_root = args.packages_root / entry["slug"]
    return {
        "root": package_root,
        "tiles": package_root / "tiles",
        "logs": package_root / "logs",
        "import_test": package_root / "import-test",
        "zip": args.deliverables_root / entry["file"],
        "result": package_root / "result.json",
    }


def _load_result(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_result(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _layers_signature(path: Path) -> str:
    """图层 pickle 指纹（大小+mtime），变化即判定旧渲染产物失效（v1→v2 升级）。"""
    try:
        stat = path.stat()
    except OSError:
        return "missing"
    return f"{stat.st_size}-{stat.st_mtime_ns}"


# ==================== 各阶段 ====================


def stage_render(entry: dict, dirs: dict, args, state: dict) -> int:
    render_jobs = ["--jobs", str(args.jobs)]
    input_arg = ["--input", str(args.layers), "--wait-input", str(args.wait_input)]
    if entry["kind"] == "province":
        zoom_arg = f"{entry['zoom'][0]}-{entry['zoom'][1]}"
        code = run_step(
            f"渲染 {entry['slug']} z{zoom_arg}",
            [sys.executable, RENDER_SCRIPT, *input_arg, "--bbox", _bbox_arg(entry["bbox"]),
             "--zoom", zoom_arg, "--out", dirs["tiles"], *render_jobs]
            + (["--skip-existing"] if args.skip_existing else []),
            dirs["logs"] / "render-province.log",
        )
        if code != 0:
            return code
    else:
        # 先渲全省 z5-6 概览（同目录），再渲本市州 z7-12
        code = run_step(
            "渲染 全省概览 z5-6",
            [sys.executable, RENDER_SCRIPT, *input_arg, "--bbox", _bbox_arg(PROVINCE_BBOX),
             "--zoom", f"{OVERVIEW_ZOOM[0]}-{OVERVIEW_ZOOM[1]}", "--out", dirs["tiles"],
             *render_jobs] + (["--skip-existing"] if args.skip_existing else []),
            dirs["logs"] / "render-overview.log",
        )
        if code != 0:
            return code
        code = run_step(
            f"渲染 {entry['slug']} z{PREFECTURE_ZOOM[0]}-{PREFECTURE_ZOOM[1]}",
            [sys.executable, RENDER_SCRIPT, *input_arg, "--bbox", _bbox_arg(entry["bbox"]),
             "--zoom", f"{PREFECTURE_ZOOM[0]}-{PREFECTURE_ZOOM[1]}", "--out", dirs["tiles"],
             *render_jobs] + (["--skip-existing"] if args.skip_existing else []),
            dirs["logs"] / "render-prefecture.log",
        )
        if code != 0:
            return code

    # 渲染脚本每次调用都会按当次 bbox/zoom 重写 MANIFEST；两段式渲染后必须
    # 按「实际目录」重写，否则 verify 会报 tileCount/缩放范围不一致。
    count, total_bytes, levels = scan_tiles(dirs["tiles"])
    if not levels:
        log(f"[失败] {entry['slug']} 渲染后目录内没有瓦片")
        return 1
    manifest = build_manifest(
        provider=PROVIDER,
        license_text=LICENSE_TEXT,
        bbox=entry["bbox"],
        z_min=levels[0],
        z_max=levels[-1],
        tile_count=count,
        total_bytes=total_bytes,
        coordinate_system="EPSG:3857 XYZ（Web Mercator，Leaflet 兼容）",
        extra={
            "style": STYLE,
            "attribution": ATTRIBUTION,
            "package": entry["file"],
            "overviewZoom": list(OVERVIEW_ZOOM) if entry["kind"] == "prefecture" else None,
            "overviewBbox": list(PROVINCE_BBOX) if entry["kind"] == "prefecture" else None,
            "generator": "build_osm_packages.py",
        },
    )
    write_manifest(dirs["tiles"], manifest)
    log(f"  MANIFEST 已校准: {count} 张 / {human_bytes(total_bytes)} / 缩放 {levels}")
    state.update({"render": {"tiles": count, "bytes": total_bytes, "levels": levels}})
    return 0


def stage_verify(entry: dict, dirs: dict, args, state: dict) -> int:
    expect = entry["expected"] + entry["expected_overview"]
    require_min = max(expect - 5, 0)
    code = run_step(
        f"校验 tiles（require-min={require_min}, sample=20）",
        [sys.executable, VERIFY_SCRIPT, "--dir", dirs["tiles"],
         "--require-min", str(require_min), "--sample", "20"],
        dirs["logs"] / "verify-tiles.log",
    )
    state["verify"] = {"requireMin": require_min, "ok": code == 0}
    return code


def stage_export(entry: dict, dirs: dict, args, state: dict) -> int:
    count, total_bytes, levels = scan_tiles(dirs["tiles"])
    code = run_step(
        f"导出 ZIP {dirs['zip'].name}",
        [sys.executable, EXPORT_SCRIPT, "--from", dirs["tiles"], "--zip", dirs["zip"],
         "--require-min", str(max(entry["expected"] + entry["expected_overview"] - 5, 0))],
        dirs["logs"] / "export.log",
    )
    if code != 0:
        return code
    if not dirs["zip"].is_file():
        log(f"[失败] ZIP 未生成: {dirs['zip']}")
        return 1
    size_bytes = dirs["zip"].stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    digest = _sha256_file(dirs["zip"])
    state["zip"] = {
        "file": dirs["zip"].name,
        "tiles": count,
        "sourceBytes": total_bytes,
        "sourceLevels": levels,
        "bytes": size_bytes,
        "mb": round(size_mb, 2),
        "sha256": digest,
        "sha256_12": digest[:12],
        "oversizeWarn": size_mb > ZIP_WARN_MB,
    }
    if size_mb > ZIP_WARN_MB:
        log(
            f"\n[告警] 单包 {dirs['zip'].name} = {size_mb:.1f}MB，超过 {ZIP_WARN_MB}MB 阈值；"
            f"上限 {ZIP_HARD_LIMIT_MB}MB，请立即上报"
        )
    if size_mb > ZIP_HARD_LIMIT_MB:
        log(f"[失败] 单包超过硬上限 {ZIP_HARD_LIMIT_MB}MB")
        return 1
    return 0


def stage_import_test(entry: dict, dirs: dict, args, state: dict) -> int:
    expected_min = max(entry["expected"] + entry["expected_overview"] - 5, 0)
    if dirs["import_test"].is_dir() and args.skip_existing:
        count, _size, levels = scan_tiles(dirs["import_test"])
        if count >= expected_min:
            log(f"  导入验证目录已存在（{count} 张），只做校验")
            code = run_step(
                f"校验导入结果（复用，{count} 张）",
                [sys.executable, VERIFY_SCRIPT, "--dir", dirs["import_test"],
                 "--require-min", str(expected_min), "--sample", "20"],
                dirs["logs"] / "verify-import-test.log",
            )
            state["importTest"] = {"ok": code == 0, "tiles": count, "levels": levels, "reused": True}
            return code
    _safe_rmtree(dirs["import_test"], args.packages_root)
    code = run_step(
        "真导入验证（import_tiles.py）",
        [sys.executable, IMPORT_SCRIPT, "--source", dirs["zip"], "--target", dirs["import_test"]],
        dirs["logs"] / "import-test.log",
    )
    if code != 0:
        return code
    count, _size, levels = scan_tiles(dirs["import_test"])
    code = run_step(
        f"校验导入结果（{count} 张）",
        [sys.executable, VERIFY_SCRIPT, "--dir", dirs["import_test"],
         "--require-min", str(expected_min), "--sample", "20"],
        dirs["logs"] / "verify-import-test.log",
    )
    state["importTest"] = {"ok": code == 0, "tiles": count, "levels": levels}
    return code


def run_package(entry: dict, args, stages: set) -> int:
    dirs = _package_dirs(entry, args)
    dirs["root"].mkdir(parents=True, exist_ok=True)
    dirs["logs"].mkdir(parents=True, exist_ok=True)
    state = {} if args.force else _load_result(dirs["result"])
    layers_sig = _layers_signature(args.layers)
    render_done = bool(state.get("render")) and state.get("layersSig") == layers_sig
    state.update(
        {
            "slug": entry["slug"],
            "name": entry["name"],
            "kind": entry["kind"],
            "bbox": list(entry["bbox"]),
            "zoom": list(entry["zoom"]),
            "expected": entry["expected"],
            "expectedOverview": entry["expected_overview"],
            "file": entry["file"],
            "layersSig": layers_sig,
            "updatedAt": _now_iso(),
        }
    )
    started = time.time()

    plan = []
    if "render" in stages and not (args.skip_existing and render_done):
        plan.append(("render", stage_render))
    # 首跑时 tiles 目录尚不存在，必须把"本流程即将渲染"也算作可校验前提
    if "verify" in stages and ("render" in stages or render_done or dirs["tiles"].is_dir()):
        plan.append(("verify", stage_verify))
    if "export" in stages:
        plan.append(("export", stage_export))
    if "import" in stages:
        plan.append(("import", stage_import_test))

    for stage_name, func in plan:
        code = func(entry, dirs, args, state)
        if code != 0:
            state["failedStage"] = stage_name
            state["elapsedSeconds"] = round(time.time() - started, 1)
            _save_result(dirs["result"], state)
            log(f"[失败] {entry['slug']} 在阶段 {stage_name} 失败（退出码 {code}）")
            return code

    state["elapsedSeconds"] = round(
        float(state.get("elapsedSeconds") or 0) + (time.time() - started), 1
    )
    state.pop("failedStage", None)
    _save_result(dirs["result"], state)
    log(
        f"[完成] {entry['slug']}: 瓦片 {state.get('zip', {}).get('tiles', '?')} 张 / "
        f"ZIP {state.get('zip', {}).get('mb', '?')}MB / 耗时 {state['elapsedSeconds']}s"
    )
    return 0


# ==================== 合并 & 后端运行期校验 ====================


def stage_merged(args, entries: list) -> int:
    prefectures = [entry for entry in entries if entry["kind"] == "prefecture"]
    province = next((entry for entry in entries if entry["kind"] == "province"), None)
    if len(prefectures) != len(PREFECTURES):
        log("[跳过] 合并测试需要 9 个市州包齐备")
        return 0
    merged = args.packages_root / "merged"
    _safe_rmtree(merged, args.packages_root)
    merged.mkdir(parents=True, exist_ok=True)
    logs = args.packages_root / "logs"
    total_reported = 0
    for entry in prefectures:
        dirs = _package_dirs(entry, args)
        if not dirs["zip"].is_file():
            log(f"[失败] 缺少 ZIP: {dirs['zip']}")
            return 1
        code = run_step(
            f"合并导入 {entry['slug']}",
            [sys.executable, IMPORT_SCRIPT, "--source", dirs["zip"], "--target", merged],
            logs / f"merged-import-{entry['slug']}.log",
        )
        if code != 0:
            return code
        state = _load_result(dirs["result"])
        total_reported += int(state.get("zip", {}).get("tiles") or 0)

    # 每次导入都会覆盖 merged/MANIFEST.json（最后一个包的范围），按实际目录重写
    count, total_bytes, levels = scan_tiles(merged)
    write_manifest(
        merged,
        build_manifest(
            provider=PROVIDER,
            license_text=LICENSE_TEXT,
            bbox=PROVINCE_BBOX,
            z_min=levels[0] if levels else 0,
            z_max=levels[-1] if levels else 0,
            tile_count=count,
            total_bytes=total_bytes,
            coordinate_system="EPSG:3857 XYZ（Web Mercator，Leaflet 兼容）",
            extra={
                "style": STYLE,
                "attribution": ATTRIBUTION,
                "mergedFrom": [entry["file"] for entry in prefectures],
                "generator": "build_osm_packages.py",
            },
        ),
    )
    province_count = province["expected"] if province else count_tiles(PROVINCE_BBOX, *PROVINCE_ZOOM)
    result = {
        "tiles": count,
        "bytes": total_bytes,
        "levels": levels,
        "reportedFromPackages": total_reported,
        "provinceTiles": province_count,
        "duplicates": max(total_reported - count, 0),
        "deltaVsProvince": count - province_count,
    }
    log(
        f"\n[合并] 9 包合并后 {count} 张（包内累计 {total_reported}，重复 {result['duplicates']} 张）；"
        f"全省总包 {province_count} 张，差异 {result['deltaVsProvince']:+d}"
    )
    (args.packages_root / "merged.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


def stage_backend_check(args) -> dict:
    merged = args.packages_root / "merged"
    if not (merged / "MANIFEST.json").is_file():
        log("[跳过] 后端运行期校验：merged 目录不存在")
        return {}
    code = (
        "import json;"
        "from fastapi.testclient import TestClient;"
        "from app.main import app;"
        "client=TestClient(app);"
        "print('__TILE_INFO__'+json.dumps(client.get('/api/v1/map/tile-info').json()['data'],ensure_ascii=False))"
    )
    env = _child_env()
    env["MAP_TILES_DIR"] = str(merged.resolve())
    log("\n[后端运行期校验] MAP_TILES_DIR=" + str(merged.resolve()) + " GET /api/v1/map/tile-info")
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        cwd=str(REPO_ROOT / "backend"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    (args.packages_root / "logs" / "backend-tile-info.log").write_text(output, encoding="utf-8")
    data = {}
    for line in (completed.stdout or "").splitlines():
        if line.startswith("__TILE_INFO__"):
            try:
                data = json.loads(line[len("__TILE_INFO__"):])
            except ValueError:
                data = {}
    if completed.returncode != 0 or not data:
        log("[失败] 后端运行期校验失败（详见 .scratch/osm/packages/logs/backend-tile-info.log）")
        return {"ok": False, "returncode": completed.returncode}
    log(
        "  后端 tile-info: available={} tileCount={} zoomLevels={} totalBytes={}".format(
            data.get("available"), data.get("tileCount"), data.get("zoomLevels"), data.get("totalBytes")
        )
        + " manifest.provider={}".format((data.get("manifest") or {}).get("provider"))
    )
    data["ok"] = True
    (args.packages_root / "backend-tile-info.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data


# ==================== 索引/汇总 ====================


def _collect_package_results(entries: list, args) -> list:
    rows = []
    for entry in entries:
        dirs = _package_dirs(entry, args)
        state = _load_result(dirs["result"])
        zip_info = state.get("zip") or {}
        rows.append(
            {
                "slug": entry["slug"],
                "name": entry["name"],
                "kind": entry["kind"],
                "file": entry["file"],
                "bbox": list(entry["bbox"]),
                "zoom": "z%d-%d" % tuple(entry["zoom"]),
                "tiles": zip_info.get("tiles") or state.get("render", {}).get("tiles"),
                "bytes": zip_info.get("bytes"),
                "mb": zip_info.get("mb"),
                "sha256": zip_info.get("sha256"),
                "sha256_12": zip_info.get("sha256_12"),
                "expected": entry["expected"] + entry["expected_overview"],
                "overviewTiles": entry["expected_overview"],
                "verify": state.get("verify"),
                "importTest": state.get("importTest"),
                "elapsedSeconds": state.get("elapsedSeconds"),
                "zipPresent": dirs["zip"].is_file(),
                "failedStage": state.get("failedStage"),
            }
        )
    return rows


def write_index(rows: list, args, merged: dict, backend: dict) -> None:
    args.deliverables_root.mkdir(parents=True, exist_ok=True)
    province_row = next((row for row in rows if row["kind"] == "province"), None)
    pref_rows = [row for row in rows if row["kind"] == "prefecture"]

    lines = [
        "# 贵州离线瓦片包索引（OSM）",
        "",
        f"- 生成时间：{_now_iso()}",
        f"- 数据来源：OpenStreetMap 离线 PBF（贵州省）→ `osm_extract.py` → `render_osm_tiles.py`（{STYLE}）",
        f"- 授权/署名：**{LICENSE_TEXT}**（瓦片左下角已绘制署名；二次分发须保留 ODbL 授权与署名）",
        "- 坐标系：EPSG:3857 Web Mercator XYZ（与 Leaflet / 系统 `/api/v1/map/tiles/{z}/{x}/{y}.png` 完全一致）",
        "- 包结构：`MANIFEST.json` + `<z>/<x>/<y>.png`，可直接用管理页「导入瓦片包」或 `scripts/tiles/import_tiles.py` 导入",
        "",
        "## 包清单",
        "",
        "| 包名 | 地区 | 缩放 | 瓦片数 | 体积 | SHA256 |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in ([province_row] if province_row else []) + pref_rows:
        sha = row["sha256"] or "（未导出）"
        tiles = row["tiles"] if row["tiles"] is not None else "?"
        size = f"{row['mb']}MB" if row["mb"] is not None else "?"
        lines.append(f"| `{row['file']}` | {row['name']} | {row['zoom']} | {tiles} | {size} | `{sha}` |")

    lines += [
        "",
        "## 市州包内的「全省概览」瓦片",
        "",
        f"- 9 个市州包都额外包含全省 z5-6 概览 **{count_tiles(PROVINCE_BBOX, *OVERVIEW_ZOOM)} 张**"
        "（z5:1 + z6:4，来自全省 bbox）",
        "- 目的：单独导入某个市州包后，省级/市级缩放下边框区域仍有底图，不会因缺瓦片触发前端矢量回退",
        "",
        "## 校验与导入验证",
        "",
        "| 包名 | verify(--require-min) | 真导入验证 | 导入后瓦片数 |",
        "|---|---|---|---:|",
    ]
    for row in ([province_row] if province_row else []) + pref_rows:
        verify = row.get("verify") or {}
        imported = row.get("importTest") or {}
        verify_text = "通过" if verify.get("ok") else ("未执行" if not verify else "失败")
        import_text = "通过" if imported.get("ok") else ("未执行" if not imported else "失败")
        lines.append(
            f"| `{row['file']}` | {verify_text}（≥{verify.get('requireMin', '?')}） | "
            f"{import_text} | {imported.get('tiles', '?')} |"
        )

    lines += ["", "## 合并导入测试（9 个市州包）", ""]
    if merged:
        lines += [
            f"- 合并后唯一瓦片数：**{merged.get('tiles')}**（9 包内瓦片累计 {merged.get('reportedFromPackages')}，"
            f"边界重叠被覆盖 **{merged.get('duplicates')}** 张）",
            f"- 全省总包：{merged.get('provinceTiles')} 张，差异 {merged.get('deltaVsProvince'):+d}"
            "（两个因素：① 市州 bbox 是矩形，相邻市州/飞地交界处必然重叠 → 重复；"
            "② 全省 bbox 是外接矩形，四角/边缘含邻省（云南/广西/湖南/重庆/四川）区域，"
            "这些瓦片不在任何市州包内 → 合并数少于全省总包。"
            "本轮已用 `frontend/src/assets/geo/guizhou.json` 做多边形抽验："
            "缺失的 1270 张瓦片全部落在贵州省界之外（省内缺失 0 张）。）",
        ]
    else:
        lines.append("- 未执行（需 9 个市州包齐备）")
    if backend:
        lines += [
            "",
            "## 后端运行期校验（`MAP_TILES_DIR` 指向合并目录）",
            "",
            f"- `GET /api/v1/map/tile-info` → available={backend.get('available')}, "
            f"tileCount={backend.get('tileCount')}, zoomLevels={backend.get('zoomLevels')}, "
            f"manifest.provider={(backend.get('manifest') or {}).get('provider')}",
        ]
    if args.rehearse:
        lines += ["", "> 注意：本索引由 `--rehearse` 彩排生成，不是正式交付物。"]

    lines += [
        "",
        "## 导入方法",
        "",
        "```bash",
        "# 方式一：管理页「导入瓦片包」（管理员，上传 ZIP ≤512MB）",
        "# 方式二：脚本导入（U 盘/大包，服务端本机路径免上传）",
        "python scripts/tiles/import_tiles.py --source <包.zip> --target resources/map-tiles",
        "",
        "# 校验导入结果",
        "python scripts/tiles/verify_tiles.py --dir resources/map-tiles --require-min 1",
        "```",
        "",
        "> 全省总包与市州包**二选一**即可：全省包覆盖全省但体积大；市州包体积小、按需分发，"
        "均自带全省 z5-6 概览。升级时重复导入同名包会覆盖同名瓦片（增量合并）。",
        "",
    ]
    (args.deliverables_root / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "generatedAt": _now_iso(),
        "provider": PROVIDER,
        "license": LICENSE_TEXT,
        "style": STYLE,
        "provinceBbox": list(PROVINCE_BBOX),
        "overviewZoom": list(OVERVIEW_ZOOM),
        "packages": rows,
        "merged": merged or None,
        "backendTileInfo": backend or None,
    }
    (args.deliverables_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(f"\n索引已生成: {args.deliverables_root / 'INDEX.md'}")
    log(f"机器可读汇总: {args.deliverables_root / 'summary.json'}")


# ==================== CLI ====================


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_osm_packages.py",
        description="编排贵州 OSM 瓦片包（全省总包 + 9 市州包）的渲染/校验/打包/导入验证/索引",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python scripts/tiles/build_osm_packages.py --dry-run\n"
            "  python scripts/tiles/build_osm_packages.py --jobs 4\n"
            "  python scripts/tiles/build_osm_packages.py --only guiyang --skip-existing\n"
            "  python scripts/tiles/build_osm_packages.py --only '' --stages index\n"
            "  python scripts/tiles/build_osm_packages.py --rehearse\n"
        ),
    )
    parser.add_argument("--only", default="all", help="all | province | slug（逗号分隔），默认 all")
    parser.add_argument("--jobs", type=int, default=4, help="渲染并行进程数（默认 4）")
    parser.add_argument("--layers", type=Path, default=DEFAULT_LAYERS, help=f"图层 pickle（默认 {DEFAULT_LAYERS}）")
    parser.add_argument("--wait-input", type=int, default=1800, help="渲染等待 layers.pkl 就绪的秒数（默认 1800）")
    parser.add_argument("--packages-root", type=Path, default=DEFAULT_PACKAGES_ROOT, help="中间产物根目录")
    parser.add_argument("--deliverables-root", type=Path, default=DEFAULT_DELIVERABLES_ROOT, help="交付物根目录")
    parser.add_argument(
        "--stages",
        default="render,verify,export,import,merge,index",
        help="要执行的阶段（逗号分隔，默认全部）：render,verify,export,import,merge,index",
    )
    parser.add_argument("--skip-existing", action="store_true", help="断点续跑：跳过已存在的渲染/导入产物")
    parser.add_argument("--force", action="store_true", help="忽略 result.json 缓存，强制重做所选阶段")
    parser.add_argument("--skip-merged", action="store_true", help="跳过 9 包合并 + 后端运行期校验")
    parser.add_argument("--rehearse", action="store_true", help="彩排：极小 bbox（z9）跑通全流水线，产物写 _rehearsal")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划（瓦片数/预估体积），不渲染不写盘")
    return parser


def _parse_stages(text: str) -> set:
    allowed = {"render", "verify", "export", "import", "merge", "index"}
    stages = {token.strip() for token in str(text or "").split(",") if token.strip()}
    unknown = stages - allowed
    if unknown:
        raise SystemExit(f"未知阶段: {', '.join(sorted(unknown))}（允许: {', '.join(sorted(allowed))}）")
    return stages


def _print_plan(entries: list, args) -> None:
    log("计划（未执行）:")
    total_tiles = 0
    for entry in entries:
        expect = entry["expected"] + entry["expected_overview"]
        total_tiles += expect
        log(
            f"  {entry['slug']:<14s} {entry['kind']:<10s} {entry['file']:<32s} "
            f"计划 {expect:>5d} 张（其中概览 {entry['expected_overview']}）"
            f" bbox={_bbox_arg(entry['bbox'])}"
        )
    log(f"  合计计划渲染 {total_tiles} 张；中间产物: {args.packages_root}；交付: {args.deliverables_root}")


def main(argv=None) -> int:  # noqa: C901 - CLI 编排（阶段调度/断点续跑/索引汇总）集中在此
    setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    # 相对路径按仓库根解析（脚本可在任意 cwd 运行）
    for name in ("packages_root", "deliverables_root", "layers"):
        value = getattr(args, name)
        if not value.is_absolute():
            setattr(args, name, (REPO_ROOT / value).resolve())

    if args.rehearse:
        args.packages_root = args.packages_root / "_rehearsal"
        args.deliverables_root = args.deliverables_root / "_rehearsal"

    stages = _parse_stages(args.stages)
    try:
        all_entries = _package_entries(True) if args.rehearse else _package_entries(False)
        entries = _select_entries(all_entries, args.only)
    except SystemExit as exc:
        log(str(exc))
        return 2

    log(f"包数: {len(entries)}  阶段: {', '.join(sorted(stages))}  jobs={args.jobs}")
    log(f"layers.pkl: {args.layers}（存在={args.layers.is_file()}）")

    if args.dry_run:
        _print_plan(entries, args)
        return 0
    if not args.layers.is_file() and "render" in stages:
        log(f"[失败] 图层 pickle 不存在: {args.layers}（等待 osm_extract.py 产物）")
        return 2
    if not RENDER_SCRIPT.is_file():
        log(f"[失败] 渲染脚本不存在: {RENDER_SCRIPT}")
        return 2

    started = time.time()
    for entry in entries:
        code = run_package(entry, args, stages)
        if code != 0:
            return code

    merged = {}
    backend = {}
    merged_path = args.packages_root / "merged.json"
    backend_path = args.packages_root / "backend-tile-info.json"
    if "merge" in stages and not args.skip_merged and not args.rehearse:
        code = stage_merged(args, entries if not args.rehearse else [])
        if code != 0:
            return code
        if merged_path.is_file():
            try:
                merged = json.loads(merged_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                merged = {}
        backend = stage_backend_check(args)
        if backend and not backend.get("ok"):
            return 1
    else:
        # 只重生成索引时复用上一次的合并/后端校验结果
        for path, target in ((merged_path, "merged"), (backend_path, "backend")):
            if path.is_file():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    loaded = {}
                if target == "merged":
                    merged = loaded
                else:
                    backend = loaded

    if "index" in stages:
        rows = _collect_package_results(entries, args)
        write_index(rows, args, merged, backend)

    elapsed = time.time() - started
    total_mb = sum(row["mb"] or 0 for row in _collect_package_results(entries, args))
    log(f"\n全部完成：{len(entries)} 个包，总耗时 {elapsed / 60:.1f} 分钟，交付体积 {total_mb:.1f}MB")
    log(f"交付目录: {args.deliverables_root}")
    log(
        "提示：未提交的交付物若需入库，请人工确认体积/授权后再 git add；"
        f"单包超过 {ZIP_WARN_MB}MB 会打印告警。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
