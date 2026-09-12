"""app.api.v1.search 覆盖补全 — _append_fund_results 结果追加循环与异常降级 (lines 159-169)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1.search import _append_fund_results


def _fund(**kw):
    defaults = dict(id=1, name="扶贫专项资金", code="F001", project_name="修路项目")
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class TestAppendFundResults:
    def test_results_appended(self):
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.limit.return_value = q
        q.all.return_value = [_fund()]
        items = []
        with patch("app.api.v1.search.scoped_filter", return_value=q):
            _append_fund_results(items, "扶贫", 5, MagicMock(), MagicMock())
        assert len(items) == 1
        assert items[0].type == "fund"
        assert items[0].title == "扶贫专项资金"
        assert items[0].subtitle == "修路项目"
        assert items[0].link == "/funds/1"

    def test_name_code_fallback_title(self):
        """name/code 均为空 → 标题回退为 资金 #id (line 163)"""
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.limit.return_value = q
        q.all.return_value = [_fund(id=7, name=None, code=None, project_name=None)]
        items = []
        with patch("app.api.v1.search.scoped_filter", return_value=q):
            _append_fund_results(items, "x", 5, MagicMock(), MagicMock())
        assert items[0].title == "资金 #7"
        assert items[0].subtitle is None

    def test_exception_is_logged_and_swallowed(self):
        items = []
        with patch("app.api.v1.search.scoped_filter", side_effect=RuntimeError("db down")):
            with patch("app.api.v1.search.logger") as mock_log:
                _append_fund_results(items, "x", 5, MagicMock(), MagicMock())
        assert items == []
        mock_log.warning.assert_called_once()
