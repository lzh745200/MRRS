"""v1.12.9 覆盖率补口：app/api/v1/system/audit.py before_date fail-closed（W15 深审 LIVE）。

覆盖行（当前代码行号）：
- 79-80 `BatchDeleteRequest.validate_before_date` 的 None 直通分支；
- 81-89 非法 ISO 日期 → 422（绝不降级为"无过滤"后执行 query.delete() 清空审计表）；
- 156-166 端点内二次兜底：绕过 schema 直接调用时非法日期一律 400，删除永不执行。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.system.audit import BatchDeleteRequest, batch_delete_audit_logs


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


class TestValidateBeforeDate:
    def test_none_passthrough(self):
        assert BatchDeleteRequest.validate_before_date(None) is None

    def test_blank_string_becomes_none(self):
        assert BatchDeleteRequest.validate_before_date("   ") is None

    def test_iso_date_kept(self):
        assert BatchDeleteRequest.validate_before_date("2026-01-01") == "2026-01-01"

    def test_invalid_date_rejected_at_schema(self):
        with pytest.raises(ValidationError) as ei:
            BatchDeleteRequest(before_date="2026-13-45")
        assert "before_date" in str(ei.value)


class TestBatchDeleteBeforeDateGuard:
    async def test_invalid_before_date_400_before_any_delete(self):
        """schema 已校验；直接调用端点（内部调用路径）也必须 400 且不触发删除。"""
        db = MagicMock()
        body = SimpleNamespace(ids=None, actions=None, action=None, before_date="not-a-date")
        with pytest.raises(HTTPException) as ei:
            await batch_delete_audit_logs(body=body, current_user=_admin(), db=db)
        assert ei.value.status_code == 400
        assert "before_date 格式无效" in ei.value.detail
        db.query.return_value.delete.assert_not_called()

    async def test_action_and_valid_date_filters_query(self):
        query = MagicMock()
        query.filter.return_value = query  # 链式 filter 保持同一 query 对象
        query.delete.return_value = 5
        db = MagicMock()
        db.query.return_value = query
        body = SimpleNamespace(ids=None, actions=["create"], action=None, before_date="2026-01-01")
        with patch("app.api.v1.system.audit.safe_commit") as m_commit:
            result = await batch_delete_audit_logs(body=body, current_user=_admin(), db=db)
        assert result["data"]["deleted_count"] == 5
        m_commit.assert_called_once_with(db)

    async def test_no_filter_skips_delete(self):
        db = MagicMock()
        body = SimpleNamespace(ids=None, actions=None, action=None, before_date=None)
        result = await batch_delete_audit_logs(body=body, current_user=_admin(), db=db)
        assert result["data"]["deleted_count"] == 0
        db.query.return_value.delete.assert_not_called()
