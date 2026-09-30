"""v1.12.9 覆盖率补口：app/api/v1/monitoring/secrets.py 清理保留天数下界（W15 深审 #62）。

覆盖行（当前代码行号）：
- 94-100 `/secrets/cleanup`：keep_days < 1 时 400。
  keep_days<=0 会让 cutoff = now - keep_days*86400 落到当前时刻/未来，
  使"已撤销且创建时间早于 cutoff"对全部非活跃版本成立 → 一次调用清空所有密钥。
  Query(ge=1) 只拦 HTTP 查询串；直接调用端点函数（内部调用/单测）必须同样拒绝。
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.api.v1.monitoring import secrets as secrets_api


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


class TestCleanupExpiredKeysKeepDaysGuard:
    async def test_zero_keep_days_rejected_before_manager_call(self):
        with patch.object(secrets_api, "secrets_manager") as m:
            with pytest.raises(HTTPException) as ei:
                await secrets_api.cleanup_expired_keys(keep_days=0, current_user=_admin())
        assert ei.value.status_code == 400
        assert "keep_days" in ei.value.detail
        m.cleanup_expired_keys.assert_not_called()

    async def test_negative_keep_days_rejected(self):
        with pytest.raises(HTTPException) as ei:
            await secrets_api.cleanup_expired_keys(keep_days=-5, current_user=_admin())
        assert ei.value.status_code == 400

    async def test_lower_bound_accepted(self):
        with patch.object(secrets_api, "secrets_manager") as m:
            m.cleanup_expired_keys.return_value = 3
            result = await secrets_api.cleanup_expired_keys(keep_days=1, current_user=_admin())
        assert result["data"]["deleted_count"] == 3
        m.cleanup_expired_keys.assert_called_once_with(1)

    async def test_non_admin_rejected(self):
        with pytest.raises(HTTPException) as ei:
            await secrets_api.cleanup_expired_keys(
                keep_days=90, current_user=SimpleNamespace(role="user", is_superuser=False)
            )
        assert ei.value.status_code == 403
