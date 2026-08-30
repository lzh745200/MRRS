"""
业务指标监控服务
提供关键业务指标的收集、计算和导出
支持 Prometheus 格式
"""

import time
from datetime import timezone, datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.models.fund import Fund, FundStatus
from app.models.approval import ApprovalTask, ApprovalStatus
from app.models.monitoring import APIMetric
from app.models.user import User
from app.models.data_report import DataReport
from app.core.database import SessionLocal


class BusinessMetricsService:
    """业务指标服务"""

    def __init__(self):
        self._cache: Dict[str, tuple] = {}
        self._cache_ttl = 60  # 缓存60秒

    def _get_cached(self, key: str) -> Optional[any]:
        """获取缓存值"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            del self._cache[key]
        return None

    def _set_cached(self, key: str, value: any):
        """设置缓存值"""
        self._cache[key] = (value, time.time())

    def get_fund_approval_metrics(self, db: Session) -> Dict:
        """
        资金审批指标
        - 审批成功率
        - 平均审批时间
        - 待审批数量
        """
        cache_key = "fund_approval_metrics"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 获取最近30天的审批数据
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # 总审批数
        total_approvals = db.query(ApprovalTask).filter(ApprovalTask.created_at >= thirty_days_ago).count()

        # 已审批数（通过+拒绝）
        decided_approvals = (
            db.query(ApprovalTask)
            .filter(
                and_(
                    ApprovalTask.created_at >= thirty_days_ago,
                    ApprovalTask.status.in_([ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]),
                )
            )
            .count()
        )

        # 通过数
        approved_count = (
            db.query(ApprovalTask)
            .filter(
                and_(ApprovalTask.created_at >= thirty_days_ago, ApprovalTask.status == ApprovalStatus.APPROVED)
            )
            .count()
        )

        # 待审批数
        pending_count = db.query(ApprovalTask).filter(ApprovalTask.status == ApprovalStatus.PENDING).count()

        # 计算成功率
        approval_success_rate = (approved_count / decided_approvals * 100) if decided_approvals > 0 else 0

        # 计算平均审批时间（小时）
        avg_approval_time = (
            db.query(
                func.avg(func.julianday(ApprovalTask.updated_at) - func.julianday(ApprovalTask.created_at)) * 24
            )
            .filter(
                and_(
                    ApprovalTask.created_at >= thirty_days_ago,
                    ApprovalTask.status.in_([ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]),
                    ApprovalTask.updated_at.isnot(None),
                )
            )
            .scalar()
            or 0
        )

        metrics = {
            "total_approvals_30d": total_approvals,
            "approved_count_30d": approved_count,
            "rejected_count_30d": decided_approvals - approved_count,
            "pending_count": pending_count,
            "approval_success_rate": round(approval_success_rate, 2),
            "avg_approval_time_hours": round(avg_approval_time, 2),
        }

        self._set_cached(cache_key, metrics)
        return metrics

    def get_fund_utilization_metrics(self, db: Session) -> Dict:
        """
        资金使用指标
        - 资金拨付率
        - 各状态资金分布
        """
        cache_key = "fund_utilization_metrics"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 各状态资金统计（软删经费排除）
        status_counts = (
            db.query(Fund.status, func.count(Fund.id).label("count"), func.sum(Fund.amount).label("total_amount"))
            .filter(Fund.is_active == True)  # noqa: E712
            .group_by(Fund.status)
            .all()
        )

        status_distribution = {}
        for status, count, amount in status_counts:
            status_distribution[status] = {"count": count, "amount": float(amount or 0)}

        # 总资金数
        total_funds = db.query(func.count(Fund.id)).filter(Fund.is_active == True).scalar() or 0  # noqa: E712
        total_amount = db.query(func.sum(Fund.amount)).filter(Fund.is_active == True).scalar() or 0  # noqa: E712

        # 已完成资金
        completed_funds = status_distribution.get(FundStatus.COMPLETED, {}).get("count", 0)
        completed_amount = status_distribution.get(FundStatus.COMPLETED, {}).get("amount", 0)

        # 拨付率（金额列是 Numeric/Decimal，混合运算前统一转 float，防 float/Decimal TypeError）
        allocation_rate = (float(completed_amount) / float(total_amount) * 100) if float(total_amount) > 0 else 0

        metrics = {
            "total_funds": total_funds,
            "total_amount": float(total_amount),
            "completed_funds": completed_funds,
            "completed_amount": float(completed_amount),
            "allocation_rate": round(allocation_rate, 2),
            "status_distribution": status_distribution,
        }

        self._set_cached(cache_key, metrics)
        return metrics

    def get_data_report_metrics(self, db: Session) -> Dict:
        """
        数据上报指标
        - 上报及时率
        - 上报完成率
        """
        cache_key = "data_report_metrics"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 获取当前月份
        now = datetime.now(timezone.utc)
        month_prefix = now.strftime("%Y-%m")

        # 本月应上报数（DataReport 无 report_month 字段，按创建时间月份统计）
        expected_reports = (
            db.query(DataReport)
            .filter(func.strftime("%Y-%m", DataReport.created_at) == month_prefix)
            .count()
        )

        # 本月已上报数
        completed_reports = (
            db.query(DataReport)
            .filter(
                and_(
                    func.strftime("%Y-%m", DataReport.created_at) == month_prefix,
                    DataReport.status == "completed",
                )
            )
            .count()
        )

        # 上报完成率
        report_completion_rate = (completed_reports / expected_reports * 100) if expected_reports > 0 else 0

        # 计算及时率（在截止日期前上报）
        on_time_reports = (
            db.query(DataReport)
            .filter(
                and_(
                    func.strftime("%Y-%m", DataReport.created_at) == month_prefix,
                    DataReport.status == "completed",
                    DataReport.submitted_at.isnot(None),
                    DataReport.deadline.isnot(None),
                    DataReport.submitted_at <= DataReport.deadline,
                )
            )
            .count()
        )

        on_time_rate = (on_time_reports / completed_reports * 100) if completed_reports > 0 else 0

        metrics = {
            "expected_reports": expected_reports,
            "completed_reports": completed_reports,
            "report_completion_rate": round(report_completion_rate, 2),
            "on_time_reports": on_time_reports,
            "on_time_rate": round(on_time_rate, 2),
        }

        self._set_cached(cache_key, metrics)
        return metrics

    def get_user_activity_metrics(self, db: Session) -> Dict:
        """
        用户活跃度指标
        - 活跃用户数量
        - 新增用户数
        """
        cache_key = "user_activity_metrics"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 最近7天活跃用户（有API调用的用户）
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        active_users = (
            db.query(APIMetric.user_id)
            .filter(and_(APIMetric.timestamp >= seven_days_ago, APIMetric.user_id.isnot(None)))
            .distinct()
            .count()
        )

        # 最近30天新增用户
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        new_users = db.query(User).filter(User.created_at >= thirty_days_ago).count()

        # 总用户数
        total_users = db.query(func.count(User.id)).scalar() or 0

        metrics = {
            "active_users_7d": active_users,
            "new_users_30d": new_users,
            "total_users": total_users,
            "activity_rate": round((active_users / total_users * 100), 2) if total_users > 0 else 0,
        }

        self._set_cached(cache_key, metrics)
        return metrics

    def get_system_error_metrics(self, db: Session) -> Dict:
        """
        系统错误率指标
        """
        cache_key = "system_error_metrics"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # 最近24小时
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        # 总请求数
        total_requests = db.query(APIMetric).filter(APIMetric.timestamp >= twenty_four_hours_ago).count()

        # 错误请求数（状态码 >= 500）
        error_requests = (
            db.query(APIMetric)
            .filter(and_(APIMetric.timestamp >= twenty_four_hours_ago, APIMetric.status_code >= 500))
            .count()
        )

        # 错误率
        error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0

        metrics = {
            "total_requests_24h": total_requests,
            "error_requests_24h": error_requests,
            "error_rate": round(error_rate, 2),
        }

        self._set_cached(cache_key, metrics)
        return metrics

    def get_all_metrics(self) -> Dict:
        """获取所有业务指标"""
        db = SessionLocal()
        try:
            return {
                "fund_approval": self.get_fund_approval_metrics(db),
                "fund_utilization": self.get_fund_utilization_metrics(db),
                "data_report": self.get_data_report_metrics(db),
                "user_activity": self.get_user_activity_metrics(db),
                "system_error": self.get_system_error_metrics(db),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            db.close()

    def to_prometheus_format(self) -> str:
        """导出为 Prometheus 格式"""
        metrics = self.get_all_metrics()
        lines = []

        # 资金审批指标
        fund_approval = metrics.get("fund_approval", {})
        lines.append("# HELP fund_approval_success_rate 资金审批成功率")
        lines.append("# TYPE fund_approval_success_rate gauge")
        lines.append(f"fund_approval_success_rate {fund_approval.get('approval_success_rate', 0)}")

        lines.append("# HELP fund_pending_count 待审批资金数量")
        lines.append("# TYPE fund_pending_count gauge")
        lines.append(f"fund_pending_count {fund_approval.get('pending_count', 0)}")

        lines.append("# HELP fund_avg_approval_time_hours 平均审批时间（小时）")
        lines.append("# TYPE fund_avg_approval_time_hours gauge")
        lines.append(f"fund_avg_approval_time_hours {fund_approval.get('avg_approval_time_hours', 0)}")

        # 资金使用指标
        fund_util = metrics.get("fund_utilization", {})
        lines.append("# HELP fund_allocation_rate 资金拨付率")
        lines.append("# TYPE fund_allocation_rate gauge")
        lines.append(f"fund_allocation_rate {fund_util.get('allocation_rate', 0)}")

        lines.append("# HELP fund_total_amount 资金总额")
        lines.append("# TYPE fund_total_amount gauge")
        lines.append(f"fund_total_amount {fund_util.get('total_amount', 0)}")

        # 数据上报指标
        data_report = metrics.get("data_report", {})
        lines.append("# HELP data_report_completion_rate 数据上报完成率")
        lines.append("# TYPE data_report_completion_rate gauge")
        lines.append(f"data_report_completion_rate {data_report.get('report_completion_rate', 0)}")

        lines.append("# HELP data_report_on_time_rate 数据上报及时率")
        lines.append("# TYPE data_report_on_time_rate gauge")
        lines.append(f"data_report_on_time_rate {data_report.get('on_time_rate', 0)}")

        # 用户活跃度指标
        user_activity = metrics.get("user_activity", {})
        lines.append("# HELP active_users_7d 7天活跃用户数")
        lines.append("# TYPE active_users_7d gauge")
        lines.append(f"active_users_7d {user_activity.get('active_users_7d', 0)}")

        lines.append("# HELP new_users_30d 30天新增用户数")
        lines.append("# TYPE new_users_30d gauge")
        lines.append(f"new_users_30d {user_activity.get('new_users_30d', 0)}")

        # 系统错误指标
        system_error = metrics.get("system_error", {})
        lines.append("# HELP system_error_rate 系统错误率")
        lines.append("# TYPE system_error_rate gauge")
        lines.append(f"system_error_rate {system_error.get('error_rate', 0)}")

        lines.append("# HELP total_requests_24h 24小时总请求数")
        lines.append("# TYPE total_requests_24h counter")
        lines.append(f"total_requests_24h {system_error.get('total_requests_24h', 0)}")

        return "\n".join(lines)


# 全局业务指标服务实例
business_metrics_service = BusinessMetricsService()
