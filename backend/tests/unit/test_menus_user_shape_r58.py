# -*- coding: utf-8 -*-
"""回归：前端整站导航的数据源 /menus/accessible 不得因 user 对象形态不完整而 500。

背景（2026-10-31 巡检）：menus.py 里 4 处直接访问 user.allowed_menus_list，
而 auth.py 的 4 处用 getattr(..., None) 防御 —— 同一契约两种写法。
实测：传入缺该属性的 user 对象（SimpleNamespace / 非 ORM 契约）时，
/menus/accessible 抛 AttributeError → 500，前端整站导航拿不到菜单。
修复：menus.py 统一改为 getattr 兜底。
"""
from types import SimpleNamespace


def _user(**kw):
    base = dict(
        id=1, username="admin", role="super_admin", is_superuser=True, is_active=True,
        organization_id=None, permissions_list=["*"], data_scope=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _call(client, user):
    from app.core.security import get_current_user
    from app.main import app

    prev = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        return client.get("/api/v1/menus/accessible")
    finally:
        if prev is not None:
            app.dependency_overrides[get_current_user] = prev
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_tolerates_user_without_allowed_menus_list(client):
    """缺 allowed_menus_list 的用户对象：不得 500（修复前实测 500 + AttributeError）。"""
    r = _call(client, _user())
    assert r.status_code == 200, r.text[:250]
    body = r.json()
    assert body.get("success") is True, body


def test_explicit_none_uses_role_default(client):
    """显式 allowed_menus_list=None → source 应为 role（未设用户级配置）。"""
    r = _call(client, _user(allowed_menus_list=None))
    assert r.status_code == 200, r.text[:250]
    assert r.json().get("source") == "role", r.json().get("source")


def test_explicit_empty_list_means_no_menu(client):
    """显式空数组 [] → source=user（表示"无菜单"而非"继承"）。"""
    r = _call(client, _user(allowed_menus_list=[]))
    assert r.status_code == 200, r.text[:250]
    assert r.json().get("source") == "user", r.json().get("source")
