"""app.api.v1.funds 覆盖补全 — _parse_date_value 各解析分支 (lines 144-163)
与 _transition_status 未知字段跳过告警分支 (line 580)."""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1.funds import _parse_date_value, _transition_status


class TestParseDateValue:
    def test_non_date_field_passthrough(self):
        assert _parse_date_value("amount", "2026-07-21") == "2026-07-21"

    def test_none_passthrough(self):
        assert _parse_date_value("date", None) is None

    def test_date_object_returned_as_is(self):
        d = date(2026, 7, 21)
        assert _parse_date_value("date", d) is d

    def test_datetime_object_returned_as_is(self):
        dt = datetime(2026, 7, 21, 10, 0, 0)
        assert _parse_date_value("audit_date", dt) is dt

    def test_empty_string_becomes_none(self):
        assert _parse_date_value("date", "   ") is None

    def test_iso_datetime_with_t_separator(self):
        assert _parse_date_value("audit_date", "2026-07-21T10:30:00") == datetime(2026, 7, 21, 10, 30, 0)

    def test_datetime_with_space_separator(self):
        # 第一种格式解析失败 (continue) → 第二种命中 (lines 154-155)
        assert _parse_date_value("start_date", "2026-07-21 10:30:00") == datetime(2026, 7, 21, 10, 30, 0)

    def test_datetime_with_microseconds(self):
        assert _parse_date_value("end_date", "2026-07-21T10:30:00.123456") == datetime(2026, 7, 21, 10, 30, 0, 123456)

    def test_plain_date_string(self):
        assert _parse_date_value("date", "2026-07-21") == date(2026, 7, 21)

    def test_unparseable_string_returned_as_is_with_warning(self):
        with patch("app.api.v1.funds.logger") as mock_log:
            result = _parse_date_value("date", "not-a-date")
        assert result == "not-a-date"
        mock_log.warning.assert_called_once()


class TestTransitionStatus:
    def test_unknown_kwarg_field_is_skipped_with_warning(self):
        """kwargs 中含 Fund 不存在的字段 → 跳过并告警 (line 580)

        正常调用方只传 Fund 已有字段，这里直接调用内部函数构造防御场景。
        """
        fund = SimpleNamespace(id=1, status="pending")
        db = MagicMock(name="db")
        with patch("app.api.v1.funds.safe_commit") as mock_commit:
            with patch("app.api.v1.funds.logger") as mock_log:
                _transition_status(db, fund, "approved", ["pending"], bogus_field="x")
        assert fund.status == "approved"
        assert not hasattr(fund, "bogus_field")
        mock_log.warning.assert_called_once()
        # T048 设计：状态流转与操作日志分两次提交（后者的 except 注释为
        # "日志失败不阻断主流程"，见 app/api/v1/funds.py），故 safe_commit
        # 实际被调用两次（状态+历史一次、操作日志一次）。
        assert mock_commit.call_count == 2
        mock_commit.assert_any_call(db)
