"""年度数据滚动填报（prefill 差异元信息 + 批量沿用）回归测试。

覆盖：
- 服务层纯函数：板块白名单规范化、空值判定、字段白名单/标签、成员快照、状态计算；
- GET /supported-villages/{id}/yearly/{year}/prefill：逐字段差异、默认取上年、
  from_year 自定义/非法、无上年数据友好提示、数据域（404/403/跨村隔离）；
- POST /supported-villages/{id}/yearly/{year}/rollforward：只填空不覆盖、
  overwrite 二选一、板块白名单、元数据列不写、委员会成员子表沿用、
  无上年数据 200 友好返回、跨村隔离、单事务原子回滚。
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.security import get_current_user
from app.models.supported_village import (
    VillageCommitteeInfo,
    VillageCommitteeMember,
    VillageIncome,
    VillagePopulation,
)
from app.services import yearly_rollforward_service as svc

BASE = "/api/v1/supported-villages"


# ── 测试辅助 ──────────────────────────────────────────────────

def _create_village(client, name="滚动测试村"):
    resp = client.post(
        BASE,
        json={
            "village_name": name,
            "province": "贵州省",
            "city": "毕节市",
            "county": "大方县",
            "department": "某部",
            "support_unit": "某单位",
        },
    )
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    return (body.get("data") or body)["id"]


def _save_section(client, village_id, year, section, payload):
    resp = client.post(f"{BASE}/{village_id}/yearly/{year}/{section}", json=payload)
    assert resp.status_code == 200, resp.text
    return resp


def _prefill(client, village_id, year, **params):
    return client.get(f"{BASE}/{village_id}/yearly/{year}/prefill", params=params or None)


def _section_of(payload, key):
    return next(item for item in payload["sections"] if item["key"] == key)


def _field_of(section, field):
    return next(item for item in section["fields"] if item["field"] == field)


def _row(db, model, village_id, year):
    return (
        db.query(model)
        .filter(model.supported_village_id == village_id, model.year == year)
        .first()
    )


# ═══════════════════════════════════════════════════════════════
#  服务层纯函数
# ═══════════════════════════════════════════════════════════════

class TestNormalizeSectionKeys:
    def test_empty_rejected(self):
        with pytest.raises(svc.RollforwardError, match="不能为空"):
            svc.normalize_section_keys([])

    def test_unknown_rejected_with_available_hint(self):
        with pytest.raises(svc.UnknownSectionError) as exc:
            svc.normalize_section_keys(["income", "unknown-section"])
        assert "unknown-section" in str(exc.value)
        assert "population" in str(exc.value)

    def test_alias_normalized_and_deduped(self):
        result = svc.normalize_section_keys(
            ["force_investment", "force-investment", " income ", "income"]
        )
        assert result == ["force-investment", "income"]

    def test_blank_and_non_string_rejected(self):
        with pytest.raises(svc.UnknownSectionError):
            svc.normalize_section_keys(["", None])


class TestIsEmpty:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, True),
            ("", True),
            ("   ", True),
            (0, True),
            (0.0, True),
            (False, True),
            (5, False),
            (1.5, False),
            (True, False),
            ("总户数", False),
            (["a"], False),
        ],
    )
    def test_is_empty(self, value, expected):
        assert svc._is_empty(value) is expected


class TestFieldHelpers:
    def test_field_label_comment_and_fallback(self):
        assert svc._field_label(SimpleNamespace(name="x", comment=" 总户数 ")) == "总户数"
        assert svc._field_label(SimpleNamespace(name="x", comment="")) == "x"
        assert svc._field_label(SimpleNamespace(name="x", comment=None)) == "x"

    def test_field_columns_excludes_metadata(self):
        names = [column.name for column in svc._field_columns(VillagePopulation)]
        assert "total_households" in names
        for skipped in ("id", "supported_village_id", "year", "created_at", "updated_at"):
            assert skipped not in names

    def test_field_status_three_states(self):
        assert svc._field_status(False, False) == svc.STATUS_BLANK
        assert svc._field_status(True, True) == svc.STATUS_KEEP
        assert svc._field_status(True, False) == svc.STATUS_COPY

    def test_members_snapshot_without_row(self, auth_client_with_db):
        client, db = auth_client_with_db
        assert svc._members_snapshot(db, None) == []
        assert svc._members_snapshot(db, SimpleNamespace(id=None)) == []
        assert svc._load_members(db, None) == []


# ═══════════════════════════════════════════════════════════════
#  GET prefill
# ═══════════════════════════════════════════════════════════════

class TestPrefillApi:
    def test_field_level_diff_metadata(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "population",
                      {"total_households": 120, "total_population": 300})
        _save_section(client, vid, 2025, "population", {"total_population": 280})

        resp = _prefill(client, vid, 2025)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        data = body["data"]
        assert body["message"] == data["message"]
        assert data["villageId"] == vid
        assert data["year"] == 2025
        assert data["fromYear"] == 2024
        assert data["hasPreviousData"] is True
        assert len(data["sections"]) == 11

        population = _section_of(data, "population")
        assert population["title"] == "人口数据"
        assert population["hasPreviousData"] is True
        households = _field_of(population, "total_households")
        assert households["label"] == "总户数"
        assert households["previousValue"] == 120
        assert households["currentValue"] in (0, None)
        assert households["hasPreviousValue"] is True
        assert households["status"] == "copy"
        population_field = _field_of(population, "total_population")
        assert population_field["previousValue"] == 300
        assert population_field["currentValue"] == 280
        assert population_field["status"] == "keep"
        labor = _field_of(population, "labor_force")
        assert labor["hasPreviousValue"] is False
        assert labor["status"] == "blank"
        assert population["copyableCount"] == 1
        assert population["keptCount"] == 1

        # 无上年数据的板块：全部字段 blank；委员会板块附带 members 虚拟字段
        income = _section_of(data, "income")
        assert income["hasPreviousData"] is False
        assert all(field["status"] == "blank" for field in income["fields"])
        committee = _section_of(data, "committee")
        members_field = _field_of(committee, "members")
        assert members_field["status"] == "blank"
        assert members_field["previousValue"] == []

        summary = data["summary"]
        assert summary["sectionCount"] == 11
        assert summary["availableSectionCount"] == 1
        assert summary["copyableFieldCount"] == 1
        assert summary["keptFieldCount"] == 1
        assert "可" in data["message"]

    def test_explicit_from_year(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2023, "income", {"per_capita_income": 1.2})

        resp = _prefill(client, vid, 2025, from_year=2023)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["fromYear"] == 2023
        income = _section_of(data, "income")
        assert income["hasPreviousData"] is True
        assert _field_of(income, "per_capita_income")["status"] == "copy"

    def test_from_year_same_as_year_rejected(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        resp = _prefill(client, vid, 2025, from_year=2025)
        assert resp.status_code == 400, resp.text
        assert "不能相同" in resp.json()["detail"]

    def test_no_previous_data_returns_friendly_payload(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        resp = _prefill(client, vid, 2031)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["hasPreviousData"] is False
        assert data["summary"]["availableSectionCount"] == 0
        assert "没有可沿用" in data["message"]
        assert all(section["hasPreviousData"] is False for section in data["sections"])

    def test_previous_record_without_values_message(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        db.add(VillagePopulation(supported_village_id=vid, year=2024))
        db.commit()
        data = _prefill(client, vid, 2025).json()["data"]
        assert data["hasPreviousData"] is True
        assert data["summary"]["copyableFieldCount"] == 0
        assert data["summary"]["keptFieldCount"] == 0
        assert "没有可沿用的有效字段" in data["message"]

    def test_all_fields_filled_message(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "population",
                      {"total_households": 120, "total_population": 300})
        _save_section(client, vid, 2025, "population",
                      {"total_households": 130, "total_population": 310})
        data = _prefill(client, vid, 2025).json()["data"]
        assert data["summary"]["copyableFieldCount"] == 0
        assert data["summary"]["keptFieldCount"] == 2
        assert "均已填写" in data["message"]

    def test_committee_members_copy_and_keep_status(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        _save_section(
            client, vid, 2024, "committee",
            {"overview": "2024年概况",
             "members": [{"name": "张三", "position": "主任", "isVeteran": True}]},
        )
        # 本年度已有成员 → keep
        _save_section(
            client, vid, 2025, "committee",
            {"members": [{"name": "李四", "position": "书记"}]},
        )
        data = _prefill(client, vid, 2025).json()["data"]
        members_field = _field_of(_section_of(data, "committee"), "members")
        assert members_field["status"] == "keep"
        assert members_field["hasCurrentValue"] is True
        assert members_field["currentValue"][0]["name"] == "李四"

        # 本年度委员会存在但无成员 → copy（成员子表可沿用）
        _save_section(client, vid, 2026, "committee", {"overview": "2026年概况"})
        data2 = _prefill(client, vid, 2026, from_year=2024).json()["data"]
        members_field2 = _field_of(_section_of(data2, "committee"), "members")
        assert members_field2["status"] == "copy"
        assert members_field2["previousValue"][0]["name"] == "张三"

    def test_unknown_village_404(self, auth_client_with_db):
        client, _db = auth_client_with_db
        resp = _prefill(client, 999999, 2025)
        assert resp.status_code == 404

    def test_cross_org_forbidden_403(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        regular = Mock()
        regular.id = 2
        regular.role = "user"
        regular.is_superuser = False
        regular.organization_id = 2
        client.app.dependency_overrides[get_current_user] = lambda: regular
        resp = _prefill(client, vid, 2025)
        assert resp.status_code == 403

    def test_cross_village_isolation(self, auth_client_with_db):
        client, _db = auth_client_with_db
        village_a = _create_village(client, name="甲村")
        village_b = _create_village(client, name="乙村")
        _save_section(client, village_a, 2024, "income", {"per_capita_income": 9.9})
        data = _prefill(client, village_b, 2025).json()["data"]
        assert data["hasPreviousData"] is False
        assert _section_of(data, "income")["hasPreviousData"] is False


# ═══════════════════════════════════════════════════════════════
#  POST rollforward
# ═══════════════════════════════════════════════════════════════

class TestRollforwardApi:
    def test_fill_empty_creates_and_preserves(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "population",
                      {"total_households": 120, "total_population": 300})
        _save_section(client, vid, 2024, "income",
                      {"per_capita_income": 1.5, "collective_income": 2.5})
        _save_section(client, vid, 2025, "population", {"total_population": 280})

        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["population", "income"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["mode"] == "fill_empty"
        assert data["hasPreviousData"] is True
        assert data["createdSections"] == ["income"]
        assert data["appliedSections"] == ["population", "income"]
        assert data["appliedFields"] == 3
        assert data["keptFields"] == 1
        assert data["skippedSections"] == []
        assert "已从 2024 年沿用 3 项字段" in resp.json()["message"]

        population_2025 = _row(db, VillagePopulation, vid, 2025)
        assert population_2025.total_households == 120
        assert population_2025.total_population == 280  # 非空值未被覆盖
        income_2025 = _row(db, VillageIncome, vid, 2025)
        assert income_2025 is not None
        assert income_2025.per_capita_income == 1.5
        assert income_2025.collective_income == 2.5
        # 元数据列不参与沿用：目标行是独立新行
        assert income_2025.id is not None
        assert income_2025.supported_village_id == vid
        assert income_2025.year == 2025

    def test_default_does_not_overwrite_existing_values(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "population", {"total_population": 300})
        _save_section(client, vid, 2025, "population", {"total_population": 280})
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["population"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["appliedFields"] == 0
        assert data["keptFields"] == 1
        assert data["sections"]["population"]["keptFields"] == ["total_population"]
        assert _row(db, VillagePopulation, vid, 2025).total_population == 280
        # 上年有数据但本年度字段均已填写 → 友好提示，不报错
        assert "未做修改" in resp.json()["message"]

    def test_overwrite_true_replaces_existing_values(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "population",
                      {"total_households": 120, "total_population": 300})
        _save_section(client, vid, 2025, "population",
                      {"total_households": 130, "total_population": 280})
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["population"], "from_year": 2024, "overwrite": True},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["mode"] == "overwrite"
        assert data["keptFields"] == 0
        assert data["appliedFields"] == 2
        row = _row(db, VillagePopulation, vid, 2025)
        assert row.total_households == 120
        assert row.total_population == 300

    def test_unknown_section_rejected_400(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["unknown-section"]},
        )
        assert resp.status_code == 400, resp.text
        assert "未知的年度数据板块" in resp.json()["detail"]

    def test_empty_section_keys_pydantic_422(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": []},
        )
        assert resp.status_code == 422, resp.text

    def test_from_year_same_as_year_rejected_400(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["population"], "from_year": 2025},
        )
        assert resp.status_code == 400, resp.text
        assert "不能相同" in resp.json()["detail"]

    def test_no_previous_data_returns_friendly_200(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        resp = client.post(
            f"{BASE}/{vid}/yearly/2031/rollforward",
            json={"section_keys": list(svc.YEARLY_SECTION_MODELS)},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["hasPreviousData"] is False
        assert data["appliedFields"] == 0
        assert data["createdSections"] == []
        assert len(data["skippedSections"]) == 11
        assert "没有可沿用的年度数据" in resp.json()["message"]
        assert _row(db, VillagePopulation, vid, 2031) is None

    def test_partial_sections_skipped(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "population", {"total_population": 300})
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["population", "income"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["createdSections"] == ["population"]
        assert data["skippedSections"] == [
            {"section": "income", "reason": "no_previous_data"}
        ]

    def test_underscore_alias_accepted(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "force-investment", {"senior_leader_visits": 6})
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["force_investment"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        from app.models.supported_village import ForceInvestment
        assert _row(db, ForceInvestment, vid, 2025).senior_leader_visits == 6

    def test_committee_members_copied_when_created(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(
            client, vid, 2024, "committee",
            {"overview": "2024年概况",
             "members": [
                 {"name": "张三", "position": "主任", "isVeteran": True},
                 {"name": "王五", "position": "委员"},
             ]},
        )
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["committee"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["sections"]["committee"]["memberCount"] == 2
        assert "members" in data["sections"]["committee"]["writtenFields"]
        info = _row(db, VillageCommitteeInfo, vid, 2025)
        assert info.overview == "2024年概况"
        members = (
            db.query(VillageCommitteeMember)
            .filter(VillageCommitteeMember.committee_info_id == info.id)
            .order_by(VillageCommitteeMember.id)
            .all()
        )
        assert [m.name for m in members] == ["张三", "王五"]
        assert members[0].is_veteran is True

    def test_committee_members_kept_without_overwrite(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(
            client, vid, 2024, "committee",
            {"overview": "2024年概况", "members": [{"name": "张三"}]},
        )
        _save_section(
            client, vid, 2025, "committee",
            {"overview": "2025年概况", "members": [{"name": "新人"}]},
        )
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["committee"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "members" in data["sections"]["committee"]["keptFields"]
        assert "members" not in data["sections"]["committee"]["writtenFields"]
        info = _row(db, VillageCommitteeInfo, vid, 2025)
        members = (
            db.query(VillageCommitteeMember)
            .filter(VillageCommitteeMember.committee_info_id == info.id)
            .all()
        )
        assert [m.name for m in members] == ["新人"]
        assert info.overview == "2025年概况"

    def test_committee_members_replaced_with_overwrite(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(
            client, vid, 2024, "committee",
            {"overview": "2024年概况", "members": [{"name": "张三"}]},
        )
        _save_section(
            client, vid, 2025, "committee",
            {"overview": "2025年概况", "members": [{"name": "新人"}]},
        )
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["committee"], "from_year": 2024, "overwrite": True},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["sections"]["committee"]["memberCount"] == 1
        info = _row(db, VillageCommitteeInfo, vid, 2025)
        members = (
            db.query(VillageCommitteeMember)
            .filter(VillageCommitteeMember.committee_info_id == info.id)
            .all()
        )
        assert [m.name for m in members] == ["张三"]

    def test_committee_without_members_copies_scalars_only(self, auth_client_with_db):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "committee", {"overview": "2024年概况"})
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["committee"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        stats = resp.json()["data"]["sections"]["committee"]
        assert stats["memberCount"] == 0
        assert "members" not in stats["writtenFields"]
        info = _row(db, VillageCommitteeInfo, vid, 2025)
        assert info.overview == "2024年概况"
        assert (
            db.query(VillageCommitteeMember)
            .filter(VillageCommitteeMember.committee_info_id == info.id)
            .count()
            == 0
        )

    def test_unknown_village_404(self, auth_client_with_db):
        client, _db = auth_client_with_db
        resp = client.post(
            f"{BASE}/999999/yearly/2025/rollforward",
            json={"section_keys": ["population"]},
        )
        assert resp.status_code == 404

    def test_cross_org_forbidden_403(self, auth_client_with_db):
        client, _db = auth_client_with_db
        vid = _create_village(client)
        regular = Mock()
        regular.id = 2
        regular.role = "user"
        regular.is_superuser = False
        regular.organization_id = 2
        client.app.dependency_overrides[get_current_user] = lambda: regular
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["population"]},
        )
        assert resp.status_code == 403

    def test_cross_village_isolation(self, auth_client_with_db):
        client, db = auth_client_with_db
        village_a = _create_village(client, name="甲村")
        village_b = _create_village(client, name="乙村")
        _save_section(client, village_a, 2024, "income", {"per_capita_income": 9.9})
        resp = client.post(
            f"{BASE}/{village_b}/yearly/2025/rollforward",
            json={"section_keys": ["income"], "from_year": 2024},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["hasPreviousData"] is False
        assert _row(db, VillageIncome, village_b, 2025) is None
        # 甲村数据未被波及
        assert _row(db, VillageIncome, village_a, 2025) is None
        assert _row(db, VillageIncome, village_a, 2024).per_capita_income == 9.9

    def test_atomic_rollback_on_section_failure(self, auth_client_with_db, monkeypatch):
        client, db = auth_client_with_db
        vid = _create_village(client)
        _save_section(client, vid, 2024, "population", {"total_population": 300})
        _save_section(client, vid, 2024, "income", {"per_capita_income": 1.5})

        original = svc._apply_section
        calls = {"count": 0}

        def boom(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 2:
                raise RuntimeError("模拟第二个板块写入失败")
            return original(*args, **kwargs)

        monkeypatch.setattr(svc, "_apply_section", boom)
        resp = client.post(
            f"{BASE}/{vid}/yearly/2025/rollforward",
            json={"section_keys": ["population", "income"], "from_year": 2024},
        )
        assert resp.status_code == 500, resp.text
        # 第一个板块已写入的行必须随事务回滚，不能留半套数据
        assert _row(db, VillagePopulation, vid, 2025) is None
        assert _row(db, VillageIncome, vid, 2025) is None
