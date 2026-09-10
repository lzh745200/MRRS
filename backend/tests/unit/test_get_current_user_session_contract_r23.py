"""R23 回归：``get_current_user`` 的会话契约（注入复用 vs 直调自建）。

背景缺陷
--------
P1-2 将 ``get_current_user`` 由"自建 ``SessionLocal()``"改为
``db: Session = Depends(get_db)`` 注入会话后，两个**直接调用**路径不会发生注入：

1. ``app/api/v1/system/backup.py::_jwt_user_from_request`` ——
   Electron 内部通道之外的真实 JWT 备份请求；
2. 单元测试直调 ``get_current_user(credentials=...)``。

此时 ``db`` 退化为 ``Depends(get_db)`` 默认哨兵对象，``db.query`` 抛
``AttributeError: 'Depends' object has no attribute 'query'``，使备份接口对
合法 JWT 用户直接 500。

修复后语义
----------
- ``db`` 为真实 ``Session`` 实例（DI 注入）→ 复用，**不关闭**（生命周期归 ``get_db``）。
- ``db`` 非真实 ``Session``（未注入）→ 自建 ``SessionLocal()``，``finally`` 关闭。

本文件锁定上述两点，防止再次回归。全量套件此前仅 3 例直调测试失败，正是
因为缺少对备份直调路径的覆盖，故此处补充生产路径断言。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.core import security as sec


async def test_direct_call_self_manages_session(monkeypatch):
    """未注入 db：函数自建会话，查询后关闭，返回用户。"""
    user = SimpleNamespace(id=1, username="admin", token_version_safe=0)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    session_local = MagicMock(return_value=db)
    monkeypatch.setattr("app.core.database.SessionLocal", session_local)
    monkeypatch.setattr(
        sec, "decode_token", MagicMock(return_value={"sub": "admin", "type": "access"})
    )

    result = await sec.get_current_user(credentials=SimpleNamespace(credentials="tok"))

    assert result is user
    session_local.assert_called_once()
    db.close.assert_called_once()


async def test_injected_session_is_reused_and_not_closed(monkeypatch):
    """注入真实 Session：复用且不关闭，也不得回退自建会话。"""
    user = SimpleNamespace(id=2, username="admin", token_version_safe=0)
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = user
    monkeypatch.setattr(
        "app.core.database.SessionLocal",
        MagicMock(side_effect=AssertionError("注入路径不应自建会话")),
    )
    monkeypatch.setattr(
        sec, "decode_token", MagicMock(return_value={"sub": "admin", "type": "access"})
    )

    result = await sec.get_current_user(
        credentials=SimpleNamespace(credentials="tok"), db=db
    )

    assert result is user
    db.close.assert_not_called()


async def test_backup_jwt_helper_direct_call_without_injection(monkeypatch):
    """生产路径：备份内部通道 helper 直调 get_current_user（无注入）必须可用。"""
    from app.api.v1.system import backup as backup_mod

    user = SimpleNamespace(id=3, username="admin", token_version_safe=0)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    monkeypatch.setattr("app.core.database.SessionLocal", MagicMock(return_value=db))
    monkeypatch.setattr(
        sec, "decode_token", MagicMock(return_value={"sub": "admin", "type": "access"})
    )

    request = MagicMock()
    request.app = None  # 无 dependency_overrides → 走直调分支
    request.headers = {"Authorization": "Bearer faketoken"}

    result = await backup_mod._jwt_user_from_request(request)

    assert result is user
    db.close.assert_called_once()
