# -*- coding: utf-8 -*-
"""P1–P4 回归测试：组织编码接入权威行政区划表（2026-10-27）。

## 背景（真实缺陷，均由体检实证）

| 编号 | 缺陷 | 本文件对应用例 |
|---|---|---|
| P1 | 初始化建根组织时编码被随机 `ORG-XXXXXXXX` 替换，忽略传入的行政区划代码 | `TestServicePersistsAdminCode` |
| P2 | 初始化硬性要求省级编码（`XX0000`），市州/县级单位无法首启 | `TestInitRootCodeLevels` |
| P3 | 只按末位规律判层级，**不校验代码是否真实存在**（`522799` 可入库） | `TestExistence` |
| P4 | 只校验层级差，**不校验父子同属一个行政区划**（522701 可挂到 520100 下） | `TestParentChild` |

数据基准：`backend/app/data/admin_divisions.json`
（省级=GB/T 2260；贵州市州/县级=仓库内置 geojson adcode，88 个县级要素）。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.admin_division_service import AdminDivisionService as ADS
from app.services.organization_code_service import OrganizationCodeService as OCS

# 黔南布依族苗族自治州及 12 个县市（GeoJSON 权威 adcode）
QIANNAN = "522700"
QIANNAN_COUNTIES = {
    "522701": "都匀市",
    "522702": "福泉市",
    "522722": "荔波县",
    "522723": "贵定县",
    "522725": "瓮安县",
    "522726": "独山县",
    "522727": "平塘县",
    "522728": "罗甸县",
    "522729": "长顺县",
    "522730": "龙里县",
    "522731": "惠水县",
    "522732": "三都水族自治县",
}


class TestTableIntegrity:
    """权威表自身完整性：父子闭合、层级与末位规律一致、覆盖范围可读。"""

    def test_picture_of_coverage(self):
        cov = ADS.coverage()
        assert cov["level1"] == 34, "全国省级应为 34 个"
        assert cov["level2"] == 9, "贵州省 9 个市州"
        assert cov["level3"] == 88, "贵州省 88 个县级单位"
        assert cov["aliases"] >= 1

    def test_qiannan_and_all_counties_resolve(self):
        assert ADS.name_of(QIANNAN) == "黔南布依族苗族自治州"
        assert ADS.level_of(QIANNAN) == 2
        for code, name in QIANNAN_COUNTIES.items():
            item = ADS.lookup(code)
            assert item is not None, f"{code} 应在权威表中"
            assert item["name"] == name
            assert item["level"] == 3
            assert item["parent"] == QIANNAN, f"{code} 的上级必须是黔南州"

    def test_child_parent_closed(self):
        """表内每个下级都能找到其上级（无悬空节点）。"""
        for code in list(QIANNAN_COUNTIES):
            assert ADS.lookup(ADS.parent_of(code)) is not None

    def test_level_matches_pattern_for_guizhou(self):
        """贵州全量：表内层级必须与末位规律一致（否则说明数据或规则有误）。"""
        for code in list(QIANNAN_COUNTIES) + [QIANNAN, "520000", "520100", "520102"]:
            assert ADS.level_of(code) == ADS.pattern_level(code), code


class TestExistence:
    """P3：不存在的代码必须被拒绝（贵州为全量校验）。"""

    @pytest.mark.parametrize("bad", ["522799", "5227000", "52270", "5227AB", "", "  "])
    def test_rejects_bad_codes(self, bad):
        with pytest.raises(ValueError):
            ADS.validate_code(bad)

    def test_rejects_unlisted_guizhou_code(self):
        """"522724" 是贵州代码段里的空号（荔波 522722 与 瓮安 522725 之间）。"""
        with pytest.raises(ValueError) as exc:
            ADS.validate_code("522724")
        assert "权威区划表" in str(exc.value)

    def test_accepts_real_codes(self):
        for code in ["520000", QIANNAN, *QIANNAN_COUNTIES]:
            assert ADS.validate_code(code) == code

    def test_other_provinces_fall_back_to_pattern(self):
        """未入表的省份退回末位规律（不误杀）：320102（南京市玄武区）。"""
        assert ADS.lookup("320102") is None
        assert ADS.validate_code("320102") == "320102"

    def test_alias_normalized(self):
        assert ADS.validate_code("520222") == "520281"


class TestParentChild:
    """P4：父子必须同属一个行政区划。"""

    def test_county_under_wrong_prefecture_rejected(self):
        """522701（都匀市，黔南）不能挂到 520100（贵阳市）下。"""
        with pytest.raises(ValueError) as exc:
            ADS.validate_code("522701", parent_code="520100")
        msg = str(exc.value)
        assert QIANNAN in msg and "520100" in msg

    def test_county_under_correct_prefecture_ok(self):
        for code in QIANNAN_COUNTIES:
            assert ADS.validate_code(code, parent_code=QIANNAN) == code

    def test_county_under_other_qian_prefecture_rejected(self):
        """522701 与 522600（黔东南州）同省不同州，也必须拒绝。"""
        with pytest.raises(ValueError):
            ADS.validate_code("522701", parent_code="522600")

    def test_prefecture_under_wrong_province_rejected(self):
        with pytest.raises(ValueError):
            ADS.validate_code(QIANNAN, parent_code="530000")  # 云南省

    def test_pattern_fallback_parent_check(self):
        """表外代码（如江苏）按前缀校验父子：320102 的上级应为 320100。"""
        assert ADS.validate_code("320102", parent_code="320100") == "320102"
        with pytest.raises(ValueError):
            ADS.validate_code("320102", parent_code="320200")


class TestInferLevelUsesTable:
    """层级判定以表为准（规律仅兜底）。"""

    def test_table_levels(self):
        assert OCS.infer_level("520000") == "level_1"
        assert OCS.infer_level(QIANNAN) == "level_2"
        assert OCS.infer_level("522701") == "level_3"

    def test_unknown_code_still_pattern_classified(self):
        assert OCS.infer_level("320102") == "level_3"


class TestServicePersistsAdminCode:
    """P1：OrganizationService 必须落传入的行政区划代码，不能生成随机码。"""

    def _svc(self, first_results):
        from app.services.organization_service import OrganizationService

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = first_results
        db.query.return_value.filter.return_value.scalar.return_value = 0
        # flush 后模拟自增 id，路径才能落成 "/{id}/"
        db.add.side_effect = lambda obj: setattr(obj, "id", 42)
        db.flush.side_effect = lambda: None
        return OrganizationService(db=db), db

    def test_root_keeps_code_and_level(self):
        svc, db = self._svc([None])
        data = SimpleNamespace(
            parent_id=None, code=QIANNAN, code_prefix="ORG", name="黔南州",
            is_active=True, description=None, contact_person=None,
            contact_phone=None, address=None,
        )
        org = asyncio.run(svc.create_organization(data, created_by=0))
        assert org.code == QIANNAN
        assert str(org.level) == "2"
        assert org.path == "/42/"

    def test_child_keeps_code_and_level(self):
        parent = SimpleNamespace(id=1, code=QIANNAN, level="2", path="/1/")
        svc, db = self._svc([parent, None])
        data = SimpleNamespace(
            parent_id=1, code="522701", code_prefix="ORG", name="都匀市",
            is_active=True, description=None, contact_person=None,
            contact_phone=None, address=None,
        )
        org = asyncio.run(svc.create_organization(data, created_by=0))
        assert org.code == "522701"
        assert str(org.level) == "3"

    def test_child_with_wrong_code_prefix_rejected(self):
        """P4 在服务层同样生效：都匀市挂到贵阳市下 → ValueError。"""
        parent = SimpleNamespace(id=1, code="520100", level="2", path="/1/")
        svc, _ = self._svc([parent, None])
        data = SimpleNamespace(
            parent_id=1, code="522701", code_prefix="ORG", name="都匀市",
            is_active=True, description=None, contact_person=None,
            contact_phone=None, address=None,
        )
        with pytest.raises(ValueError):
            asyncio.run(svc.create_organization(data, created_by=0))

    def test_duplicate_code_rejected(self):
        from app.services.organization_service import OrganizationCodeDuplicateError

        svc, _ = self._svc([MagicMock()])  # 查重命中
        data = SimpleNamespace(
            parent_id=None, code=QIANNAN, code_prefix="ORG", name="重复州",
            is_active=True, description=None, contact_person=None,
            contact_phone=None, address=None,
        )
        with pytest.raises(OrganizationCodeDuplicateError):
            asyncio.run(svc.create_organization(data, created_by=0))

    def test_missing_code_rejected(self):
        svc, _ = self._svc([None])
        data = SimpleNamespace(
            parent_id=None, code="", code_prefix="ORG", name="无码单位",
            is_active=True, description=None, contact_person=None,
            contact_phone=None, address=None,
        )
        with pytest.raises(ValueError):
            asyncio.run(svc.create_organization(data, created_by=0))


class TestDegradedMode:
    """表不可用（未打包/文件损坏）时必须降级为"仅末位规律"，绝不误杀。"""

    def test_missing_file_falls_back_to_pattern(self, monkeypatch, tmp_path):
        import app.services.admin_division_service as mod

        monkeypatch.setattr(mod, "DATA_FILE", tmp_path / "missing.json")
        mod._table.cache_clear()
        mod._aliases.cache_clear()
        try:
            assert mod.AdminDivisionService.lookup("522701") is None
            # 缺表 → 不再做存在性强校验，522799 按规律放行（县市级）
            assert mod.AdminDivisionService.validate_code("522799") == "522799"
            assert OCS.infer_level("522799") == "level_3"
        finally:
            mod._table.cache_clear()
            mod._aliases.cache_clear()

    def test_corrupt_file_falls_back(self, monkeypatch, tmp_path):
        import app.services.admin_division_service as mod

        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(mod, "DATA_FILE", bad)
        mod._table.cache_clear()
        mod._aliases.cache_clear()
        try:
            assert mod.AdminDivisionService.coverage()["level1"] == 0
        finally:
            mod._table.cache_clear()
            mod._aliases.cache_clear()


class TestInitRootCodeLevels:
    """P2：首启单位可以是省 / 市州 / 县级。"""

    def test_levels_accepted(self):
        from app.api.v1.system.init import _resolve_root_org_code

        assert _resolve_root_org_code("520000") == "520000"
        assert _resolve_root_org_code(QIANNAN) == QIANNAN
        assert _resolve_root_org_code("522701") == "522701"

    def test_unknown_code_rejected(self):
        from fastapi import HTTPException

        from app.api.v1.system.init import _resolve_root_org_code

        with pytest.raises(HTTPException) as exc:
            _resolve_root_org_code("522799")
        assert exc.value.status_code == 400
