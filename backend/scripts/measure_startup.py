#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""后端启动耗时测量工具（P2-4 启动时间优化）。

做什么：
  1. 分阶段计时：进程启动 → 依赖 import（config）→ app 实例创建 + 中间件注册 +
     路由注册（import app.main 一次性包含，模块级完成）→ lifespan 启动
     （DB 初始化 / 种子 / 调度器 / 任务队列）→ 首个请求（/health）。
  2. 同一次子进程用 ``-X importtime`` 采集「最耗时的 import」top-N（按自身耗时）。
  3. 默认重复 3 次（每次全新冷启动子进程）后逐阶段取中位数，支持 ``--json``。

隔离与可重复：
  子进程把数据目录重定向到一次性临时目录（``BUMOFU_BACKEND_DIR_OVERRIDE``），
  因而每次都是「冷库」启动，且不会污染真实仓库数据。

为什么用子进程：
  Python 的 import 有全局缓存，同进程无法重复测「冷启动」；只有每次新起进程才
  能真实反映启动耗时。

用法：
    python scripts/measure_startup.py                # 人类可读表
    python scripts/measure_startup.py --json         # JSON（前后对比用）
    python scripts/measure_startup.py --repeats 5 --top 20
    python scripts/measure_startup.py --import-only  # 只测 import，跳过 lifespan
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR: Path = Path(__file__).resolve().parents[1]

# -X importtime 输出形如： import time:      1234 |       5678 |   app.core.config
_IMPORTTIME_RE = re.compile(r"^import time:\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.+?)\s*$")

# 阶段顺序（用于表格展示）
_STAGE_ORDER: List[Tuple[str, str]] = [
    ("import_config_ms", "import app.core.config（基础配置 + 路径）"),
    ("import_app_main_ms", "import app.main（app 创建 + 中间件 + 路由注册）"),
    ("total_import_ms", "依赖 import 合计（config + app.main）"),
    ("lifespan_startup_ms", "lifespan 启动（DB 初始化/种子/调度器/任务队列）"),
    ("first_request_get_health_ms", "首个请求 GET /health"),
]

# 子进程内执行的探针（等价于 app.main:app 的启动路径）
_CHILD_SNIPPET = r"""
import json, sys, time
_stages = {}
try:
    _t0 = time.perf_counter()
    import app.core.config  # noqa: F401
    _t_config = time.perf_counter()
    _stages["import_config_ms"] = round((_t_config - _t0) * 1000, 1)

    import app.main as _m
    _t_app = time.perf_counter()
    _stages["import_app_main_ms"] = round((_t_app - _t_config) * 1000, 1)
    _stages["total_import_ms"] = round((_t_app - _t0) * 1000, 1)
    _stages["routes"] = len(_m.app.routes)
    _stages["middlewares"] = len(_m.app.user_middleware)

    if "__MRRS_IMPORT_ONLY__" not in sys.argv:
        from starlette.testclient import TestClient
        _t1 = time.perf_counter()
        with TestClient(_m.app) as _client:
            _t2 = time.perf_counter()
            _stages["lifespan_startup_ms"] = round((_t2 - _t1) * 1000, 1)
            _t3 = time.perf_counter()
            _resp = _client.get("/health")
            _stages["first_request_get_health_ms"] = round(
                (time.perf_counter() - _t3) * 1000, 1
            )
            _stages["health_status"] = _resp.status_code
except Exception as _e:  # pragma: no cover - 测量脚本诊断路径
    _stages["error"] = repr(_e)[:400]
sys.stdout.write("MRRS_STAGES=" + json.dumps(_stages) + "\n")
"""


def _child_env(tmpdir: str) -> Dict[str, str]:
    """构造子进程环境：UTF-8 + backend 上 sys.path + 数据目录隔离到 tmpdir。"""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("ENVIRONMENT", "test")
    env.setdefault("SECRET_KEY", "test-secret-key-for-ci")
    # BUMOFU_BACKEND_DIR_OVERRIDE 会把所有 dev 数据目录派生到 tmpdir（见 app/utils/paths.py）
    env["BUMOFU_BACKEND_DIR_OVERRIDE"] = tmpdir
    env["BUMOFU_DEV_MODE"] = "1"
    return env


def _parse_importtime(stderr_text: str) -> List[Tuple[int, int, str]]:
    """解析 -X importtime 输出为 (self_us, cumulative_us, module) 列表。"""
    rows: List[Tuple[int, int, str]] = []
    for line in stderr_text.splitlines():
        m = _IMPORTTIME_RE.match(line)
        if m:
            rows.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return rows


def _run_once(import_only: bool, with_importtime: bool = True) -> Dict[str, Any]:
    """在一次性临时数据目录中冷启动一个子进程并采集阶段耗时 + importtime。

    ``with_importtime=False`` 时不加 ``-X importtime``：因为该开关会给 import
    阶段带来可观开销，需以「无插桩」数据判断真实启动耗时。
    """
    tmpdir = tempfile.mkdtemp(prefix="mrrs_startup_")
    try:
        env = _child_env(tmpdir)
        args = [sys.executable]
        if with_importtime:
            args += ["-X", "importtime"]
        args += ["-c", _CHILD_SNIPPET]
        if import_only:
            args.append("__MRRS_IMPORT_ONLY__")
        proc = subprocess.run(
            args,
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        stages: Optional[Dict[str, Any]] = None
        for line in (proc.stdout or "").splitlines():
            if line.startswith("MRRS_STAGES="):
                stages = json.loads(line[len("MRRS_STAGES="):])
        return {
            "stages": stages,
            "imports": _parse_importtime(proc.stderr or ""),
            "returncode": proc.returncode,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _median_stages(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """对多次运行的数值型阶段取中位数；整型元数据（routes 等）取末次。"""
    ok = [r["stages"] for r in runs if r.get("stages")]
    if not ok:
        return {}
    keys = set()
    for s in ok:
        keys.update(s.keys())
    out: Dict[str, Any] = {}
    for k in keys:
        vals = [s[k] for s in ok if isinstance(s.get(k), (int, float))]
        if vals:
            out[k] = round(statistics.median(vals), 1)
        else:
            out[k] = next((s[k] for s in ok if k in s), None)
    return out


def _median_imports(runs: List[Dict[str, Any]], top: int) -> List[Dict[str, Any]]:
    """按「自身耗时 self_us」跨运行取中位数，返回 top-N 最耗时 import。"""
    per_name: Dict[str, List[int]] = {}
    per_cum: Dict[str, List[int]] = {}
    for r in runs:
        for self_us, cum_us, name in r.get("imports", []):
            per_name.setdefault(name, []).append(self_us)
            per_cum.setdefault(name, []).append(cum_us)
    rows = [
        {
            "module": name,
            "self_us_median": int(statistics.median(v)),
            "cum_us_median": int(statistics.median(per_cum[name])),
        }
        for name, v in per_name.items()
    ]
    rows.sort(key=lambda x: x["self_us_median"], reverse=True)
    return rows[:top]


def _fmt_ms(v: Any) -> str:
    return f"{v:.1f}" if isinstance(v, (int, float)) else str(v)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="后端启动耗时测量（P2-4）")
    ap.add_argument("--repeats", type=int, default=3, help="冷启动重复次数（默认 3）")
    ap.add_argument("--top", type=int, default=20, help="最耗时 import 显示条数（默认 20）")
    ap.add_argument("--json", action="store_true", help="输出 JSON（前后对比用）")
    ap.add_argument("--import-only", action="store_true", help="只测 import，跳过 lifespan")
    ap.add_argument("--no-importtime", action="store_true",
                    help="不注入 -X importtime（更接近真实启动，但无 top import 明细）")
    args = ap.parse_args(argv)

    runs: List[Dict[str, Any]] = []
    for i in range(max(1, args.repeats)):
        if not args.json:
            print(f"[{i + 1}/{args.repeats}] 冷启动测量中...", file=sys.stderr, flush=True)
        runs.append(_run_once(args.import_only, with_importtime=not args.no_importtime))

    stages = _median_stages(runs)
    imports = _median_imports(runs, args.top)
    errors = [r["stages"].get("error") for r in runs if r.get("stages") and r["stages"].get("error")]

    if args.json:
        print(json.dumps(
            {"repeats": args.repeats, "stages_median_ms": stages,
             "top_imports": imports, "errors": errors},
            ensure_ascii=False, indent=2,
        ))
        return 0

    print("=" * 72)
    print(f"后端启动耗时（{args.repeats} 次冷启动取中位数；数据目录隔离到临时目录）")
    print("=" * 72)
    for key, label in _STAGE_ORDER:
        if key in stages:
            print(f"  {label:<52} {_fmt_ms(stages[key]):>10} ms")
    if "routes" in stages or "middlewares" in stages:
        print(f"  {'元数据：路由数 / 中间件数':<52} {stages.get('routes')} / {stages.get('middlewares')}")
    print("-" * 72)
    print(f"  最耗时 import top-{len(imports)}（按自身耗时 self 中位数排序）：")
    for row in imports:
        print(
            f"    {row['self_us_median'] / 1000:>9.1f} ms  "
            f"(cum {row['cum_us_median'] / 1000:>9.1f} ms)  {row['module']}"
        )
    if errors:
        print("-" * 72)
        for e in errors:
            print(f"  [警告] {e}")
    print("=" * 72)
    return 0


if __name__ == "__main__":  # pragma: no cover - 脚本入口守卫
    raise SystemExit(main())
