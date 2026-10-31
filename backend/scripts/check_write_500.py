#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""写端点 5xx 巡检（slow 档，隔离库 + 管理员令牌 + CSRF，逐写请求探测）。

为什么值得有一道：endpoint_500 只扫 GET，而全站 845 个 /api 端点里有 417 个是写端点
（POST 300 / DELETE 62 / PUT 53 / PATCH 2）—— 占一半还多，此前完全没人整体探过。
写端点最容易出 500 的恰恰不是正常路径（crud_smoke 只覆盖帮扶村/项目/政策/数据包/上报等主链路），
而是「脏输入 + 不存在的路径参数」：请求体校验漏了某一层、拿 None 去查库、关联对象缺失时
直接 .attribute，都会在真实进程里变成 500，单测用 MagicMock 喂正常数据则永远是绿的。

探测口径（只问「会不会 500」，不问业务语义）：
- 请求体一律 {"}（空对象）：必填字段缺失时应当 422/400，而不是 500；
  全部字段可选的端点会真的执行（导出/备份/清缓存等），这正是我们想看的正常路径。
- 路径参数代入「不存在的值」（*_id/id -> 999999，年份类 -> 2025，其它 -> smoke-missing）：
  不存在就应当 404，而不是 500 —— 顺带避免真的删掉播种数据。
- 每条请求都带管理员令牌与 CSRF 双提交头，绕过鉴权/CSRF 短路，真正进入处理函数。
- auth 态下的 401 也算违规（令牌有效却被拒说明鉴权链路坏了），5xx 一律违规。

隔离：.scratch/write500-* 下一次性库（alembic upgrade head）→ 起实例 → 扫完删目录。
跑完即弃，所以在端点里发生的写操作（清缓存、建备份、生成上传会话）不会污染任何真实数据。

故意跳过（会停机 / 重置换库 / 让令牌全部失效，跑完后续探测就没意义了）：
    /api/v1/system/shutdown、/api/v1/shutdown、/api/v1/system/init/*、
    /api/v1/system/backup/restore、/api/v1/system/backup/upload-restore、
    /api/v1/system/admin/restore、/api/v1/secrets/rotate、/api/v1/encryption/initialize、
    /api/v1/machine-code/recover-admin-factory-password、/api/v1/data-tier/restore、
    /api/v1/auth/{login,logout,refresh}（认证生命周期已由 crud_smoke 覆盖）

用法:
    python backend/scripts/check_write_500.py              # 隔离库 + 管理员令牌全扫
    python backend/scripts/check_write_500.py --update     # 人工确认后写回已知豁免（慎用）
    python backend/scripts/check_write_500.py --keep-server
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import check_crud_smoke as cs  # noqa: E402  复用带 CSRF 的 HttpClient
import check_endpoint_500 as ep  # noqa: E402  复用隔离库/建表/令牌/端口助手

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
BASELINE = ROOT / "scripts" / "gate_baselines" / "write_500.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

WRITE_METHODS = ("POST", "PUT", "PATCH")
PATH_METHODS = ("DELETE",)
ALL_METHODS = WRITE_METHODS + PATH_METHODS

MISSING_ID = "999999"
SAMPLE_YEAR = "2025"
MISSING_SLUG = "smoke-missing"
YEAR_PARAMS = {"year", "annual", "annual_year"}

# 合法状态：4xx 全是「被拒绝」，属门禁期望；503 是维护窗口中间件对写请求的合法降级。
ALLOWED_STATUSES = {
    200, 201, 202, 204, 206,
    301, 302, 303, 304, 307, 308,
    400, 401, 403, 404, 405, 406, 409, 410, 411, 412, 413, 414, 415, 416,
    422, 423, 425, 428, 429, 431, 503,
}

# 会停机 / 重置换库 / 令牌全失效的端点：探测它们会让后续扫描失去意义。
SKIP_PATHS = frozenset({
    "/api/v1/system/shutdown",
    "/api/v1/shutdown",
    "/api/v1/system/init/initialize",
    "/api/v1/system/init/reset",
    "/api/v1/system/backup/restore",
    "/api/v1/system/backup/upload-restore",
    "/api/v1/system/admin/restore",
    "/api/v1/secrets/rotate",
    "/api/v1/encryption/initialize",
    "/api/v1/machine-code/recover-admin-factory-password",
    "/api/v1/data-tier/restore",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
})


def sample_value(param: str) -> str:
    """给路径参数挑一个「必然不存在」的样例值（只求进入处理函数）。"""
    name = param.split(":")[0].strip().lower()
    if name in YEAR_PARAMS:
        return SAMPLE_YEAR
    if name == "id" or name == "rid" or name.endswith("_id"):
        return MISSING_ID
    return MISSING_SLUG


def expand_path(path: str) -> str:
    """把 /api/v1/foo/{item_id} 展开成可请求的具体路径；catch-all 原样保留。"""
    return re.sub(r"\{([^}]+)\}", lambda m: sample_value(m.group(1)), path)


def skip_reason(path: str) -> Optional[str]:
    """判断该端点是否属于「探测即自毁」的跳过项；返回跳过理由（None 表示可扫）。"""
    if ":path}" in path:
        return "SPA catch-all"
    if path in SKIP_PATHS:
        return "会停机/重置/令令牌失效"
    return None


def sample_body(method: str) -> Optional[Dict[str, object]]:
    """写请求的空对象请求体；DELETE 不带体（FastAPI 里 DELETE 参数一律走路径/查询）。"""
    return None if method in PATH_METHODS else {}


def classify(status: int) -> Optional[str]:
    """判定一次写探测是否违规；返回违规说明，None 表示合法。

    - status < 0：连接失败（实例挂了/超时）；
    - 401：带管理员令牌仍被拒 → 鉴权链路坏了；
    - 5xx 或其它不在白名单的状态：服务端错误。
    """
    if status < 0:
        return "连接失败"
    if status == 401:
        return "带管理员令牌仍返回 401"
    if status in ALLOWED_STATUSES:
        return None
    return "HTTP %d" % status


def entry_key(entry: dict) -> Tuple[str, str, int]:
    """豁免条目的唯一键：方法 + 展开后的路径 + 状态码。"""
    return (str(entry.get("method") or "POST"), str(entry["path"]), int(entry["status"]))


def partition_violations(
    found: List[Tuple[str, str, int]], known: Sequence[dict]
) -> Tuple[List[Tuple[str, str, int]], List[Tuple[str, str, int]]]:
    """按豁免清单切分「新出现的违规」与「已登记豁免」；fresh 非空即门禁红。"""
    known_keys = {entry_key(item) for item in known}
    fresh: List[Tuple[str, str, int]] = []
    excused: List[Tuple[str, str, int]] = []
    for method, path, status in found:
        (excused if (method, path, status) in known_keys else fresh).append((method, path, status))
    return fresh, excused


def filter_write_routes(route_objects: Iterable[object]) -> Tuple[List[Tuple[str, str]], List[str]]:
    """从路由对象里挑出可探测的写端点（纯函数，便于自测）。

    返回 (可探测的 (method, 展开路径) 列表, 被跳过端点的说明列表)。
    """
    routes: List[Tuple[str, str]] = []
    skipped: List[str] = []
    for route in route_objects:
        methods = getattr(route, "methods", None) or set()
        route_path = getattr(route, "path", None)
        if not route_path or not route_path.startswith("/api"):
            continue
        write_methods = sorted(m for m in methods if m in ALL_METHODS)
        if not write_methods:
            continue
        reason = skip_reason(route_path)
        if reason:
            skipped.append("%s %s（%s）" % ("/".join(write_methods), route_path, reason))
            continue
        expanded = expand_path(route_path)
        for method in write_methods:
            routes.append((method, expanded))
    routes.sort()
    skipped.sort()
    return routes, skipped


def collect_write_routes() -> Tuple[List[Tuple[str, str]], List[str]]:
    """枚举写端点（进程内 FastAPI 路由，本应用仅 DEBUG 才开 /openapi.json）。"""
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from app.main import app as fastapi_app

    return filter_write_routes(getattr(fastapi_app, "routes", []))


def probe_all(client: "cs.HttpClient", routes: Sequence[Tuple[str, str]],
              timeout: float = 30.0) -> List[Tuple[str, str, int]]:
    """逐个写端点探测，返回违规三元组 (method, path, status)；连接失败记 -1。"""
    violations: List[Tuple[str, str, int]] = []
    for method, path in routes:
        try:
            resp = client.request(method, path, payload=sample_body(method), timeout=timeout)
        except cs.SmokeFailure:
            violations.append((method, path, -1))
            continue
        if classify(resp.status):
            violations.append((method, path, resp.status))
    return violations


def scratch_dir() -> Path:
    """隔离的可写落点（不用 %TEMP%：受限环境下不可写）。"""
    base = ROOT / ".scratch"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="write500-", dir=str(base)))
    return scratch


def isolated_env(scratch: Path) -> Dict[str, str]:
    """一次性库 + 隔离数据目录的进程环境（绝对 sqlite URL，避免路径双源）。"""
    data_dir = scratch / "data"
    cache_dir = scratch / "cache"
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DATA_DIR"] = str(data_dir)
    env["CACHE_DIR"] = str(cache_dir)
    env["DATABASE_URL"] = "sqlite:///" + (data_dir / "write500.db").as_posix()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def database_file(env: Dict[str, str]) -> Path:
    return Path(env["DATABASE_URL"][len("sqlite:///"):])


def bootstrap_token(env: Dict[str, str], base_url: str) -> str:
    """解锁首登强制改密并取管理员令牌（只作用于一次性库）。"""
    db_path = database_file(env)
    for _ in range(60):
        if db_path.exists():
            break
        time.sleep(0.5)
    if not db_path.exists():
        raise RuntimeError("一次性库未创建: %s" % db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE users SET must_change_password = 0")
        conn.commit()
    finally:
        conn.close()
    status, body = ep.http_post_json(
        base_url + "/api/v1/auth/login",
        {"username": ep.FACTORY_ADMIN_USERNAME, "password": ep.FACTORY_ADMIN_PASSWORD},
    )
    if status != 200:
        raise RuntimeError("管理员登录失败: HTTP %d %s" % (status, body[:200]))
    payload = json.loads(body)
    data = payload.get("data") or payload
    token = data.get("access_token") or data.get("accessToken")
    if not token:
        raise RuntimeError("登录响应缺少 access_token: %s" % body[:200])
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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="写端点 5xx 巡检（隔离库 + 管理员令牌）")
    ap.add_argument("--port", type=int, default=8802)
    ap.add_argument("--update", action="store_true", help="人工确认后写回已知豁免")
    ap.add_argument("--keep-server", action="store_true", help="调试：结束后不杀进程、不删目录")
    ap.add_argument("--timeout", type=float, default=30.0, help="单请求超时秒数")
    args = ap.parse_args(argv)

    scratch = scratch_dir()
    env = isolated_env(scratch)
    keep = args.keep_server
    proc: Optional[subprocess.Popen] = None
    try:
        ep.prepare_schema(env)
        port = _pick_port(args.port)
        log_path = scratch / "server.log"
        with open(log_path, "wb") as log_file:
            proc = subprocess.Popen(
                [ep.venv_python(), "-m", "uvicorn", "app.main:app",
                 "--host", "127.0.0.1", "--port", str(port)],
                cwd=str(BACKEND),
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        base = "http://127.0.0.1:%d" % port
        try:
            ep.wait_ready(base)
            # 路由枚举在门禁进程内做，先把该进程也指到一次性库，避免碰到真实数据目录
            os.environ.update({k: env[k] for k in ("DATA_DIR", "CACHE_DIR", "DATABASE_URL")})
            routes, skipped = collect_write_routes()
            if not routes:
                print("[FAIL] 未解析到任何写端点", file=sys.stderr)
                return 1
            token = bootstrap_token(env, base)
            client = cs.HttpClient(base, token=token)
            client.fetch_csrf()
            violations = probe_all(client, routes, timeout=args.timeout)
        except (RuntimeError, cs.SmokeFailure) as exc:
            print("[FAIL] %s" % exc, file=sys.stderr)
            try:
                tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
                print("\n".join(tail), file=sys.stderr)
            except OSError:
                pass
            return 1

        if args.update:
            BASELINE.parent.mkdir(parents=True, exist_ok=True)
            entries = [
                {"method": method, "path": path, "status": status, "reason": "人工确认豁免"}
                for method, path, status in violations
            ]
            BASELINE.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("[update] 豁免清单 %s <- %d 条" % (BASELINE.relative_to(ROOT), len(entries)))
            return 0

        known: List[dict] = []
        if BASELINE.exists():
            known = json.loads(BASELINE.read_text(encoding="utf-8"))
        fresh, excused = partition_violations(violations, known)
        if fresh:
            for method, path, status in fresh:
                print("  x [%s] %s  ->  %s" % (method, path, classify(status)))
            print(
                "\n说明：以上写端点返回服务端错误 / 令牌被拒。"
                "脏输入与不存在的路径参数应当被 4xx 拒绝，不应 500；"
                "若属有意为之：运行 --update 并在基线里写明理由；否则请修降级路径。",
                file=sys.stderr,
            )
            return 1
        literal = sum(1 for _m, p in routes if MISSING_ID not in p and MISSING_SLUG not in p)
        print(
            "[gate:write_500] OK (isolation DB, modes=admin, probed %d write endpoints "
            "(%d literal + %d with path params), exemptions %d, skipped %d)"
            % (len(routes), literal, len(routes) - literal, len(excused), len(skipped))
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
            if not ep.cleanup_scratch(scratch):
                print("[warn] 临时目录未能删除: %s" % scratch, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
