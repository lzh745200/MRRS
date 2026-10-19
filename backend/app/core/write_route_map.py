"""写接口 → 模块 映射（R33 单位授权守卫的前置件）。

## 为什么用"规则表 + 最长前缀"而不是逐接口清单

本仓写接口上千个，逐条维护必然漂移；而授权粒度是**模块**，同一模块下写接口语义一致，
前缀匹配足以表达。规则按前缀长度**降序**匹配，保证 `/api/v1/auth/users` 这类更具体的
规则优先于 `/api/v1/auth`。

## 未命中 = None

`resolve_module()` 返回 None 表示"没有可归属的模块"。守卫在 `enforce` 模式下对 None
**fail-closed 拒绝**，在 `shadow` 模式下只记日志。因此上线前必须先跑
`scripts/report_unmapped_write_routes.py`，把未命中清单清零 —— 否则会误拦。

## 豁免

少数写接口必须放行（登录、匿名反馈、授权包导入自举、健康探针）。豁免按**路径边界**
匹配（`path == p` 或 `path.startswith(p + "/")`），避免 `/api/v1/auth/login` 顺带豁免
`/api/v1/auth/login-audit` 这类无关路径。
"""

from __future__ import annotations

from typing import Optional

# 视为"写入"的 HTTP 方法
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# 必须放行的写接口（路径边界匹配）
EXEMPT_PREFIXES: tuple = (
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/change-password",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/verify-2fa",
    "/api/v1/auth/register",         # 公开注册（是否放开由业务开关控制，与单位授权无关）
    "/api/v1/feedback",              # 匿名可提交，无单位归属
    "/api/v1/org-grants/import",     # 授权包导入：自举路径，被拦则无法更新授权
    "/api/v1/control-packages/import",
    "/api/v1/health",
    "/health",
)

# (路径前缀, 模块 key)。模块 key 与 MENU_DEFINITIONS 的 key 同源。
MODULE_RULES: tuple = (
    # ── 身份与权限（比 /api/v1/auth 更具体，必须排在前面）──
    ("/api/v1/auth/users", "users-orgs"),
    ("/api/v1/auth/rbac", "roles"),
    ("/api/v1/auth/two-factor", "system-console-security"),
    ("/api/v1/users", "users-orgs"),
    ("/api/v1/rbac", "roles"),
    ("/api/v1/menus", "menus"),
    ("/api/v1/permission-packs", "system-permission-packs"),
    ("/api/v1/permission-package", "system-permission-packs"),
    ("/api/v1/org-policies", "system-permission-packs"),
    ("/api/v1/org-grants", "system-permission-packs"),
    ("/api/v1/organizations", "organizations"),
    # ── 业务主链 ──
    ("/api/v1/supported-villages", "villages"),
    ("/api/v1/villages", "villages"),
    ("/api/v1/households", "households"),
    ("/api/v1/projects", "projects"),
    ("/api/v1/schools", "schools"),
    ("/api/v1/funds", "funds"),
    ("/api/v1/fund-budgets", "funds-budget"),
    ("/api/v1/fund-lifecycle", "funds-lifecycle"),
    ("/api/v1/pairing", "pairing"),
    ("/api/v1/donation", "donation"),
    ("/api/v1/consumption", "consumption"),
    ("/api/v1/policies", "policies"),
    ("/api/v1/rural-works", "rural-works"),
    ("/api/v1/work-logs", "work-calendar"),
    ("/api/v1/todos", "todos"),
    ("/api/v1/approval", "approval"),
    ("/api/v1/messages", "messages"),
    ("/api/v1/media", "media-library"),
    ("/api/v1/effectiveness", "effectiveness"),
    ("/api/v1/analytics", "analytics"),
    ("/api/v1/map", "map-tiles"),
    ("/api/v1/sentiment", "sentiment"),
    ("/api/v1/checkin", "checkin"),
    # ── 数据交换 ──
    ("/api/v1/import-export", "batch-import"),
    ("/api/v1/import", "batch-import"),
    ("/api/v1/export", "report-export"),
    ("/api/v1/reports", "report-templates"),
    ("/api/v1/data-sync", "data-sync-import"),
    ("/api/v1/data-package", "data-package"),
    ("/api/v1/data-packages", "data-package"),
    ("/api/v1/data", "data"),
    # ── 系统与运维 ──
    ("/api/v1/system", "system"),
    ("/api/v1/encryption", "encryption"),
    ("/api/v1/backup", "backup"),
    ("/api/v1/audit", "audit"),
    ("/api/v1/monitoring", "monitor"),
    ("/api/v1/zero-trust", "zero-trust"),
    ("/api/v1/secrets", "secrets"),
    ("/api/v1/machine-codes", "machine-code"),
    ("/api/v1/pass-codes", "pass-code"),
    ("/api/v1/validation-rules", "validation-rules"),
    ("/api/v1/i18n", "i18n"),
    ("/api/v1/email", "email"),
    ("/api/v1/control-packages", "control-package"),
    ("/api/v1/config-packages", "config-package"),
    # ── 实测补齐（2026-10-19 用 scripts/report_unmapped_write_routes.py 扫全量路由得到）──
    # 注意单复数差异：实际路由是 machine-code / pairings / donations /
    # permission-packages，与上面的复数写法不同，必须分别列出。
    ("/api/v1/machine-code", "machine-code"),
    ("/api/v1/data-reports", "data-package-report"),
    ("/api/v1/pairings", "pairing"),
    ("/api/v1/rural-tasks", "rural-works-list"),
    ("/api/v1/data-quality", "data"),
    ("/api/v1/reminders", "reminder"),
    ("/api/v1/report-templates", "report-templates"),
    ("/api/v1/validation", "validation-rules"),
    ("/api/v1/ai-enhanced", "analytics"),
    ("/api/v1/ai", "analytics"),
    ("/api/v1/batch", "batch-operations"),
    ("/api/v1/chunked-upload", "chunked-upload"),
    ("/api/v1/notifications", "messages"),
    ("/api/v1/dashboard", "dashboard"),
    ("/api/v1/data-tier", "data-tier"),
    ("/api/v1/donations", "donation"),
    ("/api/v1/permission-packages", "system-permission-packs"),
    ("/api/v1/subordinate-reports", "data-package-report"),
    ("/api/v1/subordinates", "data-package-report"),
    ("/api/v1/system-health", "health-check"),
    ("/api/v1/two-factor", "system-console-security"),
    ("/api/v1/async-export", "report-export"),
    ("/api/v1/offline-map", "map-tiles"),
    ("/api/v1/performance", "cache"),
    ("/api/v1/files", "media-library"),
    ("/api/v1/handover", "handover"),
    ("/api/v1/shutdown", "system-console-ops"),
)

# 按前缀长度降序，保证更具体的规则优先命中
_SORTED_RULES = tuple(sorted(MODULE_RULES, key=lambda item: len(item[0]), reverse=True))


def is_write_method(method: str) -> bool:
    """是否为写方法（大小写不敏感）。"""
    return method.upper() in WRITE_METHODS


def is_exempt(path: str) -> bool:
    """是否属于必须放行的写接口（路径边界匹配）。"""
    normalized = path.rstrip("/") or "/"
    for prefix in EXEMPT_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


def resolve_module(path: str) -> Optional[str]:
    """把请求路径归属到模块 key；无法归属返回 None（调用方决定 fail-closed 还是告警）。"""
    normalized = path.rstrip("/") or "/"
    for prefix, module_key in _SORTED_RULES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return module_key
    return None


def unmapped_write_routes(routes) -> list:
    """从 FastAPI 路由表挑出"是写方法但归属不到模块"的接口。

    `routes` 传 `app.routes`。返回 `[(methods, path)]`，供上线前清零未命中清单。
    """
    result = []
    for route in routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        write_methods = {m for m in methods if is_write_method(m)}
        if not write_methods:
            continue
        if is_exempt(path):
            continue
        if resolve_module(path) is None:
            result.append((sorted(write_methods), path))
    return result
