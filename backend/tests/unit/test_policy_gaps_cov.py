"""app.api.v1.policy 覆盖率攻坚测试（缺口补丁）

覆盖：
- get_policy_types：空分类/合并去重/DB 异常回退预定义
- get_categories：查询异常 → 静态分类配置
- get_category_tree：父子嵌套 / 异常 → []
- create_policy：非法 effective_date 忽略、HTTPException 透传
- update_policy：非法日期剔除、无对应模型列的字段剔除（expiry_date）、HTTPException 透传
- get_user_favorites：越权 403
- search_policies：FTS 端点
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.policy as m
from app.models.policy import Policy


def _admin():
    return SimpleNamespace(id=1, role="super_admin", is_superuser=True)


def _q(all_=None, first=None):
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = all_ if all_ is not None else []
    q.first.return_value = first
    db = MagicMock()
    db.query.return_value = q
    return db


class TestGetPolicyTypes:
    async def test_predefined_only_when_no_categories(self):
        result = await m.get_policy_types(db=_q(all_=[]))
        values = [t["value"] for t in result["data"]]
        assert "military" in values and "other" in values

    async def test_db_categories_merged_and_deduped(self):
        cats = [
            SimpleNamespace(code="military", name="专项政策"),  # 与预定义重复 → 跳过
            SimpleNamespace(code="special", name="专项政策"),   # 新分类 → 追加
            SimpleNamespace(code=None, name="无名分类"),        # code 为空 → 用 name
        ]
        result = await m.get_policy_types(db=_q(all_=cats))
        values = [t["value"] for t in result["data"]]
        assert values.count("military") == 1
        assert "special" in values
        assert "无名分类" in values

    async def test_db_error_falls_back_to_predefined(self):
        db = MagicMock()
        db.query.side_effect = Exception("db down")
        result = await m.get_policy_types(db=db)
        assert len(result["data"]) == 7  # 预定义 7 类


class TestGetCategoriesExcept:
    async def test_query_error_returns_static_config(self):
        db = MagicMock()
        db.query.side_effect = TypeError("boom")
        result = await m.get_categories(
            parent_id=None, is_active=None, current_user=_admin(), db=db, response=None)
        assert result["military"]["label"] == "专项政策"
        assert result["local"]["label"] == "地方政策"


class TestGetCategoryTree:
    async def test_parent_child_nesting(self):
        cats = [
            SimpleNamespace(id=1, name="父类", code="p", parent_id=None),
            SimpleNamespace(id=2, name="子类", code="c", parent_id=1),
        ]
        tree = await m.get_category_tree(current_user=_admin(), db=_q(all_=cats))
        assert len(tree) == 1
        assert tree[0]["children"][0]["id"] == 2

    async def test_query_error_returns_empty(self):
        db = MagicMock()
        db.query.side_effect = ValueError("boom")
        assert await m.get_category_tree(current_user=_admin(), db=db) == []


class TestCreatePolicy:
    async def test_invalid_effective_date_ignored(self):
        data = m.PolicyCreateRequest(title="新政策", effective_date="bad-date")
        with patch.object(m, "cache_manager", AsyncMock()):
            result = await m.create_policy(data=data, current_user=_admin(), db=_q())
        assert result["data"]["title"] == "新政策"  # success_response 信封

    async def test_http_exception_passthrough(self):
        data = m.PolicyCreateRequest(title="新政策")
        with (
            patch.object(m, "safe_commit", side_effect=HTTPException(status_code=503)),
            patch.object(m, "cache_manager", AsyncMock()),
            pytest.raises(HTTPException) as exc_info,
        ):
            await m.create_policy(data=data, current_user=_admin(), db=_q())
        assert exc_info.value.status_code == 503


class TestUpdatePolicy:
    @staticmethod
    def _existing():
        return Policy(id=1, title="旧标题")

    async def test_invalid_date_field_dropped(self):
        policy = self._existing()
        data = m.PolicyUpdateRequest(title="新标题", publish_date="not-a-date")
        with patch.object(m, "cache_manager", AsyncMock()):
            await m.update_policy(1, data=data, current_user=_admin(), db=_q(first=policy))
        assert policy.title == "新标题"
        assert policy.issue_date is None  # 非法日期被剔除

    async def test_unknown_field_dropped(self):
        policy = self._existing()
        # expiry_date 在 schema 中但 Policy 模型无此列 → 被剔除
        data = m.PolicyUpdateRequest(expiry_date="2027-01-01")
        with patch.object(m, "cache_manager", AsyncMock()):
            await m.update_policy(1, data=data, current_user=_admin(), db=_q(first=policy))
        assert not hasattr(policy, "expiry_date")

    async def test_http_exception_passthrough(self):
        data = m.PolicyUpdateRequest(title="x")
        with (
            patch.object(m, "safe_commit", side_effect=HTTPException(status_code=503)),
            patch.object(m, "cache_manager", AsyncMock()),
            pytest.raises(HTTPException) as exc_info,
        ):
            await m.update_policy(1, data=data, current_user=_admin(), db=_q(first=self._existing()))
        assert exc_info.value.status_code == 503


class TestGetUserFavorites:
    async def test_forbidden_for_other_user(self):
        with pytest.raises(HTTPException) as exc_info:
            await m.get_user_favorites(user_id=2, current_user=_admin(), db=MagicMock())
        assert exc_info.value.status_code == 403


class TestSearchPolicies:
    async def test_fts_endpoint(self):
        with patch("app.services.policy_fts_service.search_policies_fts",
                   return_value=[{"id": 1, "title": "乡村振兴"}]) as fts:
            result = await m.search_policies(q="乡", limit=20, offset=0, db=MagicMock())
        fts.assert_called_once()
        assert result is not None
