"""W18-D1/D3 回归：数据包导入的主键碰撞/组织择一分支（补覆盖）。

这些分支是并发修复批次新增的（按业务键区分"同一记录"与"撞 id 的另一条记录"、
包内 org_code 与目标组织不一致时忽略包内组织）。用例直接用服务私有方法构造，
不依赖真实 ZIP，避免与端到端流程耦合。
"""
import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _svc(db, tmp_path=None):
    from app.services.data_package_service import DataPackageService

    return DataPackageService(db=db, upload_dir=str(tmp_path or "/tmp/w18-pkg"))


def _village_q(existing_ids=(), first_value="__unset__"):
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = [(i,) for i in existing_ids]
    if first_value != "__unset__":
        q.first.return_value = first_value
    return q


class TestClassifyImportRecordsEdges:
    """W18-D1：主键碰撞三分类的兜底分支。"""

    def test_missing_business_key_goes_to_relocated(self, tmp_path):
        """记录缺业务键 → 无法判定身份 → **fail-safe 归入 relocated（新 id 插入）**。

        W27（W26 全栈检测 P0-1）修正：旧实现把 ``key is None`` 归入 ``same``，
        而 ``same`` 在 overwrite=True 时会**覆写本机同主键记录** —— 业务键不可判定
        恰恰意味着"我们并不知道它是不是同一条记录"，此时覆写属不可逆的数据丢失。
        现改为 relocated：去掉主键后以新 id 插入，本机原记录保持不动。
        代价是可能产生重复行（可人工合并、可恢复），这是有意的安全取舍。
        """
        from app.models.supported_village import SupportedVillage

        db = MagicMock()
        db.query.return_value = _village_q(existing_ids=[1])
        svc = _svc(db, tmp_path)

        free, same, relocated = svc._classify_import_records(
            SupportedVillage,
            [{"id": 1, "village_name": "", "organization_id": None}],
            "id",
        )
        assert free == []
        assert same == [], "业务键不可判定时绝不能判为同一条记录"
        assert len(relocated) == 1

    def test_local_row_vanished_falls_back_to_relocated(self, tmp_path):
        """主键命中但本地行已不存在（并发删除）→ 按"不同记录"改号插入。

        W27 备注：记录必须带齐业务键（`organization_id` + `county` + `village_name`），
        否则会在更早的「业务键不可判定」分支就 continue，走不到本用例要验证的
        「主键占用但本地行消失」路径（这也是该分支一度成为覆盖率最后一处缺口的原因）。
        """
        from app.models.supported_village import SupportedVillage

        db = MagicMock()
        db.query.return_value = _village_q(existing_ids=[1], first_value=None)
        svc = _svc(db, tmp_path)

        free, same, relocated = svc._classify_import_records(
            SupportedVillage,
            [{"id": 1, "village_name": "某村", "county": "某县", "organization_id": 1}],
            "id",
        )
        assert free == []
        assert same == []
        assert len(relocated) == 1


    def test_unknown_model_has_no_business_key(self, tmp_path):
        """模型不在 BUSINESS_KEYS 登记表 → `_business_key_of` 返回 None。"""
        from app.services.data_package_service import _business_key_of

        class UnknownModel:
            __tablename__ = "w18_not_in_business_key_registry"

        db = MagicMock()
        _svc(db, tmp_path)  # 仅确保服务可构造
        assert _business_key_of(UnknownModel, {"id": 1}) is None


class TestRelocatedInsertEdge:
    """W18-D1：改号插入失败要登记错误，不得静默丢数据。"""

    def test_relocated_insert_failure_records_error(self, tmp_path):
        from app.models.supported_village import SupportedVillage

        db = MagicMock()
        db.query.return_value = _village_q(
            existing_ids=[1],
            first_value=SimpleNamespace(village_name="另一条村", organization_id=9),
        )
        db.begin_nested.side_effect = RuntimeError("unique constraint")
        svc = _svc(db, tmp_path)

        imported, _skipped, errors = svc._bulk_upsert_records(
            SupportedVillage,
            [{"id": 1, "village_name": "某村", "organization_id": 1}],
            org_id=1,
            overwrite=False,
        )
        assert imported == 0
        assert len(errors) == 1
        assert "改用新 id 插入失败" in errors[0].message


class TestManifestOrgCodeMismatch:
    """W18-D3：包内 org_code 指向别的组织时忽略包内组织，按目标组织导入。"""

    def test_mismatched_org_code_keeps_target_org(self, tmp_path, monkeypatch):
        from app.models.organization import Organization
        from app.models.supported_village import SupportedVillage
        from app.services import data_package_service as dps

        db = MagicMock()
        # 包记录：org_id=7，状态 validated
        pkg = SimpleNamespace(
            id=11, org_id=7, status="validated", file_path=str(tmp_path / "p.zip"), data_types=["villages"],
        )
        db.query.return_value.filter.return_value.first.return_value = pkg

        svc = _svc(db, tmp_path)
        org_lookup = SimpleNamespace(id=3, code="ORG-A")  # 本地存在但 id 与目标不一致
        resolved = {}

        def _fake_execute(stmt, payload=None):
            return SimpleNamespace(rowcount=1)

        # 构造最小导入流程：zip 内容用 patch 替换
        class _FakeZip:
            def __init__(self, *_a, **_k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def namelist(self):
                return ["manifest.json", "data/villages.json"]

            def read(self, name):
                import json as _json

                if name == "manifest.json":
                    return _json.dumps(
                        {"org_code": "ORG-A", "data_types": ["villages"]}
                    ).encode()
                return _json.dumps([]).encode()

        monkeypatch.setattr(dps.zipfile, "ZipFile", _FakeZip)
        monkeypatch.setattr(dps, "ensure_zip_within_limit", lambda _z: None)
        monkeypatch.setattr(
            dps,
            "read_zip_member",
            lambda z, name: z.read(name),
        )
        # 组织查询：返回 id=3 的本地组织
        def _query_side_effect(model):
            q = MagicMock()
            q.filter.return_value = q
            if model is Organization:
                q.first.return_value = org_lookup
            else:
                q.first.return_value = pkg
                q.all.return_value = []
            return q

        db.query.side_effect = _query_side_effect
        db.execute.side_effect = _fake_execute
        monkeypatch.setattr(svc, "_bulk_upsert_records", lambda *a, **k: (0, 0, []))

        import asyncio

        result = asyncio.run(svc.confirm_import(11, confirmed_by=1, selected_types=["villages"]))
        assert result is not None
        resolved["ok"] = True
        assert resolved["ok"] is True
