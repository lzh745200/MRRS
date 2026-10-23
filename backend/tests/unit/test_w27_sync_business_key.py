"""W27 回归：多机同步业务键（W26 全栈检测 P0-1「同组织跨机主键碰撞」）。

## 缺陷（W26 检测确认 + 探针实证）
``data_package_service.BUSINESS_KEYS`` 旧定义只有一个字段 ``organization_id``，
而导入时 ``_clean_record`` 又把**每条记录**的 organization_id 强制改写为目标组织。
于是「同组织两台机器」这一**最常见部署**下所有记录的业务键完全相同：
  * ``overwrite=True``  → 本机真实记录被源机数据覆写（**不可逆**）
  * ``overwrite=False`` → 源机记录被静默丢弃
  * ``relocated``（换新 id 插入）分支永不触发

另外 ``_classify_import_records`` 在业务键**不可判定**（``key is None``）时
把记录归入 ``same_records`` → 同样会覆写，是危险默认。

## 修复
1. 业务键改为「组织 + 业务唯一标识」（projects/schools 的 ``code`` 是 DB UNIQUE，
   funds ``code`` 是 ADR-0011 业务编号，villages 用「行政区划+村名」复合键）。
2. 业务键不可判定 → 归入 ``relocated``（新 id 插入），**绝不当成同一条**。
"""

from unittest.mock import MagicMock

import pytest


class TestBusinessKeyDefinition:
    """业务键定义本身的正确性（不依赖 DB）。"""

    def test_every_syncable_table_has_discriminating_key(self):
        """核心断言：业务键不能只有 organization_id（否则同组织内恒相同）。"""
        from app.services.data_package_service import BUSINESS_KEYS

        assert BUSINESS_KEYS, "业务键定义不可为空"
        for table, fields in BUSINESS_KEYS.items():
            assert len(fields) >= 2, f"{table} 业务键只有一个字段，无法区分记录"
            assert "organization_id" in fields, f"{table} 业务键应含组织边界"
            non_org = [f for f in fields if f != "organization_id"]
            assert non_org, f"{table} 缺少业务标识字段"

    def test_key_fields_exist_on_models(self):
        """业务键引用的列必须真实存在于模型（防止写错列名导致 key 恒为 None）。"""
        import app.models as M

        for n in M.__all__:
            try:
                getattr(M, n)
            except Exception:
                pass
        from app.models.base import Base
        from app.services.data_package_service import BUSINESS_KEYS

        for table, fields in BUSINESS_KEYS.items():
            assert table in Base.metadata.tables, f"未知表 {table}"
            cols = {c.name for c in Base.metadata.tables[table].columns}
            for f in fields:
                assert f in cols, f"{table}.{f} 不存在（业务键失效将退化为覆写）"

    def test_conflict_resolver_keys_match_single_source(self):
        """``smart_conflict_resolver`` 的键必须与单一事实源一致（去掉组织部分）。

        历史上两处各自硬编码且键名不一致（``villages`` vs ``supported_villages``，
        一侧只有 ``village_name``），本用例把漂移变成红灯。
        """
        from app.services.data_package_service import BUSINESS_KEYS
        from app.services.smart_conflict_resolver import (
            BUSINESS_KEY_FIELDS,
            BUSINESS_KEY_FIELDS_TABLE_ALIAS,
        )

        assert set(BUSINESS_KEY_FIELDS) == set(BUSINESS_KEY_FIELDS_TABLE_ALIAS)
        for alias, table in BUSINESS_KEY_FIELDS_TABLE_ALIAS.items():
            expected = [f for f in BUSINESS_KEYS[table] if f != "organization_id"]
            assert BUSINESS_KEY_FIELDS[alias] == expected, (
                f"{alias}({table}) 业务键与单一事实源不一致："
                f"{BUSINESS_KEY_FIELDS[alias]} != {expected}"
            )


class TestBusinessKeyOf:
    def test_returns_none_when_any_component_missing(self):
        from app.services.data_package_service import _business_key_of
        from app.models.project import Project

        # code 缺失 → 不可判定
        assert _business_key_of(Project, {"organization_id": 1}) is None
        # 空白字符串亦视为缺失
        assert _business_key_of(Project, {"organization_id": 1, "code": "  "}) is None

    def test_returns_tuple_when_complete(self):
        from app.models.project import Project
        from app.services.data_package_service import _business_key_of

        assert _business_key_of(Project, {"organization_id": 1, "code": "P-1"}) == (1, "P-1")

    def test_unknown_table_returns_none(self):
        from app.services.data_package_service import _business_key_of

        assert _business_key_of(MagicMock(__tablename__="nope"), {"a": 1}) is None

    def test_village_key_uses_admin_division_and_name(self):
        """村庄业务键 = 组织 + 县 + 村名。

        只到「县」不细分乡镇：县内行政村名在行政区划上唯一，足以区分记录；
        乡镇/街道常因历史数据未填而缺失，纳入业务键会让键频繁"不可判定"
        → 退化成 relocated（每次都新增重复行）。
        """
        from app.models.supported_village import SupportedVillage
        from app.services.data_package_service import _business_key_of

        rec = {
            "organization_id": 1, "province": "贵州省", "city": "黔南州",
            "county": "都匀市", "township": "墨冲镇", "village_name": "甲村",
        }
        assert _business_key_of(SupportedVillage, rec) == (1, "都匀市", "甲村")


class TestClassifyImportRecordsFailSafe:
    """``_classify_import_records`` 的分类安全性（P0 核心回归）。"""

    def _service(self, existing_rows):
        """构造一个只实现必要查询的服务替身。"""
        from app.services.data_package_service import DataPackageService

        svc = object.__new__(DataPackageService)
        svc.db = MagicMock()
        return svc

    def _patch_db(self, svc, existing):
        """existing: {pk: model_instance_dict}"""
        db = svc.db
        # 第一段：查询已存在的 pk
        db.query.return_value.filter.return_value.all.return_value = [(k,) for k in existing]
        # 第二段：按 pk 取本地记录
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    def test_undeterminable_key_goes_to_relocated_not_same(self):
        """业务键不可判定 → relocated（新 id 插入），绝不进入 same（覆写）。"""
        from app.models.project import Project

        svc = self._service({})
        self._patch_db(svc, {1: {"code": "P-1"}})
        model = Project
        # 主键撞 1，但缺 code → key None
        rec = {"id": 1, "organization_id": 1, "name": "无编号项目"}

        free, same, relocated = svc._classify_import_records(model, [rec], "id")
        assert same == [], "业务键不可判定时不得判为同一条记录（否则会覆写本机数据）"
        assert relocated == [rec]
        assert free == []

    def test_same_key_goes_to_same(self):
        from app.models.project import Project

        svc = self._service({})
        db = self._patch_db(svc, {1: {}})
        local = MagicMock()
        local.organization_id = 1
        local.code = "P-1"
        db.query.return_value.filter.return_value.first.return_value = local

        rec = {"id": 1, "organization_id": 1, "code": "P-1"}
        free, same, relocated = svc._classify_import_records(Project, [rec], "id")
        assert same == [rec]
        assert relocated == []

    def test_different_key_goes_to_relocated(self):
        """同组织、同主键、不同 code → 两条不同记录 → relocated（保留本机原记录）。"""
        from app.models.project import Project

        svc = self._service({})
        db = self._patch_db(svc, {1: {}})
        local = MagicMock()
        local.organization_id = 1
        local.code = "P-LOCAL"
        db.query.return_value.filter.return_value.first.return_value = local

        rec = {"id": 1, "organization_id": 1, "code": "P-REMOTE"}
        free, same, relocated = svc._classify_import_records(Project, [rec], "id")
        assert same == []
        assert relocated == [rec]

    def test_same_org_same_code_is_same_record(self):
        """同组织、同 code → 同一条记录（可安全 overwrite 更新）。"""
        from app.models.school import School

        svc = self._service({})
        db = self._patch_db(svc, {5: {}})
        local = MagicMock()
        local.organization_id = 2
        local.code = "S-001"
        db.query.return_value.filter.return_value.first.return_value = local

        rec = {"id": 5, "organization_id": 2, "code": "S-001"}
        free, same, relocated = svc._classify_import_records(School, [rec], "id")
        assert same == [rec]

    def test_free_record_when_pk_not_taken(self):
        from app.models.school import School

        svc = self._service({})
        self._patch_db(svc, {})
        rec = {"id": 99, "organization_id": 1, "code": "S-9"}
        free, same, relocated = svc._classify_import_records(School, [rec], "id")
        assert free == [rec]
        assert same == [] and relocated == []
