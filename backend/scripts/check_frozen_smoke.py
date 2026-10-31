#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""冻结产物冒烟门禁（P0-F1）：构建≠可运行，产物必须先证明一次。

v1.18.23~26 连续多个 tag 重建的直接原因都是**冻结产物缺模块**
（ARM64 DEB 漏 difflib、PyInstaller 门禁被重复/砍掉又补回）——发行流程反复踩坑
的原因是**没有一道固定门禁在出包后真正运行产物时检查**。`start.py` 已经内置了
`BACKEND_IMPORT_CHECK=1` 的导入自检（走完整路由链），这个门禁把它的结果做成棘轮：
    1) 冻结 `assistance-backend.exe` => `BACKEND_IMPORT_CHECK=1` 必须返回 OK；
    2) 用指定端口真实启动 => /health 必须 200，证明编译产物真的能起服务。

缺失产物时 **SKIP**（不在 `run_gates` 默认通路上挡住日常开发）。
用法:
    python backend/scripts/check_frozen_smoke.py            # 完整两阶段检查
    python backend/scripts/check_frozen_smoke.py --skip-health  # 只跑 import 自检（快）
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FROZEN_EXE = ROOT / "backend" / "dist" / "assistance-backend" / "assistance-backend.exe"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(512).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(512).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"无法连接 {url}: {exc}")


def _scratch_dir() -> Path:
    """隔离的可写落点。

    不用系统 %TEMP%：本机沙箱与部分企业策略下 %TEMP% 对进程不可写（实测 WinError 5，
    表现为 `PermissionError: 拒绝访问` 甚至静默写不出结果文件）。
    用仓库内 `.scratch/` 作为稳定落点，CI 与本地都成立。
    """
    base = ROOT / ".scratch"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="frozen-smoke-", dir=str(base)))


def _isolated_env(scratch: Path) -> dict[str, str]:
    """给冻结产物一个隔离的可写运行目录。

    `settings.CACHE_DIR` 默认是 **cwd 相对** 的 `./data/cache`；NSIS 安装后程序的工作目录是
    安装目录（Program Files 下通常只读），基本即死法 `attempt to write a readonly database`。
    冒烟门禁的语义是「验证产物代码是否完整可运行」，不该被宿主工作目录判定 —— 因此显式提供
    DATA_DIR/CACHE_DIR。这同时也说明：这两个环境变量在部署时**必须显式**。
    """
    env = os.environ.copy()
    env["DATA_DIR"] = str(scratch / "data")
    env["CACHE_DIR"] = str(scratch / "cache")
    return env

def run_import_selfcheck(timeout_s: float = 180.0) -> tuple[bool, str]:
    scratch = _scratch_dir()
    # 结果文件必须落在**可写**目录：%TEMP% 在受限环境下写不进去，会让自检恒判非 OK
    result_path = str(scratch / "import-check.txt")
    env = _isolated_env(scratch)
    env["BACKEND_IMPORT_CHECK"] = "1"
    env["BACKEND_IMPORT_CHECK_RESULT"] = result_path
    proc = subprocess.run(
        [str(FROZEN_EXE)], env=env, cwd=str(FROZEN_EXE.parent),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout_s,
    )
    try:
        result_text = Path(result_path).read_text(encoding="utf-8").strip()
    except OSError:
        result_text = ""
    tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip().splitlines()[-5:]
    ok = proc.returncode == 0 and result_text == "OK"
    return ok, "\n".join(tail)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_health_probe(timeout_s: float = 180.0) -> tuple[bool, str]:
    port = _pick_free_port()
    scratch = _scratch_dir()
    env = _isolated_env(scratch)
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        [str(FROZEN_EXE)], env=env, cwd=str(FROZEN_EXE.parent),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + timeout_s
        health_ok = False
        while time.time() < deadline:
            try:
                status, _ = _http_get(base + "/health", timeout=3.0)
                if status == 200:
                    health_ok = True
                    break
            except RuntimeError:
                pass
            time.sleep(1.5)
        if not health_ok:
            return False, f"/health 在 {timeout_s:.0f}s 内没有 200（冻结产物起服务失败）"
        # /health 只证明进程活着；再证一次**路由与鉴权中间件已装载**：
        # 任一 /api/v1 受保护 GET 必须给出 401/403（而不是 404/500）。
        # 不绑定单一端点：路由名可能调整，因此按候选顺序取第一个非 404。
        candidates = ("/api/v1/menus", "/api/v1/auth/me", "/api/v1/system/health")
        probed = []
        for path in candidates:
            status, _ = _http_get(base + path, timeout=5.0)
            probed.append(f"{path}={status}")
            if status in (401, 403):
                return True, f"health 200 / {path} {status} on :{port}"
            if status != 404:
                return False, f"{path} 期望 401/403，实际 {status}"
        return False, "所有候选受保护端点都 404（路由未装载）: " + ", ".join(probed)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="冻结后端产物冒烟门禁")
    ap.add_argument("--skip-health", action="store_true", help="只跑 BACKEND_IMPORT_CHECK 阶段（更快）")
    args = ap.parse_args(argv)
    if not FROZEN_EXE.exists():
        # 不在 ROOT 之下（例如测试注入的绝对路径）时 relative_to 会抛，SKIP 提示不该因此炸
        try:
            shown = FROZEN_EXE.relative_to(ROOT)
        except ValueError:
            shown = FROZEN_EXE
        print(f"SKIP: 产物不存在 {shown}")
        return 0
    ok, tail = run_import_selfcheck()
    if not ok:
        print("[FAIL] BACKEND_IMPORT_CHECK 非 OK:", file=sys.stderr)
        print(tail, file=sys.stderr)
        return 1
    print("[1/2] BACKEND_IMPORT_CHECK OK")
    if args.skip_health:
        print("[gate:frozen_smoke] OK（仅导入自检）")
        return 0
    ok, detail = run_health_probe()
    if not ok:
        print(f"[FAIL] 冻结产物起服务: {detail}", file=sys.stderr)
        return 1
    print(f"[2/2] {detail}")
    print("[gate:frozen_smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())