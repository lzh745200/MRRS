"""审计链纯函数测试（不依赖数据库）。"""
from types import SimpleNamespace

from app.core.audit_chain import compute_payload_hash, payload_dict, verify_chain


def _row(row_id, prev, **overrides):
    base = dict(
        id=row_id,
        user_id=1,
        username="admin",
        action="login",
        resource_type="user",
        resource_id="1",
        new_value={"ok": True},
        status="success",
        level="info",
        prev_hash=prev,
    )
    base.update(overrides)
    row = SimpleNamespace(**base)
    row.payload_hash = compute_payload_hash(row)
    return row


def test_payload_dict_and_hash_are_stable():
    row = _row(1, None)
    assert set(payload_dict(row)) == {
        "user_id", "username", "action", "resource_type",
        "resource_id", "new_value", "status", "level",
    }
    assert compute_payload_hash(row) == compute_payload_hash(row)


def test_valid_chain_passes():
    first = _row(1, None)
    second = _row(2, first.payload_hash, action="logout")
    ok, broken = verify_chain([first, second])
    assert ok is True
    assert broken is None


def test_tampered_row_fails():
    first = _row(1, None)
    second = _row(2, first.payload_hash)
    second.new_value = {"ok": False}
    ok, broken = verify_chain([first, second])
    assert ok is False
    assert broken == 2


def test_wrong_prev_hash_fails():
    first = _row(1, None)
    second = _row(2, "deadbeef")
    ok, broken = verify_chain([first, second])
    assert ok is False
    assert broken == 2


def test_persist_chain_when_enabled(monkeypatch):
    from unittest.mock import MagicMock

    from app.models.audit import AuditAction
    from app.utils.audit_logger import AuditLogger

    session = MagicMock()
    session.query.return_value.order_by.return_value.first.return_value = ("prevhash",)
    monkeypatch.setattr("app.core.database.SessionLocal", lambda: session)
    monkeypatch.setattr("app.core.config.settings.AUDIT_CHAIN_ENABLED", True)

    AuditLogger._persist_to_db(
        {"action": "login", "username": "u", "user_id": 1},
        AuditAction.LOGIN,
    )
    added = session.add.call_args_list[0][0][0]
    assert added.prev_hash == "prevhash"
    assert len(added.payload_hash) == 64
