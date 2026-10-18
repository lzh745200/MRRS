"""消费帮扶台账 API（W22 v1.14.0，替换原舆情监测）。

覆盖：列表 envelope/筛选/分页/软删与 include_deleted 降级、数据域隔离、
年度统计（总额/笔数/品类分布/村分布）、导出 xlsx/csv（含格式错误）、
CRUD（含帮扶村可达性 404/403、审计留痕、软删）。
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
    from app.models.consumption import ConsumptionRecord  # noqa: F401
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

    village = SupportedVillage(
        village_name=name, organization_id=org_id, created_by=created_by, is_active=active
    )
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


def _mk_record(db, **kw):
    from app.models.consumption import ConsumptionRecord

    base = dict(
        category="agriculture",
        item_name="土鸡蛋",
        quantity=100,
        unit="斤",
        amount=2000,
        buyer="某部队食堂",
        seller="张三",
        seller_type="farmer",
        year=2026,
        organization_id=1,
        created_by=7,
        is_active=True,
    )
    base.update(kw)
    record = ConsumptionRecord(**base)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _post(client, **overrides):
    payload = {
        "category": "livestock",
        "item_name": "生态猪肉",
        "quantity": 50,
        "unit": "斤",
        "amount": 3500,
        "buyer": "某部队",
        "seller": "养殖合作社",
        "seller_type": "cooperative",
        "year": 2026,
        "record_date": "2026-06-01",
    }
    payload.update(overrides)
    return client.post("/api/v1/consumption", json=payload)


class TestCreateConsumption:
    def test_create_with_village(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        resp = _post(client, supported_village_id=village.id)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["item_name"] == "生态猪肉"
        assert data["amount"] == 3500.0
        assert data["category"] == "livestock"
        assert data["seller_type"] == "cooperative"
        assert data["village_name"] == "幸福村"
        assert data["organization_id"] == 1
        assert data["created_by"] == 7
        assert data["is_active"] is True

        from app.models.work_log import WorkLog

        log = (
            db.query(WorkLog)
            .filter(WorkLog.category == "consumption")
            .order_by(WorkLog.id.desc())
            .first()
        )
        assert log is not None
        assert "生态猪肉" in log.content

    def test_create_without_village_and_defaults(self, api_client):
        client, _db, _state = api_client
        resp = client.post(
            "/api/v1/consumption",
            json={"item_name": "竹篮", "amount": 120, "year": 2026},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["category"] == "agriculture"      # 默认品类
        assert data["supported_village_id"] is None
        assert data["village_name"] is None

    def test_invalid_enum_and_negative_amount(self, api_client):
        client, _db, _state = api_client
        assert _post(client, category="alien").status_code == 422
        assert _post(client, seller_type="alien").status_code == 422
        assert _post(client, amount=-1).status_code == 422
        assert _post(client, quantity=-1).status_code == 422
        assert _post(client, item_name="").status_code == 422
        assert _post(client, year="abc").status_code == 422

    def test_village_not_found_and_cross_org(self, api_client):
        client, db, state = api_client
        r1 = _post(client, supported_village_id=999)
        assert r1.status_code == 404
        assert "帮扶村" in r1.json()["message"]

        other = _mk_village(db, name="外人村", org_id=2)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        r2 = _post(client, supported_village_id=other.id)
        assert r2.status_code == 403


class TestListConsumption:
    def test_list_envelope_and_village_name(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        _mk_record(db, item_name="土鸡蛋", supported_village_id=village.id)
        _mk_record(db, item_name="腊肉", supported_village_id=None)
        body = client.get("/api/v1/consumption").json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 20
        names = {i["item_name"]: i["village_name"] for i in data["items"]}
        assert names["土鸡蛋"] == "幸福村"
        assert names["腊肉"] is None

    def test_filters_year_category_village_keyword(self, api_client):
        client, db, _state = api_client
        v1 = _mk_village(db, name="一村")
        v2 = _mk_village(db, name="二村")
        _mk_record(db, item_name="苹果", category="agriculture", year=2025, supported_village_id=v1.id, buyer="甲单位")
        _mk_record(db, item_name="土鸡", category="livestock", year=2026, supported_village_id=v2.id, seller="乙合作社")
        _mk_record(db, item_name="竹编", category="handicraft", year=2026, supported_village_id=None)

        def total(**params):
            return client.get("/api/v1/consumption", params=params).json()["data"]["total"]

        assert total(year=2026) == 2
        assert total(category="livestock") == 1
        assert total(village_id=v1.id) == 1
        assert total(keyword="苹果") == 1
        assert total(keyword="甲单位") == 1
        assert total(keyword="乙合作社") == 1
        page1 = client.get("/api/v1/consumption", params={"page": 1, "page_size": 2}).json()["data"]
        assert page1["total"] == 3 and len(page1["items"]) == 2
        page2 = client.get("/api/v1/consumption", params={"page": 2, "page_size": 2}).json()["data"]
        assert len(page2["items"]) == 1

    def test_soft_deleted_hidden_and_include_deleted(self, api_client):
        client, db, state = api_client
        _mk_record(db, item_name="在用")
        _mk_record(db, item_name="已删", is_active=False)
        assert client.get("/api/v1/consumption").json()["data"]["total"] == 1
        assert (
            client.get("/api/v1/consumption", params={"include_deleted": True}).json()["data"]["total"]
            == 2
        )
        # 非管理员传 include_deleted 静默降级
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        assert (
            client.get("/api/v1/consumption", params={"include_deleted": True}).json()["data"]["total"]
            == 1
        )

    def test_org_isolation(self, api_client):
        client, db, state = api_client
        _mk_record(db, item_name="一团记录", organization_id=1)
        _mk_record(db, item_name="二团记录", organization_id=2)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        body = client.get("/api/v1/consumption").json()["data"]
        assert [i["item_name"] for i in body["items"]] == ["一团记录"]


class TestStatistics:
    def test_statistics_totals_and_groups(self, api_client):
        client, db, _state = api_client
        v1 = _mk_village(db, name="一村")
        v2 = _mk_village(db, name="二村")
        _mk_record(db, item_name="苹果", category="agriculture", amount=1000, year=2026, supported_village_id=v1.id)
        _mk_record(db, item_name="梨", category="agriculture", amount=500, year=2026, supported_village_id=v1.id)
        _mk_record(db, item_name="土鸡", category="livestock", amount=2000, year=2025, supported_village_id=v2.id)
        _mk_record(db, item_name="竹编", category="handicraft", amount=300, year=2026, supported_village_id=None)

        data = client.get("/api/v1/consumption/statistics", params={"year": 2026}).json()["data"]
        assert data["record_count"] == 3
        assert data["total_amount"] == 1800.0
        categories = {row["category"]: row for row in data["by_category"]}
        assert categories["agriculture"]["record_count"] == 2
        assert categories["agriculture"]["amount"] == 1500.0
        assert categories["handicraft"]["amount"] == 300.0
        assert "livestock" not in categories  # year 过滤生效
        by_village = {row["village_name"]: row for row in data["by_village"]}
        assert by_village["一村"]["amount"] == 1500.0
        assert None not in by_village  # 未关联帮扶村的记录不进入村分布

    def test_statistics_all_years_and_scope(self, api_client):
        client, db, state = api_client
        _mk_record(db, amount=100, organization_id=1)
        _mk_record(db, amount=200, organization_id=1, is_active=False)
        _mk_record(db, amount=900, organization_id=2)
        all_years = client.get("/api/v1/consumption/statistics").json()["data"]
        assert all_years["record_count"] == 2      # 管理员全量：org1 在用 + org2 在用
        assert all_years["total_amount"] == 1000.0
        with_deleted = client.get(
            "/api/v1/consumption/statistics", params={"include_deleted": True}
        ).json()["data"]
        assert with_deleted["record_count"] == 3
        assert with_deleted["total_amount"] == 1200.0

        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        scoped = client.get("/api/v1/consumption/statistics").json()["data"]
        assert scoped["record_count"] == 1
        assert scoped["total_amount"] == 100.0


class TestExport:
    def test_export_xlsx_and_csv(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        _mk_record(db, item_name="土鸡蛋", supported_village_id=village.id, record_date=None)
        _mk_record(db, item_name="竹编", category="handicraft", supported_village_id=None, record_date=None)

        xlsx = client.get("/api/v1/consumption/export")
        assert xlsx.status_code == 200
        assert "spreadsheetml" in xlsx.headers["content-type"]
        assert "attachment" in xlsx.headers["content-disposition"]
        assert xlsx.content[:2] == b"PK"

        csv_resp = client.get("/api/v1/consumption/export", params={"format": "csv", "year": 2026})
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        text = csv_resp.content.decode("utf-8")
        assert "\ufeff" in text
        assert "产品名称" in text
        assert "土鸡蛋" in text
        assert "幸福村" in text

    def test_export_filter_and_invalid_format(self, api_client):
        client, db, _state = api_client
        v1 = _mk_village(db, name="一村")
        v2 = _mk_village(db, name="二村")
        _mk_record(db, item_name="苹果", category="agriculture", year=2026, supported_village_id=v1.id)
        _mk_record(db, item_name="土鸡", category="livestock", year=2026, supported_village_id=v2.id)
        narrowed = client.get(
            "/api/v1/consumption/export",
            params={"format": "csv", "category": "livestock", "village_id": v2.id},
        )
        text = narrowed.content.decode("utf-8")
        assert "土鸡" in text and "苹果" not in text

        bad = client.get("/api/v1/consumption/export", params={"format": "pdf"})
        assert bad.status_code == 400
        assert "不支持的导出格式" in bad.json()["detail"]


class TestUpdate:
    def test_partial_update_and_clear_village(self, api_client):
        client, db, _state = api_client
        village = _mk_village(db)
        record = _mk_record(db, supported_village_id=village.id)
        resp = client.put(
            f"/api/v1/consumption/{record.id}",
            json={"amount": 2500, "supported_village_id": None},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["amount"] == 2500.0
        assert data["supported_village_id"] is None
        assert data["item_name"] == "土鸡蛋"  # 未更新字段保持

    def test_update_without_village_and_seller_type(self, api_client):
        """不带 supported_village_id 的更新（分支覆盖）+ seller_type 校验/更新。"""
        client, db, _state = api_client
        record = _mk_record(db)
        resp = client.put(f"/api/v1/consumption/{record.id}", json={"item_name": "新名称"})
        assert resp.status_code == 200
        assert resp.json()["data"]["item_name"] == "新名称"
        assert client.put(
            f"/api/v1/consumption/{record.id}", json={"seller_type": "alien"}
        ).status_code == 422
        ok = client.put(f"/api/v1/consumption/{record.id}", json={"seller_type": "enterprise"})
        assert ok.status_code == 200
        assert ok.json()["data"]["seller_type"] == "enterprise"

    def test_update_validation_and_missing_village(self, api_client):
        client, db, _state = api_client
        record = _mk_record(db)
        assert client.put(f"/api/v1/consumption/{record.id}", json={"category": "alien"}).status_code == 422
        assert client.put(f"/api/v1/consumption/{record.id}", json={"amount": -1}).status_code == 422
        resp = client.put(f"/api/v1/consumption/{record.id}", json={"supported_village_id": 999})
        assert resp.status_code == 404

    def test_update_not_found_and_cross_org(self, api_client):
        client, db, state = api_client
        assert client.put("/api/v1/consumption/999", json={"amount": 1}).status_code == 404

        record = _mk_record(db, organization_id=2, created_by=7)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        resp = client.put(f"/api/v1/consumption/{record.id}", json={"amount": 1})
        assert resp.status_code == 403
        assert "无权编辑" in resp.json()["detail"]


class TestDelete:
    def test_delete_soft(self, api_client):
        client, db, _state = api_client
        record = _mk_record(db, item_name="待删记录")
        resp = client.delete(f"/api/v1/consumption/{record.id}")
        assert resp.status_code == 200
        assert resp.json()["data"] == {"id": record.id}

        db.refresh(record)
        assert record.is_active is False
        assert record.deleted_at is not None
        assert client.get("/api/v1/consumption").json()["data"]["total"] == 0
        assert (
            client.get("/api/v1/consumption", params={"include_deleted": True}).json()["data"]["total"]
            == 1
        )

        from app.models.work_log import WorkLog

        assert (
            db.query(WorkLog)
            .filter(WorkLog.category == "consumption", WorkLog.content.like("%待删记录%"))
            .count()
            >= 1
        )

    def test_delete_not_found_and_cross_org(self, api_client):
        client, db, state = api_client
        assert client.delete("/api/v1/consumption/999").status_code == 404

        record = _mk_record(db, organization_id=2, created_by=7)
        _as(state, id=9, role="user", organization_id=1, data_scope="org")
        resp = client.delete(f"/api/v1/consumption/{record.id}")
        assert resp.status_code == 403
        assert "无权删除" in resp.json()["detail"]
