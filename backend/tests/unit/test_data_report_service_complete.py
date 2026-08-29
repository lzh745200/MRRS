"""
完整测试 - app.services.data_report_service (API changed)
"""
import pytest


from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

class TestExceptions:
    """测试自定义异常类"""

    def test_report_not_found_error(self):
        """测试上报不存在错误"""
        from app.services.data_report_service import ReportNotFoundError

        error = ReportNotFoundError(123)
        assert "上报不存在" in str(error)
        assert error.report_id == 123

    def test_report_status_error(self):
        """测试上报状态错误"""
        from app.services.data_report_service import ReportStatusError

        error = ReportStatusError(123, "DRAFT", "APPROVED")
        assert "上报状态错误" in str(error)
        assert error.report_id == 123
        assert error.current_status == "DRAFT"
        assert error.expected_status == "APPROVED"


class TestNotificationService:
    """测试 NotificationService 类"""

    def test_notification_service_creation(self):
        """测试通知服务创建"""
        from app.services.data_report_service import NotificationService

        service = NotificationService()
        assert service.notifications == []

    def test_send_notification(self):
        """测试发送通知"""
        from app.services.data_report_service import NotificationService

        service = NotificationService()
        result = service.send_notification(
            recipient_org_id=1,
            notification_type="test",
            title="Test Title",
            content="Test Content",
            related_id=123
        )

        assert result is True
        assert len(service.notifications) == 1
        assert service.notifications[0]["recipient_org_id"] == 1
        assert service.notifications[0]["type"] == "test"

    def test_get_notifications(self):
        """测试获取通知"""
        from app.services.data_report_service import NotificationService

        service = NotificationService()
        service.send_notification(1, "test", "Title1", "Content1")
        service.send_notification(2, "test", "Title2", "Content2")
        service.send_notification(1, "test", "Title3", "Content3")

        org1_notifications = service.get_notifications(1)
        assert len(org1_notifications) == 2

class TestDataReportServiceCreation:
    """测试 DataReportService 创建"""

    def test_service_creation(self):
        """测试创建服务"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)
        assert service.db is mock_db

class TestValidTransitions:
    """测试状态转换规则"""

    def test_valid_transitions_structure(self):
        """测试状态转换规则结构"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        # 使用小写值因为 ReportStatus.value 是小写
        assert ReportStatus.DRAFT.value in service.VALID_TRANSITIONS
        assert ReportStatus.SUBMITTED.value in service.VALID_TRANSITIONS
        assert ReportStatus.REJECTED.value in service.VALID_TRANSITIONS
        assert ReportStatus.APPROVED.value in service.VALID_TRANSITIONS
        assert ReportStatus.CANCELLED.value in service.VALID_TRANSITIONS

class TestCreateReport:
    """测试 create_report 方法"""

    @pytest.mark.asyncio
    async def test_create_report_success(self):
        """测试成功创建上报"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        # 模拟数据包
        mock_package = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_package

        # 模拟组织服务
        mock_target_org = MagicMock()
        mock_target_org.id = 2
        mock_source_org = MagicMock()
        mock_source_org.id = 1
        mock_source_org.code = "ORG001"

        with patch.object(service.org_service, 'get_organization') as mock_get_org:
            with patch.object(service, '_is_superior', return_value=True):
                mock_get_org.side_effect = [mock_target_org, mock_source_org]

                # 使用MagicMock模拟DataReportCreate，提供服务需要的字段
                data = MagicMock()
                data.package_id = 1
                data.target_org_id = 2
                data.title = "Test Report"
                data.description = "Test Description"
                data.deadline = datetime.utcnow() + timedelta(days=7)

                result = await service.create_report(data, source_org_id=1, created_by=1)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_report_package_not_found(self):
        """测试数据包不存在"""
        from app.services.data_report_service import DataReportService
        from app.core.exceptions import BusinessError

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        data = MagicMock()
        data.package_id = 999
        data.target_org_id = 2
        data.title = "Test Report"

        with pytest.raises(BusinessError) as exc_info:
            await service.create_report(data, source_org_id=1, created_by=1)

        assert "数据包不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_report_target_org_not_found(self):
        """测试目标组织不存在"""
        from app.services.data_report_service import DataReportService
        from app.core.exceptions import BusinessError

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_package = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_package

        with patch.object(service.org_service, 'get_organization', return_value=None):
            data = MagicMock()
            data.package_id = 1
            data.target_org_id = 999
            data.title = "Test Report"

            with pytest.raises(BusinessError) as exc_info:
                await service.create_report(data, source_org_id=1, created_by=1)

        assert "目标组织不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_report_source_org_not_found(self):
        """测试来源组织不存在"""
        from app.services.data_report_service import DataReportService
        from app.core.exceptions import BusinessError

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_package = MagicMock()
        mock_target_org = MagicMock()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_package

        with patch.object(service.org_service, 'get_organization') as mock_get_org:
            mock_get_org.side_effect = [mock_target_org, None]

            data = MagicMock()
            data.package_id = 1
            data.target_org_id = 2
            data.title = "Test Report"

            with pytest.raises(BusinessError) as exc_info:
                await service.create_report(data, source_org_id=1, created_by=1)

        assert "来源组织不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_report_not_superior(self):
        """测试目标不是上级组织"""
        from app.services.data_report_service import DataReportService
        from app.core.exceptions import BusinessError

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_package = MagicMock()
        mock_target_org = MagicMock()
        mock_source_org = MagicMock()

        mock_db.query.return_value.filter.return_value.first.return_value = mock_package

        with patch.object(service.org_service, 'get_organization') as mock_get_org:
            with patch.object(service, '_is_superior', return_value=False):
                mock_get_org.side_effect = [mock_target_org, mock_source_org]

                data = MagicMock()
                data.package_id = 1
                data.target_org_id = 2
                data.title = "Test Report"

                with pytest.raises(BusinessError) as exc_info:
                    await service.create_report(data, source_org_id=1, created_by=1)

        assert "上级" in str(exc_info.value)

class TestSubmitReport:
    """测试 submit_report 方法"""

    @pytest.mark.asyncio
    async def test_submit_report_success(self):
        """测试成功提交上报"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_report.status = ReportStatus.DRAFT.value

        with patch.object(service, '_get_report', return_value=mock_report):
            with patch.object(service, '_validate_status_transition'):
                with patch.object(service, '_notify_submission'):
                    result = await service.submit_report(1, submitted_by=1, comment="Submitting")

        assert mock_report.status == ReportStatus.SUBMITTED.value
        assert mock_report.submitted_by == 1
        assert mock_report.comment == "Submitting"
        mock_db.commit.assert_called_once()

class TestReviewReport:
    """测试 review_report 方法"""

    @pytest.mark.asyncio
    async def test_review_report_approve(self):
        """测试审批通过"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_report.status = ReportStatus.SUBMITTED.value

        # 使用MagicMock模拟DataReportReview，提供action字段
        review = MagicMock()
        review.action = "approve"
        review.comment = "Approved"
        review.rejection_reason = None

        with patch.object(service, '_get_report', return_value=mock_report):
            with patch.object(service, '_validate_status_transition'):
                with patch.object(service, '_notify_review_result'):
                    result = await service.review_report(1, review, reviewed_by=2)

        assert mock_report.status == ReportStatus.APPROVED.value
        assert mock_report.reviewed_by == 2
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_report_reject(self):
        """测试审批拒绝"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_report.status = ReportStatus.SUBMITTED.value

        review = MagicMock()
        review.action = "reject"
        review.comment = "Rejected"
        review.rejection_reason = "Invalid data"

        with patch.object(service, '_get_report', return_value=mock_report):
            with patch.object(service, '_validate_status_transition'):
                with patch.object(service, '_notify_review_result'):
                    result = await service.review_report(1, review, reviewed_by=2)

        assert mock_report.status == ReportStatus.REJECTED.value
        assert mock_report.rejection_reason == "Invalid data"

class TestGetReport:
    """测试 get_report 方法"""

    def test_get_report_found(self):
        """测试获取存在的上报"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_report

        result = service.get_report(1)

        assert result is mock_report

    def test_get_report_not_found(self):
        """测试获取不存在的上报"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.get_report(999)

        assert result is None

class TestGetSubordinateReports:
    """测试 get_subordinate_reports 方法"""

    def test_get_subordinate_reports_no_filter(self):
        """测试获取下级上报列表（无筛选）"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_reports = [MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_reports

        result = service.get_subordinate_reports(org_id=1)

        assert len(result) == 2

    def test_get_subordinate_reports_with_status(self):
        """测试获取下级上报列表（带状态筛选）"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_reports = [MagicMock()]
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_reports

        result = service.get_subordinate_reports(org_id=1, status="SUBMITTED")

        assert len(result) == 1

class TestGetSubmittedReports:
    """测试 get_submitted_reports 方法"""

    def test_get_submitted_reports(self):
        """测试获取已提交的上报列表"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_reports = [MagicMock(), MagicMock(), MagicMock()]
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_reports

        result = service.get_submitted_reports(org_id=1)

        assert len(result) == 3

    def test_get_submitted_reports_with_status(self):
        """测试获取已提交的上报列表（带状态筛选）"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_reports = [MagicMock()]
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_reports

        result = service.get_submitted_reports(org_id=1, status="SUBMITTED")

        assert len(result) == 1

class TestGetReportStatistics:
    """测试 get_report_statistics 方法"""

    def test_get_report_statistics(self):
        """测试获取上报统计"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report1 = MagicMock()
        mock_report1.status = ReportStatus.DRAFT.value
        mock_report1.deadline = datetime.utcnow() - timedelta(days=1)  # overdue
        mock_report1.source_org_id = 1
        mock_report1.submitted_at = None

        mock_report2 = MagicMock()
        mock_report2.status = ReportStatus.SUBMITTED.value
        mock_report2.deadline = None
        mock_report2.source_org_id = 2
        mock_report2.submitted_at = datetime.utcnow()

        mock_report3 = MagicMock()
        mock_report3.status = ReportStatus.APPROVED.value
        mock_report3.deadline = None
        mock_report3.source_org_id = 1
        mock_report3.submitted_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_report1, mock_report2, mock_report3]

        result = service.get_report_statistics(org_id=1)

        assert result.total == 3
        assert result.submitted == 1
        assert result.approved == 1
        # Note: draft/cancelled/overdue are calculated but not in schema, only total/submitted/approved/rejected/pending are kept

class TestGetSubordinateDashboard:
    """测试 get_subordinate_dashboard 方法"""

    def test_get_subordinate_dashboard(self):
        """测试获取下级单位仪表板"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_suborg = MagicMock()
        mock_suborg.id = 2
        mock_suborg.name = "Sub Org"
        mock_suborg.code = "SUB001"

        with patch.object(service.org_service, 'get_subordinate_organizations', return_value=[mock_suborg]):
            mock_report = MagicMock()
            mock_report.status = ReportStatus.SUBMITTED.value
            mock_report.deadline = None
            mock_report.submitted_at = datetime.utcnow()
            mock_report.source_org_id = 2  # 必须匹配子组织ID

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_report]

            result = service.get_subordinate_dashboard(org_id=1)

        assert result.total_subordinates == 1
        assert result.reported_count == 1

    def test_get_subordinate_dashboard_with_overdue(self):
        """测试获取下级单位仪表板（包含逾期）- 覆盖逾期计数逻辑"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_suborg = MagicMock()
        mock_suborg.id = 2
        mock_suborg.name = "Sub Org"
        mock_suborg.code = "SUB001"

        with patch.object(service.org_service, 'get_subordinate_organizations', return_value=[mock_suborg]):
            # 创建一个逾期的草稿报告
            mock_report = MagicMock()
            mock_report.status = ReportStatus.DRAFT.value
            mock_report.deadline = datetime.utcnow() - timedelta(days=1)  # 已过期
            mock_report.submitted_at = None
            mock_report.source_org_id = 2  # 必须匹配子组织ID

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_report]

            # 只验证调用不抛出异常即可（覆盖line 429）
            result = service.get_subordinate_dashboard(org_id=1)

        # 验证函数成功执行
        assert result is not None

class TestPrivateMethods:
    """测试私有方法"""

    def test_get_report_found_private(self):
        """测试 _get_report 找到上报"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_report

        result = service._get_report(1)

        assert result is mock_report

    def test_get_report_not_found_private(self):
        """测试 _get_report 上报不存在"""
        from app.services.data_report_service import DataReportService, ReportNotFoundError

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ReportNotFoundError) as exc_info:
            service._get_report(999)

        assert exc_info.value.report_id == 999

    def test_validate_status_transition_valid(self):
        """测试有效的状态转换"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        # 不应该抛出异常
        service._validate_status_transition(
            ReportStatus.DRAFT.value,
            ReportStatus.SUBMITTED.value
        )

    def test_validate_status_transition_invalid(self):
        """测试无效的状态转换"""
        from app.services.data_report_service import DataReportService, ReportStatusError
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        with pytest.raises(ReportStatusError) as exc_info:
            service._validate_status_transition(
                ReportStatus.APPROVED.value,
                ReportStatus.DRAFT.value
            )

    def test_is_superior_true(self):
        """测试是上级关系"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_org = MagicMock()
        mock_ancestor = MagicMock()
        mock_ancestor.id = 1

        with patch.object(service.org_service, 'get_organization', return_value=mock_org):
            with patch.object(service.org_service, 'get_ancestors', return_value=[mock_ancestor]):
                result = service._is_superior(1, 2)

        assert result is True

    def test_is_superior_false(self):
        """测试不是上级关系"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_org = MagicMock()

        with patch.object(service.org_service, 'get_organization', return_value=mock_org):
            with patch.object(service.org_service, 'get_ancestors', return_value=[]):
                result = service._is_superior(1, 2)

        assert result is False

    def test_is_superior_org_not_found(self):
        """测试组织不存在时不是上级"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        with patch.object(service.org_service, 'get_organization', return_value=None):
            result = service._is_superior(1, 999)

        assert result is False

    def test_generate_report_code(self):
        """测试生成上报编码"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        result = service._generate_report_code("ORG001")

        assert result.startswith("RPT-ORG001-")

    def test_notify_submission(self):
        """测试提交通知"""
        from app.services.data_report_service import DataReportService

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_report.source_org_id = 1
        mock_report.target_org_id = 2
        mock_report.id = 123

        mock_org = MagicMock()
        mock_org.name = "Test Org"

        with patch.object(service.org_service, 'get_organization', return_value=mock_org):
            with patch.object(service.notification_service, 'send_notification') as mock_send:
                service._notify_submission(mock_report)

        mock_send.assert_called_once()

    def test_notify_review_result_approved(self):
        """测试审批通过通知"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_report.source_org_id = 1
        mock_report.status = ReportStatus.APPROVED.value
        mock_report.report_code = "RPT-001"
        mock_report.id = 123

        with patch.object(service.notification_service, 'send_notification') as mock_send:
            service._notify_review_result(mock_report)

        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        assert "已批准" in call_args["title"]

    def test_notify_review_result_rejected(self):
        """测试审批拒绝通知"""
        from app.services.data_report_service import DataReportService
        from app.models.data_report import ReportStatus

        mock_db = MagicMock()
        service = DataReportService(db=mock_db)

        mock_report = MagicMock()
        mock_report.source_org_id = 1
        mock_report.status = ReportStatus.REJECTED.value
        mock_report.report_code = "RPT-001"
        mock_report.id = 123

        with patch.object(service.notification_service, 'send_notification') as mock_send:
            service._notify_review_result(mock_report)

        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        assert "已拒绝" in call_args["title"]
