"""覆盖 app.core.data_permission 缺口：未知 scope 的防御性兜底返回。"""
from unittest.mock import MagicMock, patch

import app.core.data_permission as dp


class TestUnknownScopeFallback:
    """get_data_scope 返回未知值时（防御性分支，正常枚举不会到达）。"""

    def test_apply_scope_to_query_fails_closed(self):
        """未知 scope 必须返回**空集**（fail-closed），不得放行全量。

        2026-10-29 审计修复：原实现 return query（放行全量），与本模块
        check_record_access 对未知 scope 返回 False 的口径相反 —— 同一数据面
        两条相反口径，扩展枚举值时最易静默泄漏全量（违反 ADR-0002）。
        """
        query = MagicMock(name="query")
        model = MagicMock(name="model")
        user = MagicMock(name="user")
        with patch.object(dp, "get_data_scope", return_value="unknown_scope"):
            result = dp.apply_scope_to_query(query, model, user)
        # 必须施加过滤（空集），而不是原样返回
        query.filter.assert_called_once()
        assert result is not query

    def test_unknown_scope_paths_consistent(self):
        """列表过滤与单条检查对未知 scope 必须同口径（都 fail-closed）。"""
        record = MagicMock(name="record")
        user = MagicMock(name="user")
        with patch.object(dp, "get_data_scope", return_value="unknown_scope"):
            assert dp.check_record_access(record, user) is False
            q = MagicMock(name="q")
            dp.apply_scope_to_query(q, MagicMock(name="m"), user)
            q.filter.assert_called_once()

    def test_check_record_access_returns_false(self):
        record = MagicMock(name="record")
        user = MagicMock(name="user")
        with patch.object(dp, "get_data_scope", return_value="unknown_scope"):
            assert dp.check_record_access(record, user) is False
