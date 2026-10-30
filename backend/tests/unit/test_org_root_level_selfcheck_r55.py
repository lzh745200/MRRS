# -*- coding: utf-8 -*-
"""根组织层级相关的同类缺陷回归（2026-10-30）。

共同根因：v1.18.14 起「省 / 市州 / 县级都可作为根组织」，但旧规则「根必须是省级」
残留在多处，导致市州级单位（如黔南州 522700）被误拒或误报：

| 位置 | 旧行为 | 影响 |
|---|---|---|
| api/v1/organization.py::_resolve_create_code | 无父级时仍要求 child_order == 0+1 | **422 拒绝建根**（用户实测）|
| services/self_check_service.py::_check_org_hierarchy | 根 level != 1 记入 problems | 自检**误报**「根组织非省级」|
"""
from types import SimpleNamespace
from unittest.mock import MagicMock


def _org(id_, name, level, parent_id=None, code="522700"):
    return SimpleNamespace(
        id=id_, name=name, level=level, parent_id=parent_id, code=code, is_active=True,
    )


def _run_check(orgs):
    from app.services.self_check_service import _check_org_hierarchy

    db = MagicMock()
    # db.query(Organization).filter(...).all() → orgs
    db.query.return_value.filter.return_value.all.return_value = orgs
    return _check_org_hierarchy(db)


def test_root_prefecture_not_flagged():
    """根组织为市州级（level=2）时，自检不得报「根组织非省级」。"""
    r = _run_check([_org(1, "黔南州", "2")])
    assert r["level"] == "ok", r
    assert "根组织非省级" not in r["detail"]


def test_root_county_not_flagged():
    """根组织为县市级（level=3）同样合规（业务只有三级，县级根不再建下级）。"""
    r = _run_check([_org(1, "都匀市", "3")])
    assert r["level"] == "ok", r


def test_root_province_still_ok():
    """省级根（原有行为）不得回归。"""
    r = _run_check([_org(1, "贵州省", "1")])
    assert r["level"] == "ok", r


def test_skip_level_still_flagged():
    """真正跨级（省 → 县市）必须仍被报出来，修复不能放宽。"""
    orgs = [_org(1, "贵州省", "1"), _org(2, "都匀市", "3", parent_id=1)]
    r = _run_check(orgs)
    assert r["level"] == "warn", r
    assert "父级与子级不相邻" in r["detail"]


def test_normal_chain_ok():
    """省 → 市州 → 县市 正常链不得报警。"""
    orgs = [
        _org(1, "贵州省", "1"),
        _org(2, "黔南州", "2", parent_id=1),
        _org(3, "都匀市", "3", parent_id=2),
    ]
    r = _run_check(orgs)
    assert r["level"] == "ok", r