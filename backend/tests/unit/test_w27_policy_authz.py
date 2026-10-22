"""W27 回归：政策写操作归属守卫（W26 全栈检测 P0-3）。

## 缺陷背景（W26 检测确认）
``update`` / ``delete`` / ``publish`` / ``archive`` / ``upload`` 五个写端点此前只经过
``require_policy_operator_role()``（``api/v1/deps.py:31-38`` 的**函数体就是
``return None``**，放行全部已认证角色），随后用**裸 ID** 取记录
（``policy.py`` 的 ``db.query(Policy).filter(Policy.id == policy_id).first()``）。

因此任意 ``user`` 角色账号可改写 / 软删 / 发布 / 归档**他人创建的未发布草稿**
（``viewer`` 被 ``ViewerReadOnlyMiddleware`` 拦在写方法之外，不受影响）；而软删在
模块内没有恢复入口（``delete_policy`` 只置 ``is_active=False``，列表恒过滤
``is_active``）⇒ 越权即造成**不可逆的政务资料丢失**。

## 修复口径
写权限按「归属」收敛，兼容产品既定意图（每个用户仍可完整增删改查**自己**的政策）：

* 管理员（super_admin / admin / is_superuser）→ 全部可写；
* 普通用户 → 仅 ``created_by == 本人``；
* 其余（含 ``created_by`` 为空的历史脏数据）→ fail-closed 403。

本文件锁定上述四条分支 + 端点接入。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.policy import _assert_policy_writable


def _user(uid=1, role="user", is_superuser=False):
    return SimpleNamespace(id=uid, role=role, is_superuser=is_superuser, username=f"u{uid}")


def _policy(created_by=1, status="draft"):
    return SimpleNamespace(id=10, created_by=created_by, status=status, title="某政策")


class TestPolicyWriteGuard:
    """``_assert_policy_writable`` 四分支全覆盖。"""

    def test_super_admin_can_write_any(self):
        _assert_policy_writable(_policy(created_by=999), _user(role="super_admin"))

    def test_is_superuser_flag_can_write_any(self):
        _assert_policy_writable(_policy(created_by=999), _user(role="user", is_superuser=True))

    def test_department_admin_can_write_any(self):
        # admin（非超管）按 is_admin 语义亦属管理员：可写任何政策
        _assert_policy_writable(_policy(created_by=999), _user(role="admin"))

    def test_owner_can_write_own_draft(self):
        _assert_policy_writable(_policy(created_by=7), _user(uid=7))

    def test_non_owner_cannot_write_draft(self):
        """核心回归：普通用户改他人草稿必须 403。"""
        with pytest.raises(HTTPException) as ei:
            _assert_policy_writable(_policy(created_by=999), _user(uid=7))
        assert ei.value.status_code == 403
        assert "无权修改他人创建的政策" in ei.value.detail

    def test_legacy_null_creator_fail_closed(self):
        """历史脏数据（created_by 为 NULL）→ 非管理员一律拒绝（fail-closed）。"""
        with pytest.raises(HTTPException) as ei:
            _assert_policy_writable(_policy(created_by=None), _user(uid=7))
        assert ei.value.status_code == 403

    def test_legacy_missing_creator_attr_fail_closed(self):
        """记录对象缺 created_by 属性 → 同样 fail-closed。"""
        rec = SimpleNamespace(id=10, status="draft")
        with pytest.raises(HTTPException) as ei:
            _assert_policy_writable(rec, _user(uid=7))
        assert ei.value.status_code == 403


class TestPolicyWriteEndpointsWired:
    """确认五个写端点确实接入了守卫（防止后续重构把它丢掉）。"""

    @pytest.mark.parametrize(
        "endpoint_name",
        ["update_policy", "delete_policy", "publish_policy", "archive_policy", "upload_policy_file"],
    )
    def test_endpoint_source_contains_guard(self, endpoint_name):
        import inspect

        from app.api.v1 import policy as policy_mod

        fn = getattr(policy_mod, endpoint_name)
        src = inspect.getsource(fn)
        assert "_assert_policy_writable(" in src, f"{endpoint_name} 未接入归属守卫"

    @pytest.mark.asyncio
    async def test_delete_policy_rejects_non_owner(self):
        """端到端：非创建人删除他人政策 → 403 且**不产生软删**。"""
        from app.api.v1 import policy as policy_mod

        rec = MagicMock()
        rec.id = 10
        rec.created_by = 999
        rec.status = "draft"
        rec.title = "他人政策"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec

        with pytest.raises(HTTPException) as ei:
            await policy_mod.delete_policy(10, current_user=_user(uid=7), db=db)
        assert ei.value.status_code == 403
        # 关键：守卫必须在软删与提交之前抛错 —— 绝不能落到「删除成功」
        db.commit.assert_not_called()
