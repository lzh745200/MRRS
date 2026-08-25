from unittest.mock import MagicMock, patch

import pytest

from app.models.fund import Fund
from app.services.fund_service import (
    FundService,
    FundStatistics,
    YearlyFundSummary,
    calculate_utilization_rate,
    calculate_total_from_yearly_values,
    FUND_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def svc(db):
    return FundService(db)


# ---------------------------------------------------------------------------
# FundService - get_funds
# ---------------------------------------------------------------------------

class TestGetFunds:
    def test_no_filters(self, svc, db):
        db.execute.return_value.scalar_one.return_value = 0
        db.execute.return_value.scalars.return_value.unique.return_value.all.return_value = []
        result = svc.get_funds()
        assert result["total"] == 0
        assert result["items"] == []
        assert result["page"] == 1
        assert result["page_size"] == 20

    def test_all_filters(self, svc, db):
        db.execute.return_value.scalar_one.return_value = 2
        fund1, fund2 = MagicMock(), MagicMock()
        db.execute.return_value.scalars.return_value.unique.return_value.all.return_value = [fund1, fund2]
        result = svc.get_funds(
            page=2, page_size=10,
            village_id=1, project_id=2,
            organization_id=3, status="active",
            keyword="search_term",
        )
        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["page"] == 2
        assert result["page_size"] == 10

    def test_keyword_with_special_chars(self, svc, db):
        db.execute.return_value.scalar_one.return_value = 1
        fund = MagicMock()
        db.execute.return_value.scalars.return_value.unique.return_value.all.return_value = [fund]
        result = svc.get_funds(keyword="test%")
        assert result["total"] == 1


# ---------------------------------------------------------------------------
# FundService - get_fund (patches Fund.attachments because the source uses
# selectinload(Fund.attachments) but the model has no such relationship)
# ---------------------------------------------------------------------------

class TestGetFund:
    def test_found(self, svc, db):
        fund_mock = MagicMock(spec=Fund)
        fund_mock.id = 1
        db.execute.return_value.scalar_one_or_none.return_value = fund_mock
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.options.return_value = mock_query
        with patch.object(Fund, "attachments", MagicMock(), create=True), \
             patch("app.services.fund_service.select", return_value=mock_query), \
             patch("app.services.fund_service.selectinload", return_value=MagicMock()):
            result = svc.get_fund(1)
        assert result is fund_mock
        assert result.id == 1

    def test_not_found(self, svc, db):
        db.execute.return_value.scalar_one_or_none.return_value = None
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.options.return_value = mock_query
        with patch.object(Fund, "attachments", MagicMock(), create=True), \
             patch("app.services.fund_service.select", return_value=mock_query), \
             patch("app.services.fund_service.selectinload", return_value=MagicMock()):
            result = svc.get_fund(99999)
        assert result is None


# ---------------------------------------------------------------------------
# FundService - create_fund
# ---------------------------------------------------------------------------

class TestCreateFund:
    def test_auto_commit_true(self, svc, db):
        fund = svc.create_fund(name="test", amount=100, auto_commit=True)
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(fund)
        assert fund.name == "test"

    def test_auto_commit_false(self, svc, db):
        svc.create_fund(name="test", amount=100, auto_commit=False)
        db.add.assert_called_once()
        db.commit.assert_not_called()
        db.refresh.assert_not_called()
        db.flush.assert_called_once()

    def test_default_auto_commit(self, svc, db):
        svc.create_fund(name="test")
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# FundService - update_fund (patches get_fund to avoid selectinload issue)
# ---------------------------------------------------------------------------

class TestUpdateFund:
    def test_not_found(self, svc, db):
        with patch.object(svc, "get_fund", return_value=None):
            result = svc.update_fund(999, name="new")
            assert result is None

    def test_found_auto_commit(self, svc, db):
        fund = MagicMock(spec=Fund)
        fund.name = ""
        with patch.object(svc, "get_fund", return_value=fund):
            result = svc.update_fund(1, name="updated", amount=200, auto_commit=True)
            assert result.name == "updated"
            assert result.amount == 200
            db.commit.assert_called_once()
            db.refresh.assert_called_once_with(fund)

    def test_found_auto_commit_false(self, svc, db):
        fund = MagicMock(spec=Fund)
        fund.name = ""
        with patch.object(svc, "get_fund", return_value=fund):
            result = svc.update_fund(1, name="updated", auto_commit=False)
            assert result is fund
            db.commit.assert_not_called()
            db.flush.assert_called_once()

    def test_skip_none_values(self, svc, db):
        fund = MagicMock(spec=Fund)
        fund.name = ""
        with patch.object(svc, "get_fund", return_value=fund):
            result = svc.update_fund(1, name="updated", amount=None)
            assert result is fund
            assert result.name == "updated"
            db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# FundService - delete_fund (patches get_fund to avoid selectinload issue)
# ---------------------------------------------------------------------------

class TestDeleteFund:
    def test_not_found(self, svc, db):
        with patch.object(svc, "get_fund", return_value=None):
            result = svc.delete_fund(999)
            assert result is False

    def test_found_auto_commit(self, svc, db):
        fund = MagicMock(spec=Fund)
        with patch.object(svc, "get_fund", return_value=fund):
            result = svc.delete_fund(1, auto_commit=True)
            assert result is True
            db.delete.assert_called_once_with(fund)
            db.commit.assert_called_once()

    def test_found_auto_commit_false(self, svc, db):
        fund = MagicMock(spec=Fund)
        with patch.object(svc, "get_fund", return_value=fund):
            result = svc.delete_fund(1, auto_commit=False)
            assert result is True
            db.delete.assert_called_once_with(fund)
            db.commit.assert_not_called()
            db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# FundService - batch_update_status
# ---------------------------------------------------------------------------

class TestBatchUpdateStatus:
    def _mock_rows(self, db, rows):
        db.query.return_value.filter.return_value.all.return_value = rows

    def test_empty_ids(self, svc, db):
        result = svc.batch_update_status([], "active")
        assert result == 0
        db.execute.assert_not_called()

    def test_auto_commit(self, svc, db):
        self._mock_rows(db, [(1, "pending"), (2, "pending"), (3, "pending")])
        mock_result = MagicMock()
        mock_result.rowcount = 3
        db.execute.return_value = mock_result
        result = svc.batch_update_status([1, 2, 3], "approved", auto_commit=True)
        assert result == 3
        db.commit.assert_called_once()

    def test_auto_commit_false(self, svc, db):
        self._mock_rows(db, [(4, "in_use"), (5, "in_use")])
        mock_result = MagicMock()
        mock_result.rowcount = 2
        db.execute.return_value = mock_result
        result = svc.batch_update_status([4, 5], "completed", auto_commit=False)
        assert result == 2
        db.commit.assert_not_called()
        db.flush.assert_called_once()

    def test_illegal_status_value_rejected(self, svc, db):
        with pytest.raises(ValueError, match="非法经费状态"):
            svc.batch_update_status([1], "active")
        db.execute.assert_not_called()

    def test_illegal_transition_rejected(self, svc, db):
        """W2-T4：批量流转必须过状态机白名单，任一记录非法即整体拒绝"""
        self._mock_rows(db, [(1, "audited"), (2, "pending")])
        with pytest.raises(ValueError, match="非法状态流转"):
            svc.batch_update_status([1, 2], "approved")
        db.execute.assert_not_called()

    def test_rejected_is_legal_status_now(self, svc, db):
        """W2-T4：REJECTED 枚举补齐后，rejected 为合法目标态"""
        self._mock_rows(db, [(1, "pending")])
        mock_result = MagicMock()
        mock_result.rowcount = 1
        db.execute.return_value = mock_result
        assert svc.batch_update_status([1], "rejected") == 1


# ---------------------------------------------------------------------------
# calculate_utilization_rate
# ---------------------------------------------------------------------------

class TestCalculateUtilizationRate:
    def test_planned_zero_actual_positive(self):
        assert calculate_utilization_rate(50, 0) == 100.0

    def test_planned_zero_actual_zero(self):
        assert calculate_utilization_rate(0, 0) == 0.0

    def test_planned_negative(self):
        assert calculate_utilization_rate(10, -1) == 100.0

    def test_normal_rate(self):
        assert calculate_utilization_rate(50, 100) == 50.0

    def test_over_one_hundred_capped(self):
        assert calculate_utilization_rate(150, 100) == 100.0


# ---------------------------------------------------------------------------
# calculate_total_from_yearly_values
# ---------------------------------------------------------------------------

class TestCalculateTotalFromYearlyValues:
    def test_all_numbers(self):
        assert calculate_total_from_yearly_values([1, 2, 3]) == 6

    def test_with_none(self):
        assert calculate_total_from_yearly_values([1, None, 3, None]) == 4

    def test_empty(self):
        assert calculate_total_from_yearly_values([]) == 0


# ---------------------------------------------------------------------------
# FundStatistics
# ---------------------------------------------------------------------------

class TestFundStatistics:
    def test_defaults(self):
        fs = FundStatistics(fund_type="project", fund_type_label="项目")
        assert fs.military_investment == 0.0
        assert fs.utilization_rate == 0.0

    def test_to_dict(self):
        fs = FundStatistics(
            fund_type="infra", fund_type_label="基础设施",
            military_investment=100.123, total_investment=200.456,
        )
        d = fs.to_dict()
        assert d["fund_type"] == "infra"
        assert d["military_investment"] == 100.123
        assert d["total_investment"] == 200.456
        assert d["utilization_rate"] == 0.0


# ---------------------------------------------------------------------------
# YearlyFundSummary
# ---------------------------------------------------------------------------

class TestYearlyFundSummary:
    def test_defaults(self):
        ys = YearlyFundSummary(year=2024)
        assert ys.total_military == 0.0
        assert ys.by_type == {}

    def test_to_dict_plain(self):
        ys = YearlyFundSummary(year=2024, total_military=50.123)
        d = ys.to_dict()
        assert d["year"] == 2024
        assert d["total_military"] == 50.123
        assert d["by_type"] == {}

    def test_to_dict_with_by_type(self):
        fs = FundStatistics(fund_type="edu", fund_type_label="教育", total_investment=30.456)
        ys = YearlyFundSummary(year=2024, total_actual=30.456)
        ys.by_type["edu"] = fs
        d = ys.to_dict()
        assert d["by_type"]["edu"]["total_investment"] == 30.456

    def test_to_dict_by_type_non_dataclass(self):
        ys = YearlyFundSummary(year=2024)
        ys.by_type["raw"] = {"key": "value"}
        d = ys.to_dict()
        assert d["by_type"]["raw"] == {"key": "value"}


# ---------------------------------------------------------------------------
# FUND_TYPES
# ---------------------------------------------------------------------------

class TestFundTypes:
    def test_has_expected_keys(self):
        assert "transition" in FUND_TYPES
        assert "industry" in FUND_TYPES
        assert FUND_TYPES["education"] == "教育帮扶"

    def test_all_keys(self):
        expected = {"transition", "industry", "infrastructure",
                    "party_building", "medical", "education"}
        assert set(FUND_TYPES.keys()) == expected


class TestZjCodegen:
    """ADR-0011：code 留空自动生成 ZJ+年份+6位流水；手输编号不覆盖。"""

    def _svc(self):
        from unittest.mock import MagicMock, patch

        from app.services.fund_service import FundService

        db = MagicMock()
        db.refresh.side_effect = lambda o: setattr(o, "id", 123)
        return FundService(db), patch

    def test_auto_zj_format(self):
        import datetime

        svc, _ = self._svc()

        class D:
            code = None
            name = "测试经费"

            def model_dump(self, exclude_none=True):
                return {"name": "测试经费"}

        with patch("app.services.fund_service.safe_commit"):
            fund = svc.create_fund_for_user(D(), created_by=1)
        year = datetime.date.today().year
        assert fund.code == f"ZJ{year}000123"

    def test_manual_code_preserved(self):
        svc, _ = self._svc()

        class D:
            code = "MY-001"
            name = "手输编号"

            def model_dump(self, exclude_none=True):
                return {"code": "MY-001", "name": "手输编号"}

        with patch("app.services.fund_service.safe_commit"):
            fund = svc.create_fund_for_user(D(), created_by=1)
        assert fund.code == "MY-001"
