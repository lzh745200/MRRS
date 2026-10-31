#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端点 500 巡检（P0-F2，slow 档，隔离库 + 双登录态逐 GET 探测）。

为什么值得有一道：生产上最贵的信号是「用户看到白屏 / 500」，
它不在单测里出现（单测都走正常路径 + 正常 mock），只有在真实进程里逐个 GET 才会暴露。
2026-10-29/30 的导航端点 user 形态不完整致 500、OrgGrant 组织树类型、auth 部门级管理员被错标
超级管理员，都属于这一类，且全靠人工巡检发现。本门禁把「任何 GET 端点返回 5xx」做成可执行规格。

2026-10-31 两处硬化（原版只做匿名扫描，深度有限）：

① 隔离库：原实现复用本机开发库（backend/data/rural_revitalization.db）起实例，
   门禁结果随本机脏数据漂移，CI 也跑不了，且「只读探测」只是约定而非保证。
   现在改为 .scratch/endpoint500-* 下的一次性库：alembic upgrade head 建 schema →
   启动实例 → 探测结束删目录。同一 commit 在任何人机器上结果一致。

② 带令牌二次扫描：匿名扫描下 293 个 GET 里 277 个死在 401（鉴权中间件直接短路），
   处理函数体一行都没跑 —— 这正是历史 bug 逃逸的缝隙。现在扫两遍：
   anon（未登录，覆盖越权路径的降级）+ auth（管理员令牌，真正进入处理函数）。
   auth 态下额外把 401 视为违规：令牌有效却被拒说明鉴权链路本身坏了。

用法:
    python backend/scripts/check_endpoint_500.py               # 隔离库 + 两种登录态全扫
    python backend/scripts/check_endpoint_500.py --update      # 人工确认后写回已知豁免（慎用）
    python backend/scripts/check_endpoint_500.py --skip-auth   # 只扫匿名态（排障用）
    python backend/scripts/check_endpoint_500.py --keep-server # 调试：结束后不杀进程 / 不删目录

已知豁免记在 scripts/gate_baselines/endpoint_500.json（带理由 + mode），新增违规即红。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
BASELINE = ROOT / "scripts" / "gate_baselines" / "endpoint_500.json"
FACTORY_ADMIN_USERNAME = "admin"
FACTORY_ADMIN_PASSWORD = "zgcZGC733035#"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


# 401/403（未登录被拦）、404（路由不存在）、405（方法不存在）、422（参数校验）、
# 429（限流）、503（维护窗口）都是合法的服务端状态；只有 500-599 与连接失败视为错误。
ALLOWED_STATUSES = {200, 204, 301, 302, 304, 307, 308, 401, 403, 404, 405, 422, 429, 503}

MODE_ANON = "anon"
MODE_AUTH = "auth"


def classify(status: int, mode: str) -> str | None:
    """判定一次探测是否违规；返回违规说明，None 表示合法。

    - 连接失败：两种登录态都算违规；
    - auth 态下的 401：令牌有效却被拒 → 鉴权链路坏了，算违规；
      匿名态的 401 是正常的越权拦截，不算；
    - 其余不在 ALLOWED_STATUSES 里的状态（含 500/502 等 5xx）都算违规。
      注意 503 在白名单内：它是维护窗口中间件对写请求的合法降级响应，不是服务端错误。
    """
    if status < 0:
        return "连接失败"
    if mode == MODE_AUTH and status == 401:
        return "带管理员令牌仍返回 401"
    if status in ALLOWED_STATUSES:
        return None
    return f"HTTP {status}"


def entry_key(entry: dict) -> tuple[str, str, int]:
    """豁免条目的唯一键；历史条目缺 mode 时按匿名态解释（向后兼容）。"""
    return (str(entry.get("mode") or MODE_ANON), str(entry["path"]), int(entry["status"]))


def partition_violations(
    found: list[tuple[str, int, str]], known: list[dict]
) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """按豁免清单切分「新出现的违规」与「已登记豁免」；fresh 非空即门禁红。"""
    known_keys = {entry_key(x) for x in known}
    fresh: list[tuple[str, int, str]] = []
    excused: list[tuple[str, int, str]] = []
    for item_path, status, mode in found:
        (excused if (mode, item_path, status) in known_keys else fresh).append((item_path, status, mode))
    return fresh, excused


def http_get(url: str, timeout: float = 10.0, token: str | None = None) -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(512).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(512).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"无法连接 {url}: {exc}") from exc


def http_post_json(url: str, payload: dict, timeout: float = 20.0) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"无法连接 {url}: {exc}") from exc


def wait_ready(base_url: str, timeout_s: float = 150.0) -> None:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        try:
            status, _ = http_get(base_url + "/health", timeout=2.5)
            if status in ALLOWED_STATUSES:
                return
            last = f"HTTP {status}"
        except RuntimeError as exc:
            last = str(exc)
        time.sleep(1.0)
    raise RuntimeError(f"实例在超时内不可达（/health, 最后状态: {last}）")


def collect_get_paths() -> list[str]:
    """枚举 GET 端点：本应用仅 DEBUG 才开 /openapi.json，改用进程内 FastAPI 路由。"""
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from app.main import app as fastapi_app

    paths: list[str] = []
    for route in getattr(fastapi_app, "routes", []):
        methods = getattr(route, "methods", None) or set()
        route_path = getattr(route, "path", None)
        if "GET" not in methods or not route_path or "{" in route_path:
            continue
        paths.append(route_path)
    return sorted(set(paths))


def probe_all(
    base_url: str, paths: list[str], mode: str, token: str | None = None
) -> list[tuple[str, int, str]]:
    """逐个 GET 探测，返回违规三元组 (path, status, mode)。"""
    violations: list[tuple[str, int, str]] = []
    for probe_path in paths:
        try:
            status, _ = http_get(base_url + probe_path, token=token)
        except RuntimeError as exc:
            raise RuntimeError(f"{probe_path}: {exc}") from exc
        if classify(status, mode):
            violations.append((probe_path, status, mode))
    return violations


def _scratch_dir() -> Path:
    """隔离的可写落点（不用 %TEMP%：受限环境下不可写）。"""
    base = ROOT / ".scratch"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="endpoint500-", dir=str(base)))


def isolated_env(scratch: Path) -> dict[str, str]:
    """一次性库 + 隔离数据目录的进程环境。

    DATABASE_URL 用绝对 sqlite URL：相对写法会被 config 折算到 DATA_DIR 下，
    而 paths.get_database_path() 对相对 URL 会退回 data/rural_revitalization.db，
    两个消费者看到不同的库（历史路径双源 bug 同款）。
    """
    data_dir = scratch / "data"
    cache_dir = scratch / "cache"
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
    env["CACHE_DIR"] = str(cache_dir)
    env["DATABASE_URL"] = "sqlite:///" + (data_dir / "endpoint500.db").as_posix()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def venv_python() -> str:
    win = BACKEND / ".venv" / "Scripts" / "python.exe"
    return str(win if win.exists() else BACKEND / ".venv" / "bin" / "python")


def prepare_schema(env: dict[str, str]) -> None:
    """在一次性库上跑 alembic upgrade head（schema 权威来源）。"""
    proc = subprocess.run(
        [venv_python(), "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        tail = "\n".join(((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-15:])
        raise RuntimeError(f"alembic upgrade head 失败（rc={proc.returncode}）:\n{tail}")


def database_file(env: dict[str, str]) -> Path:
    return Path(env["DATABASE_URL"][len("sqlite:///"):])


def grant_admin_token(base_url: str, db_path: Path) -> str:
    """解锁首登强制改密并取管理员令牌。

    一次性库由启动播种创建 admin（must_change_password=True），服务端中间件会拦下除改密外的
    所有请求，探测就没有意义。这里直接置位 —— 只作用于一次性库，不影响任何真实库。
    """
    for _ in range(60):
        if db_path.exists():
            break
        time.sleep(0.5)
    if not db_path.exists():
        raise RuntimeError(f"一次性库未创建: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE users SET must_change_password = 0")
        conn.commit()
    finally:
        conn.close()
    status, body = http_post_json(
        base_url + "/api/v1/auth/login",
        {"username": FACTORY_ADMIN_USERNAME, "password": FACTORY_ADMIN_PASSWORD},
    )
    if status != 200:
        raise RuntimeError(f"管理员登录失败: HTTP {status} {body[:200]}")
    payload = json.loads(body)
    data = payload.get("data") or payload
    token = data.get("access_token") or data.get("accessToken")
    if not token:
        raise RuntimeError(f"登录响应缺少 access_token: {body[:200]}")
    return str(token)


def _pick_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="GET 端点 5xx 巡检（隔离库 + 匿名/管理员双登录态）")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--skip-auth", action="store_true", help="只扫匿名态（排障用）")
    ap.add_argument("--keep-server", action="store_true", help="调试：结束后不杀进程、不删目录")
    args = ap.parse_args(argv)

    scratch = _scratch_dir()
    env = isolated_env(scratch)
    keep = args.keep_server
    proc: subprocess.Popen | None = None
    try:
        prepare_schema(env)
        port = _pick_port(args.port)
        log_path = scratch / "server.log"
        with open(log_path, "wb") as log_file:
            proc = subprocess.Popen(
                [venv_python(), "-m", "uvicorn", "app.main:app",
                 "--host", "127.0.0.1", "--port", str(port)],
                cwd=str(BACKEND),
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        base = f"http://127.0.0.1:{port}"
        auth_checked = False
        try:
            wait_ready(base)
            paths = collect_get_paths()
            if not paths:
                print("[FAIL] 未解析到任何 GET 端点", file=sys.stderr)
                return 1
            violations = probe_all(base, paths, MODE_ANON)
            if not args.skip_auth:
                token = grant_admin_token(base, database_file(env))
                violations.extend(probe_all(base, paths, MODE_AUTH, token=token))
                auth_checked = True
        except RuntimeError as exc:
            print(f"[FAIL] {exc}", file=sys.stderr)
            try:
                tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
                print("\n".join(tail), file=sys.stderr)
            except OSError:
                pass
            return 1

        if args.update:
            BASELINE.parent.mkdir(parents=True, exist_ok=True)
            entries = [
                {"mode": mode, "path": item_path, "status": status, "reason": "人工确认豁免"}
                for item_path, status, mode in violations
            ]
            BASELINE.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[update] 豁免清单 {BASELINE.relative_to(ROOT)} <- {len(entries)} 条")
            return 0

        known: list[dict] = []
        if BASELINE.exists():
            known = json.loads(BASELINE.read_text(encoding="utf-8"))
        fresh, excused = partition_violations(violations, known)
        if fresh:
            for item_path, status, mode in fresh:
                print(f"  x [{mode}] {item_path}  ->  {classify(status, mode)}")
            print(
                "\n说明：以上 GET 端点返回服务端错误 / 令牌被拒。"
                "若属有意为之：运行 --update 并在基线里写明理由；否则请修降级路径。",
                file=sys.stderr,
            )
            return 1
        modes = "anon+auth" if auth_checked else "anon"
        sweeps = 2 if auth_checked else 1
        print(
            f"[gate:endpoint_500] OK (isolation DB, modes={modes}, "
            f"probed {len(paths)} GET endpoints x {sweeps}, exemptions {len(excused)})"
        )
        return 0
    finally:
        if proc is not None and not keep:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
        if not keep:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
