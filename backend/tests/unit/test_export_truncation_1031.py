"""短期项 1（2026-11-01 审计报告）：导出被上限截断时必须显式提示。

历史行为：`/export/*` 五端点最多导出 10000 行，超出部分被 `.limit()` 静默丢弃，
文件照常返回、页面不报错 —— 用户以为导出完整。现改为响应头告知
（X-Export-Truncated / Total / Returned / Limit），前端据此弹提示。
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def test_no_headers_when_not_truncated():
    from app.api.v1.import_export.export import _truncation_headers

    assert _truncation_headers(10, 10) == {}
    assert _truncation_headers(9, 10) == {}


def test_headers_when_truncated():
    from app.api.v1.import_export.export import MAX_EXPORT_ROWS, _truncation_headers

    headers = _truncation_headers(12000, 3)
    assert headers["X-Export-Truncated"] == "true"
    assert headers["X-Export-Total"] == "12000"
    assert headers["X-Export-Returned"] == "3"
    assert headers["X-Export-Limit"] == str(MAX_EXPORT_ROWS)


def test_mocked_total_does_not_break_export():
    """query 被整体 mock 时 `.count()` 不是 int —— 不能为加提示把成功导出变成 500。"""
    from app.api.v1.import_export.export import _truncation_headers

    assert _truncation_headers(MagicMock(), 3) == {}
    assert _truncation_headers(None, 3) == {}


@pytest.fixture
def client_and_query():
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    db = MagicMock(name="db")
    query = MagicMock(name="query")
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = []
    db.query.return_value = query

    user = MagicMock(name="user")
    user.id = 1
    user.role = "super_admin"
    user.is_superuser = True
    user.organization_id = None

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, query
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_export_endpoint_returns_truncation_headers(client_and_query):
    """端到端：总数 12000 > 返回 0 行 → 响应头带提示（csv 路径，避开 xlsx 服务依赖）。"""
    client, query = client_and_query
    query.count.return_value = 12000

    resp = client.get("/api/v1/export/villages", params={"format": "csv"})

    assert resp.status_code == 200
    assert resp.headers.get("x-export-truncated") == "true"
    assert resp.headers.get("x-export-total") == "12000"
    assert resp.headers.get("x-export-returned") == "0"
