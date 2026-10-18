"""W22（v1.14.0）：走访记录挂户 + households.last_visit_date 回写。

覆盖：
- 创建走访带 household_id → 回写该户最近走访日期；
- 多次走访取最大 visit_date；更新/删除走访后重算；
- 改挂另一户时旧户重算；
- 户不存在 404 / 跨组织 403（非管理员）；
- 不传 household_id 时不影响任何户；to_dict 暴露 household_id。
"""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


def _user(**kw):
    base = dict(id=7, username="admin7", role="admin", organization_id=1, data_scope="all")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def api_client():
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app
    from app.models import Base
    from app.models.household import Household  # noqa: F401
    from app.models.organization import Organization  # noqa: F401
    from app.models.pairing import PairingRecord, VisitRecord  # noqa: F401
    from app.models.supported_village import SupportedVillage  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.work_log import WorkLog  # noqa: F401
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    state = {"user": _user()}

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, session, state
    finally:
        app.dependency_overrides = original_overrides
        session.close()
        engine.dispose()


def _mk_village(db, name="幸福村", org_id=1):
    from app.models.supported_village import SupportedVillage

    v = SupportedVillage(village_name=name, organization_id=org_id, created_by=7, is_active=True)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _mk_household(db, village_id, name="张三", org_id=1, last_visit=None):
    from app.models.household import Household

    h = Household(
        supported_village_id=village_id,
        household_name=name,
        household_type="monitor",
        risk_level="medium",
        organization_id=org_id,
        created_by=7,
        last_visit_date=last_visit,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


def _mk_pairing(db, org_id=1):
    from app.models.pairing import PairingRecord

    p = PairingRecord(
        subject_type="unit",
        subject_name="某单位",
        partner_type="village",
        title="对口帮扶",
        status="active",
        organization_id=org_id,
        created_by=7,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _create_visit(client, pairing_id, visit_date, household_id=None, **kw):
    payload = {"visit_date": visit_date.isoformat(), "visitors": "甲", **kw}
    if household_id is not None:
        payload["household_id"] = household_id
    return client.post(f"/api/v1/pairings/{pairing_id}/visits", json=payload)


def _household_last_visit(db, household_id):
    from app.models.household import Household

    db.expire_all()
    return db.query(Household).filter(Household.id == household_id).one().last_visit_date


class TestVisitHouseholdLink:
    def test_create_visit_links_household_and_writes_last_visit(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        household = _mk_household(db, village.id)
        pairing = _mk_pairing(db)

        resp = _create_visit(client, pairing.id, date(2026, 3, 1), household.id)
        assert resp.status_code == 200
        assert resp.json()["data"]["household_id"] == household.id
        assert _household_last_visit(db, household.id) == date(2026, 3, 1)

    def test_last_visit_date_keeps_max_of_multiple_visits(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        household = _mk_household(db, village.id)
        pairing = _mk_pairing(db)

        _create_visit(client, pairing.id, date(2026, 5, 1), household.id)
        _create_visit(client, pairing.id, date(2026, 3, 1), household.id)
        assert _household_last_visit(db, household.id) == date(2026, 5, 1)

    def test_update_visit_date_recomputes_last_visit(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        household = _mk_household(db, village.id)
        pairing = _mk_pairing(db)
        created = _create_visit(client, pairing.id, date(2026, 3, 1), household.id).json()["data"]
        assert _household_last_visit(db, household.id) == date(2026, 3, 1)

        _create_visit(client, pairing.id, date(2026, 6, 1), household.id)
        resp = client.put(
            f"/api/v1/pairings/{pairing.id}/visits/{created['id']}",
            json={"visit_date": "2026-07-01"},
        )
        assert resp.status_code == 200
        assert _household_last_visit(db, household.id) == date(2026, 7, 1)

    def test_move_visit_to_another_household_recomputes_both(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        h1 = _mk_household(db, village.id, name="甲户")
        h2 = _mk_household(db, village.id, name="乙户")
        pairing = _mk_pairing(db)

        visit = _create_visit(client, pairing.id, date(2026, 3, 1), h1.id).json()["data"]
        assert _household_last_visit(db, h1.id) == date(2026, 3, 1)

        resp = client.put(
            f"/api/v1/pairings/{pairing.id}/visits/{visit['id']}",
            json={"household_id": h2.id},
        )
        assert resp.status_code == 200
        assert _household_last_visit(db, h1.id) is None
        assert _household_last_visit(db, h2.id) == date(2026, 3, 1)

    def test_delete_visit_recomputes_last_visit(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        household = _mk_household(db, village.id)
        pairing = _mk_pairing(db)
        first = _create_visit(client, pairing.id, date(2026, 3, 1), household.id).json()["data"]
        _create_visit(client, pairing.id, date(2026, 8, 1), household.id)
        assert _household_last_visit(db, household.id) == date(2026, 8, 1)

        resp = client.delete(f"/api/v1/pairings/{pairing.id}/visits/{first['id']}")
        assert resp.status_code == 200
        assert _household_last_visit(db, household.id) == date(2026, 8, 1)

        latest = (
            db.query(
                __import__("app.models.pairing", fromlist=["VisitRecord"]).VisitRecord
            )
            .filter_by(household_id=household.id, is_active=True)
            .one()
        )
        client.delete(f"/api/v1/pairings/{pairing.id}/visits/{latest.id}")
        assert _household_last_visit(db, household.id) is None

    def test_unknown_household_returns_404(self, api_client):
        client, db, _state = api_client
        pairing = _mk_pairing(db)
        resp = _create_visit(client, pairing.id, date(2026, 3, 1), 99999)
        assert resp.status_code == 404

    def test_cross_org_household_forbidden_for_non_admin(self, api_client):
        client, db, state = api_client
        village = _mk_village(db, name="别的村", org_id=2)
        household = _mk_household(db, village.id, org_id=2)
        pairing = _mk_pairing(db)
        state["user"] = _user(id=8, username="user8", role="user", data_scope="own")
        resp = _create_visit(client, pairing.id, date(2026, 3, 1), household.id)
        assert resp.status_code == 403

    def test_absent_household_id_does_not_touch_any_household(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        household = _mk_household(db, village.id)
        pairing = _mk_pairing(db)
        resp = _create_visit(client, pairing.id, date(2026, 3, 1))
        assert resp.status_code == 200
        assert resp.json()["data"]["household_id"] is None
        assert _household_last_visit(db, household.id) is None

    def test_non_admin_same_org_household_allowed(self, api_client):
        """非管理员 + 同组织户：_resolve_household 的放行分支（W22 覆盖率缺口补齐）。"""
        client, db, state = api_client
        village = _mk_village(db, name="本村", org_id=1)
        household = _mk_household(db, village.id, org_id=1)
        pairing = _mk_pairing(db)
        state["user"] = _user(id=8, username="user8", role="user", data_scope="own")
        resp = _create_visit(client, pairing.id, date(2026, 3, 2), household.id)
        assert resp.status_code == 200
        assert _household_last_visit(db, household.id) == date(2026, 3, 2)

    def test_sync_last_visit_ignores_missing_household(self, api_client):
        """_sync_household_last_visit 的 household 不存在分支（删除后残留引用防御）。"""
        from app.api.v1.pairing import _sync_household_last_visit

        _client, db, _state = api_client
        _sync_household_last_visit(db, 99999)  # 不存在：不抛错、不写库
        _sync_household_last_visit(db, None)  # 未挂户：直接返回
