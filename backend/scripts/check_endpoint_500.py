#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端点 500 巡检（P0-F2，slow 档，离线启动本机实例逐 GET 探测）。

为什么值得有一道：生产上最贵的信号是一个「用户看到白屏/500」；
它不在单测里出现（单测都走正常路径+正常 mock），只有在真实进程里逐个 GET 才会暴露 ——
2026-10-29/30 的导航端点 `user 形态不完整致 500`、`OrgGrant 组织树类型` 、
`auth 部门级管理员被错标为超级管理员` 就是这类，而这批全靠人工巡检发现的。
本门禁把「任何一个 GET 端点返回 5xx」做成**可执行的规格**（棘轮只减不增）：

用法:
    python backend/scripts/check_endpoint_500.py               # 启动 uvicorn 探测全部 GET
    python backend/scripts/check_endpoint_500.py --update      # 人工确认后写回已知豁免（慎用）
    python backend/scripts/check_endpoint_500.py --port 8799  # 指定端口（默认 8799）

已知豁免以 `scripts/gate_baselines/endpoint_500.json` 记录（带理由），新增 5xx 即红。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts" / "gate_baselines" / "endpoint_500.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


# 401/403 (未登录被拦)、404 (路由不存在)、405 (方法不存在)、422 (参数校验)、
# 429 (限流)、503 (维护窗口) 都是**合法**的服务端状态；只有 500-599 视为服务端错误。
ALLOWED_STATUSES = {200, 204, 301, 302, 304, 307, 308, 401, 403, 404, 405, 422, 429, 503}
VIOLET_STATUSES = {500, 501, 502, 504, 505, 506, 507, 508, 510, 511}


def http_get(url: str, timeout: float = 10.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(512).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(512).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"无法连接 {url}: {exc}")


def wait_ready(base_url: str, timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            status, _ = http_get(base_url + "/health", timeout=2.5)
            if status in ALLOWED_STATUSES:
                return
        except RuntimeError:
            pass
        time.sleep(1.0)
    raise RuntimeError("实例在超时内不可达（/health）")


def collect_get_paths(base_url: str) -> list[str]:
    """枚举 GET 端点：本应用仅 DEBUG 才开 /openapi.json，改用进程内遍历 FastAPI 路由。"""
    backend = str(ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from fastapi import FastAPI  # noqa: PLC0415 -- 仅这一处在不彻底启动 uvicorn 时仍需安装
    import importlib  # noqa: PLC0415

    app = importlib.import_module("app.main").app  # type: ignore[attr-defined]
    del app  # 仅校验是 FastAPI 实例
    from app.main import app as fastapi_app  # noqa: PLC0415

    paths: list[str] = []
    for route in getattr(fastapi_app, "routes", []):
        methods = getattr(route, "methods", None) or set()
        if "GET" not in methods:
            continue
        path = getattr(route, "path", None)
        if not path or "{" in path:
            continue
        paths.append(path)
    return sorted(set(paths))


def probe_all(base_url: str, paths: list[str], delay_s: float = 0.0) -> list[tuple[str, int]]:
    violations: list[tuple[str, int]] = []
    for p in paths:
        try:
            status, _ = http_get(base_url + p)
        except RuntimeError as exc:
            raise RuntimeError(f"{p}: {exc}")
        if status not in ALLOWED_STATUSES:
            violations.append((p, status))
        if delay_s:
            time.sleep(delay_s)
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GET 端点 5xx 巡检")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--keep-server", action="store_true", help="调试：结束后不杀进程")
    ap.add_argument("--kill-existing", action="store_true", default=True)
    args = ap.parse_args(argv)

    venv_python = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
    python = str(venv_python if venv_python.exists() else ROOT / "backend" / ".venv" / "bin" / "python")
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PORT", str(args.port))
    # 注意：实例复用本机 DB（数据不变，因为所有探测都是只读 GET）
    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
        cwd=str(ROOT / "backend"), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{args.port}"
    try:
        wait_ready(base)
        paths = collect_get_paths(base)
        if not paths:
            print("[FAIL] 未从 /openapi.json 解析到任何 GET 端点", file=sys.stderr)
            return 1
        violations = probe_all(base, paths)
        if args.update:
            BASELINE.write_text(json.dumps([{"path": p, "status": s, "reason": "人工确认豁免"} for p, s in violations], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[update] 豁免清单 {BASELINE.relative_to(ROOT)} <- {len(violations)} 条")
            return 0
        known = []
        if BASELINE.exists():
            known = json.loads(BASELINE.read_text(encoding="utf-8"))
        known_paths = {(x["path"], x["status"]) for x in known}
        fresh = [(p, s) for p, s in violations if (p, s) not in known_paths]
        if fresh:
            for p, s in fresh:
                print(f"  x {p}  ->  HTTP {s}")
            print("说明：以上 GET 端点在无登录态下返回 5xx。", file=sys.stderr)
            print("若属有意为之：运行 --update 并在基线里写明理由；否则请修降级路径。", file=sys.stderr)
            return 1
        print(f"[gate:endpoint_500] OK (probed {len(paths)} GET endpoints, exemptions {len(known_paths)})")
        return 0
    finally:
        if not args.keep_server:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
