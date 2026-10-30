# -*- coding: utf-8 -*-
"""根组织层级误判的回归（2026-10-30，用户实测 522700 被拒）。

症状：输入黔南州市州级代码 522700 新建**根组织**（无上级），
报 422「层级必须逐级挂接：省级 → 市州级 → 县市级（当前上级层级不匹配）」。

根因：`_resolve_create_code` 在 parent 为 None 时把 parent_order 当成 0，
仍要求 child_order == parent_order + 1 → 根组织被迫只能是省级（order=1）。
这与 organization_service.create_organization（只在 parent 存在时校验）不一致，
也违反 v1.18.14「首启单位不限于省级：省 / 市州 / 县级都可作为根组织」。
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.organization import _resolve_create_code


def _resolve(code, parent, declared=None):
    db = MagicMock()
    # 查重：无冲突
    db.query.return_value.filter.return_value.first.return_value = None
    return _resolve_create_code(db, code, parent, declared)


def test_root_prefecture_level_allowed():
    """无上级时，市州级代码（522700 黔南州）必须能建为根组织。"""
    code, order = _resolve("522700", None)
    assert code == "522700"
    assert order == 2, "市州级 order 应为 2"


def test_root_county_level_allowed():
    """无上级时，县市级代码（522701 都匀市）同样可建为根组织。"""
    code, order = _resolve("522701", None)
    assert code == "522701"
    assert order == 3, "县市级 order 应为 3"


def test_root_province_level_allowed():
    """省级根（原有行为）不得回归。"""
    code, order = _resolve("520000", None)
    assert code == "520000"
    assert order == 1


def test_child_still_requires_consecutive_level():
    """有上级时，跨级依然必须被拒（本次修复不能放宽子级校验）。"""
    from types import SimpleNamespace

    parent = SimpleNamespace(id=1, code="520000", level="1", path="/1/")  # 省级
    with pytest.raises(HTTPException) as exc:
        _resolve("522701", parent)  # 直接挂县级 → 跨级
    assert exc.value.status_code == 422
    assert "逐级挂接" in exc.value.detail


def test_child_correct_level_passes():
    """有上级且层级正确（市州级 → 县市级）必须通过。"""
    from types import SimpleNamespace

    parent = SimpleNamespace(id=2, code="522700", level="2", path="/1/2/")
    code, order = _resolve("522701", parent)
    assert code == "522701"
    assert order == 3