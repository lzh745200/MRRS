"""组织模块写权限的共享规则（R48 阶段 4：闸门收敛）。

本模块只放**常量与纯函数**，不查库、不依赖 FastAPI，供两个执行点共用：

1. :mod:`app.middleware.org_module_policy_gate` —— 管控包下发的
   ``org_module_policies``（早期 ASGI 拦截 + shadow 观察头）；
2. :mod:`app.core.grant_guard` —— R33 授权矩阵；矩阵 active 时同一写请求
   还会尊重 ``org_module_policies``（更严者生效），避免两个闸门各判一套。

边界：``org_grants``（R33 矩阵）与 ``org_module_policies``（模块开关）仍是
两类独立配置——前者回答“这个单位能不能录入该模块”，后者回答“这个模块在
该单位是否只读/禁用”；本模块只统一“什么值算禁止”和“模式如何归一化”，
不合并两张表。
"""

from __future__ import annotations

from typing import Optional

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_ENFORCE = "enforce"

VALID_MODES = frozenset({MODE_OFF, MODE_SHADOW, MODE_ENFORCE})

#: 中间件默认 shadow（上线观察期）；守卫默认 off（见各自 settings）。
DEFAULT_GATE_MODE = MODE_SHADOW

#: 只有这两种 edit_mode 会收窄写权限；full_edit / 未知值均放行（fail-open）。
BLOCKED_EDIT_MODES = frozenset({"read_only", "disabled"})

_EDIT_MODE_LABELS = {"read_only": "只读", "disabled": "禁用"}


def normalize_mode(raw: Optional[str], default: str = DEFAULT_GATE_MODE) -> str:
    """归一化模式：合法值原样返回，其余（含 None/空/未知）回退 ``default``。"""
    text = str(raw or "").strip().lower()
    return text if text in VALID_MODES else default


def is_blocked_edit_mode(edit_mode: Optional[str]) -> bool:
    """``read_only`` / ``disabled`` → True；``None`` / ``full_edit`` / 未知 → False。"""
    return edit_mode in BLOCKED_EDIT_MODES


def edit_mode_label(edit_mode: Optional[str]) -> str:
    """给用户看的 edit_mode 中文标签（未知值原样返回）。"""
    return _EDIT_MODE_LABELS.get(str(edit_mode or ""), str(edit_mode or ""))
