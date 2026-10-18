# -*- coding: utf-8 -*-
"""业务数据体检（W17-008）回归测试。

覆盖 app/services/business_health_service.py 与 app/api/v1/system/business_health.py：

1. 空库/满库均可用：空库 0 计数不抛异常，满库逐项计数/入口/明细正确；
2. 四类业务数据问题：村年度缺失、金额矛盾（used>amount、负数）、长期未动项目/经费、
   组织归属缺失；
3. 管理员专属（403）+ 参数校验（422）+ 路由注册；
4. 响应不含任何 PII（人名/手机号/项目/经费名称）；
5. 扫描 SQL 不使用原始 f-string 拼接（源码静态守卫）。
"""

import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.models.fund import Fund
from app.models.project import Project
from app.models.supported_village import (
    SupportedVillage,
    VillageIncome,
    VillagePopulation,
)
from app.services.business_health_service import (
    DEFAULT_ITEM_LIMIT,
    DEFAULT_STALE_DAYS,
    MAX_ITEM_LIMIT,
    BusinessHealthService,
)
from app.utils.time_utils import utcnow

# 年度数据使用的"上一年度"（默认年度为当前年，二者恒不相等）
YEAR = date.today().year - 1

CHECK_KEYS = [
    "village_annual_missing",
    "fund_used_exceeds_amount",
    "fund_negative_amount",
    "stale_projects",
    "stale_funds",
    "village_organization_missing",
    "project_organization_missing",
    "fund_organization_missing",
]

CHECK_ITEM_KEYS = {
    "key",
    "title",
    "severity",
    "count",
    "entry",
    "hint",
    "items",
    "items_truncated",
}


def _get(payload, key):
    return next(check for check in payload["checks"] if check["key"] == key)


def _seed_full(db):
    """满库样本：每个体检项至少命中一个实体，且含"不应命中"的对照实体。"""
    now = utcnow()
    old = now - timedelta(days=365)
    medium = now - timedelta(days=30)

    # ── 村：完整 / 缺收入 / 缺全部年度 / 组织缺失 ──
    full = SupportedVillage(village_name="完整村", organization_id=1)
    no_income = SupportedVillage(village_name="缺收入村", organization_id=1)
    no_annual = SupportedVillage(village_name="无年度村", organization_id=1)
    no_org = SupportedVillage(village_name="无组织村")
    db.add_all([full, no_income, no_annual, no_org])
    db.flush()
    db.add_all(
        [
            VillageIncome(supported_village_id=full.id, year=YEAR, per_capita_income=2.0),
            VillagePopulation(supported_village_id=full.id, year=YEAR, total_population=100),
            VillagePopulation(
                supported_village_id=no_income.id, year=YEAR, total_population=50
            ),
        ]
    )

    # ── 经费：used>amount / 负数 / 长期未动 / 已收口长期未动 / 组织缺失 ──
    overrun = Fund(
        name="张三经费13812345678",
        amount=10,
        used_amount=15,
        organization_id=1,
        status="in_use",
        updated_at=now,
    )
    negative_amount = Fund(
        name="负数申请经费",
        amount=-5,
        organization_id=1,
        status="pending",
        updated_at=now,
    )
    negative_used = Fund(
        name="负数使用经费",
        used_amount=-1,
        organization_id=1,
        status="pending",
        updated_at=now,
    )
    stale_fund = Fund(
        name="长期未动经费",
        amount=1,
        organization_id=1,
        status="pending",
        updated_at=old,
    )
    closed_stale_fund = Fund(
        name="已完成经费",
        amount=1,
        organization_id=1,
        status="completed",
        updated_at=old,
    )
    org_missing_fund = Fund(
        name="无组织经费",
        amount=1,
        status="pending",
        updated_at=now,
    )
    db.add_all(
        [
            overrun,
            negative_amount,
            negative_used,
            stale_fund,
            closed_stale_fund,
            org_missing_fund,
        ]
    )

    # ── 项目：长期未动 / 中期未动（仅严格阈值命中） / 新建且组织缺失 / 已完成 ──
    stale_project = Project(
        name="张三项目13812345678",
        status="in_progress",
        organization_id=1,
        updated_at=old,
        is_active=True,
    )
    medium_project = Project(
        name="中期未动项目",
        status="in_progress",
        organization_id=1,
        updated_at=medium,
        is_active=True,
    )
    fresh_project = Project(
        name="新建项目",
        status="in_progress",
        updated_at=now,
        is_active=True,
    )
    closed_project = Project(
        name="已完成项目",
        status="completed",
        organization_id=1,
        updated_at=old,
        is_active=True,
    )
    db.add_all([stale_project, medium_project, fresh_project, closed_project])
    db.commit()


# ==================== 服务层：空库 / 结构 ====================


class TestEmptyDatabase:
    def test_collect_on_empty_database(self, real_db_session):
        payload = BusinessHealthService(real_db_session, year=YEAR).collect()
        assert payload["status"] == "healthy"
        assert payload["year"] == YEAR
        assert payload["stale_days"] == DEFAULT_STALE_DAYS
        assert payload["item_limit"] == DEFAULT_ITEM_LIMIT
        assert payload["summary"] == {
            "check_count": len(CHECK_KEYS),
            "affected_checks": 0,
            "issue_count": 0,
        }
        assert [check["key"] for check in payload["checks"]] == CHECK_KEYS
        for check in payload["checks"]:
            assert set(check) == CHECK_ITEM_KEYS
            assert check["count"] == 0
            assert check["items"] == []
            assert check["items_truncated"] is False
            assert check["entry"].startswith("/")
            assert check["hint"]
        assert payload["generated_at"]

    def test_empty_database_still_returns_serializable_payload(self, real_db_session):
        payload = BusinessHealthService(real_db_session).collect()
        # 空库响应必须可直接 JSON 序列化（无 datetime 对象泄漏）
        assert json.loads(json.dumps(payload, ensure_ascii=False))["summary"]["issue_count"] == 0


# ==================== 服务层：满库逐项体检 ====================


class TestFullDatabase:
    def test_all_checks_counts(self, real_db_session):
        _seed_full(real_db_session)
        payload = BusinessHealthService(real_db_session, year=YEAR).collect()

        assert payload["status"] == "warning"
        assert _get(payload, "village_annual_missing")["count"] == 3
        # 负数申请（amount=-5）同时满足 used(0) > amount(-5)，两项均命中属预期
        assert _get(payload, "fund_used_exceeds_amount")["count"] == 2
        assert _get(payload, "fund_negative_amount")["count"] == 2
        assert _get(payload, "stale_projects")["count"] == 1
        assert _get(payload, "stale_funds")["count"] == 1
        assert _get(payload, "village_organization_missing")["count"] == 1
        assert _get(payload, "project_organization_missing")["count"] == 1
        assert _get(payload, "fund_organization_missing")["count"] == 1
        # 12 = 3+2+2+1+1+1+1+1
        assert payload["summary"]["issue_count"] == 12
        assert payload["summary"]["affected_checks"] == len(CHECK_KEYS)

    def test_village_annual_missing_details(self, real_db_session):
        _seed_full(real_db_session)
        check = _get(
            BusinessHealthService(real_db_session, year=YEAR).collect(),
            "village_annual_missing",
        )
        by_name = {item["name"]: item for item in check["items"]}
        assert set(by_name) == {"缺收入村", "无年度村", "无组织村"}
        assert by_name["缺收入村"]["missing_sections"] == ["income"]
        assert by_name["无年度村"]["missing_sections"] == ["income", "population"]
        assert check["entry"] == "/supported-villages/yearly"
        assert "%s" % YEAR in check["hint"]

    def test_fund_amount_details(self, real_db_session):
        _seed_full(real_db_session)
        payload = BusinessHealthService(real_db_session, year=YEAR).collect()

        overrun = _get(payload, "fund_used_exceeds_amount")
        assert overrun["items"][0]["amount"] == 10.0
        assert overrun["items"][0]["used_amount"] == 15.0
        assert overrun["items"][0]["overrun"] == 5.0
        assert overrun["entry"] == "/funds"

        negative = _get(payload, "fund_negative_amount")
        negatives = {item["negative_fields"][0] for item in negative["items"]}
        assert negatives == {"amount", "used_amount"}
        for item in negative["items"]:
            assert set(item["amounts"]) == {"amount", "allocated_amount", "used_amount"}

    def test_stale_details_exclude_closed_records(self, real_db_session):
        _seed_full(real_db_session)
        payload = BusinessHealthService(real_db_session, year=YEAR).collect()

        projects = _get(payload, "stale_projects")
        assert [item["status"] for item in projects["items"]] == ["in_progress"]
        assert projects["items"][0]["updated_at"]

        funds = _get(payload, "stale_funds")
        assert [item["status"] for item in funds["items"]] == ["pending"]

    def test_organization_missing_entries(self, real_db_session):
        _seed_full(real_db_session)
        payload = BusinessHealthService(real_db_session, year=YEAR).collect()
        assert _get(payload, "village_organization_missing")["entry"] == "/organizations"
        assert _get(payload, "project_organization_missing")["entry"] == "/projects"
        assert _get(payload, "fund_organization_missing")["entry"] == "/funds"

    def test_no_pii_in_payload(self, real_db_session):
        _seed_full(real_db_session)
        payload = BusinessHealthService(real_db_session, year=YEAR).collect()
        text = json.dumps(payload, ensure_ascii=False)
        # 项目/经费名称、人名、手机号一律不得出境
        for leaked in ("张三", "13812345678", "张三经费", "张三项目", "长期未动经费", "负数申请经费"):
            assert leaked not in text
        # 项目/经费明细只给 id（名称字段可能夹带个人姓名）
        for key in (
            "fund_used_exceeds_amount",
            "fund_negative_amount",
            "stale_projects",
            "stale_funds",
        ):
            for item in _get(payload, key)["items"]:
                assert "name" not in item

    def test_item_limit_truncates(self, real_db_session):
        _seed_full(real_db_session)
        payload = BusinessHealthService(real_db_session, year=YEAR, item_limit=1).collect()
        annual = _get(payload, "village_annual_missing")
        assert annual["count"] == 3
        assert len(annual["items"]) == 1
        assert annual["items_truncated"] is True
        assert payload["item_limit"] == 1
        # 其它项明细本来就少于上限 → 不误报截断
        assert _get(payload, "village_organization_missing")["items_truncated"] is False

    def test_stale_days_threshold(self, real_db_session):
        _seed_full(real_db_session)
        default_payload = BusinessHealthService(real_db_session, year=YEAR).collect()
        assert _get(default_payload, "stale_projects")["count"] == 1

        tight_payload = BusinessHealthService(
            real_db_session, year=YEAR, stale_days=7
        ).collect()
        assert tight_payload["stale_days"] == 7
        assert _get(tight_payload, "stale_projects")["count"] == 2

    def test_year_parameter_and_default_year(self, real_db_session):
        _seed_full(real_db_session)
        explicit = BusinessHealthService(real_db_session, year=YEAR).collect()
        assert explicit["year"] == YEAR
        assert _get(explicit, "village_annual_missing")["count"] == 3

        defaulted = BusinessHealthService(real_db_session).collect()
        assert defaulted["year"] == date.today().year
        # 当前年度没有任何年度数据 → 4 个在册村全部缺失
        assert _get(defaulted, "village_annual_missing")["count"] == 4


# ==================== 端点：权限 / 参数 / 注册 ====================


def _override_user(client, user):
    from app.core.security import get_current_user

    client.app.dependency_overrides[get_current_user] = lambda: user
    return client


@pytest.fixture
def admin_user():
    return Mock(
        id=1,
        username="admin",
        role="admin",
        is_superuser=True,
        is_active=True,
        organization_id=1,
    )


def _path(query=""):
    suffix = ("?" + query) if query else ""
    return "/api/v1/system/business-health" + suffix


class TestEndpoint:
    def test_route_registered(self):
        from app.main import app

        assert _path() in {route.path for route in app.routes}

    def test_unauthenticated_rejected(self, client):
        resp = client.get(_path())
        assert resp.status_code in (401, 403)

    def test_non_admin_forbidden(self, client):
        user = Mock(id=2, username="u", role="user", is_superuser=False, is_active=True)
        resp = _override_user(client, user).get(_path())
        assert resp.status_code == 403

    def test_empty_database_ok(self, client, admin_user):
        _override_user(client, admin_user)
        resp = client.get(_path())
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["status"] == "healthy"
        assert data["summary"]["check_count"] == len(CHECK_KEYS)
        assert data["summary"]["issue_count"] == 0
        for check in data["checks"]:
            assert check["count"] == 0
            assert check["items"] == []

    def test_full_database_ok(self, client_with_db, admin_user):
        client, db = client_with_db
        _seed_full(db)
        _override_user(client, admin_user)
        resp = client.get(_path("year=%s" % YEAR))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "warning"
        assert data["year"] == YEAR
        assert data["summary"]["issue_count"] == 12
        for check in data["checks"]:
            assert set(check) == CHECK_ITEM_KEYS

    def test_query_parameters_applied(self, client_with_db, admin_user):
        client, db = client_with_db
        _seed_full(db)
        _override_user(client, admin_user)
        resp = client.get(_path("year=%s&stale_days=7&item_limit=1" % YEAR))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["year"] == YEAR
        assert data["stale_days"] == 7
        assert data["item_limit"] == 1
        annual = next(c for c in data["checks"] if c["key"] == "village_annual_missing")
        assert annual["count"] == 3
        assert len(annual["items"]) == 1
        assert annual["items_truncated"] is True

    def test_invalid_parameters_rejected(self, client, admin_user):
        _override_user(client, admin_user)
        assert client.get(_path("year=1999")).status_code == 422
        assert client.get(_path("stale_days=0")).status_code == 422
        assert client.get(_path("item_limit=%s" % (MAX_ITEM_LIMIT + 1))).status_code == 422

    def test_response_has_no_pii(self, client_with_db, admin_user):
        client, db = client_with_db
        _seed_full(db)
        _override_user(client, admin_user)
        resp = client.get(_path("year=%s" % YEAR))
        assert resp.status_code == 200
        for leaked in ("张三", "13812345678", "长期未动经费"):
            assert leaked not in resp.text


# ==================== 源码静态守卫：禁止 f-string 拼 SQL ====================


class TestSqlSafety:
    def test_scanner_uses_orm_only(self):
        backend_dir = Path(__file__).resolve().parents[2]
        sources = [
            (backend_dir / "app" / "services" / "business_health_service.py").read_text(
                encoding="utf-8"
            ),
            (backend_dir / "app" / "api" / "v1" / "system" / "business_health.py").read_text(
                encoding="utf-8"
            ),
        ]
        for source in sources:
            # 无原生 SQL 执行入口 → 不存在拼接面
            assert "text(" not in source
            assert "execute(" not in source
            assert "SELECT" not in source.upper()
            assert "f\"SELECT" not in source
