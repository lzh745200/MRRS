"""R29 回归锁定：`report_type` 必须真正落库（此前为必填却静默丢弃）。

R29 探针实测：`POST /api/v1/data-reports` 带 `report_type="monthly"` —— 请求模型
`DataReportCreate.report_type` 是**必填**字段、响应模型 `DataReportResponse` 也回显
该字段，但：

- `data_reports` 表与 `DataReport` 模型都没有 `report_type` 列；
- `DataReportService.create_report` 从未读取 `data.report_type`。

于是调用方必须传一个"传了也没用"的值，且响应里 `report_type` 恒为空串
（实测响应 `{"title":"R29 探针上报","report_type":"", …}`）——典型的静默丢弃。
"""

import pytest

from app.models.data_report import DataReport
from app.schemas.data_report import DataReportCreate, DataReportResponse


class TestSchemaContract:
    def test_create_requires_report_type(self):
        with pytest.raises(Exception):
            DataReportCreate(title="t", package_id=1)

    def test_response_exposes_report_type(self):
        assert "report_type" in DataReportResponse.model_fields


class TestModelColumn:
    def test_model_has_report_type_column(self):
        assert "report_type" in DataReport.__table__.c

    def test_column_round_trip(self, real_db_session):
        report = DataReport(
            report_code="RPT-R29-1",
            package_id=1,
            source_org_id=2,
            target_org_id=1,
            status="draft",
            title="R29 上报",
            report_type="monthly",
        )
        real_db_session.add(report)
        real_db_session.commit()
        real_db_session.expire_all()
        got = real_db_session.query(DataReport).filter(DataReport.id == report.id).first()
        assert got.report_type == "monthly"
        assert DataReportResponse.model_validate(got).report_type == "monthly"


class TestServicePersistsReportType:
    def test_create_report_passes_report_type(self):
        """源码级锁定：service 必须把 data.report_type 传给模型。"""
        import inspect

        from app.services.data_report_service import DataReportService

        src = inspect.getsource(DataReportService.create_report)
        assert "report_type=" in src, "create_report 必须落库 report_type"

    @pytest.mark.asyncio
    async def test_create_report_end_to_end(self, real_db_session, monkeypatch):
        """真实调用 service.create_report，断言 report_type 落库。"""
        from app.models.data_package import DataPackage
        from app.models.organization import Organization
        from app.services.data_report_service import DataReportService

        parent = Organization(id=1, name="上级", code="P1", org_type="department",
                              level="level_1", path="/1/", is_active=True)
        child = Organization(id=2, name="下级", code="C1", org_type="support_unit",
                             level="level_2", parent_id=1, path="/1/2/", is_active=True)
        pkg = DataPackage(package_code="R29-PKG", org_id=2, file_path="/tmp/p.zip",
                          file_name="p.zip", file_size=1, data_types=["villages"], record_count=0)
        real_db_session.add_all([parent, child, pkg])
        real_db_session.commit()

        svc = DataReportService(real_db_session)
        report = await svc.create_report(
            data=DataReportCreate(title="R29", report_type="annual", package_id=pkg.id, target_org_id=1),
            source_org_id=2,
            created_by=1,
        )
        assert report.report_type == "annual"
