# -*- coding: utf-8 -*-
"""路由认证覆盖门禁：新增的业务路由必须有认证依赖。

## 为什么需要

`api_v1_router` **没有**全局认证依赖（只有 `enforce_write_grant` 的写权限门禁），
所以每个路由必须自己声明 `Depends(get_current_user)` 之类。853 个路由里
670+70 处显式认证 —— 差额全靠人工保证，新增一个路由忘了写依赖就是**越权入口**，
而且代码 review 很难看出来（少写一行 `Depends` 而已）。

本门禁用 FastAPI 运行时依赖树递归判定（比 AST 更准：能识别经
`require_manager_role` 等中间依赖间接要求认证的路由），把"无认证"路由与
白名单比对，出现白名单外的新增项即失败。

## 白名单的两类

1. **设计必需公开**：登录/登出/CSRF/公开配置、健康检查（容器探针）、
   地图瓦片（Leaflet `<img>` 直连带不了 token）、机器码激活、权限包导入
   （限 loopback）、反馈（有意匿名）、shutdown（loopback + 内部密钥）。
   这些都有各自的保护机制，逐个核查过（见 2026-10-28 审计记录）。

2. **待加固（静态字典）**：`/policies/options/*` 等下拉选项接口。它们返回的是
   中文字典标签，泄露危害低，但按"所有业务 API 需认证"的口径应当加依赖。
   先登记在此，加固后从白名单移除 —— 白名单是**收敛**用的，不是免死金牌。

## 用法（在 backend 目录）

    python ../scripts/check_route_auth.py            # 门禁
    python ../scripts/check_route_auth.py --list     # 打印当前所有无认证路由
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SECRET_KEY", "route-auth-gate-secret-key-32-chars!!")
os.environ.setdefault("ENVIRONMENT", "test")

sys.path.insert(0, ".")

from fastapi.routing import APIRoute  # noqa: E402

from app.main import app  # noqa: E402

# 视为"认证依赖"的函数名（含间接要求认证的角色守卫）
AUTH_FUNC_NAMES = {
    "get_current_user",
    "get_current_active_user",
    "get_current_superuser",
    "get_current_admin_user",
    "require_admin",
    "require_manager_role",
    "require_policy_operator_role",
    "require_funds_operator_role",
    "verify_api_key",
    "verify_internal_token",
    "enforce_admin_include_deleted",
}

# 允许无认证的路径前缀（按前缀匹配，`/api/v1/health` 覆盖其全部子路径）
PUBLIC_PREFIXES = (
    # —— 设计必需公开 ——
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/register",
    "/api/v1/auth/logout",
    "/api/v1/auth/public-config",
    "/api/v1/auth/csrf-token",
    "/api/v1/auth/two-factor/verify-login",
    "/api/v1/health",
    "/api/v1/map/tiles",
    "/api/v1/map/regions",
    "/api/v1/map/county-coords",
    "/api/v1/map/tile-info",
    "/api/v1/offline-map",
    "/api/v1/machine-code",
    "/api/v1/permission-packages/import",
    "/api/v1/permission-packages/confirm",
    "/api/v1/feedback",
    "/api/v1/shutdown",
    "/api/v1/system/version",
    "/api/v1/system/update-logs",
    # 系统信息/健康/帮助：健康检查供容器探针，帮助与版本号属公开元信息。
    # `/system/info` `/system/status` `/system/environment` 有 get_current_user，
    # `/system/shutdown` `/system/restart` 在函数体内调 require_admin（脚本检测不到
    # 函数内校验，故不列；它们若丢失校验会被这里挡住）。
    "/api/v1/system/health",
    "/api/v1/system/help",
    "/api/v1/system/version",
    # 初始化：初始化前系统没有用户，无法认证；`_run_initialization` 内
    # `if svc.is_initialized(): 400 系统已完成初始化，不能重复执行` 兜住重复调用。
    "/api/v1/system/init",
    # 备份：用自定义认证函数（`_authenticate_backup_request` 等，在函数体内
    # `await` 调用而非 Depends，脚本的依赖树检测看不到）。三个接口分别校验
    # 「内部密钥或写权限账号」「内部密钥或登录用户」「内部密钥或管理员」，
    # 详见 app/api/v1/system/backup.py:154-210。
    "/api/v1/system/backup",
    # 字典选项（低危）：返回中文字典标签。按「所有业务 API 需认证」的口径
    # 应当加 Depends，属待加固项；加固后请从此处移除。
    "/api/v1/system/audit/actions",
    "/api/v1/system/audit/levels",
    # —— 待加固：静态字典 / 模板下载（前端走 axios 带 token，可安全加认证）——
    # 加固后请从此处删除，让门禁继续收紧。
    "/api/v1/organizations/types/options",
    "/api/v1/policies/options/",
    "/api/v1/policies/types",
    "/api/v1/policies/import/template",
    "/api/v1/schools/options/",
    "/api/v1/schools/import/template",
    "/api/v1/supported-villages/import-template",
    "/api/v1/report-templates/available-fields",
    # —— 基础设施（非业务 API）——
    "/health",
    "/favicon.ico",
    "/version.json",
    "/docs",
    "/redoc",
    "/openapi.json",
    # SPA 前端路由兜底（静态文件服务，不返回任何业务数据）
    "/{full_path:path}",
)


def _has_auth(dependant, seen: set[int] | None = None) -> bool:
    if seen is None:
        seen = set()
    for dep in getattr(dependant, "dependencies", []) or []:
        fn = getattr(dep, "call", None)
        if getattr(fn, "__name__", "") in AUTH_FUNC_NAMES:
            return True
        if fn is None or id(fn) in seen:
            continue
        seen.add(id(fn))
        if _has_auth(dep, seen):
            return True
    return False


def _allowed(path: str) -> bool:
    return any(path == p.rstrip("/") or path.startswith(p) for p in PUBLIC_PREFIXES)


def main() -> int:
    offenders: list[str] = []
    total = 0
    no_auth = 0
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        total += 1
        if _has_auth(route.dependant):
            continue
        no_auth += 1
        if not _allowed(route.path):
            methods = ",".join(sorted(m for m in route.methods if m != "HEAD"))
            offenders.append(f"{methods:10s} {route.path}")

    if "--list" in sys.argv:
        print(f"路由总数 {total}，无认证 {no_auth}，白名单外 {len(offenders)}")
        for o in offenders:
            print("  ", o)
        return 0

    print(f"路由总数 {total}，无认证 {no_auth}（均在白名单内）" if not offenders
          else f"路由总数 {total}，无认证 {no_auth}，**白名单外 {len(offenders)}**")
    if offenders:
        print("\n以下路由没有认证依赖，且不在白名单里：")
        for o in offenders:
            print("  ", o)
        print(
            "\n处理方式：① 给路由加 `current_user=Depends(get_current_user)`（推荐）；"
            "② 若确属设计上必须公开，加进本脚本 PUBLIC_PREFIXES 并写明保护机制。"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
