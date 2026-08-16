"""
Data Report Service
数据上报管理服务
"""

import logging
from datetime import timezone, datetime
from typing import Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessError
from app.models.data_package import DataPackage
from app.models.data_report import DataReport, ReportStatus
from app.schemas.data_report import (
    DataReportCreate,
    DataReportReview,
    DataReportStatistics,
    ReviewActionEnum,
    SubordinateReportDashboard,
    SubordinateReportSummary,
)
from app.services.organization_service import OrganizationService
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class ReportNotFoundError(BusinessError):
    """上报不存在错误"""

    def __init__(self, report_id: int):
        super().__init__(f"上报不存在: {report_id}")
        self.report_id = report_id


class ReportStatusError(BusinessError):
    """上报状态错误"""

    def __init__(self, report_id: int, current_status: str, expected_status: str):
        super().__init__(f"上报状态错误: 当前状态 {current_status}, 期望状态 {expected_status}")
        self.report_id = report_id
        self.current_status = current_status
        self.expected_status = expected_status


class ReportPermissionError(BusinessError):
    """上报权限错误"""

    def __init__(self, user_id: int, report_id: int, action: str):
        super().__init__(f"用户 {user_id} 无权{action}上报 {report_id}")
        self.user_id = user_id
        self.report_id = report_id
        self.action = action


class NotificationService:
    """通知服务（简化实现）"""

    def __init__(self):
        self.notifications: List[Dict] = []

    def send_notification(
        self,
        recipient_org_id: int,
        notification_type: str,
        title: str,
        content: str,
        related_id: int = None,
    ) -> bool:
        """发送通知"""
        notification = {
            "recipient_org_id": recipient_org_id,
            "type": notification_type,
            "title": title,
            "content": content,
            "related_id": related_id,
            "sent_at": datetime.now(timezone.utc),
            "is_read": False,
        }
        self.notifications.append(notification)
        logger.info(f"Notification sent: {notification_type} to org {recipient_org_id}")
        return True

    def get_notifications(self, org_id: int) -> List[Dict]:
        """获取组织的通知"""
        return [n for n in self.notifications if n["recipient_org_id"] == org_id]


class DataReportService:
    """
    数据上报管理服务
    负责上报的提交、审批、查询和统计
    """

    # 有效的状态转换
    VALID_TRANSITIONS = {
        ReportStatus.DRAFT.value: [
            ReportStatus.SUBMITTED.value,
            ReportStatus.CANCELLED.value,
        ],
        ReportStatus.SUBMITTED.value: [
            ReportStatus.APPROVED.value,
            ReportStatus.REJECTED.value,
        ],
        ReportStatus.REJECTED.value: [
            ReportStatus.SUBMITTED.value,
            ReportStatus.CANCELLED.value,
        ],
        ReportStatus.APPROVED.value: [],
        ReportStatus.CANCELLED.value: [],
    }

    def __init__(self, db: Session):
        self.db = db
        self.org_service = OrganizationService(db)
        self.notification_service = NotificationService()

    async def create_report(self, data: DataReportCreate, source_org_id: int, created_by: int) -> DataReport:
        """
        创建上报记录

        Args:
            data: 创建数据
            source_org_id: 来源组织ID
            created_by: 创建人ID

        Returns:
            创建的上报记录
        """
        # 验证数据包存在
        package = self.db.query(DataPackage).filter(DataPackage.id == data.package_id).first()

        if not package:
            raise BusinessError(f"数据包不存在: {data.package_id}")

        # 验证目标组织是上级
        target_org = self.org_service.get_organization(data.target_org_id)
        if not target_org:
            raise BusinessError(f"目标组织不存在: {data.target_org_id}")

        source_org = self.org_service.get_organization(source_org_id)
        if not source_org:
            raise BusinessError(f"来源组织不存在: {source_org_id}")

        # 验证目标是来源的上级
        if not self._is_superior(data.target_org_id, source_org_id):
            raise BusinessError("目标组织必须是来源组织的上级")

        # 生成上报编码
        report_code = self._generate_report_code(source_org.code)

        # 创建上报记录
        report = DataReport(
            report_code=report_code,
            package_id=data.package_id,
            source_org_id=source_org_id,
            target_org_id=data.target_org_id,
            status=ReportStatus.DRAFT.value,
            title=data.title,
            description=data.description,
            deadline=data.deadline,
            created_by=created_by,
        )

        self.db.add(report)
        safe_commit(self.db)
        self.db.refresh(report)

        return report

    async def submit_report(self, report_id: int, submitted_by: int, comment: str = None) -> DataReport:
        """
        提交上报

        Args:
            report_id: 上报ID
            submitted_by: 提交人ID
            comment: 提交备注

        Returns:
            更新后的上报记录
        """
        report = self._get_report(report_id)

        # 验证状态转换
        self._validate_status_transition(report.status, ReportStatus.SUBMITTED.value)

        # 更新状态
        report.status = ReportStatus.SUBMITTED.value
        report.submitted_at = datetime.now(timezone.utc)
        report.submitted_by = submitted_by
        if comment:
            report.comment = comment

        safe_commit(self.db)
        self.db.refresh(report)

        # 发送通知给上级单位
        self._notify_submission(report)

        return report

    async def review_report(self, report_id: int, review: DataReportReview, reviewed_by: int) -> DataReport:
        """
        审批上报

        Args:
            report_id: 上报ID
            review: 审批数据
            reviewed_by: 审批人ID

        Returns:
            更新后的上报记录
        """
        report = self._get_report(report_id)

        # 确定目标状态
        if review.action == ReviewActionEnum.APPROVE:
            target_status = ReportStatus.APPROVED.value
        else:
            target_status = ReportStatus.REJECTED.value

        # 验证状态转换
        self._validate_status_transition(report.status, target_status)

        # 更新状态
        report.status = target_status
        report.reviewed_at = datetime.now(timezone.utc)
        report.reviewed_by = reviewed_by

        if review.comment:
            report.comment = review.comment

        if review.action == ReviewActionEnum.REJECT and review.rejection_reason:
            report.rejection_reason = review.rejection_reason

        safe_commit(self.db)
        self.db.refresh(report)

        # 发送通知给下级单位
        self._notify_review_result(report)

        return report

    def get_report(self, report_id: int) -> Optional[DataReport]:
        """获取上报记录"""
        return self.db.query(DataReport).filter(DataReport.id == report_id).first()

    def get_subordinate_reports(
        self, org_id: int, status: str = None, skip: int = 0, limit: int = 20
    ) -> List[DataReport]:
        """
        获取下级单位上报列表

        Args:
            org_id: 组织ID（上级单位）
            status: 状态筛选
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            上报列表
        """
        query = self.db.query(DataReport).filter(DataReport.target_org_id == org_id)

        if status:
            query = query.filter(DataReport.status == status)

        return query.order_by(DataReport.submitted_at.desc()).offset(skip).limit(limit).all()

    def get_submitted_reports(
        self, org_id: int, status: str = None, skip: int = 0, limit: int = 20
    ) -> List[DataReport]:
        """
        获取本单位提交的上报列表

        Args:
            org_id: 组织ID（下级单位）
            status: 状态筛选
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            上报列表
        """
        query = self.db.query(DataReport).filter(DataReport.source_org_id == org_id)

        if status:
            query = query.filter(DataReport.status == status)

        return query.order_by(DataReport.created_at.desc()).offset(skip).limit(limit).all()

    def get_report_statistics(self, org_id: int) -> DataReportStatistics:
        """
        获取上报统计

        Args:
            org_id: 组织ID

        Returns:
            统计信息
        """
        # 获取所有相关上报（作为目标的上报）
        reports = self.db.query(DataReport).filter(DataReport.target_org_id == org_id).all()

        total = len(reports)
        draft = sum(1 for r in reports if r.status == ReportStatus.DRAFT.value)
        submitted = sum(1 for r in reports if r.status == ReportStatus.SUBMITTED.value)
        approved = sum(1 for r in reports if r.status == ReportStatus.APPROVED.value)
        rejected = sum(1 for r in reports if r.status == ReportStatus.REJECTED.value)
        cancelled = sum(1 for r in reports if r.status == ReportStatus.CANCELLED.value)

        # 计算逾期数
        now = datetime.now(timezone.utc)
        overdue = sum(
            1
            for r in reports
            if r.deadline
            and (r.deadline.replace(tzinfo=timezone.utc) if r.deadline.tzinfo is None else r.deadline) < now
            and r.status == ReportStatus.DRAFT.value
        )

        # 计算批准率
        reviewed = approved + rejected
        approval_rate = (approved / reviewed * 100) if reviewed > 0 else 0

        # 按来源组织统计
        by_source_org = {}
        for report in reports:
            org_key = str(report.source_org_id)
            by_source_org[org_key] = by_source_org.get(org_key, 0) + 1

        # 按月份统计
        by_month = {}
        for report in reports:
            if report.submitted_at:
                month_key = report.submitted_at.strftime("%Y-%m")
                by_month[month_key] = by_month.get(month_key, 0) + 1

        return DataReportStatistics(
            total=total,
            draft=draft,
            submitted=submitted,
            approved=approved,
            rejected=rejected,
            cancelled=cancelled,
            overdue=overdue,
            pending_review=submitted,
            approval_rate=round(approval_rate, 2),
            by_source_org=by_source_org,
            by_month=by_month,
        )

    def get_subordinate_dashboard(self, org_id: int) -> SubordinateReportDashboard:
        """
        获取下级单位上报仪表板

        Args:
            org_id: 组织ID

        Returns:
            仪表板数据
        """
        # 获取所有下级组织
        subordinates = self.org_service.get_subordinate_organizations(org_id, include_self=False)

        total_subordinates = len(subordinates)
        subordinate_summaries = []
        reported_count = 0
        pending_review_count = 0
        overdue_count = 0
        now = datetime.now(timezone.utc)

        # 获取所有下级组织的ID
        subordinate_ids = [sub_org.id for sub_org in subordinates]

        # 一次性查询所有相关报告（避免N+1查询）
        all_reports = (
            self.db.query(DataReport)
            .filter(
                DataReport.source_org_id.in_(subordinate_ids),
                DataReport.target_org_id == org_id,
            )
            .all()
        )

        # 按组织ID分组报告
        reports_by_org = {}
        for report in all_reports:
            if report.source_org_id not in reports_by_org:
                reports_by_org[report.source_org_id] = []
            reports_by_org[report.source_org_id].append(report)

        for sub_org in subordinates:
            reports = reports_by_org.get(sub_org.id, [])

            total_reports = len(reports)
            pending = sum(1 for r in reports if r.status == ReportStatus.SUBMITTED.value)
            approved = sum(1 for r in reports if r.status == ReportStatus.APPROVED.value)
            rejected = sum(1 for r in reports if r.status == ReportStatus.REJECTED.value)

            has_overdue = any(
                r.deadline
                and (r.deadline.replace(tzinfo=timezone.utc) if r.deadline.tzinfo is None else r.deadline) < now
                and r.status == ReportStatus.DRAFT.value
                for r in reports
            )

            latest_date = max((r.submitted_at for r in reports if r.submitted_at), default=None)

            if total_reports > 0:
                reported_count += 1

            pending_review_count += pending
            if has_overdue:
                overdue_count += 1

            subordinate_summaries.append(
                SubordinateReportSummary(
                    org_id=sub_org.id,
                    org_name=sub_org.name,
                    org_code=sub_org.code,
                    total_reports=total_reports,
                    pending_reports=pending,
                    approved_reports=approved,
                    rejected_reports=rejected,
                    latest_report_date=latest_date,
                    has_overdue=has_overdue,
                )
            )

        not_reported_count = total_subordinates - reported_count
        report_rate = (reported_count / total_subordinates * 100) if total_subordinates > 0 else 0

        return SubordinateReportDashboard(
            total_subordinates=total_subordinates,
            reported_count=reported_count,
            not_reported_count=not_reported_count,
            pending_review_count=pending_review_count,
            overdue_count=overdue_count,
            report_rate=round(report_rate, 2),
            subordinates=subordinate_summaries,
        )

    # ========================================================================
    # 私有方法
    # ========================================================================

    def _get_report(self, report_id: int) -> DataReport:
        """获取上报记录，不存在则抛出异常"""
        report = self.get_report(report_id)
        if not report:
            raise ReportNotFoundError(report_id)
        return report

    def _validate_status_transition(self, current_status: str, target_status: str) -> None:
        """验证状态转换是否有效"""
        valid_targets = self.VALID_TRANSITIONS.get(current_status, [])
        if target_status not in valid_targets:
            raise ReportStatusError(0, current_status, target_status)

    def _is_superior(self, superior_org_id: int, subordinate_org_id: int) -> bool:
        """检查是否是上级关系"""
        subordinate = self.org_service.get_organization(subordinate_org_id)
        if not subordinate:
            return False

        ancestors = self.org_service.get_ancestors(subordinate_org_id)
        return any(a.id == superior_org_id for a in ancestors)

    def _generate_report_code(self, org_code: str) -> str:
        """生成上报编码（毫秒级时间戳 + 4位随机后缀，避免同一秒内多次创建撞唯一约束）"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:-3]
        suffix = uuid.uuid4().hex[:4]
        return f"RPT-{org_code}-{timestamp}-{suffix}"

    def _notify_submission(self, report: DataReport) -> None:
        """通知上级单位有新上报"""
        source_org = self.org_service.get_organization(report.source_org_id)

        self.notification_service.send_notification(
            recipient_org_id=report.target_org_id,
            notification_type="report_submitted",
            title="收到新的数据上报",
            content=f"{source_org.name if source_org else '下级单位'} 提交了数据上报",
            related_id=report.id,
        )

    def _notify_review_result(self, report: DataReport) -> None:
        """通知下级单位审批结果"""
        status_text = "已批准" if report.status == ReportStatus.APPROVED.value else "已拒绝"

        self.notification_service.send_notification(
            recipient_org_id=report.source_org_id,
            notification_type="report_reviewed",
            title=f"数据上报{status_text}",
            content=f"您的数据上报 {report.report_code} {status_text}",
            related_id=report.id,
        )
