"""结对帮扶与走访台账 API（w17-002）。

覆盖：CRUD 契约（envelope/ok_list）、字段组合校验、对象可达性（404/403）、
数据域（列表隔离 / 点查 403 / fail-closed）、软删与 include_deleted 降级、
走访记录（继承组织域、排序、独立软删）、统计口径。
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
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base
    from app.models.user import User  # noqa: F401  FK 目标表注册
    from app.models.organization import Organization  # noqa: F401
    from app.models.supported_village import SupportedVillage  # noqa: F401
    from app.models.school import School  # noqa: F401
    from app.models.pairing import PairingRecord, VisitRecord  # noqa: F401
    from app.models.work_log import WorkLog  # noqa: F401

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


def _as(state, **kw):
    state["user"] = _user(**kw)


def _mk_village(db, name="幸福村", org_id=1, created_by=7, active=True):
    from app.models.supported_village import SupportedVillage

    v = SupportedVillage(
        village_name=name, organization_id=org_id, created_by=created_by, is_active=active
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _mk_school(db, name="希望小学", org_id=1, created_by=7, active=True):
    from app.models.school import School

    s = School(name=name, organization_id=org_id, created_by=created_by, is_active=active)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _mk_pairing(db, **kw):
    from app.models.pairing import PairingRecord

    base = dict(
        subject_type="unit",
        subject_name="某单位",
        partner_type="village",
        title="对口帮扶",
        status="active",
        organization_id=1,
        created_by=7,
    )
    base.update(kw)
    p = PairingRecord(**base)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _mk_visit(db, pairing_id, **kw):
    from app.models.pairing import VisitRecord

    base = dict(
        pairing_id=pairing_id,
        visit_date=date(2026, 3, 1),
        visitors="甲",
        organization_id=1,
        created_by=7,
    )
    base.update(kw)
    v = VisitRecord(**base)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _post_pairing(client, **overrides):
    payload = {
        "subject_type": "unit",
        "subject_name": "某单位",
        "partner_type": "village",
        "title": "对口帮扶",
    }
    payload.update(overrides)
    return client.post("/api/v1/pairings", json=payload)


class TestCreatePairing:
    def test_create_village_pairing(self, api_client):
        client, db, _state = api_client
        from app.models.pairing import PairingRecord
        from app.models.work_log import WorkLog

        v = _mk_village(db)
        resp = _post_pairing(client, village_id=v.id, content="年度计划", start_date="2026-01-01")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["id"]
        assert data["partner_name"] == "幸福村"
        assert data["status"] == "active"
        assert data["is_deleted"] is False
        row = db.query(PairingRecord).filter(PairingRecord.id == data["id"]).first()
        assert row.organization_id == 1
        assert row.created_by == 7
        assert db.query(WorkLog).count() >= 1

    def test_create_school_pairing(self, api_client):
        client, db, _state = api_client
        s = _mk_school(db)
        resp = _post_pairing(
            client, subject_type="person", subject_name="张三", partner_type="school", school_id=s.id
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["partner_name"] == "希望小学"

    def test_create_student_pairing_normalizes_foreign_fields(self, api_client):
        client, db, _state = api_client
        _mk_village(db)
        resp = _post_pairing(
            client,
            partner_type="student",
            student_name="李四",
            village_id=1,
            school_id=1,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["partner_name"] == "李四"
        assert data["village_id"] is None
        assert data["school_id"] is None

    def test_create_without_username_falls_back(self, api_client):
        client, db, state = api_client
        from app.models.pairing import PairingRecord

        v = _mk_village(db)
        state["user"] = SimpleNamespace(id=8, role="admin", organization_id=1)
        resp = _post_pairing(client, village_id=v.id)
        assert resp.status_code == 200
        row = db.query(PairingRecord).filter(PairingRecord.organization_id == 1).first()
        assert row.created_by == 8

    @pytest.mark.parametrize(
        "overrides,expected",
        [
            ({"subject_type": "army"}, 422),
            ({"partner_type": "city"}, 422),
            ({"status": "frozen", "village_id": 1}, 422),
            ({"partner_type": "village"}, 422),
            ({"partner_type": "school"}, 422),
            ({"partner_type": "student"}, 422),
            ({"subject_name": ""}, 422),
            ({"title": ""}, 422),
            (
                {"village_id": 1, "start_date": "2026-05-01", "end_date": "2026-04-30"},
                422,
            ),
        ],
    )
    def test_create_validation_errors(self, api_client, overrides, expected):
        client, db, _state = api_client
        _mk_village(db)
        resp = _post_pairing(client, **overrides)
        assert resp.status_code == expected

    def test_create_village_not_found(self, api_client):
        client, _db, _state = api_client
        resp = _post_pairing(client, village_id=999)
        assert resp.status_code == 404

    def test_create_village_soft_deleted(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db, active=False)
        resp = _post_pairing(client, village_id=v.id)
        assert resp.status_code == 404

    def test_create_village_cross_org_forbidden(self, api_client):
        client, db, state = api_client
        v = _mk_village(db, org_id=1, created_by=7)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        resp = _post_pairing(client, village_id=v.id)
        assert resp.status_code == 403

    def test_create_school_not_found(self, api_client):
        client, _db, _state = api_client
        resp = _post_pairing(client, partner_type="school", school_id=999)
        assert resp.status_code == 404

    def test_create_school_soft_deleted(self, api_client):
        client, db, _state = api_client
        s = _mk_school(db, active=False)
        resp = _post_pairing(client, partner_type="school", school_id=s.id)
        assert resp.status_code == 404

    def test_create_school_cross_org_forbidden(self, api_client):
        client, db, state = api_client
        s = _mk_school(db, org_id=1, created_by=7)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        resp = _post_pairing(client, partner_type="school", school_id=s.id)
        assert resp.status_code == 403


class TestListPairings:
    def _seed(self, db):
        v = _mk_village(db, name="幸福村")
        s = _mk_school(db, name="希望小学")
        p1 = _mk_pairing(db, title="对口帮扶一", village_id=v.id)
        p2 = _mk_pairing(
            db,
            subject_type="person",
            subject_name="张三",
            partner_type="school",
            school_id=s.id,
            title="助学",
            status="ended",
        )
        p3 = _mk_pairing(
            db,
            subject_type="branch",
            subject_name="第一支部",
            partner_type="student",
            student_name="李四",
            title="困难学生帮扶",
            village_id=None,
        )
        return v, s, p1, p2, p3

    def test_list_envelope_and_partner_names(self, api_client):
        client, db, _state = api_client
        self._seed(db)
        resp = client.get("/api/v1/pairings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 20
        names = {item["title"]: item["partner_name"] for item in data["items"]}
        assert names["对口帮扶一"] == "幸福村"
        assert names["助学"] == "希望小学"
        assert names["困难学生帮扶"] == "李四"

    def test_list_supports_filters(self, api_client):
        client, db, _state = api_client
        v, s, _p1, _p2, _p3 = self._seed(db)

        assert client.get("/api/v1/pairings", params={"keyword": "对口"}).json()["data"]["total"] == 1
        assert client.get("/api/v1/pairings", params={"keyword": "李四"}).json()["data"]["total"] == 1
        assert (
            client.get("/api/v1/pairings", params={"keyword": "张三"}).json()["data"]["total"] == 1
        )
        assert (
            client.get("/api/v1/pairings", params={"subject_type": "person"}).json()["data"]["total"]
            == 1
        )
        assert (
            client.get("/api/v1/pairings", params={"partner_type": "school"}).json()["data"]["total"]
            == 1
        )
        assert (
            client.get("/api/v1/pairings", params={"status": "ended"}).json()["data"]["total"] == 1
        )
        assert (
            client.get(
                "/api/v1/pairings", params={"partner_type": "village", "partner_id": v.id}
            ).json()["data"]["total"]
            == 1
        )
        assert (
            client.get(
                "/api/v1/pairings", params={"partner_type": "school", "partner_id": s.id}
            ).json()["data"]["total"]
            == 1
        )
        assert (
            client.get("/api/v1/pairings", params={"partner_id": v.id}).json()["data"]["total"] == 2
        )  # 未指定 partner_type：按村/校双列 OR 匹配（村 1 与同 id 的学校记录均命中）

    def test_list_pagination(self, api_client):
        client, db, _state = api_client
        self._seed(db)
        resp = client.get("/api/v1/pairings", params={"page": 2, "page_size": 1})
        data = resp.json()["data"]
        assert data["total"] == 3
        assert data["page"] == 2
        assert len(data["items"]) == 1

    def test_list_empty(self, api_client):
        client, _db, _state = api_client
        data = client.get("/api/v1/pairings").json()["data"]
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_include_deleted_downgrade_and_admin_passthrough(self, api_client):
        client, db, state = api_client
        v = _mk_village(db)
        p = _mk_pairing(db, village_id=v.id)
        resp = client.delete(f"/api/v1/pairings/{p.id}")
        assert resp.status_code == 200

        # 非管理员：include_deleted 静默降级，软删记录不可见
        _as(state, id=8, role="user", organization_id=1, data_scope="org")
        data = client.get("/api/v1/pairings", params={"include_deleted": "true"}).json()["data"]
        assert data["total"] == 0

        # 管理员：透传，可见且标记 is_deleted
        _as(state)
        data = client.get("/api/v1/pairings", params={"include_deleted": "true"}).json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["is_deleted"] is True
        # 管理员默认（不带参数）同样隐藏软删
        assert client.get("/api/v1/pairings").json()["data"]["total"] == 0

    def test_list_scope_isolation(self, api_client):
        client, db, state = api_client
        v = _mk_village(db)
        _mk_pairing(db, village_id=v.id)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        assert client.get("/api/v1/pairings").json()["data"]["total"] == 0


class TestPairingStats:
    def test_stats(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        p1 = _mk_pairing(db, village_id=v.id)
        _mk_pairing(db, partner_type="school", school_id=1, status="ended", title="助学")
        _mk_visit(db, pairing_id=p1.id)
        resp = client.get("/api/v1/pairings/stats")
        assert resp.status_code == 200
        assert resp.json()["data"] == {
            "total": 2,
            "active": 1,
            "ended": 1,
            "villages": 1,
            "schools": 1,
            "students": 0,
            "visits": 1,
        }

    def test_stats_empty(self, api_client):
        client, _db, _state = api_client
        assert client.get("/api/v1/pairings/stats").json()["data"] == {
            "total": 0,
            "active": 0,
            "ended": 0,
            "villages": 0,
            "schools": 0,
            "students": 0,
            "visits": 0,
        }

    def test_stats_include_deleted_for_admin(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db)
        client.delete(f"/api/v1/pairings/{p.id}")
        assert client.get("/api/v1/pairings/stats").json()["data"]["total"] == 0
        data = client.get(
            "/api/v1/pairings/stats", params={"include_deleted": "true"}
        ).json()["data"]
        assert data["total"] == 1


class TestPairingDetail:
    def test_detail_ok(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        p = _mk_pairing(db, village_id=v.id)
        resp = client.get(f"/api/v1/pairings/{p.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == p.id
        assert data["partner_name"] == "幸福村"
        assert data["viewableBecause"] is None

    def test_detail_not_found(self, api_client):
        client, _db, _state = api_client
        assert client.get("/api/v1/pairings/999").status_code == 404

    def test_detail_cross_org_forbidden(self, api_client):
        client, db, state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        assert client.get(f"/api/v1/pairings/{p.id}").status_code == 403

    def test_detail_soft_deleted_admin_metadata(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db)
        client.delete(f"/api/v1/pairings/{p.id}")
        data = client.get(f"/api/v1/pairings/{p.id}").json()["data"]
        assert data["viewableBecause"] == "admin"
        assert data["is_deleted"] is True


class TestPairingUpdate:
    def test_update_partial_title(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db, partner_type="student", student_name="李四", title="旧事项")
        resp = client.put(f"/api/v1/pairings/{p.id}", json={"title": "新事项"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "新事项"
        assert resp.json()["data"]["partner_name"] == "李四"

    def test_update_partner_type_normalizes(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        p = _mk_pairing(db, village_id=v.id)
        resp = client.put(
            f"/api/v1/pairings/{p.id}",
            json={"partner_type": "student", "student_name": "王五"},
        )
        data = resp.json()["data"]
        assert data["partner_type"] == "student"
        assert data["village_id"] is None
        assert data["partner_name"] == "王五"

    def test_update_change_village_missing(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db)
        resp = client.put(f"/api/v1/pairings/{p.id}", json={"village_id": 999, "partner_type": "village"})
        assert resp.status_code == 404

    def test_update_validation_error(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        p = _mk_pairing(db, village_id=v.id)
        resp = client.put(
            f"/api/v1/pairings/{p.id}",
            json={"start_date": "2026-05-01", "end_date": "2026-04-30"},
        )
        assert resp.status_code == 422

    def test_update_not_found(self, api_client):
        client, _db, _state = api_client
        assert client.put("/api/v1/pairings/999", json={"title": "x"}).status_code == 404

    def test_update_cross_org_forbidden(self, api_client):
        client, db, state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        assert client.put(f"/api/v1/pairings/{p.id}", json={"title": "x"}).status_code == 403


class TestPairingDelete:
    def test_delete_soft(self, api_client):
        client, db, _state = api_client
        from app.models.pairing import PairingRecord

        p = _mk_pairing(db)
        resp = client.delete(f"/api/v1/pairings/{p.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == p.id
        db.refresh(p)
        assert p.is_active is False
        assert p.deleted_at is not None
        assert client.get("/api/v1/pairings").json()["data"]["total"] == 0
        assert db.query(PairingRecord).filter(PairingRecord.id == p.id).count() == 1

    def test_delete_not_found(self, api_client):
        client, _db, _state = api_client
        assert client.delete("/api/v1/pairings/999").status_code == 404

    def test_delete_cross_org_forbidden(self, api_client):
        client, db, state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        assert client.delete(f"/api/v1/pairings/{p.id}").status_code == 403


class TestVisits:
    def test_create_visit_inherits_org(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        resp = client.post(
            f"/api/v1/pairings/{p.id}/visits",
            json={
                "visit_date": "2026-03-05",
                "visitors": "甲、乙",
                "purpose": "助学走访",
                "content": "慰问",
                "materials": "书包 20 个",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["pairing_id"] == p.id
        assert data["organization_id"] == 1
        assert data["created_by"] == 7

    def test_create_visit_pairing_not_found(self, api_client):
        client, _db, _state = api_client
        resp = client.post(
            "/api/v1/pairings/999/visits",
            json={"visit_date": "2026-03-05", "visitors": "甲"},
        )
        assert resp.status_code == 404

    def test_create_visit_pairing_forbidden(self, api_client):
        client, db, state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        resp = client.post(
            f"/api/v1/pairings/{p.id}/visits",
            json={"visit_date": "2026-03-05", "visitors": "甲"},
        )
        assert resp.status_code == 403

    def test_list_visits_order_and_envelope(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db)
        _mk_visit(db, pairing_id=p.id, visit_date=date(2026, 1, 1), visitors="旧")
        _mk_visit(db, pairing_id=p.id, visit_date=date(2026, 3, 1), visitors="新")
        resp = client.get(f"/api/v1/pairings/{p.id}/visits")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert [v["visitors"] for v in data["items"]] == ["新", "旧"]

    def test_list_visits_include_deleted_downgrade(self, api_client):
        client, db, state = api_client
        p = _mk_pairing(db)
        v = _mk_visit(db, pairing_id=p.id)
        assert client.delete(f"/api/v1/pairings/{p.id}/visits/{v.id}").status_code == 200
        assert client.get(f"/api/v1/pairings/{p.id}/visits").json()["data"]["total"] == 0
        _as(state, id=8, role="user", organization_id=1, data_scope="org")
        data = client.get(
            f"/api/v1/pairings/{p.id}/visits", params={"include_deleted": "true"}
        ).json()["data"]
        assert data["total"] == 0
        _as(state)
        data = client.get(
            f"/api/v1/pairings/{p.id}/visits", params={"include_deleted": "true"}
        ).json()["data"]
        assert data["total"] == 1

    def test_update_visit_partial(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db)
        v = _mk_visit(db, pairing_id=p.id)
        resp = client.put(
            f"/api/v1/pairings/{p.id}/visits/{v.id}", json={"visitors": "丙", "content": "新增记录"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["visitors"] == "丙"
        assert data["content"] == "新增记录"

    def test_update_visit_wrong_pairing(self, api_client):
        client, db, _state = api_client
        p1 = _mk_pairing(db)
        p2 = _mk_pairing(db, title="另一结对")
        v = _mk_visit(db, pairing_id=p2.id)
        resp = client.put(f"/api/v1/pairings/{p1.id}/visits/{v.id}", json={"visitors": "丙"})
        assert resp.status_code == 404

    def test_update_visit_unknown(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db)
        assert (
            client.put(f"/api/v1/pairings/{p.id}/visits/999", json={"visitors": "丙"}).status_code
            == 404
        )

    def test_update_visit_cross_org_forbidden(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        v = _mk_visit(db, pairing_id=p.id, organization_id=99, created_by=99)
        resp = client.put(f"/api/v1/pairings/{p.id}/visits/{v.id}", json={"visitors": "丙"})
        assert resp.status_code == 403

    def test_delete_visit_soft(self, api_client):
        client, db, _state = api_client
        from app.models.pairing import VisitRecord

        p = _mk_pairing(db)
        v = _mk_visit(db, pairing_id=p.id)
        resp = client.delete(f"/api/v1/pairings/{p.id}/visits/{v.id}")
        assert resp.status_code == 200
        db.refresh(v)
        assert v.is_active is False
        assert v.deleted_at is not None
        assert db.query(VisitRecord).filter(VisitRecord.id == v.id).count() == 1

    def test_delete_visit_unknown(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db)
        assert client.delete(f"/api/v1/pairings/{p.id}/visits/999").status_code == 404

    def test_delete_visit_cross_org_forbidden(self, api_client):
        client, db, _state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        v = _mk_visit(db, pairing_id=p.id, organization_id=99, created_by=99)
        resp = client.delete(f"/api/v1/pairings/{p.id}/visits/{v.id}")
        assert resp.status_code == 403

    def test_delete_visit_pairing_forbidden(self, api_client):
        client, db, state = api_client
        p = _mk_pairing(db, organization_id=1, created_by=7)
        v = _mk_visit(db, pairing_id=p.id)
        _as(state, id=9, role="user", organization_id=2, data_scope="org")
        assert client.delete(f"/api/v1/pairings/{p.id}/visits/{v.id}").status_code == 403
