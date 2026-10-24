# -*- coding: utf-8 -*-
"""首次初始化的单位编码契约（`app/api/v1/system/init.py::_resolve_root_org_code`）。

v1.16.4 起组织编码是首次初始化的强制契约，该函数有 4 条出口：
缺 code / 非数字或长度非法 / 非省级 / 合法。
此前只有"缺 code"被偶然覆盖（旧测试构造器漏传 code 才走到），另外两条错误分支
从未被断言 —— CI 合并覆盖率因此在 `init.py` 出现 134-135、138 三行缺口
（`TOTAL 45563 5 11328 1 99.99%`）。本文件逐条钉住，避免再靠副作用覆盖。
"""

import pytest
from fastapi import HTTPException

from app.api.v1.system import init as init_mod
from app.api.v1.system.init import _resolve_root_org_code


class TestResolveRootOrgCode:
    def test_missing_code_raises_400(self):
        with pytest.raises(HTTPException) as ei:
            _resolve_root_org_code(None)
        assert ei.value.status_code == 400
        assert "必须提供单位编码" in ei.value.detail

    def test_blank_code_raises_400(self):
        with pytest.raises(HTTPException) as ei:
            _resolve_root_org_code("   ")
        assert ei.value.status_code == 400

    def test_non_numeric_code_raises_400(self):
        with pytest.raises(HTTPException) as ei:
            _resolve_root_org_code("abc123")
        assert ei.value.status_code == 400
        assert "纯数字" in ei.value.detail

    def test_wrong_length_code_raises_400(self):
        with pytest.raises(HTTPException) as ei:
            _resolve_root_org_code("5201")
        assert ei.value.status_code == 400
        assert "6 位" in ei.value.detail

    def test_non_province_level_raises_400(self):
        """市级码（末两位非 00 的省级位）不能作为根组织。"""
        with pytest.raises(HTTPException) as ei:
            _resolve_root_org_code("520100")
        assert ei.value.status_code == 400
        assert "根组织必须是省级单位" in ei.value.detail

    def test_county_level_code_raises_400(self):
        with pytest.raises(HTTPException) as ei:
            _resolve_root_org_code("520102")
        assert ei.value.status_code == 400

    def test_valid_province_code_passes(self):
        assert _resolve_root_org_code("520000") == "520000"

    def test_surrounding_space_is_stripped(self):
        assert _resolve_root_org_code("  520000  ") == "520000"


class TestEnsureRootOrganizationHttpException:
    """`_ensure_root_organization` 的参数错误路径（init.py 179-180）。

    根组织不存在 + 缺 code 时，`_resolve_root_org_code` 抛 400；
    该 except 必须**原样上抛**（不能被下面的 `except Exception` 包成 500）并回滚。
    此前这条只靠旧测试构造器漏传 code 顺带覆盖，构造器修好后必须显式钉住。
    """

    async def test_missing_code_rolls_back_and_reraises_400(self, monkeypatch):
        from unittest.mock import MagicMock

        db = MagicMock(name="db")
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        request = init_mod.InitRequest(
            organization_name="某单位",
            admin_username="admin",
            admin_password="Str0ng!Passw0rd#2026",
        )
        steps: list[dict] = []

        with pytest.raises(HTTPException) as ei:
            await init_mod._ensure_root_organization(db, request, steps)

        assert ei.value.status_code == 400
        assert "必须提供单位编码" in ei.value.detail
        db.rollback.assert_called_once()
        assert steps == []
