"""写接口授权守卫（R33）。

## 为什么不用 `Depends(get_current_user)`

`get_current_user` 缺凭证即 401。挂在 app 级依赖上会让登录、健康检查这些**公开路由**
全部 401。因此本守卫**不参与依赖图**，而是在函数体内惰性解析用户：

- `mode == "off"`（默认）→ 立即返回，**零开销、零行为变化**；
- 只在写方法 + 非豁免路径 + 能解析出用户 + 单位已下发授权时，才真正裁决。

解析失败（无 token / token 无效 / 用户不存在）一律**放行** —— 本守卫是"额外收窄"，
不是认证本身；真正的认证仍由路由的 `get_current_user` 负责，它会正确返回 401。

## 三种模式

| 模式 | 行为 |
|---|---|
| `off` | 完全关闭（默认） |
| `shadow` | 只记日志不拦截，用于上线前收集"将被拦"清单 |
| `enforce` | 越权写请求返回 403 |

切换只需设环境变量 `GRANT_GUARD_MODE=shadow|enforce`，无需改代码。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from app.core.write_route_map import is_exempt, is_write_method, resolve_module

logger = logging.getLogger(__name__)

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_ENFORCE = "enforce"
VALID_MODES = frozenset({MODE_OFF, MODE_SHADOW, MODE_ENFORCE})

_BEARER_PREFIX = "bearer "


def current_mode() -> str:
    """读当前模式（非法值按 off 处理，避免配置写错就把全站写接口锁死）。"""
    from app.core.config import settings

    raw = str(getattr(settings, "GRANT_GUARD_MODE", MODE_OFF) or MODE_OFF).strip().lower()
    return raw if raw in VALID_MODES else MODE_OFF


def _decode(token: str):
    """解 token（独立成函数，便于测试替换且不受跨模块 patch 影响）。"""
    from app.core.security import decode_token

    return decode_token(token)


def resolve_user(request: Request, db):
    """从 Authorization 头解析用户；任何一步失败返回 None（放行）。

    只做"够用"的校验（token 可解、sub 存在、用户存在）。吊销/类型/2FA 中间态等严格
    校验由路由的 `get_current_user` 负责 —— 本函数放宽只会让守卫少拦，不会多放行。
    """
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith(_BEARER_PREFIX):
        return None
    token = header[len(_BEARER_PREFIX):].strip()
    if not token:
        return None

    payload = _decode(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None

    from app.models.user import User

    return db.query(User).filter(User.username == username).first()


def _deny(mode: str, request: Request, reason: str, module: Optional[str]) -> None:
    """enforce 抛 403；shadow 只记日志。"""
    detail = "无该模块的录入权限" if module else "该接口未配置模块授权映射"
    logger.warning(
        "R33 授权守卫[%s] %s %s module=%s reason=%s",
        mode,
        request.method,
        request.url.path,
        module or "-",
        reason,
    )
    if mode == MODE_ENFORCE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


async def enforce_write_grant(request: Request) -> None:
    """app 级依赖：按单位授权矩阵收窄写接口。"""
    mode = current_mode()
    if mode == MODE_OFF:
        return
    if not is_write_method(request.method):
        return

    path = request.url.path
    if is_exempt(path):
        return

    # 只有确定要裁决时才建会话（off / 读方法 / 豁免路径都不会走到这里）
    from app.core.database import SessionLocal
    from app.services.effective_grant_service import get_grant_matrix

    db = SessionLocal()
    try:
        user = resolve_user(request, db)
        if user is None:
            return
        matrix = get_grant_matrix(db, user)
        if not matrix.active:
            # 单位未下发授权 → legacy，行为与升级前一致
            return

        module = resolve_module(path)
        if module is None:
            _deny(mode, request, "unmapped", None)
            return
        if not matrix.can_edit(module):
            _deny(mode, request, "level=%s" % matrix.level(module), module)
    finally:
        db.close()
