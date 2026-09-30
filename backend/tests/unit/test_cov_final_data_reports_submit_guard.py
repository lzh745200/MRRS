"""app.api.v1.data.data.data_reports 覆盖补全：提交上报的 ReportNotFoundError 分支。

line 231 —— 端点已完成归属校验后，服务层并发再查不到该上报（get_report 命中、
submit_report 落空）时必须回落成 404；缺此分支会变成未捕获异常 → 500，
把"记录已不存在"这一可纠正的用户输入错误报成服务故障。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.data.data.data_reports import submit_report
from app.core.exceptions import NotFoundException
from app.services.data_report_service import ReportNotFoundError


class TestSubmitReportNotFound:
    async def test_service_report_not_found_maps_to_404(self):
        service = MagicMock(name="service")
        service.get_report.return_value = SimpleNamespace(id=7, source_org_id=10)
        service.submit_report = AsyncMock(side_effect=ReportNotFoundError("上报不存在"))
        user = SimpleNamespace(id=3, organization_id=10)

        with pytest.raises(NotFoundException) as excinfo:
            await submit_report(
                report_id=7, comment=None, current_user=user, service=service,
            )

        assert excinfo.value.status_code == 404
        assert excinfo.value.message == "上报不存在"
        service.submit_report.assert_awaited_once_with(
            report_id=7, submitted_by=3, comment=None,
        )

    async def test_not_found_only_after_ownership_check(self):
        """越权者（非来源组织）先撞 403，不会走到 line 231 —— 保证分支只对归属者开放。"""
        from fastapi import HTTPException

        service = MagicMock(name="service")
        service.get_report.return_value = SimpleNamespace(id=7, source_org_id=10)
        service.submit_report = AsyncMock(side_effect=ReportNotFoundError("上报不存在"))
        intruder = SimpleNamespace(id=4, organization_id=99)

        with pytest.raises(HTTPException) as excinfo:
            await submit_report(
                report_id=7, comment=None, current_user=intruder, service=service,
            )

        assert excinfo.value.status_code == 403
        service.submit_report.assert_not_awaited()
