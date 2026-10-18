"""W22 数据上报链路端到端：下级录入 → 生成上报包 → 上级接收导入 → 查询可见。

契约（`.scratch/w22-feature-batch/000-contract.md` §2「其他」）要求不新增接口，
仅补集成测试验证链路。本用例用两套独立 SQLite 库模拟「下级机 / 上级机」：

1. 下级库录入帮扶村 / 学校 / 项目 / 经费（真实 ORM 落库）；
2. 下级调用 ``DataPackageService.export_package(package_type=report)`` 生成上报包
   （现网 API 为 ``POST /data-packages/one-click-report``，服务层入口一致）；
3. 上级 ``import_package`` 接收（落 DataPackage 记录 + 状态 validated）→
   ``confirm_import`` 导入；
4. 上级库查询断言四类数据可见，且接收记录可按 ``report`` 类型检索；
5. 重复导入幂等（非覆盖模式同业务键不重复写入）。
"""

import os
import zipfile
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _make_session():
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    return engine, session


@pytest.fixture
def lower_db():
    engine, session = _make_session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def upper_db():
    engine, session = _make_session()
    yield session
    session.close()
    engine.dispose()


def _make_org(db, name, code):
    from app.models.organization import Organization

    org = Organization(name=name, code=code)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _seed_lower_data(db, org):
    """下级机录入四类业务数据（与真实录入端点落库同构）。"""
    from app.models.fund import Fund
    from app.models.project import Project
    from app.models.school import School
    from app.models.supported_village import SupportedVillage

    village = SupportedVillage(
        village_name="上报测试村",
        county="某县",
        province="某省",
        organization_id=org.id,
        created_by=1,
        is_active=True,
    )
    school = School(
        name="上报测试学校",
        district="某区",
        student_count=120,
        organization_id=org.id,
        created_by=1,
        is_active=True,
    )
    project = Project(
        name="上报测试项目",
        organization_id=org.id,
        created_by=1,
        is_active=True,
    )
    fund = Fund(
        name="上报测试经费",
        amount=12.5,
        year=2026,
        organization_id=org.id,
        created_by=1,
        is_active=True,
    )
    db.add_all([village, school, project, fund])
    db.commit()
    for obj in (village, school, project, fund):
        db.refresh(obj)
    return SimpleNamespace(village=village, school=school, project=project, fund=fund)


async def _export_report_package(lower_db, org, tmp_path):
    from app.models.data_package import PackageType
    from app.services.data_package_service import DataPackageService

    service = DataPackageService(lower_db, upload_dir=str(tmp_path / "lower_packages"))
    result = await service.export_package(
        org_id=org.id,
        data_types=["villages", "schools", "projects", "funds"],
        export_by=1,
        description="W22 上报链路测试",
        package_type=PackageType.report,
        exported_by_name="下级录入员",
    )
    return service, result


async def _receive_and_confirm(upper_db, report_file, upper_org, tmp_path, overwrite=False):
    from app.services.data_package_service import DataPackageService

    service = DataPackageService(upper_db, upload_dir=str(tmp_path / "upper_packages"))
    import_result = await service.import_package(
        file_path=report_file,
        file_name=os.path.basename(report_file),
        org_id=upper_org.id,
        imported_by=2,
    )
    confirm_result = await service.confirm_import(
        import_result.package_id, confirmed_by=2, overwrite_existing=overwrite
    )
    return service, import_result, confirm_result


class TestDataReportRoundtrip:
    @pytest.mark.asyncio
    async def test_report_roundtrip_end_to_end(self, lower_db, upper_db, tmp_path):
        """核心链路：导出上报包 → 上级导入 → 四类数据在上级库可见。"""
        from app.models.data_package import DataPackage, PackageStatus

        lower_org = _make_org(lower_db, "下级单位", "ORG-LOW-W22")
        upper_org = _make_org(upper_db, "上级单位", "ORG-HIGH-W22")
        seeded = _seed_lower_data(lower_db, lower_org)

        service, result = await _export_report_package(lower_db, lower_org, tmp_path)
        assert result.package_id > 0
        assert result.file_name.endswith(".zip")
        assert os.path.exists(result.file_path)

        # 上报包内容与 manifest 类型正确
        with zipfile.ZipFile(result.file_path) as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            for data_type in ("villages", "schools", "projects", "funds"):
                assert f"data/{data_type}.json" in names
        lower_package = service.get_package(result.package_id)
        assert lower_package.type == "report"
        assert sum(result.manifest.record_counts.values()) >= 4

        # 上级接收 + 确认导入
        upper_service, import_result, confirm_result = await _receive_and_confirm(
            upper_db, result.file_path, upper_org, tmp_path
        )
        assert getattr(import_result.status, "value", import_result.status) == "validated"
        assert confirm_result.success is True
        assert confirm_result.errors == []
        assert confirm_result.imported_counts["villages"] == 1
        assert confirm_result.imported_counts["schools"] == 1
        assert confirm_result.imported_counts["projects"] == 1
        assert confirm_result.imported_counts["funds"] == 1

        # 接收记录可见：DataPackage 状态 imported，且可按 report 类型检索
        received = upper_db.query(DataPackage).filter(DataPackage.id == import_result.package_id).one()
        assert received.status == PackageStatus.imported.value
        assert received.imported_by == 2
        assert received.imported_at is not None
        report_packages = upper_service.get_packages_by_org(upper_org.id, type_filter="report")
        assert [pkg.id for pkg in report_packages] == [import_result.package_id]

        # 查询可见：四类数据落在上级组织数据域内
        from app.models.fund import Fund
        from app.models.project import Project
        from app.models.school import School
        from app.models.supported_village import SupportedVillage

        village = upper_db.query(SupportedVillage).filter(
            SupportedVillage.village_name == "上报测试村"
        ).one()
        school = upper_db.query(School).filter(School.name == "上报测试学校").one()
        project = upper_db.query(Project).filter(Project.name == "上报测试项目").one()
        fund = upper_db.query(Fund).filter(Fund.name == "上报测试经费").one()
        for row in (village, school, project, fund):
            assert row.organization_id == upper_org.id  # 数据归属落在上级组织
        assert float(fund.amount) == 12.5
        assert village.id == seeded.village.id  # 主键在目标库空闲时原样保留

    @pytest.mark.asyncio
    async def test_repeated_import_is_idempotent(self, lower_db, upper_db, tmp_path):
        """重复接收同一上报包：同业务键按非覆盖模式跳过，不产生重复行。"""
        from app.models.supported_village import SupportedVillage

        lower_org = _make_org(lower_db, "下级单位2", "ORG-LOW-W22B")
        upper_org = _make_org(upper_db, "上级单位2", "ORG-HIGH-W22B")
        _seed_lower_data(lower_db, lower_org)
        _service, result = await _export_report_package(lower_db, lower_org, tmp_path)

        await _receive_and_confirm(upper_db, result.file_path, upper_org, tmp_path)
        assert upper_db.query(SupportedVillage).count() == 1

        _svc2, _imp2, confirm2 = await _receive_and_confirm(
            upper_db, result.file_path, upper_org, tmp_path, overwrite=False
        )
        assert confirm2.success is True
        assert confirm2.imported_counts["villages"] == 0     # DO NOTHING 不计入
        assert confirm2.skipped_counts["villages"] == 1
        assert upper_db.query(SupportedVillage).count() == 1

    @pytest.mark.asyncio
    async def test_report_received_record_serialization(self, lower_db, upper_db, tmp_path):
        """上级「接收记录」序列化字段（/data-packages/received 的数据源）完整。"""
        from app.api.v1.data.data.data_packages import _received_package_to_dict

        lower_org = _make_org(lower_db, "下级单位3", "ORG-LOW-W22C")
        upper_org = _make_org(upper_db, "上级单位3", "ORG-HIGH-W22C")
        _seed_lower_data(lower_db, lower_org)
        _service, result = await _export_report_package(lower_db, lower_org, tmp_path)
        _usvc, import_result, _confirm = await _receive_and_confirm(
            upper_db, result.file_path, upper_org, tmp_path
        )

        from app.models.data_package import DataPackage

        package = upper_db.query(DataPackage).filter(DataPackage.id == import_result.package_id).one()
        payload = _received_package_to_dict(package)
        assert payload["status"] == "imported"
        assert payload["data_types"] == ["villages", "schools", "projects", "funds"]
        assert payload["record_count"] >= 4
        assert payload["imported_at"] is not None
