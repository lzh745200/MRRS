"""Targeted coverage tests for validation.py uncovered lines.

Covers:
- _apply_query_condition (lines 385-425): every operator branch of the
  "small friendly" condition query check helper.
- query_check endpoint row loop (lines 484-490): and/or logic over real DB rows.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base
from app.models.supported_village import SupportedVillage
from app.api.v1.validation import QueryCondition, _apply_query_condition

BASE = "/api/v1/validation"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session):
    from app.main import app

    def _get_db():
        yield db_session

    admin = Mock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "admin"
    admin.is_superuser = True
    admin.is_active = True
    admin.permissions_list = ["*"]
    admin.organization_id = 1
    admin.email = "admin@test.com"
    admin.full_name = "Admin"

    async def _get_current_user():
        return admin

    _original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user

    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original


def _cond(field="f", operator="eq", value=None):
    return QueryCondition(field=field, operator=operator, value=value)


def _row(**kwargs):
    return SimpleNamespace(**kwargs)


class TestApplyQueryCondition:
    def test_value_none_empty_op(self):
        assert _apply_query_condition(_cond(operator="empty"), _row(f=None)) is True

    def test_value_none_non_empty_op(self):
        assert _apply_query_condition(_cond(operator="not_empty"), _row(f=None)) is False

    def test_empty_op_empty_string(self):
        assert _apply_query_condition(_cond(operator="empty"), _row(f="")) is True

    def test_empty_op_whitespace(self):
        assert _apply_query_condition(_cond(operator="empty"), _row(f="   ")) is True

    def test_empty_op_non_empty(self):
        assert _apply_query_condition(_cond(operator="empty"), _row(f="x")) is False

    def test_not_empty_op_non_empty(self):
        assert _apply_query_condition(_cond(operator="not_empty"), _row(f=" x ")) is True

    def test_not_empty_op_empty(self):
        assert _apply_query_condition(_cond(operator="not_empty"), _row(f="")) is False

    def test_contains_match(self):
        assert _apply_query_condition(_cond(operator="contains", value="WORLD"), _row(f="Hello World")) is True

    def test_contains_no_match(self):
        assert _apply_query_condition(_cond(operator="contains", value="xyz"), _row(f="hello")) is False

    def test_not_contains_match(self):
        assert _apply_query_condition(_cond(operator="not_contains", value="xyz"), _row(f="hello")) is True

    def test_not_contains_no_match(self):
        assert _apply_query_condition(_cond(operator="not_contains", value="world"), _row(f="hello world")) is False

    def test_eq_numeric(self):
        assert _apply_query_condition(_cond(operator="eq", value="5"), _row(f=5)) is True

    def test_ne_numeric(self):
        assert _apply_query_condition(_cond(operator="ne", value="6"), _row(f=5)) is True

    def test_eq_string_match(self):
        assert _apply_query_condition(_cond(operator="eq", value="abc"), _row(f="abc")) is True

    def test_eq_string_no_match(self):
        assert _apply_query_condition(_cond(operator="eq", value="abd"), _row(f="abc")) is False

    def test_eq_empty_target_falls_to_string(self):
        assert _apply_query_condition(_cond(operator="eq", value=""), _row(f=5)) is False

    def test_gt_true(self):
        assert _apply_query_condition(_cond(operator="gt", value="3"), _row(f=5)) is True

    def test_gt_false(self):
        assert _apply_query_condition(_cond(operator="gt", value="5"), _row(f=5)) is False

    def test_gte_true(self):
        assert _apply_query_condition(_cond(operator="gte", value="5"), _row(f=5)) is True

    def test_lt_true(self):
        assert _apply_query_condition(_cond(operator="lt", value="5"), _row(f=3)) is True

    def test_lte_true(self):
        assert _apply_query_condition(_cond(operator="lte", value="5"), _row(f=5)) is True

    def test_gt_non_numeric(self):
        assert _apply_query_condition(_cond(operator="gt", value="1"), _row(f="abc")) is False

    def test_gt_empty_target(self):
        assert _apply_query_condition(_cond(operator="gt", value=""), _row(f=5)) is False

    def test_unknown_operator(self):
        assert _apply_query_condition(_cond(operator="weird", value="x"), _row(f=5)) is False


class TestQueryCheckRowLoop:
    def _seed(self, db_session):
        db_session.add_all([
            SupportedVillage(id=1, village_name="JiaVillage", county="Hezhang",
                             transition_fund_military_total=100.0, is_active=True),
            SupportedVillage(id=2, village_name="YiVillage", county="Weining",
                             transition_fund_military_total=50.0, is_active=True),
        ])
        db_session.commit()

    def test_and_logic_matches_rows(self, client, db_session):
        self._seed(db_session)
        resp = client.post(
            f"{BASE}/query-check",
            json={
                "module": "village",
                "logic": "and",
                "conditions": [
                    {"field": "county", "operator": "eq", "value": "Hezhang"},
                    {"field": "transition_fund_military_total", "operator": "gte", "value": "80"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert data["matched"] == 1
        assert data["unmatched"] == 1
        assert len(data["results"]) == 2

    def test_or_logic_matches_rows(self, client, db_session):
        self._seed(db_session)
        resp = client.post(
            f"{BASE}/query-check",
            json={
                "module": "village",
                "logic": "or",
                "conditions": [
                    {"field": "county", "operator": "eq", "value": "Hezhang"},
                    {"field": "county", "operator": "eq", "value": "Nonexistent"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert data["matched"] == 1
