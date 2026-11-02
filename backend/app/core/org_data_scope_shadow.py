"""R48 组织级 data_scope 影子观测（默认 off，绝不改变查询结果）。

为什么存在：R33 授权矩阵管的是「菜单与写接口」，数据范围仍由
``core/data_permission`` 的角色推断（super_admin→all、admin→本组织、其余→仅本人）。
要在「组织树 + 上下级」部署里讨论组织级数据范围，先需要一个**不改变行为**的观测层：
记录「按组织配置/层级推导出的范围」与「当前角色实际范围」的差异。

模式（``ORG_DATA_SCOPE_MODE``）：
- ``off``（默认）：本模块立即返回 None，零查询、零日志；
- ``shadow``：只比较并记 WARNING（同一 user+org+scope 组合只记一次），
  返回值供自检/测试使用，调用方**不得**据此过滤数据。

生效范围永远不变：``get_data_scope`` 的返回值与改造前逐字节一致。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

MODE_OFF = "off"
MODE_SHADOW = "shadow"

#: 组织级范围 → 宽窄排序（all 最宽）
SCOPE_RANK = {"all": 3, "subtree": 2, "self": 1}

#: 角色范围（DataScope.value）→ 宽窄排序
ROLE_RANK = {"all": 3, "own_dept": 2, "own": 1}

_VALID_SCOPES = frozenset(SCOPE_RANK)

#: 已告警组合（有界，触顶清空），避免每个请求重复刷日志
_LOGGED: dict = {}
_MAX_LOGGED = 512


def current_mode() -> str:
    """读取并归一化模式；未知值按 off（影子层不允许意外开启）。"""
    raw = str(getattr(settings, "ORG_DATA_SCOPE_MODE", MODE_OFF) or MODE_OFF).lower()
    return MODE_SHADOW if raw == MODE_SHADOW else MODE_OFF


def derived_org_scope(org: Any) -> Optional[str]:
    """组织级范围：显式列优先，否则按层级推导（1/2 省市级→subtree，3 县级→self）。"""
    if org is None:
        return None
    explicit = getattr(org, "data_scope", None)
    if explicit in _VALID_SCOPES:
        return explicit
    level = str(getattr(org, "level", "") or "")
    if level in ("1", "2"):
        return "subtree"
    if level == "3":
        return "self"
    return None


def observe_org_data_scope(user: Any, role_scope: str) -> Optional[dict]:
    """影子比较；off / 不可判定返回 None。

    Returns:
        ``{org_id, org_scope, role_scope, would_narrow}``；``would_narrow=True``
        表示组织级范围比当前角色范围更窄（即若将来 enforce，会收窄可见数据）。
    """
    if current_mode() != MODE_SHADOW:
        return None
    try:
        org = getattr(user, "organization", None)
        if org is None:
            return None
        org_scope = derived_org_scope(org)
        if org_scope is None:
            return None
        role_rank = ROLE_RANK.get(str(role_scope))
        if role_rank is None:
            return None

        result = {
            "org_id": getattr(org, "id", None),
            "org_scope": org_scope,
            "role_scope": str(role_scope),
            "would_narrow": SCOPE_RANK[org_scope] < role_rank,
        }
        if result["would_narrow"]:
            _warn_once(user, result)
        return result
    except Exception as exc:  # noqa: BLE001 - 影子观测绝不影响主流程
        logger.debug("R48 组织级 data_scope 影子观测失败: %s", exc)
        return None


def _warn_once(user: Any, result: dict) -> None:
    key = (
        getattr(user, "id", None),
        result["org_id"],
        result["role_scope"],
        result["org_scope"],
    )
    if key in _LOGGED:
        return
    if len(_LOGGED) >= _MAX_LOGGED:
        _LOGGED.clear()
    _LOGGED[key] = True
    logger.warning(
        "R48 组织级 data_scope 影子观测: user=%s org=%s 角色范围=%s 组织范围=%s"
        "（shadow 模式，未改变查询结果）",
        key[0],
        key[1],
        key[2],
        key[3],
    )
