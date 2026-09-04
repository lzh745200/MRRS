"""app.services.fund_service.FundService 覆盖补充测试（真实 SQLite 会话）。

覆盖 get_funds（各过滤分支 + 分页）、get_fund、create_fund、
create_fund_for_user（type 兼容/auto_commit 双分支）、_ensure_zj_code、
update_fund、delete_fund、batch_update_status（状态机校验）。
"""
import datetime as _dt

import pytest

from app.models.fund import Fund
from app.services.fund_service import FundService, FUND_TYPES


class _StubFundCreate:
    """替代 Pydantic FundCreate：仅提供 model_dump(exclude_none=True)。"""

    def __init__(self, payload):
        self._payload = payload

    def model_dump(self, exclude_none=False):
        return dict(self._payload)


@pytest.fixture
def svc(real_db_session):
    return FundService(real_db_session)


def _mkfund(db, **kw):
    f = Fund(**kw)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


class TestGetFunds:
    def test_no_filter_returns_all(self, svc, real_db_session):
        _mkfund(real_db_session, name="A", amount=1, status="pending")
        _mkfund(real_db_session, name="B", amount=2, status="approved")
        out = svc.get_funds()
        assert out["total"] == 2
        assert len(out["items"]) == 2
        assert out["page"] == 1 and out["page_size"] == 20

    def test_filters_by_status_village_project_org(self, svc, real_db_session):
        _mkfund(real_db_session, name="A", status="pending", village_id=1,
                project_id=2, organization_id=3)
        _mkfund(real_db_session, name="B", status="approved", village_id=9)
        assert svc.get_funds(status="pending")["total"] == 1
        assert svc.get_funds(village_id=1)["total"] == 1
        assert svc.get_funds(project_id=2)["total"] == 1
        assert svc.get_funds(organization_id=3)["total"] == 1
        assert svc.get_funds(village_id=999)["total"] == 0

    def test_keyword_matches_name_code_purpose(self, svc, real_db_session):
        _mkfund(real_db_session, name="扶贫专项", code="ZJ001", purpose="教育")
        _mkfund(real_db_session, name="其它", code="ZJ002", purpose="医疗")
        assert svc.get_funds(keyword="扶贫")["total"] == 1
        assert svc.get_funds(keyword="ZJ002")["total"] == 1
        assert svc.get_funds(keyword="医疗")["total"] == 1
        assert svc.get_funds(keyword="不存在")["total"] == 0

    def test_pagination_offset(self, svc, real_db_session):
        for i in range(5):
            _mkfund(real_db_session, name=f"F{i}", status="pending")
        out = svc.get_funds(page=2, page_size=2)
        assert out["total"] == 5
        assert len(out["items"]) == 2
        assert out["page"] == 2


class TestGetFund:
    def test_existing(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="X", status="pending")
        assert svc.get_fund(f.id).name == "X"

    def test_missing_returns_none(self, svc):
        assert svc.get_fund(999999) is None


class TestCreateFund:
    def test_auto_commit_true(self, svc, real_db_session):
        f = svc.create_fund(name="新建", amount=5, status="pending")
        assert f.id is not None
        assert real_db_session.get(Fund, f.id) is not None

    def test_auto_commit_false_flushes_only(self, svc, real_db_session):
        f = svc.create_fund(name="未提交", amount=5, status="pending",
                            auto_commit=False)
        assert f.id is not None  # flush 生成 ID


class TestCreateFundForUser:
    def test_type_compat_and_status_applicant(self, svc, real_db_session):
        data = _StubFundCreate({"type": "infrastructure", "amount": 100,
                                "name": "用户创建"})
        f = svc.create_fund_for_user(data, created_by=9, organization_id=3,
                                     status="planned", applicant="张三")
        assert f.type == "infrastructure"
        assert f.fund_type == "infrastructure"
        assert f.status == "planned"
        assert f.applicant == "张三"
        assert f.created_by == 9
        assert f.organization_id == 3
        # code 自动生成 ZJ+年份+6位流水
        assert f.code and f.code.startswith(f"ZJ{_dt.date.today().year}")

    def test_existing_fund_type_not_overwritten(self, svc, real_db_session):
        data = _StubFundCreate({"type": "big", "fund_type": "detail",
                                "amount": 1, "name": "n"})
        f = svc.create_fund_for_user(data, created_by=1)
        assert f.type == "big"
        assert f.fund_type == "detail"

    def test_auto_commit_false_flush(self, svc, real_db_session):
        data = _StubFundCreate({"name": "flush", "amount": 2})
        f = svc.create_fund_for_user(data, created_by=1, auto_commit=False)
        assert f.id is not None
        assert f.code  # _ensure_zj_code 在 flush 后仍执行

    def test_no_type_key(self, svc, real_db_session):
        data = _StubFundCreate({"name": "无type", "amount": 3})
        f = svc.create_fund_for_user(data, created_by=2)
        assert f.type is None
        assert f.created_by == 2


class TestEnsureZjCode:
    def test_existing_code_untouched(self):
        f = Fund(code="EXISTING", name="n")
        f.id = 5
        FundService._ensure_zj_code(f)
        assert f.code == "EXISTING"

    def test_generates_from_id(self):
        f = Fund(name="n")
        f.id = 42
        f.code = None
        FundService._ensure_zj_code(f)
        assert f.code == f"ZJ{_dt.date.today().year}000042"

    def test_none_id_swallowed(self):
        f = Fund(name="n")
        f.id = None
        f.code = None
        FundService._ensure_zj_code(f)  # int(None) → TypeError 被吞
        assert f.code is None


class TestUpdateFund:
    def test_updates_non_none_fields(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="旧", amount=1, status="pending")
        updated = svc.update_fund(f.id, name="新", status=None, amount=9)
        assert updated.name == "新"
        assert float(updated.amount) == 9.0

    def test_missing_returns_none(self, svc):
        assert svc.update_fund(999999, name="x") is None

    def test_auto_commit_false(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="旧", status="pending")
        updated = svc.update_fund(f.id, name="改", auto_commit=False)
        assert updated.name == "改"


class TestDeleteFund:
    def test_delete_existing(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="删", status="pending")
        assert svc.delete_fund(f.id) is True
        assert real_db_session.get(Fund, f.id) is None

    def test_delete_missing_returns_false(self, svc):
        assert svc.delete_fund(999999) is False

    def test_delete_auto_commit_false(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="删2", status="pending")
        assert svc.delete_fund(f.id, auto_commit=False) is True


class TestBatchUpdateStatus:
    def test_empty_ids_returns_zero(self, svc):
        assert svc.batch_update_status([], "planned") == 0

    def test_illegal_enum_raises(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="a", status="pending")
        with pytest.raises(ValueError, match="非法经费状态"):
            svc.batch_update_status([f.id], "not_a_status")

    def test_illegal_transition_raises(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="a", status="pending")
        with pytest.raises(ValueError, match="非法状态流转"):
            svc.batch_update_status([f.id], "audited")

    def test_legal_transition_updates(self, svc, real_db_session):
        f1 = _mkfund(real_db_session, name="a", status="pending")
        f2 = _mkfund(real_db_session, name="b", status="pending")
        n = svc.batch_update_status([f1.id, f2.id], "planned")
        assert n == 2
        real_db_session.refresh(f1)
        assert f1.status == "planned"

    def test_legal_transition_flush_only(self, svc, real_db_session):
        f = _mkfund(real_db_session, name="a", status="pending")
        n = svc.batch_update_status([f.id], "approved", auto_commit=False)
        assert n == 1


class TestModuleConstants:
    def test_fund_types_dict(self):
        assert FUND_TYPES["education"] == "教育帮扶"

    def test_transitions_table_shape(self):
        assert "audited" in FundService.FUND_TRANSITIONS
        assert FundService.FUND_TRANSITIONS["audited"] == set()
