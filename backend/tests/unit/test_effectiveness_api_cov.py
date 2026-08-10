"""app.api.v1.effectiveness 覆盖率攻坚测试

覆盖 4 个端点全部分支：
- POST /evaluate：非超管403 / service error→400 / 成功
- GET /report/{vid}：村不存在404 / 报告不存在404 / 成功
- GET /compare/{vid}：村不存在404 / service error→400 / 成功
- GET /rankings：成功（排名列表组装）
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.deps import get_current_active_user, get_db

BASE = "/api/v1/effectiveness"


@pytest.fixture
def client():
    from app.main import app

    original = app.dependency_overrides.copy()
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=1, username="admin", is_superuser=True
    )
    # 数据权限过滤直通（单测不涉权限矩阵）——端点已改用 apply_scope_filter
    with patch("app.api.v1.effectiveness.apply_scope_filter", side_effect=lambda q, *a, **kw: q):
        yield TestClient(app, raise_server_exceptions=False), db
    app.dependency_overrides = original


def _non_superuser(c):
    c.app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=2, username="officer", is_superuser=False
    )


class TestEvaluate:
    def test_forbidden_for_non_superuser(self, client):
        c, _ = client
        _non_superuser(c)
        resp = c.post(f"{BASE}/evaluate", json={"village_id": 1, "year": 2026})
        assert resp.status_code == 403

    def test_service_error_400(self, client):
        c, _ = client
        with patch("app.api.v1.effectiveness.EffectivenessService.evaluate_village", return_value={"error": "村不存在"}):
            resp = c.post(f"{BASE}/evaluate", json={"village_id": 1, "year": 2026})
        assert resp.status_code == 400

    def test_success(self, client):
        c, _ = client
        with patch("app.api.v1.effectiveness.EffectivenessService.evaluate_village", return_value={"score": 88}):
            resp = c.post(f"{BASE}/evaluate", json={"village_id": 1, "year": 2026})
        assert resp.status_code == 200
        assert resp.json()["score"] == 88


class TestGetReport:
    def test_village_not_found_404(self, client):
        c, db = client
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None
        db.query.return_value = q
        assert c.get(f"{BASE}/report/1?year=2026").status_code == 404

    def test_report_not_found_404(self, client):
        c, db = client
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = SimpleNamespace(id=1)
        db.query.return_value = q
        with patch("app.api.v1.effectiveness.EffectivenessService.get_evaluation_report", return_value=None):
            assert c.get(f"{BASE}/report/1?year=2026").status_code == 404

    def test_report_success(self, client):
        c, db = client
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = SimpleNamespace(id=1)
        db.query.return_value = q
        with patch(
            "app.api.v1.effectiveness.EffectivenessService.get_evaluation_report",
            return_value={"total_score": 90},
        ):
            resp = c.get(f"{BASE}/report/1?year=2026")
        assert resp.status_code == 200
        assert resp.json()["total_score"] == 90


class TestCompare:
    def _mk_village(self, db):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = SimpleNamespace(id=1)
        db.query.return_value = q

    def test_village_not_found_404(self, client):
        c, db = client
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None
        db.query.return_value = q
        assert c.get(f"{BASE}/compare/1?year1=2025&year2=2026").status_code == 404

    def test_service_error_400(self, client):
        c, db = client
        self._mk_village(db)
        with patch("app.api.v1.effectiveness.EffectivenessService.compare_evaluations", return_value={"error": "缺数据"}):
            assert c.get(f"{BASE}/compare/1?year1=2025&year2=2026").status_code == 400

    def test_success(self, client):
        c, db = client
        self._mk_village(db)
        with patch(
            "app.api.v1.effectiveness.EffectivenessService.compare_evaluations",
            return_value={"delta": 5},
        ):
            resp = c.get(f"{BASE}/compare/1?year1=2025&year2=2026")
        assert resp.status_code == 200
        assert resp.json()["delta"] == 5


class TestRankings:
    def test_rankings_success(self, client):
        c, db = client
        ev = SimpleNamespace(
            rank=1, village_id=10, total_score=95.5, grade="A",
            economic_score=90.0, social_score=92.0, ecological_score=88.0,
        )
        q = MagicMock()
        q.join.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.limit.return_value = q
        q.all.return_value = [(ev, "幸福村")]
        db.query.return_value = q

        resp = c.get(f"{BASE}/rankings?year=2026&limit=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["year"] == 2026
        assert data["rankings"][0]["village_name"] == "幸福村"
        assert data["rankings"][0]["grade"] == "A"
