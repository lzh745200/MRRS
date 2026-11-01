"""组织模块策略闸门中间件（短期改进第 5 项，2026-11-01）。

背景
----
``org_module_policies`` 表（organization_id + module_key + visibility +
edit_mode）早有 CRUD（api/v1/org_module_policy.py）与前端配置页，但
visible / edit_mode 两端都没有执行点：把某模块配成"只读 / 禁用"后，该组织
的写接口照样能落库。本中间件补后端的 **edit_mode 执行点**；visible 对应的
"隐藏菜单入口"属于前端（本轮不改）。

行为
----
1. 只看写方法（POST/PUT/PATCH/DELETE）；GET/HEAD/OPTIONS 与 WebSocket /
   lifespan 一律放行；
2. 用静态表 ``ORG_MODULE_RULES`` 做 URL 前缀 → module_key 映射（最长前缀 +
   路径边界匹配）；映射不到（含 /api/v1/org-policies 自身，避免自锁）放行；
3. 从 Authorization Bearer 令牌取 username 查 User → 取 organization_id →
   查该组织对该 module 的策略（按 ``(organization_id, module_key)`` 做 5 秒
   进程内 TTL 缓存，见"已知边界"）。无令牌 / 令牌无效 / 查无用户 / 用户无
   组织 / 无策略 / edit_mode 为 full_edit → 放行：认证与授权由端点依赖负责，
   本层只执行"组织级模块开关"；
4. edit_mode ∈ {read_only, disabled} 时按 ``settings.ORG_MODULE_POLICY_MODE``：
   - ``off``：不拦截（零额外行为）；
   - ``shadow``（默认）：``logger.warning`` + 响应头
     ``X-Org-Module-Policy: would-block``，仍然放行 —— 上线观察期用；
   - ``enforce``：403，detail 说明模块与组织；
5. 任何判定异常（DB 不可用 / 数据异常 / 令牌头畸形）→ 放行 +
   ``logger.warning``，绝不把全站写接口变成 500。本中间件不读、不消费请求体，
   可安全包在流式上传路径外层。

中间件顺序
----------
注册位置见 main.py 处注释：执行顺序上位于 CSRF / RequestLogger / Audit /
ViewerReadOnly / MaintenanceGate 之内（被拒请求仍进访问日志与审计，且更便宜的
403/503 先返回），位于 Metrics / QueryCounter 与业务路由之外（被拒请求不进入
指标采集与 DB 业务路径）。

已知边界
--------
- 进程内 5 秒 TTL 缓存（``CACHE_TTL_SECONDS``，key=(organization_id,
  module_key)，"无策略"的 None 也缓存）：每个组织每个模块 5 秒内最多查一次
  策略表（首次判定仍需 1 次 users.username + 1 次策略查询）；策略变更最坏
  5 秒后生效，写接口可接受。``off`` 模式在缓存与查库之前直接放行（零开销）；
- **策略只作用于该组织自身，不沿组织树继承**：上级组织配 disabled / read_only
  不会自动作用于下级；如需整棵子树生效，请在每个子组织也显式配置（或由管控
  包下发）——本层不做递归/继承判断；
- 只拦 edit_mode，不拦 visibility（前端入口隐藏不在本层）；
- 方法口径会把 POST 的"读类"端点（导出 / 预览 / 查询 / OCR）也算写操作；
  enforce 上线前建议另行白名单，避免"只读"组织无法导出。
"""

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 执行模式 ────────────────────────────────────────────────────────
MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_ENFORCE = "enforce"
DEFAULT_MODE = MODE_SHADOW
VALID_MODES = frozenset({MODE_OFF, MODE_SHADOW, MODE_ENFORCE})

# ── 判定口径 ────────────────────────────────────────────────────────
# 写方法集合：GET/HEAD/OPTIONS 天然只读，不拦截（健康检查/探活均属 GET）。
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# 只有这两种 edit_mode 会收窄写权限；full_edit 与未知值均放行（fail-open）。
BLOCKED_EDIT_MODES = frozenset({"read_only", "disabled"})
_EDIT_MODE_LABELS: Dict[str, str] = {"read_only": "只读", "disabled": "禁用"}

# shadow 模式的响应头与取值（enforce 不写该头）。
SHADOW_HEADER_NAME = b"x-org-module-policy"
SHADOW_HEADER_VALUE = b"would-block"

# URL 前缀 → org_module_policies.module_key。
# 前半段取 api/v1/org_module_policy.py 的 MODULE_DEFINITIONS（配置页实际写入的
# 15 个 key）；后半段是管控包导入可能携带的 R33 模块键（control_package.py 的
# _apply_module_policies 不校验 key 白名单，故 households/media/consumption/
# villages 等键可能真实存在于表中）。映射不到就不拦，宁可漏拦不可错拦。
ORG_MODULE_RULES: Tuple[Tuple[str, str], ...] = (
    # MODULE_DEFINITIONS 15 键
    ("/api/v1/dashboard", "dashboard"),
    ("/api/v1/supported-villages", "supported-villages"),
    ("/api/v1/projects", "projects"),
    ("/api/v1/funds", "funds"),
    ("/api/v1/fund-budgets", "funds"),
    ("/api/v1/fund-lifecycle", "funds"),
    ("/api/v1/schools", "schools"),
    ("/api/v1/rural-works", "rural-works"),
    ("/api/v1/policies", "policies"),
    ("/api/v1/organizations", "organizations"),
    ("/api/v1/analytics", "analytics"),
    ("/api/v1/map", "map"),
    ("/api/v1/offline-map", "map"),
    ("/api/v1/reports", "reports"),
    ("/api/v1/report-templates", "reports"),
    ("/api/v1/data-reports", "reports"),
    ("/api/v1/data-packages", "data-package"),
    ("/api/v1/data-package", "data-package"),
    ("/api/v1/data-sync", "data-sync"),
    ("/api/v1/messages", "messages"),
    ("/api/v1/notifications", "messages"),
    ("/api/v1/system", "system"),
    ("/api/v1/backup", "system"),
    ("/api/v1/audit", "system"),
    # 管控包可能写入的 R33 模块键
    ("/api/v1/villages", "villages"),
    ("/api/v1/households", "households"),
    ("/api/v1/media", "media"),
    ("/api/v1/consumption", "consumption"),
)

# 前缀按长度降序，命中"最长前缀优先"（如 fund-budgets 不会被 funds 抢先）。
_SORTED_ORG_MODULE_RULES = tuple(
    sorted(ORG_MODULE_RULES, key=lambda rule: len(rule[0]), reverse=True)
)


def current_mode() -> str:
    """读取并规范化 ``ORG_MODULE_POLICY_MODE``；非法/空值回退 shadow。

    shadow 与默认值一致：配置笔误只会让"观察模式"继续生效，不会误把全站写接口
    锁死（enforce 必须显式配置）。
    """
    raw = str(getattr(settings, "ORG_MODULE_POLICY_MODE", "") or "").strip().lower()
    if raw in VALID_MODES:
        return raw
    logger.warning(
        "ORG_MODULE_POLICY_MODE=%r 非法（合法值: off/shadow/enforce），回退 %s",
        raw,
        DEFAULT_MODE,
    )
    return DEFAULT_MODE


def resolve_module_key(path: str) -> Optional[str]:
    """按静态表把请求路径解析为 module_key；无匹配返回 None（不拦截）。"""
    normalized = (path or "").rstrip("/") or "/"
    for prefix, module_key in _SORTED_ORG_MODULE_RULES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return module_key
    return None


def _scope_header(scope, header_name: bytes) -> Optional[str]:
    """从 ASGI scope 请求头取首个匹配值（不存在返回 None）。"""
    for name, value in scope.get("headers") or []:
        if name.lower() == header_name:
            return value.decode("latin-1")
    return None


def _bearer_token(scope) -> Optional[str]:
    """从 ASGI scope 的 Authorization 头取 Bearer token（无/格式不符返回 None）。"""
    authorization = _scope_header(scope, b"authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def resolve_user(scope, db):
    """用令牌 sub（username）查当前用户；任何一步失败返回 None（放行）。

    只做"签名有效 + 用户存在"的轻量解析，不校验黑名单 / token_version /
    组织状态 —— 那些由端点认证依赖负责；本层拿不到确定用户就不裁决。
    """
    token = _bearer_token(scope)
    if not token:
        return None
    try:
        from app.core.security import decode_token

        payload = decode_token(token)
    except Exception:
        logger.warning(
            "组织模块策略闸门：令牌解析异常，放行（鉴权由端点负责）", exc_info=True
        )
        return None
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    from app.models.user import User

    return db.query(User).filter(User.username == username).first()


def load_policy_edit_mode(db, organization_id: int, module_key: str) -> Optional[str]:
    """查该组织对该模块的策略 edit_mode；无策略返回 None。"""
    from app.models.org_module_policy import OrgModulePolicy

    policy = (
        db.query(OrgModulePolicy)
        .filter(
            OrgModulePolicy.organization_id == organization_id,
            OrgModulePolicy.module_key == module_key,
        )
        .first()
    )
    if policy is None:
        return None
    return policy.edit_mode


def _open_session():
    """惰性打开数据库会话（便于测试替换，避免模块导入期建连接）。"""
    from app.core.database import SessionLocal

    return SessionLocal()


# ── 策略 TTL 缓存 ───────────────────────────────────────────────────
# 进程内短缓存：key=(organization_id, module_key)，value=(过期时刻, edit_mode|None)。
# 命中时省掉一次 org_module_policies 索引查询；None（无策略）也缓存，避免每次
# 写请求都回查空结果。TTL 5 秒：策略改动最坏 5 秒后生效，写接口可接受。
# 用 threading.Lock 保护（FastAPI 同步端点在线程池并发执行）；临界区只做
# dict 读写与 monotonic，持锁时间可忽略。
CACHE_TTL_SECONDS = 5.0

# 单独取别名：测试可 patch ``gate._monotonic`` 控制 TTL 过期，而不影响进程内
# 其它用到 time.monotonic 的代码（httpx 超时等）。
_monotonic = time.monotonic

_CACHE_MISS = object()
_POLICY_CACHE: Dict[Tuple[int, str], Tuple[float, Optional[str]]] = {}
_CACHE_LOCK = threading.Lock()


def clear_policy_cache() -> None:
    """清空进程内策略缓存（测试隔离 / 运维手动失效用）。"""
    with _CACHE_LOCK:
        _POLICY_CACHE.clear()


def _cache_get(key: Tuple[int, str]) -> Any:
    """取缓存值；未命中或已过期返回 ``_CACHE_MISS``（过期项顺手删除）。"""
    now = _monotonic()
    with _CACHE_LOCK:
        entry = _POLICY_CACHE.get(key)
        if entry is None:
            return _CACHE_MISS
        expires_at, edit_mode = entry
        if expires_at <= now:
            del _POLICY_CACHE[key]
            return _CACHE_MISS
        return edit_mode


def _cache_set(key: Tuple[int, str], edit_mode: Optional[str]) -> None:
    """写缓存；``None``（无策略）也缓存，避免每次都回查空结果。"""
    with _CACHE_LOCK:
        _POLICY_CACHE[key] = (_monotonic() + CACHE_TTL_SECONDS, edit_mode)


def load_policy_edit_mode_cached(db, organization_id: int, module_key: str) -> Optional[str]:
    """带 5 秒 TTL 缓存的策略查询；返回 None 表示该组织该模块无策略。"""
    key = (organization_id, module_key)
    cached = _cache_get(key)
    if cached is not _CACHE_MISS:
        return cached
    edit_mode = load_policy_edit_mode(db, organization_id, module_key)
    _cache_set(key, edit_mode)
    return edit_mode


def evaluate_policy(scope, module_key: str) -> Optional[Tuple[int, str]]:
    """返回 (organization_id, edit_mode) 仅当该组织该模块应被拦截；否则 None。

    异常不在此处吞掉：由中间件统一捕获并放行 + WARNING（保证策略查询失败不会
    让写接口 500）。
    """
    db = _open_session()
    try:
        user = resolve_user(scope, db)
        if user is None:
            return None
        organization_id = getattr(user, "organization_id", None)
        if not organization_id:
            return None
        edit_mode = load_policy_edit_mode_cached(db, organization_id, module_key)
        if edit_mode not in BLOCKED_EDIT_MODES:
            return None
        return organization_id, edit_mode
    finally:
        db.close()


def _send_with_shadow_header(send):
    """包装 ASGI send：在响应起始消息上追加 shadow 观察头。"""

    async def wrapped(message):
        if message.get("type") == "http.response.start":
            headers = list(message.get("headers") or [])
            headers.append((SHADOW_HEADER_NAME, SHADOW_HEADER_VALUE))
            message = {**message, "headers": headers}
        await send(message)

    return wrapped


class OrgModulePolicyGateMiddleware:
    """组织模块策略闸门（纯 ASGI：不读请求体，按需查库，fail-open）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("method", "").upper() not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        mode = current_mode()
        if mode == MODE_OFF:
            # 零开销：在路径映射、缓存与查库之前直接放行。
            await self.app(scope, receive, send)
            return
        module_key = resolve_module_key(scope.get("path", ""))
        if module_key is None:
            await self.app(scope, receive, send)
            return
        try:
            decision = evaluate_policy(scope, module_key)
        except Exception:
            logger.warning(
                "组织模块策略闸门判定异常，已放行: %s %s",
                scope.get("method"),
                scope.get("path"),
                exc_info=True,
            )
            await self.app(scope, receive, send)
            return
        if decision is None:
            await self.app(scope, receive, send)
            return
        organization_id, edit_mode = decision
        logger.warning(
            "组织模块策略闸门[%s] 拦截 %s %s：module=%s organization_id=%s edit_mode=%s",
            mode,
            scope.get("method"),
            scope.get("path"),
            module_key,
            organization_id,
            edit_mode,
        )
        if mode == MODE_ENFORCE:
            await self._send_denied(scope, receive, send, organization_id, module_key, edit_mode)
            return
        await self.app(scope, receive, _send_with_shadow_header(send))

    async def _send_denied(self, scope, receive, send, organization_id: int, module_key: str, edit_mode: str) -> None:
        detail = (
            f"组织（ID={organization_id}）已将模块「{module_key}」设为"
            f"{_EDIT_MODE_LABELS[edit_mode]}，当前写操作被拒绝"
        )
        response = JSONResponse(
            status_code=403,
            content={
                "code": 403,
                "message": detail,
                "detail": detail,
                "success": False,
            },
        )
        await response(scope, receive, send)
