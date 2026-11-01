"""v1.18.33 覆盖率缺口回归（2026-11-01 CI 红线）。

CI 的最终覆盖率门禁是「语句 + 分支 100%」。本轮改动的四处逻辑在本地只跑了
``--no-cov`` 的相关测试文件，合并覆盖率在 CI 掉了 0.02%，缺口全部落在新增分支上：

- ``app/services/data_package_service.py:741``：父表换 id 后**确实发生**外键重写时的
  可观测日志（没有一条走通的用例来触发 ``rewritten > 0``）。
- ``app/services/data_package_service.py:1054``：模型没有任何外键时 ``_fk_targets`` 为空，
  ``_apply_fk_remap`` 必须立即返回 0（早返回分支）。
- ``app/services/fund_service.py:229``：更新经费时**改挂了项目** → 新项目也要重算决算。
- ``app/api/v1/system/admin.py:164``：``except HTTPException: raise`` —— 备份服务内部抛出
  的业务 HTTP 异常必须原样透出，不能被兜底改写成 500。

这里按「真实调用路径 + 最小替身」补测，不用 pragma/skip 掩盖。
"""

import asyncio
import contextlib
import json
import zipfile
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from app.models.base import Base
from app.models.fund import Fund
from app.models.project import Project
from app.services.data_package_service import DataPackageService


def _write_package(tmp_path, manifest: dict, data: dict[str, list]) -> str:
    """按数据包布局落一个最小 zip：manifest.json + data/<type>.json。"""
    path = tmp_path / "pkg.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for data_type, rows in data.items():
            zf.writestr(f"data/{data_type}.json", json.dumps(rows))
    return str(path)


def _package_query(package):
    query = MagicMock()
    query.filter.return_value.first.return_value = package
    return query


class TestApplyFkRemapEarlyReturn:
    def test_model_without_foreign_keys_returns_zero(self):
        """1054：目标模型没有任何外键列时直接返回 0，不做无意义的扫描。"""
        no_fk_base = declarative_base()

        class _NoFk(no_fk_base):  # type: ignore[misc, valid-type]
            __tablename__ = "cov_no_fk_rows"
            id = Column(Integer, primary_key=True)
            name = Column(String(20))

        svc = DataPackageService(MagicMock())
        rewritten = svc._apply_fk_remap(
            _NoFk, [{"id": 1, "name": "x"}], {"supported_villages": {1: 2}}
        )
        assert rewritten == 0

    def test_empty_remap_or_records_returns_zero(self):
        svc = DataPackageService(MagicMock())
        assert svc._apply_fk_remap(Project, [], {"supported_villages": {1: 2}}) == 0
        assert svc._apply_fk_remap(Project, [{"village_id": 1}], {}) == 0


class TestConfirmImportLogsForeignKeyRemap:
    async def test_logs_when_foreign_keys_rewritten(self, tmp_path, caplog):
        """741：``rewritten > 0`` 时必须留下「源 id→新 id 重写」的可观测日志。"""
        zip_path = _write_package(
            tmp_path,
            {"version": "1.0", "org_code": "", "data_types": ["projects"]},
            {"projects": [{"id": 1, "name": "项目A", "village_id": 1}]},
        )
        package = SimpleNamespace(
            id=11, status="validated", file_path=zip_path, org_id=1, imported_at=None,
            imported_by=None, error_message=None,
        )

        db = MagicMock()
        db.query.return_value = _package_query(package)
        svc = DataPackageService(db)

        seen: dict[str, object] = {}

        def _apply(model, records, remap):
            seen["called"] = True
            return 2

        svc._apply_fk_remap = _apply  # type: ignore[method-assign]
        svc._bulk_upsert_records = lambda *a, **kw: (1, 0, [])  # type: ignore[method-assign]

        with pytest.MonkeyPatch.context() as mp:
            import app.services.data_package_service as dp_mod

            mp.setattr(
                dp_mod.db_coordinator,
                "exclusive_write",
                lambda timeout: contextlib.nullcontext(),
            )
            mp.setattr(
                dp_mod,
                "validate_records",
                lambda data_type, records: {"ok": records, "corrected": [], "rejected": []},
            )
            with caplog.at_level("INFO", logger=dp_mod.logger.name):
                result = await svc.confirm_import(11, confirmed_by=9)

        assert seen.get("called") is True
        assert result.success is True
        assert "外键值按「源 id→新 id」映射重写" in caplog.text


class TestFundServiceProjectChangeRecompute:
    def _project(self, db_session, name: str) -> Project:
        project = Project(
            name=name,
            type="infrastructure",
            budget=Decimal("100.00"),
            status="in_progress",
            organization_id=1,
        )
        db_session.add(project)
        db_session.flush()
        return project

    def test_update_fund_to_another_project_recomputes_new_project(self, db_session):
        """229：项目归属变化时，新项目也要重算（不能只算原项目）。"""
        from app.models.fund_lifecycle import FundSettlement, SettlementStatus
        from app.services.fund_service import FundService

        old_project = self._project(db_session, "原项目")
        new_project = self._project(db_session, "新项目")
        db_session.add_all(
            [
                Fund(project_id=old_project.id, name="原项目经费", approved_amount=Decimal("10")),
                Fund(project_id=new_project.id, name="新项目经费", approved_amount=Decimal("80")),
                FundSettlement(
                    project_id=new_project.id,
                    settlement_no="JS-COV-PROJECT-CHANGE",
                    status=SettlementStatus.DRAFT.value,
                    total_budget=Decimal("0"),
                    total_spent=Decimal("0"),
                    total_remaining=Decimal("0"),
                ),
            ]
        )
        db_session.flush()
        fund = db_session.query(Fund).filter(Fund.name == "原项目经费").one()

        updated = FundService(db_session).update_fund(fund.id, project_id=new_project.id)

        assert updated is not None
        assert updated.project_id == new_project.id
        db_session.flush()
        settlement = (
            db_session.query(FundSettlement)
            .filter(FundSettlement.settlement_no == "JS-COV-PROJECT-CHANGE")
            .one()
        )
        # 新项目经费合计 = 原有 80 + 迁进来的 10（update_fund 已把该行改挂新项目）
        assert settlement.total_budget == Decimal("90.0000")


class TestBackupHttpExceptionReraised:
    def test_create_backup_reraises_business_http_exception(self, monkeypatch):
        """164：备份服务抛 HTTPException 时必须原样透出（如 507 磁盘不足）。"""
        from app.api.v1.system import admin as admin_mod

        def _boom():
            raise HTTPException(status_code=507, detail="磁盘空间不足")

        monkeypatch.setattr(admin_mod, "get_backup_directory", _boom)

        user = Mock()
        user.id = 1
        user.username = "admin"
        user.role = "super_admin"
        user.is_superuser = True

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(admin_mod.create_backup(current_user=user, db=Mock()))

        assert exc_info.value.status_code == 507
        assert "磁盘空间不足" in str(exc_info.value.detail)


@pytest.fixture
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()
