"""dashboard.py get_dashboard_summary 缓存分支隔离测试（单元级，不依赖路由）。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _Scope:
    org_ids = []

    @staticmethod
    def filter_by_org_ids(q, *args, **kwargs):
        return q

    def has_full_access(self):
        return True


class TestDashboardSummaryUnit:
    def test_cache_hit_returns_cached(self):
        import app.api.v1.data.data.dashboard as dash_mod

        cached_payload = {"stats": {"x": 1}, "recent_activities": []}
        with patch.object(dash_mod, "_get_cached", return_value=cached_payload):
            import asyncio

            result = asyncio.run(dash_mod.get_dashboard_summary(
                current_user=SimpleNamespace(id=1),
                data_scope=_Scope(),
                db=MagicMock(),
            ))
        assert result is cached_payload

    def test_cache_miss_queries_and_sets(self):
        import asyncio
        import app.api.v1.data.data.dashboard as dash_mod

        db = MagicMock()

        def fake_query(*_args, **_kwargs):
            q = MagicMock()
            q.filter.return_value = q
            q.first.return_value = None
            q.all.return_value = []
            q.scalar.return_value = 0
            q.order_by.return_value = q
            q.group_by.return_value = q
            q.count.return_value = 0
            return q

        db.query.side_effect = fake_query

        activities_payload = {"items": [{"id": 1, "type": "project"}]}
        with patch.object(dash_mod, "_get_cached", return_value=None), \
             patch.object(dash_mod, "_set_cached") as mock_set, \
             patch.object(dash_mod, "get_recent_activities",
                          new=AsyncMock(return_value=activities_payload)):
            result = asyncio.run(dash_mod.get_dashboard_summary(
                current_user=SimpleNamespace(id=1),
                data_scope=_Scope(),
                db=db,
            ))
        assert "stats" in result
        assert result["recent_activities"] == activities_payload["items"]
        mock_set.assert_called_once()
