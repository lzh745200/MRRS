from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.models.fund_lifecycle import (
    AnomalySeverity,
    AnomalyType,
    FundAnomaly,
    FundContract,
)
from app.models.fund_budget import FundTransaction
from app.models.fund import Fund
from app.services.fund_anomaly_detector import (
    detect_anomalies,
    _check_overspend,
    _check_deviation,
    _check_idle,
    _check_duplicate_payments,
    _check_missing_vouchers,
    _check_large_cash,
    _check_contract_split,
    _check_single_source,
    FundAnomalyDetector,
    LARGE_CASH_THRESHOLD,
    CONTRACT_SPLIT_COUNT,
)


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    return MagicMock()


def _make_fund(id=1, name="test", approved_amount=100, used_amount=0,
               deviation_rate=0, allocated_amount=0, allocation_date=None,
               project_id=1):
    f = MagicMock(spec=Fund)
    f.id = id
    f.name = name
    f.approved_amount = approved_amount
    f.amount = 200
    f.used_amount = used_amount
    f.deviation_rate = deviation_rate
    f.allocated_amount = allocated_amount
    f.allocation_date = allocation_date
    f.project_id = project_id
    f.has_anomaly = False
    f.fund_id = None
    return f


# ---------------------------------------------------------------------------
#  _check_overspend
# ---------------------------------------------------------------------------

class TestCheckOverspend:
    def test_approved_zero(self):
        fund = _make_fund(approved_amount=0)
        assert _check_overspend(fund) == []

    def test_approved_none(self):
        fund = _make_fund(approved_amount=None)
        assert _check_overspend(fund) == []

    def test_danger(self):
        fund = _make_fund(approved_amount=100, used_amount=100)
        results = _check_overspend(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.DANGER.value
        assert results[0]["anomaly_type"] == AnomalyType.OVERSPEND.value

    def test_warning(self):
        fund = _make_fund(approved_amount=100, used_amount=95)
        results = _check_overspend(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_normal(self):
        fund = _make_fund(approved_amount=100, used_amount=10)
        assert _check_overspend(fund) == []

    def test_zero_used(self):
        fund = _make_fund(approved_amount=100, used_amount=0)
        assert _check_overspend(fund) == []

    def test_fund_name_none(self):
        fund = _make_fund(name=None, approved_amount=100, used_amount=110)
        results = _check_overspend(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.DANGER.value

    def test_approved_zero_and_amount_zero(self):
        fund = _make_fund(approved_amount=0)
        fund.amount = 0
        assert _check_overspend(fund) == []


# ---------------------------------------------------------------------------
#  _check_deviation
# ---------------------------------------------------------------------------

class TestCheckDeviation:
    def test_within_threshold(self):
        fund = _make_fund(deviation_rate=5)
        assert _check_deviation(fund) == []

    def test_warning_above_threshold(self):
        fund = _make_fund(deviation_rate=20)
        results = _check_deviation(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_danger_above_30(self):
        fund = _make_fund(deviation_rate=40)
        results = _check_deviation(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.DANGER.value

    def test_negative_deviation(self):
        fund = _make_fund(deviation_rate=-25)
        results = _check_deviation(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_deviation_none(self):
        fund = _make_fund(deviation_rate=None)
        assert _check_deviation(fund) == []


# ---------------------------------------------------------------------------
#  _check_idle
# ---------------------------------------------------------------------------

class TestCheckIdle:
    def test_allocated_zero(self):
        fund = _make_fund(allocated_amount=0)
        assert _check_idle(fund) == []

    def test_used_positive(self):
        fund = _make_fund(allocated_amount=100, used_amount=50)
        assert _check_idle(fund) == []

    def test_no_alloc_date(self):
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=None)
        assert _check_idle(fund) == []

    def test_alloc_date_invalid_str(self):
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date="not-a-date")
        assert _check_idle(fund) == []

    def test_alloc_date_str_valid_recent(self):
        recent = (datetime.now() - timedelta(days=10)).isoformat()
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=recent)
        assert _check_idle(fund) == []

    def test_alloc_date_datetime_recent(self):
        recent = datetime.now() - timedelta(days=10)
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=recent)
        assert _check_idle(fund) == []

    def test_alloc_date_str_old_warning(self):
        old = (datetime.now() - timedelta(days=45)).isoformat()
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=old)
        results = _check_idle(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_alloc_date_datetime_old_danger(self):
        old = datetime.now() - timedelta(days=90)
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=old)
        results = _check_idle(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.DANGER.value

    def test_fund_name_none(self):
        old = (datetime.now() - timedelta(days=45)).isoformat()
        fund = _make_fund(id=1, name=None, allocated_amount=100, used_amount=0,
                          allocation_date=old)
        results = _check_idle(fund)
        assert len(results) == 1

    # ── 生产路径：allocation_date 是 UtcDateTime 列，ORM 读回为 **aware UTC** ──
    # 上面各用例喂的是 naive 值，恰好掩盖了「本地 naive 与 aware 相减抛 TypeError」
    # 的缺陷（资金闲置检测在生产环境静默失效）。以下三条锁定 aware 输入。

    def test_alloc_date_aware_utc_recent(self):
        recent = datetime.now(timezone.utc) - timedelta(days=10)
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=recent)
        assert _check_idle(fund) == []

    def test_alloc_date_aware_utc_old_danger(self):
        old = datetime.now(timezone.utc) - timedelta(days=90)
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=old)
        results = _check_idle(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.DANGER.value

    def test_alloc_date_aware_utc_str_warning(self):
        # to_dict()/JSON 序列化形态：带 +00:00 的字符串（fromisoformat 得 aware）
        old = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        fund = _make_fund(allocated_amount=100, used_amount=0, allocation_date=old)
        results = _check_idle(fund)
        assert len(results) == 1
        assert results[0]["severity"] == AnomalySeverity.WARNING.value


# ---------------------------------------------------------------------------
#  _check_duplicate_payments
# ---------------------------------------------------------------------------

class TestCheckDuplicatePayments:
    def test_no_duplicates(self, db):
        db.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []
        results = _check_duplicate_payments(db, 1)
        assert results == []

    def test_with_duplicates(self, db):
        db.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = [
            ("V001", 3)
        ]
        results = _check_duplicate_payments(db, 1)
        assert len(results) == 1
        assert results[0]["anomaly_type"] == AnomalyType.DUPLICATE.value
        assert results[0]["severity"] == AnomalySeverity.WARNING.value
        assert results[0]["fund_id"] is None


# ---------------------------------------------------------------------------
#  _check_missing_vouchers
# ---------------------------------------------------------------------------

class TestCheckMissingVouchers:
    def test_used_zero_skip(self, db):
        fund = _make_fund(used_amount=0)
        results = _check_missing_vouchers(db, 1, [fund])
        assert results == []

    def test_has_transactions(self, db):
        fund = _make_fund(used_amount=50)
        db.query.return_value.filter.return_value.scalar.return_value = 2
        results = _check_missing_vouchers(db, 1, [fund])
        assert results == []

    def test_missing_vouchers(self, db):
        fund = _make_fund(used_amount=50)
        db.query.return_value.filter.return_value.scalar.return_value = 0
        results = _check_missing_vouchers(db, 1, [fund])
        assert len(results) == 1
        assert results[0]["anomaly_type"] == AnomalyType.MISSING_VOUCHER.value
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_missing_vouchers_fund_name_none(self, db):
        fund = _make_fund(id=1, name=None, used_amount=10)
        db.query.return_value.filter.return_value.scalar.return_value = 0
        results = _check_missing_vouchers(db, 1, [fund])
        assert len(results) == 1


# ---------------------------------------------------------------------------
#  _check_large_cash
# ---------------------------------------------------------------------------

class TestCheckLargeCash:
    def test_no_large_tx(self, db):
        db.query.return_value.filter.return_value.all.return_value = []
        results = _check_large_cash(db, 1)
        assert results == []

    def test_with_large_tx(self, db):
        tx = MagicMock(spec=FundTransaction)
        tx.fund_id = 1
        tx.amount = 100.0
        tx.purpose = "large equipment"
        db.query.return_value.filter.return_value.all.return_value = [tx]
        results = _check_large_cash(db, 1)
        assert len(results) == 1
        assert results[0]["anomaly_type"] == "large_cash"
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_with_large_tx_no_purpose(self, db):
        tx = MagicMock(spec=FundTransaction)
        tx.fund_id = 1
        tx.amount = LARGE_CASH_THRESHOLD
        tx.purpose = None
        db.query.return_value.filter.return_value.all.return_value = [tx]
        results = _check_large_cash(db, 1)
        assert len(results) == 1
        assert "未说明" in results[0]["description"]


# ---------------------------------------------------------------------------
#  _check_contract_split
# ---------------------------------------------------------------------------

class TestCheckContractSplit:
    def test_no_contracts(self, db):
        db.query.return_value.filter.return_value.all.return_value = []
        results = _check_contract_split(db, 1)
        assert results == []

    def test_less_than_threshold(self, db):
        c = MagicMock(spec=FundContract)
        c.party_b = "SupplierA"
        c.sign_date = datetime.now().date()
        c.contract_amount = 10
        db.query.return_value.filter.return_value.all.return_value = [c]
        results = _check_contract_split(db, 1)
        assert results == []

    def test_meets_threshold_within_window(self, db):
        today = datetime.now().date()
        contracts = []
        for i in range(CONTRACT_SPLIT_COUNT):
            c = MagicMock(spec=FundContract)
            c.party_b = "SupplierA"
            c.sign_date = today + timedelta(days=i)
            c.contract_amount = 10
            contracts.append(c)
        db.query.return_value.filter.return_value.all.return_value = contracts
        results = _check_contract_split(db, 1)
        assert len(results) == 1
        assert results[0]["anomaly_type"] == "contract_split"
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_meets_threshold_outside_window(self, db):
        today = datetime.now().date()
        contracts = []
        for i in range(CONTRACT_SPLIT_COUNT):
            c = MagicMock(spec=FundContract)
            c.party_b = "SupplierA"
            c.sign_date = today + timedelta(days=i * 20)
            c.contract_amount = 10
            contracts.append(c)
        db.query.return_value.filter.return_value.all.return_value = contracts
        results = _check_contract_split(db, 1)
        assert results == []

    def test_some_dates_none(self, db):
        today = datetime.now().date()
        contracts = []
        for i in range(CONTRACT_SPLIT_COUNT):
            c = MagicMock(spec=FundContract)
            c.party_b = "SupplierA"
            c.sign_date = None
            c.contract_amount = 10
            contracts.append(c)
        db.query.return_value.filter.return_value.all.return_value = contracts
        results = _check_contract_split(db, 1)
        assert results == []

    def test_party_b_none(self, db):
        c = MagicMock(spec=FundContract)
        c.party_b = None
        c.sign_date = datetime.now().date()
        c.contract_amount = 10
        db.query.return_value.filter.return_value.all.return_value = [c]
        results = _check_contract_split(db, 1)
        assert results == []


# ---------------------------------------------------------------------------
#  _check_single_source
# ---------------------------------------------------------------------------

class TestCheckSingleSource:
    def test_less_than_two(self, db):
        db.query.return_value.filter.return_value.all.return_value = [MagicMock()]
        results = _check_single_source(db, 1)
        assert results == []

    def test_two_same_party(self, db):
        c1 = MagicMock(spec=FundContract)
        c1.party_b = "SupplierA"
        c1.contract_amount = 20
        c2 = MagicMock(spec=FundContract)
        c2.party_b = "SupplierA"
        c2.contract_amount = 30
        db.query.return_value.filter.return_value.all.return_value = [c1, c2]
        results = _check_single_source(db, 1)
        assert len(results) == 1
        assert results[0]["anomaly_type"] == "single_source"
        assert results[0]["severity"] == AnomalySeverity.WARNING.value

    def test_two_different_parties(self, db):
        c1 = MagicMock(spec=FundContract)
        c1.party_b = "SupplierA"
        c2 = MagicMock(spec=FundContract)
        c2.party_b = "SupplierB"
        db.query.return_value.filter.return_value.all.return_value = [c1, c2]
        results = _check_single_source(db, 1)
        assert results == []

    def test_some_party_b_none(self, db):
        c1 = MagicMock(spec=FundContract)
        c1.party_b = None
        c2 = MagicMock(spec=FundContract)
        c2.party_b = None
        db.query.return_value.filter.return_value.all.return_value = [c1, c2]
        results = _check_single_source(db, 1)
        assert results == []


# ---------------------------------------------------------------------------
#  detect_anomalies (main entry point)
# ---------------------------------------------------------------------------

class TestDetectAnomalies:
    def test_no_funds(self, db):
        db.query.return_value.filter.return_value.all.return_value = []
        results = detect_anomalies(db, 1)
        assert results == []

    def test_full_flow_no_new_anomalies(self, db):
        fund = _make_fund(approved_amount=100, used_amount=10, deviation_rate=5,
                          allocated_amount=0)
        db.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None

        all_calls = [0]
        def all_side():
            all_calls[0] += 1
            if all_calls[0] == 1:
                return [fund]
            return []

        db.query.return_value.filter.return_value.all.side_effect = all_side

        scalar_calls = [0]
        def scalar_side():
            scalar_calls[0] += 1
            if scalar_calls[0] == 1:
                return 2
            return 0

        db.query.return_value.filter.return_value.scalar.side_effect = scalar_side

        results = detect_anomalies(db, 1)
        assert results == []

    def test_full_flow_with_new_anomaly(self, db):
        fund = _make_fund(approved_amount=100, used_amount=100, deviation_rate=5,
                          allocated_amount=0)
        fund2 = _make_fund(id=2, approved_amount=100, used_amount=0, deviation_rate=0,
                           allocated_amount=0)

        all_calls = [0]
        def all_side():
            all_calls[0] += 1
            if all_calls[0] == 1:
                return [fund, fund2]
            return []

        db.query.return_value.filter.return_value.all.side_effect = all_side
        db.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None

        scalar_calls = [0]
        def scalar_side():
            scalar_calls[0] += 1
            if scalar_calls[0] <= 2:
                return 2
            return 1

        db.query.return_value.filter.return_value.scalar.side_effect = scalar_side

        results = detect_anomalies(db, 1)
        assert len(results) == 1
        assert results[0]["anomaly_type"] == AnomalyType.OVERSPEND.value
        assert results[0]["severity"] == AnomalySeverity.DANGER.value

    def test_dedup_existing_anomaly(self, db):
        fund = _make_fund(approved_amount=100, used_amount=100, deviation_rate=5,
                          allocated_amount=0)
        fund2 = _make_fund(id=2, approved_amount=100, used_amount=0, deviation_rate=0,
                           allocated_amount=0)

        all_calls = [0]
        def all_side():
            all_calls[0] += 1
            if all_calls[0] == 1:
                return [fund, fund2]
            return []

        db.query.return_value.filter.return_value.all.side_effect = all_side
        db.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []
        existing = MagicMock(spec=FundAnomaly)
        existing.id = 1
        db.query.return_value.filter.return_value.first.return_value = existing

        scalar_calls = [0]
        def scalar_side():
            scalar_calls[0] += 1
            if scalar_calls[0] <= 2:
                return 2
            return 1

        db.query.return_value.filter.return_value.scalar.side_effect = scalar_side

        results = detect_anomalies(db, 1)
        assert len(results) == 0

    def test_no_overlap_check_single_source_and_contract(self, db):
        fund = _make_fund(approved_amount=100, used_amount=0, deviation_rate=5,
                          allocated_amount=0)

        db.query.return_value.filter.return_value.group_by.return_value.having.return_value.all.return_value = []
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.scalar.return_value = 0

        all_calls = [0]
        def all_side():
            all_calls[0] += 1
            if all_calls[0] == 1:
                return [fund]
            return []

        db.query.return_value.filter.return_value.all.side_effect = all_side

        results = detect_anomalies(db, 1)
        assert results == []
        db.add.assert_not_called()


# ---------------------------------------------------------------------------
#  FundAnomalyDetector (wrapper class)
# ---------------------------------------------------------------------------

class TestFundAnomalyDetector:
    def test_init_without_db(self):
        d = FundAnomalyDetector()
        assert d.db is None

    def test_init_with_db(self):
        db = MagicMock()
        d = FundAnomalyDetector(db=db)
        assert d.db is db

    def test_detect_anomalies_with_db(self, db):
        db.query.return_value.filter.return_value.all.return_value = []
        d = FundAnomalyDetector(db=db)
        results = d.detect_anomalies(1)
        assert results == []

    def test_detect_anomalies_without_db(self):
        d = FundAnomalyDetector()
        results = d.detect_anomalies(1)
        assert results == []

    def test_create_with_db(self):
        db = MagicMock()
        d = FundAnomalyDetector.create(db)
        assert isinstance(d, FundAnomalyDetector)
        assert d.db is db

    def test_create_without_db(self):
        d = FundAnomalyDetector.create()
        assert isinstance(d, FundAnomalyDetector)
        assert d.db is None
