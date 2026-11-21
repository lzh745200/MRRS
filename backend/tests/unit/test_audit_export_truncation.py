"""审计日志导出截断提示回归（2026-11-21 审计 P1）。

旧实现 `query.limit(5000)` + `total=len(items)`，导出 5000 条时看起来"刚好导完"，
实际漏掉的可能有十几万条，且没有任何提示 —— 等保取证场景属实打实的数据完整性问题。
"""

from unittest import mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.unit

BASE = "/api/v1/system/audit"


@pytest.fixture
def db_client():
    """TestClient + 真实内存库（端点直接走 db.query，mock 不了 count/limit 语义）。"""
    from fastapi.testclient import TestClient

    import app.core.database as _db_module
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    _orig_engine = _db_module.engine
    _orig_session = _db_module.SessionLocal
    _db_module.engine = engine
    _db_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: mock.MagicMock(
        id=1, username="admin", role="admin", is_superuser=True
    )
    try:
        yield TestClient(app, raise_server_exceptions=False), session
    finally:
        app.dependency_overrides = original_overrides
        _db_module.engine = _orig_engine
        _db_module.SessionLocal = _orig_session
        session.close()
        engine.dispose()


def _seed(session, n=2):
    from app.models.audit import AuditLog

    for i in range(1, n + 1):
        session.add(
            AuditLog(id=i, action="create", username="admin", resource_type="user", status="success")
        )
    session.commit()


def test_csv_export_sets_truncation_headers(db_client, monkeypatch):
    client, session = db_client
    _seed(session, 2)
    import app.api.v1.system.audit as audit_mod

    monkeypatch.setattr(audit_mod, "AUDIT_EXPORT_LIMIT", 1, raising=True)

    resp = client.get(f"{BASE}/logs/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["X-Export-Truncated"] == "true"
    assert resp.headers["X-Export-Total"] == "2"
    assert resp.headers["X-Export-Returned"] == "1"
    assert resp.headers["X-Export-Limit"] == "1"


def test_json_export_total_is_real_count(db_client, monkeypatch):
    client, session = db_client
    _seed(session, 2)
    import app.api.v1.system.audit as audit_mod

    monkeypatch.setattr(audit_mod, "AUDIT_EXPORT_LIMIT", 1, raising=True)

    resp = client.get(f"{BASE}/logs/export", params={"format": "json"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2          # 真实总数，而不是截断后的 1
    assert len(data["items"]) == 1     # 实际返回被上限截断


def test_export_not_truncated_has_no_headers(db_client):
    client, session = db_client
    _seed(session, 1)

    resp = client.get(f"{BASE}/logs/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert "X-Export-Truncated" not in resp.headers
