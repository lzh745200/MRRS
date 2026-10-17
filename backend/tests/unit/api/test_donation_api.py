"""捐赠物资台账 API（w17-003）。

覆盖：CRUD 契约（envelope / ok_list）、字段组合校验、去向可达性（404/403）、
数据域（列表隔离 / 点查 403 / fail-closed）、软删与 include_deleted 降级、
筛选（关键字/类别/去向 + destination_id 四分支）、统计口径、附件与审计留痕。
"""
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
    from app.models.project import Project  # noqa: F401
    from app.models.donation_item import DonationItem  # noqa: F401
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


def _mk_project(db, name="操场改造", org_id=1, created_by=7, active=True):
    from app.models.project import Project

    p = Project(name=name, organization_id=org_id, created_by=created_by, is_active=active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _mk_item(db, **kw):
    from app.models.donation_item import DonationItem

    base = dict(
        name="图书",
        category="book",
        quantity=100,
        unit="册",
        valuation=1.5,
        source_unit="某部队",
        destination_type="village",
        organization_id=1,
        created_by=7,
    )
    base.update(kw)
    item = DonationItem(**base)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _post(client, **overrides):
    payload = {
        "name": "课外读物",
        "category": "book",
        "quantity": 200,
        "unit": "册",
        "valuation": 3.2,
        "source_unit": "某部队机关",
        "destination_type": "village",
        "receiver": "李四",
        "remark": "定向捐赠",
    }
    payload.update(overrides)
    return client.post("/api/v1/donations", json=payload)


class TestCreateDonation:
    def test_create_village_donation(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        resp = _post(client, village_id=v.id)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["name"] == "课外读物"
        assert data["quantity"] == 200.0
        assert data["valuation"] == 3.2
        assert data["destination_name"] == "幸福村"
        assert data["organization_id"] == 1
        assert data["created_by"] == 7
        assert data["is_active"] is True

        from app.models.work_log import WorkLog

        log = (
            db.query(WorkLog)
            .filter(WorkLog.category == "donation")
            .order_by(WorkLog.id.desc())
            .first()
        )
        assert log is not None
        assert "课外读物" in log.content

    def test_create_school_and_project_destinations(self, api_client):
        client, db, _state = api_client
        s = _mk_school(db)
        p = _mk_project(db)
        r1 = _post(client, destination_type="school", school_id=s.id)
        assert r1.json()["data"]["destination_name"] == "希望小学"
        r2 = _post(client, destination_type="project", project_id=p.id)
        assert r2.json()["data"]["destination_name"] == "操场改造"

    def test_create_with_attachments_and_defaults(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        resp = _post(
            client,
            village_id=v.id,
            delivery_date="2026-06-01",
            attachments=[{"url": "/uploads/1.pdf", "file_name": "签收单.pdf"}],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["delivery_date"] == "2026-06-01"
        assert data["attachments"] == [{"url": "/uploads/1.pdf", "file_name": "签收单.pdf"}]

        # quantity / valuation 缺省 → 0
        resp2 = client.post(
            "/api/v1/donations",
            json={"name": "米面", "destination_type": "village", "village_id": v.id},
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["quantity"] == 0.0
        assert resp2.json()["data"]["valuation"] == 0.0
        assert resp2.json()["data"]["category"] == "material"

    def test_invalid_category_and_destination_type(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        r1 = _post(client, category="alien", village_id=v.id)
        assert r1.status_code == 422
        assert "物资类别" in r1.json()["detail"]
        r2 = _post(client, destination_type="alien", village_id=v.id)
        assert r2.status_code == 422
        assert "去向类型" in r2.json()["detail"]

    def test_missing_destination_id(self, api_client):
        client, _db, _state = api_client
        assert _post(client).status_code == 422
        assert _post(client, destination_type="school").status_code == 422
        assert _post(client, destination_type="project").status_code == 422

    def test_negative_values_rejected_by_schema(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        assert _post(client, village_id=v.id, quantity=-1).status_code == 422
        assert _post(client, village_id=v.id, valuation=-1).status_code == 422

    def test_destination_not_found_and_cross_org(self, api_client):
        client, db, state = api_client
        r1 = _post(client, village_id=999)
        assert r1.status_code == 404
        assert "帮扶村" in r1.json()["message"]

        v2 = _mk_village(db, name="外人村", org_id=2, created_by=7)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        r2 = _post(client, village_id=v2.id)
        assert r2.status_code == 403
        assert "帮扶村" in r2.json()["detail"]


class TestListDonations:
    def test_list_envelope_and_names(self, api_client):
        client, db, _state = api_client
        _mk_village(db)
        _mk_item(db, name="图书A", village_id=1)
        _mk_item(db, name="图书B", village_id=1)
        resp = client.get("/api/v1/donations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert [i["name"] for i in data["items"]]
        assert data["items"][0]["destination_name"] == "幸福村"

    def test_filters_keyword_category_type_and_destination(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        s = _mk_school(db)
        p = _mk_project(db)
        _mk_item(db, name="图书A", category="book", village_id=v.id, source_unit="某部队")
        _mk_item(
            db,
            name="电脑",
            category="equipment",
            school_id=s.id,
            destination_type="school",
            receiver="王五",
            source_unit="某企业",
        )
        _mk_item(
            db,
            name="米面",
            category="material",
            project_id=p.id,
            destination_type="project",
            source_unit="某商会",
        )

        # keyword 命中 name / source_unit / receiver 三列
        assert client.get("/api/v1/donations", params={"keyword": "图书"}).json()["data"]["total"] == 1
        assert client.get("/api/v1/donations", params={"keyword": "部队"}).json()["data"]["total"] == 1
        assert client.get("/api/v1/donations", params={"keyword": "王五"}).json()["data"]["total"] == 1
        # 类别
        assert client.get("/api/v1/donations", params={"category": "book"}).json()["data"]["total"] == 1
        # 仅去向类型
        assert (
            client.get("/api/v1/donations", params={"destination_type": "school"}).json()["data"]["total"]
            == 1
        )
        # 类型 + id 三分支
        assert (
            client.get(
                "/api/v1/donations", params={"destination_type": "village", "destination_id": v.id}
            ).json()["data"]["total"]
            == 1
        )
        assert (
            client.get(
                "/api/v1/donations", params={"destination_type": "school", "destination_id": s.id}
            ).json()["data"]["total"]
            == 1
        )
        assert (
            client.get(
                "/api/v1/donations", params={"destination_type": "project", "destination_id": p.id}
            ).json()["data"]["total"]
            == 1
        )
        # 仅 id（无类型）→ 三列 or_ 匹配（用唯一 id 排除“三列恰好同号”干扰）
        s2 = _mk_school(db, name="第二小学")
        _mk_item(
            db,
            name="投影仪",
            category="equipment",
            school_id=s2.id,
            destination_type="school",
            source_unit="某单位",
        )
        assert (
            client.get("/api/v1/donations", params={"destination_id": s2.id}).json()["data"]["total"]
            == 1
        )
        assert (
            client.get("/api/v1/donations", params={"destination_id": 999}).json()["data"]["total"]
            == 0
        )

    def test_pagination(self, api_client):
        client, db, _state = api_client
        for i in range(3):
            _mk_item(db, name=f"物资{i}")
        first = client.get("/api/v1/donations", params={"page": 1, "page_size": 2}).json()["data"]
        assert first["total"] == 3
        assert len(first["items"]) == 2
        second = client.get("/api/v1/donations", params={"page": 2, "page_size": 2}).json()["data"]
        assert len(second["items"]) == 1

    def test_soft_deleted_hidden_and_include_deleted(self, api_client):
        client, db, state = api_client
        _mk_item(db, name="在用")
        _mk_item(db, name="已删", is_active=False)
        assert client.get("/api/v1/donations").json()["data"]["total"] == 1
        assert (
            client.get("/api/v1/donations", params={"include_deleted": True}).json()["data"]["total"]
            == 2
        )
        # 非管理员传 include_deleted 静默降级
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        assert (
            client.get("/api/v1/donations", params={"include_deleted": True}).json()["data"]["total"]
            == 1
        )

    def test_org_isolation(self, api_client):
        client, db, state = api_client
        _mk_item(db, name="一团", organization_id=1)
        _mk_item(db, name="二团", organization_id=2)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        body = client.get("/api/v1/donations").json()["data"]
        assert [i["name"] for i in body["items"]] == ["一团"]


class TestStats:
    def test_stats(self, api_client):
        client, db, _state = api_client
        _mk_item(db, quantity=10, valuation=1, destination_type="village", village_id=1)
        _mk_item(db, quantity=5, valuation=2, category="equipment", destination_type="school", school_id=1)
        body = client.get("/api/v1/donations/stats").json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 2
        assert data["villages"] == 1
        assert data["schools"] == 1
        assert data["quantity"] == 15.0
        assert data["valuation"] == 3.0

    def test_stats_include_deleted_and_scope(self, api_client):
        client, db, state = api_client
        _mk_item(db, organization_id=1)
        _mk_item(db, organization_id=1, is_active=False)
        _mk_item(db, organization_id=2)
        assert client.get("/api/v1/donations/stats").json()["data"]["total"] == 2
        assert (
            client.get("/api/v1/donations/stats", params={"include_deleted": True}).json()["data"]["total"]
            == 3
        )
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        assert client.get("/api/v1/donations/stats").json()["data"]["total"] == 1


class TestDetail:
    def test_detail_ok(self, api_client):
        client, db, _state = api_client
        _mk_village(db)
        item = _mk_item(db, village_id=1)
        body = client.get(f"/api/v1/donations/{item.id}").json()
        assert body["data"]["destination_name"] == "幸福村"
        assert body["data"]["viewableBecause"] is None

    def test_detail_not_found(self, api_client):
        client, _db, _state = api_client
        resp = client.get("/api/v1/donations/999")
        assert resp.status_code == 404
        assert resp.json()["message"] == "捐赠物资记录不存在"

    def test_detail_cross_org_forbidden(self, api_client):
        client, db, state = api_client
        item = _mk_item(db, organization_id=2, created_by=7)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        resp = client.get(f"/api/v1/donations/{item.id}")
        assert resp.status_code == 403
        assert "无权访问" in resp.json()["detail"]

    def test_detail_soft_deleted_viewable_because(self, api_client):
        client, db, state = api_client
        item = _mk_item(db, is_active=False)
        body = client.get(f"/api/v1/donations/{item.id}").json()
        assert body["data"]["viewableBecause"] == "admin"

        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        item2 = _mk_item(db, is_active=False, created_by=9, organization_id=1)
        body2 = client.get(f"/api/v1/donations/{item2.id}").json()
        assert body2["data"]["viewableBecause"] is None


class TestUpdate:
    def test_partial_update_keeps_destination(self, api_client):
        client, db, _state = api_client
        _mk_village(db)
        item = _mk_item(db, village_id=1)
        resp = client.put(f"/api/v1/donations/{item.id}", json={"name": "新名称"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "新名称"
        assert data["destination_type"] == "village"
        assert data["destination_name"] == "幸福村"

    def test_update_destination_and_attachments(self, api_client):
        client, db, _state = api_client
        v = _mk_village(db)
        item = _mk_item(db, village_id=v.id)
        s = _mk_school(db)
        resp = client.put(
            f"/api/v1/donations/{item.id}",
            json={
                "destination_type": "school",
                "school_id": s.id,
                "attachments": [{"url": "/uploads/2.pdf"}],
                "quantity": 8,
                "valuation": 0.8,
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["destination_name"] == "希望小学"
        assert data["village_id"] is None
        assert data["attachments"] == [{"url": "/uploads/2.pdf", "file_name": None}]
        assert data["quantity"] == 8.0

    def test_update_validation_failures(self, api_client):
        client, db, _state = api_client
        item = _mk_item(db, village_id=1)
        assert client.put(f"/api/v1/donations/{item.id}", json={"category": "alien"}).status_code == 422
        # 改成学校但未给 school_id → 422
        assert (
            client.put(f"/api/v1/donations/{item.id}", json={"destination_type": "school"}).status_code
            == 422
        )
        assert client.put(f"/api/v1/donations/{item.id}", json={"name": ""}).status_code == 422
        assert client.put(f"/api/v1/donations/{item.id}", json={"quantity": -5}).status_code == 422

    def test_update_destination_not_found(self, api_client):
        client, db, _state = api_client
        item = _mk_item(db, village_id=1)
        resp = client.put(f"/api/v1/donations/{item.id}", json={"village_id": 999})
        assert resp.status_code == 404

    def test_update_not_found_and_cross_org(self, api_client):
        client, db, state = api_client
        assert client.put("/api/v1/donations/999", json={"name": "x"}).status_code == 404

        item = _mk_item(db, organization_id=2, created_by=7)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        resp = client.put(f"/api/v1/donations/{item.id}", json={"name": "x"})
        assert resp.status_code == 403
        assert "无权编辑" in resp.json()["detail"]


class TestDelete:
    def test_delete_soft(self, api_client):
        client, db, _state = api_client
        item = _mk_item(db, name="待删")
        resp = client.delete(f"/api/v1/donations/{item.id}")
        assert resp.status_code == 200
        assert resp.json()["data"] == {"id": item.id}

        db.refresh(item)
        assert item.is_active is False
        assert item.deleted_at is not None
        assert client.get("/api/v1/donations").json()["data"]["total"] == 0
        assert (
            client.get("/api/v1/donations", params={"include_deleted": True}).json()["data"]["total"]
            == 1
        )

        from app.models.work_log import WorkLog

        assert (
            db.query(WorkLog)
            .filter(WorkLog.category == "donation", WorkLog.content.like("%待删%"))
            .count()
            >= 1
        )

    def test_delete_not_found_and_cross_org(self, api_client):
        client, db, state = api_client
        assert client.delete("/api/v1/donations/999").status_code == 404

        item = _mk_item(db, organization_id=2, created_by=7)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        resp = client.delete(f"/api/v1/donations/{item.id}")
        assert resp.status_code == 403
        assert "无权删除" in resp.json()["detail"]
