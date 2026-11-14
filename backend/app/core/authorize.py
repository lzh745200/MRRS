"""授权策略门面（off / shadow / enforce）。

现有权限判定分散在 `is_admin`、`is_superuser`、`data_permission` 与各处
`require_*` 中。本模块提供一个统一入口，但**不重写角色模型**：

- ``off``（默认）：完全沿用调用方传入的 legacy_allowed，零行为变化；
- ``shadow``：计算新策略并与 legacy 比较，只记录差异，仍返回 legacy；
- ``enforce``：返回新策略结果。

当前只收口管理员/超管两个动作；后续按端点逐项增加 action，避免一次性
替换所有调用点导致军审口径下的 403 行为漂移。模式由
``AUTHORIZE_MODE`` 环境变量控制。
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.core.permission_utils import is_admin, is_superuser

logger = logging.getLogger(__name__)

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_ENFORCE = "enforce"

_MODE_ALIASES = {
    "": MODE_OFF,
    "0": MODE_OFF,
    "false": MODE_OFF,
    "off": MODE_OFF,
    "shadow": MODE_SHADOW,
    "1": MODE_ENFORCE,
    "true": MODE_ENFORCE,
    "enforce": MODE_ENFORCE,
}


def current_mode() -> str:
    raw = str(getattr(settings, "AUTHORIZE_MODE", MODE_OFF) or MODE_OFF).strip().lower()
    return _MODE_ALIASES.get(raw, MODE_OFF)


def _policy_allowed(actor: Any, action: str) -> bool:
    if action in ("admin", "system.manage"):
        return is_admin(actor)
    if action in ("superuser", "system.superuser"):
        return is_superuser(actor)
    # 未登记的动作一律按 legacy 处理，避免门面自身放大权限。
    return True


def authorize(
    actor: Any,
    action: str,
    resource: str = "system",
    scope: Any = None,
    *,
    legacy_allowed: bool,
) -> bool:
    """返回最终授权结果；shadow 模式下只记录差异，不改变 legacy 行为。"""
    mode = current_mode()
    if mode == MODE_OFF:
        return legacy_allowed
    allowed = _policy_allowed(actor, action)
    if mode == MODE_SHADOW:
        if allowed != legacy_allowed:
            logger.warning(
                "授权 shadow 差异: user=%s action=%s resource=%s scope=%s "
                "legacy=%s policy=%s（未改变结果）",
                getattr(actor, "id", None),
                action,
                resource,
                scope,
                legacy_allowed,
                allowed,
            )
        return legacy_allowed
    return allowed
