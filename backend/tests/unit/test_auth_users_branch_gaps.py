"""auth/users.py 分支覆盖缺口专项（分支清零第六批）。

覆盖 coverage report --show-missing 实测的 7 个部分分支：
- update_current_user_profile：多字段 setattr 的循环回边（237->236）；
- update_user：管理员自改自己且新角色仍为 admin（626->630）、
  未携带 organization_id（634->638）、未携带 data_scope（659->662）；
- update_user_permissions：payload 不含 organization_id（723->727）、
  role（728->730）、data_scope（740->744）。

全部为直调函数级用例（asyncio_mode=auto）。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.v1.auth.users import (
    ProfileUpdate,
    UserPermissionsUpdate,
    UserUpdateBody,
    update_current_user_profile,
    update_user,
    update_user_permissions,
)


def _admin():
    u = MagicMock()
    u.id = 1
    u.username = "admin"
    u.role = "admin"
    u.is_superuser = True
    u.is_active = True
    u.permissions_list = ["*"]
    u.organization_id = 1
    return u


def _db_returning(obj):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = obj
    return db


async def test_update_profile_multiple_fields_loop_back():
    """个人资料更新含模型上不存在的字段（gender/address）→ hasattr 假 → 循环回边（237->236）。

    user 用 SimpleNamespace（非 MagicMock）：MagicMock 的 hasattr 恒为真，
    无法触发 hasattr 假分支；尾部响应只读取 user 上已存在的属性，不受影响。
    """
    user = SimpleNamespace(
        id=1,
        username="zhang",
        full_name="",
        email="",
        phone="",
        department="",
        position="",
        avatar="",
        last_login=None,
        created_at=None,
        is_active=True,
        allowed_menus_list=[],
        role="user",
        # 注意：故意不预设 gender / address / birthday / remark（响应尾部用 getattr 兜底）
    )
    db = _db_returning(user)
    data = ProfileUpdate(full_name="张三", gender="男", address="某市某区")

    resp = await update_current_user_profile(data=data, current_user=user, db=db)

    assert user.full_name == "张三"
    # SimpleNamespace 上不存在 gender/address 属性 → hasattr 为假 → 回到循环
    assert not hasattr(user, "gender")
    assert resp["success"] is True


async def test_update_user_self_with_admin_role_keeps_permission():
    """管理员自改自己、新角色仍为 admin → 不触发自锁保护（626->630）；
    未携带 organization_id 与 data_scope → 两个可选校验块跳过（634->638、659->662）。"""
    user = MagicMock()
    user.id = 1
    user.role = "user"
    user.organization_id = 1
    user.is_active = True
    db = _db_returning(user)
    data = UserUpdateBody(role="admin", organization_id=1, data_scope="all", full_name="管理员甲")

    await update_user(user_id=1, data=data, current_user=_admin(), db=db)

    assert user.role == "admin"
    assert user.full_name == "管理员甲"


async def test_update_user_role_none_rejected():
    """role 显式为 None → 归一化跳过、直接判无效角色 400（728->730 同型弧）。"""
    import pytest
    from fastapi import HTTPException

    db = MagicMock()
    user = MagicMock()
    user.id = 1
    user.role = "admin"
    user.is_superuser = True
    user.organization_id = 1
    db.query.return_value.filter.return_value.first.return_value = user
    data = UserUpdateBody(role=None)

    with pytest.raises(HTTPException) as exc:
        await update_user(user_id=1, data=data, current_user=_admin(), db=db)
    assert exc.value.status_code == 400


async def test_update_user_permissions_without_role_org_scope():
    """权限分配仅改 is_active/machine_binding_required →
    三个可选校验块全部跳过（723->727、728->730、740->744）。"""
    target = MagicMock()
    target.id = 2
    target.role = "user"
    target.is_superuser = False
    target.organization_id = 1
    db = _db_returning(target)
    data = UserPermissionsUpdate(
        is_active=True, organization_id=1, role="admin", data_scope="all"
    )

    await update_user_permissions(user_id=2, data=data, current_user=_admin(), db=db)

    assert target.is_active is True
    assert target.role == "admin"


async def test_update_permissions_role_none_rejected():
    """role 显式为 None → 归一化跳过、直接判无效角色 400（728->730）。"""
    import pytest
    from fastapi import HTTPException

    target = MagicMock()
    target.id = 2
    target.role = "user"
    target.is_superuser = False
    db = _db_returning(target)
    data = UserPermissionsUpdate(role=None)

    with pytest.raises(HTTPException) as exc:
        await update_user_permissions(user_id=2, data=data, current_user=_admin(), db=db)
    assert exc.value.status_code == 400
