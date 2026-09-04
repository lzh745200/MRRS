# -*- coding: utf-8 -*-
"""帮扶村数据持久化往返回归测试（真实 SQLite 会话，不 patch camel_to_snake 中间件）。

本文件针对任务#4 的"数据保存成功但重置为 0 / 消失"缺陷，使用 conftest 的
``client_with_db`` fixture（内存 SQLite + 共享 Session），走完整 FastAPI 中间件栈
（含 CamelToSnakeMiddleware），验证真实持久化往返，弥补原
``test_supported_village_api.py`` 全 MagicMock + patch 掉中间件导致的测试盲区。

覆盖：
- H2b（关键根因）：经费明细 camelCase 字段经中间件转 snake_case 后仍能正确落库
  （TransitionFundingItem 通过 AliasChoices 兼容），保存后总额非 0。
- H1：保存经费后 list?with_summary=true 的 summary.total_investment 非 0，
  且等于 SupportedVillage.transition_fund_military_total + transition_fund_local_total。
- H2：空 items 允许将经费清零（尊重用户主动清空意图），且当原有非零经费被清零时
  写入 WorkLog 审计日志用于追溯。
- 数据隔离：跨组织普通用户读不到他组织创建的帮扶村（apply_scope_filter 生效）。
"""
from unittest.mock import Mock

from app.core.security import get_current_user
from app.models.supported_village import (SupportedVillage, VillageCommitteeMember,
                                          VillageIncome)
from app.models.work_log import WorkLog

BASE = "/api/v1/supported-villages"


def _make_user(uid, org, role="admin"):
    """构造 Mock 用户；admin 不受数据隔离限制，user 受组织隔离。"""
    user = Mock()
    user.id = uid
    user.username = f"user{uid}"
    user.role = role
    user.is_superuser = (role == "admin")
    user.is_active = True
    user.organization_id = org
    user.permissions_list = ["*"] if role == "admin" else ["read", "write"]
    user.data_scope = None
    user.failed_login_count = 0
    user.locked_until = None
    return user


def _set_user(client, user):
    client.app.dependency_overrides[get_current_user] = lambda: user


def _create_village(client, name="持久化测试村"):
    resp = client.post(BASE, json={
        "village_name": name,
        "province": "贵州省",
        "county": "测试县",
    })
    assert resp.status_code in (200, 201), f"创建帮扶村失败: {resp.status_code} {resp.text[:200]}"
    vid = resp.json().get("data", {}).get("id")
    assert vid, "创建后应返回有效 village_id"
    return vid


def _save_funding(client, vid, items):
    resp = client.post(f"{BASE}/{vid}/transition-funding", json={"items": items})
    assert resp.status_code == 200, f"保存经费失败: {resp.status_code} {resp.text[:200]}"
    return resp


def _get_summary(client):
    resp = client.get(f"{BASE}?with_summary=true")
    assert resp.status_code == 200, f"列表查询失败: {resp.status_code} {resp.text[:200]}"
    data = resp.json().get("data", {})
    return data.get("summary") or {}, data.get("items", [])


class TestFundingPersistenceRoundTrip:
    """H2b + H1：经费保存后真实落库，并在列表 KPI 中正确反映。"""

    def test_camelcase_funding_persists_and_summary_nonzero(self, client_with_db):
        client, db = client_with_db
        admin = _make_user(1, org=1, role="admin")
        _set_user(client, admin)

        vid = _create_village(client, "H2b经费落库村")
        # 前端以 camelCase 提交；CamelToSnakeMiddleware 会把键名转为 snake_case。
        # 修复前 TransitionFundingItem 字段名(camelCase)无法命中 → 静默落 0。
        _save_funding(client, vid, [
            {"year": 2024, "militaryInvestment": 100.0,
             "localInvestment": 50.0, "totalInvestment": 150.0},
        ])

        # 直接查真实 DB 会话，确认列已落库（非 0）
        db.expire_all()
        village = db.query(SupportedVillage).filter(SupportedVillage.id == vid).first()
        assert village is not None
        assert float(village.transition_fund_military_total) == 100.0, (
            "专项投入未正确落库——camelCase 字段可能被中间件转换后丢失(H2b)"
        )
        assert float(village.transition_fund_local_total) == 50.0

        # H1：列表 KPI summary.total_investment 应等于列聚合值且非 0
        summary, _ = _get_summary(client)
        assert summary.get("total_investment") == 150.0, (
            f"H1 KPI total_investment 应反映已保存经费(150.0)，实际 {summary.get('total_investment')!r}"
        )
        assert summary.get("total", 0) >= 1

    def test_get_transition_funding_roundtrip(self, client_with_db):
        """保存后再读取明细，金额应与提交一致（端到端往返）。"""
        client, db = client_with_db
        _set_user(client, _make_user(1, org=1))

        vid = _create_village(client, "经费往返村")
        _save_funding(client, vid, [
            {"year": 2023, "militaryInvestment": 30.0, "localInvestment": 20.0, "totalInvestment": 50.0},
            {"year": 2024, "militaryInvestment": 70.0, "localInvestment": 10.0, "totalInvestment": 80.0},
        ])
        resp = client.get(f"{BASE}/{vid}/transition-funding")
        assert resp.status_code == 200
        items = resp.json().get("data", [])
        by_year = {int(it["year"]): it for it in items}
        assert by_year[2023]["militaryInvestment"] == 30.0
        assert by_year[2024]["localInvestment"] == 10.0
        # 汇总列 = 各年度之和
        db.expire_all()
        village = db.query(SupportedVillage).filter(SupportedVillage.id == vid).first()
        assert float(village.transition_fund_military_total) == 100.0
        assert float(village.transition_fund_local_total) == 30.0


class TestEmptyItemsClearSemantics:
    """H2：空 items 允许清零 + 非零→零写审计日志（与前端 fundingLoadFailed 语义对齐）。"""

    def test_empty_items_clears_funding_and_writes_audit(self, client_with_db):
        client, db = client_with_db
        admin = _make_user(1, org=1, role="admin")
        _set_user(client, admin)

        vid = _create_village(client, "H2清空村")
        # 先保存非零经费
        _save_funding(client, vid, [
            {"year": 2024, "militaryInvestment": 100.0, "localInvestment": 50.0, "totalInvestment": 150.0},
        ])
        db.expire_all()
        village = db.query(SupportedVillage).filter(SupportedVillage.id == vid).first()
        assert float(village.transition_fund_military_total) == 100.0

        # 用户主动清空所有经费行 → 提交空 items
        _save_funding(client, vid, [])

        db.expire_all()
        village = db.query(SupportedVillage).filter(SupportedVillage.id == vid).first()
        assert float(village.transition_fund_military_total or 0) == 0.0, (
            "空 items 应尊重用户主动清空意图，将专项投入覆盖为 0"
        )
        assert float(village.transition_fund_local_total or 0) == 0.0
        assert village.transition_fund_items in ("[]", "", None)

        # KPI 同步归零
        summary, _ = _get_summary(client)
        assert summary.get("total_investment") == 0.0

        # 审计留痕：非零经费被清零应写入 WorkLog
        logs = (
            db.query(WorkLog)
            .filter(WorkLog.category == "supported_village")
            .all()
        )
        assert any("转移支付资金清空" in (log.content or "") for log in logs), (
            "原有非零经费被空 items 清零时应写 write_work_log 审计日志用于追溯"
        )

    def test_empty_items_on_zero_village_no_audit(self, client_with_db):
        """原本就是 0 的村提交空 items → 正常清零，不产生多余审计日志。"""
        client, db = client_with_db
        _set_user(client, _make_user(1, org=1, role="admin"))

        vid = _create_village(client, "H2零经费村")
        _save_funding(client, vid, [])
        db.expire_all()
        village = db.query(SupportedVillage).filter(SupportedVillage.id == vid).first()
        assert float(village.transition_fund_military_total or 0) == 0.0

        logs = (
            db.query(WorkLog)
            .filter(WorkLog.category == "supported_village")
            .all()
        )
        assert not any("转移支付资金清空" in (log.content or "") for log in logs), (
            "原总额为 0 时提交空 items 不应触发清零审计日志"
        )


class TestDataIsolationReadBack:
    """数据隔离：跨组织普通用户读不到他组织创建的帮扶村及其经费 KPI。"""

    def test_cross_org_user_cannot_see_village(self, client_with_db):
        client, db = client_with_db
        admin_org1 = _make_user(1, org=1, role="admin")
        regular_org2 = _make_user(2, org=2, role="user")

        # 组织1管理员创建并保存经费
        _set_user(client, admin_org1)
        vid = _create_village(client, "组织1隔离村")
        _save_funding(client, vid, [
            {"year": 2024, "militaryInvestment": 200.0, "localInvestment": 0.0, "totalInvestment": 200.0},
        ])
        summary1, items1 = _get_summary(client)
        assert any(it.get("id") == vid for it in items1 if isinstance(it, dict)), (
            "创建者(管理员)应能看到本组织帮扶村"
        )
        assert summary1.get("total_investment") == 200.0

        # 组织2普通用户列表 → 不应看到组织1的村
        _set_user(client, regular_org2)
        resp = client.get(BASE)
        assert resp.status_code == 200, (
            f"跨组织普通用户列表应静默返回 200，实际 {resp.status_code} {resp.text[:200]}"
        )
        data2 = resp.json().get("data", {})
        items2 = data2.get("items", []) if isinstance(data2, dict) else data2
        assert not any(it.get("id") == vid for it in items2 if isinstance(it, dict)), (
            "数据隔离失效：组织2普通用户不应看到组织1创建的帮扶村"
        )

        # 详情跨组织访问 → 403
        resp_detail = client.get(f"{BASE}/{vid}")
        assert resp_detail.status_code == 403, (
            f"跨组织访问帮扶村详情应 403，实际 {resp_detail.status_code}"
        )


class TestCommitteeMemberVeteranRoundTrip:
    """H2c：村委会成员 is_veteran 经中间件后仍真实落库（消除静默 False）。"""

    def test_is_veteran_persists_true_and_false(self, client_with_db):
        client, db = client_with_db
        _set_user(client, _make_user(1, org=1, role="admin"))

        vid = _create_village(client, "H2c村委会村")
        # 前端提交 camelCase isVeteran；中间件递归转换数组内键名为 is_veteran。
        resp = client.post(f"{BASE}/{vid}/committee", json={
            "year": 2024,
            "overview": "2024年概况",
            "members": [
                {"name": "张三", "position": "主任", "phone": "13800000001",
                 "isVeteran": True, "remark": "退役"},
                {"name": "李四", "position": "委员", "phone": "13800000002",
                 "isVeteran": False, "remark": ""},
            ],
        })
        assert resp.status_code == 200, f"保存村委失败: {resp.status_code} {resp.text[:200]}"

        db.expire_all()
        members = (
            db.query(VillageCommitteeMember)
            .filter(VillageCommitteeMember.supported_village_id == vid)
            .all()
        )
        by_name = {m.name: m for m in members}
        assert set(by_name) == {"张三", "李四"}
        assert by_name["张三"].is_veteran is True, (
            "提交 isVeteran:True 的退役军人标记应真实落库为 True"
            "（H2c：中间件转 is_veteran 后原硬编码读 isVeteran 恒取不到 → 静默落 False）"
        )
        assert by_name["李四"].is_veteran is False, "isVeteran:False 应落库为 False"


class TestYearlyCopyRoundTrip:
    """H2d：/yearly/copy 经中间件后不再恒 422，年度数据真实复制。"""

    def test_yearly_copy_succeeds_and_copies_data(self, client_with_db):
        client, db = client_with_db
        _set_user(client, _make_user(1, org=1, role="admin"))

        vid = _create_village(client, "H2d年度复制村")
        # 先在 2023 年写入收入数据
        r_save = client.post(f"{BASE}/{vid}/yearly/2023/income", json={
            "perCapitaIncome": 12345.0,
            "collectiveIncome": 678.0,
        })
        assert r_save.status_code == 200, (
            f"保存 2023 收入失败: {r_save.status_code} {r_save.text[:200]}"
        )

        # 复制 2023 → 2024：修复前 fromYear/toYear 被中间件转 from_year/to_year，
        # Pydantic 必填 camelCase 字段缺失 → 恒 422。
        r_copy = client.post(f"{BASE}/{vid}/yearly/copy", json={
            "fromYear": 2023, "toYear": 2024,
        })
        assert r_copy.status_code == 200, (
            f"H2d：/yearly/copy 应返回 200（修复前恒 422），实际 "
            f"{r_copy.status_code} {r_copy.text[:200]}"
        )

        # 目标年份应真实复制到数据
        r_get = client.get(f"{BASE}/{vid}/yearly/2024")
        assert r_get.status_code == 200
        income = r_get.json().get("data", {}).get("income")
        assert income is not None, "2024 年 income 应由复制生成"
        assert income.get("perCapitaIncome") == 12345.0
        assert income.get("collectiveIncome") == 678.0

        # 直接查真实 DB 会话双确认
        db.expire_all()
        row = (
            db.query(VillageIncome)
            .filter(VillageIncome.supported_village_id == vid, VillageIncome.year == 2024)
            .first()
        )
        assert row is not None
        assert float(row.per_capita_income) == 12345.0
