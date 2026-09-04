"""
监控服务
提供性能监控、错误统计、资源监控等功能
"""

import asyncio
import logging
import os
import threading
from datetime import timezone, datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.async_utils import create_background_task
from app.core.config import settings
from app.models.monitoring import AlertHistory, AlertRule, APIMetric
from app.services.alert_service import AlertService
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class MonitoringService:
    """监控服务"""

    @staticmethod
    def get_api_performance_stats(db: Session, hours: int = 24, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """
        获取API性能统计

        Args:
            db: 数据库会话
            hours: 统计时间范围(小时)
            endpoint: 特定端点(可选)

        Returns:
            性能统计字典
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = db.query(APIMetric).filter(APIMetric.timestamp >= since)

        if endpoint:
            query = query.filter(APIMetric.endpoint == endpoint)

        metrics = query.all()

        if not metrics:
            return {
                "total_requests": 0,
                "avg_response_time_ms": 0,
                "p50_response_time_ms": 0,
                "p95_response_time_ms": 0,
                "p99_response_time_ms": 0,
                "error_rate": 0,
            }

        response_times = [m.response_time_ms for m in metrics]
        response_times.sort()

        total = len(metrics)
        errors = len([m for m in metrics if m.status_code >= 400])

        return {
            "total_requests": total,
            "avg_response_time_ms": round(sum(response_times) / total, 2),
            "p50_response_time_ms": MonitoringService._percentile(response_times, 50),
            "p95_response_time_ms": MonitoringService._percentile(response_times, 95),
            "p99_response_time_ms": MonitoringService._percentile(response_times, 99),
            "error_rate": round(errors / total * 100, 2) if total > 0 else 0,
        }

    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        index = int(len(values) * percentile / 100)
        index = min(index, len(values) - 1)
        return round(values[index], 2)

    @staticmethod
    def get_endpoint_stats(db: Session, hours: int = 24, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取各端点的统计信息

        Args:
            db: 数据库会话
            hours: 统计时间范围(小时)
            limit: 返回数量限制

        Returns:
            端点统计列表
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # 按端点分组统计
        stats = (
            db.query(
                APIMetric.endpoint,
                func.count(APIMetric.id).label("total_requests"),
                func.avg(APIMetric.response_time_ms).label("avg_response_time"),
                func.sum(case((APIMetric.status_code >= 400, 1), else_=0)).label("error_count"),
            )
            .filter(APIMetric.timestamp >= since)
            .group_by(APIMetric.endpoint)
            .order_by(func.count(APIMetric.id).desc())
            .limit(limit)
            .all()
        )

        result = []
        for stat in stats:
            error_rate = (stat.error_count / stat.total_requests * 100) if stat.total_requests > 0 else 0
            result.append(
                {
                    "endpoint": stat.endpoint,
                    "total_requests": stat.total_requests,
                    "avg_response_time_ms": round(stat.avg_response_time, 2),
                    "error_count": stat.error_count,
                    "error_rate": round(error_rate, 2),
                }
            )

        return result

    @staticmethod
    def get_error_stats(db: Session, hours: int = 24) -> Dict[str, Any]:
        """
        获取错误统计

        Args:
            db: 数据库会话
            hours: 统计时间范围(小时)

        Returns:
            错误统计字典
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # 按状态码分组统计
        stats = (
            db.query(APIMetric.status_code, func.count(APIMetric.id).label("count"))
            .filter(APIMetric.timestamp >= since, APIMetric.status_code >= 400)
            .group_by(APIMetric.status_code)
            .all()
        )

        error_by_code = {str(stat.status_code): stat.count for stat in stats}
        total_errors = sum(error_by_code.values())

        return {"total_errors": total_errors, "error_by_code": error_by_code}

    @staticmethod
    def get_resource_stats() -> Dict[str, Any]:
        """
        获取系统资源统计

        Returns:
            资源统计字典
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            # 跨平台磁盘路径：Windows 取 SystemDrive，其它平台取文件系统根 "/"
            # （曾硬编码回退 "C:\\"，在 Linux/麒麟上抛 FileNotFoundError 使整份统计变空）
            disk = psutil.disk_usage(os.environ.get("SystemDrive") or os.path.abspath(os.sep))

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": round(memory.used / 1024 / 1024, 2),
                "memory_total_mb": round(memory.total / 1024 / 1024, 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
            }
        except Exception as e:
            logger.error(f"获取资源统计失败: {e}", exc_info=True)
            return {}

    @staticmethod
    def check_alerts(db: Session):
        """
        检查告警规则并触发告警

        Args:
            db: 数据库会话
        """
        # 获取所有启用的告警规则
        rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()  # noqa: E712

        for rule in rules:
            try:
                MonitoringService._check_rule(db, rule)
            except Exception as e:
                logger.error(f"检查告警规则失败 {rule.name}: {e}")

    @staticmethod
    def _check_rule(db: Session, rule: AlertRule):
        """检查单个告警规则"""
        since = datetime.now(timezone.utc) - timedelta(seconds=rule.duration_seconds)

        if rule.metric_type == "response_time":
            # 检查平均响应时间
            avg_time = db.query(func.avg(APIMetric.response_time_ms)).filter(APIMetric.timestamp >= since).scalar()

            if avg_time and avg_time > rule.threshold:
                MonitoringService._trigger_alert(
                    db,
                    rule,
                    f"平均响应时间 {avg_time:.2f}ms 超过阈值 {rule.threshold}ms",
                    avg_time,
                )

        elif rule.metric_type == "error_rate":
            # 检查错误率
            total = db.query(func.count(APIMetric.id)).filter(APIMetric.timestamp >= since).scalar()

            errors = (
                db.query(func.count(APIMetric.id))
                .filter(APIMetric.timestamp >= since, APIMetric.status_code >= 400)
                .scalar()
            )

            if total and total > 0:
                error_rate = errors / total * 100
                if error_rate > rule.threshold:
                    MonitoringService._trigger_alert(
                        db,
                        rule,
                        f"错误率 {error_rate:.2f}% 超过阈值 {rule.threshold}%",
                        error_rate,
                    )

        elif rule.metric_type == "resource":
            # 检查资源使用率
            stats = MonitoringService.get_resource_stats()
            cpu_percent = stats.get("cpu_percent", 0)

            if cpu_percent > rule.threshold:
                MonitoringService._trigger_alert(
                    db,
                    rule,
                    f"CPU使用率 {cpu_percent:.2f}% 超过阈值 {rule.threshold}%",
                    cpu_percent,
                )

    @staticmethod
    def _trigger_alert(db: Session, rule: AlertRule, message: str, metric_value: float):
        """触发告警"""
        # 检查是否已有未解决的告警
        existing = (
            db.query(AlertHistory).filter(AlertHistory.rule_id == rule.id, AlertHistory.status == "triggered").first()
        )

        if existing:
            # 已有未解决的告警,不重复触发
            return

        # 创建告警记录
        alert = AlertHistory(
            rule_id=rule.id,
            message=message,
            metric_value=metric_value,
            status="triggered",
        )
        db.add(alert)
        safe_commit(db)

        logger.warning(f"告警触发: {rule.name} - {message}")

        # 在后台发送告警通知（不阻塞主流程）
        task = create_background_task(MonitoringService._send_alert_notification(rule, message))
        if task is None:
            # 没有运行中的事件循环，使用线程池发送通知
            logger.warning("无运行中的事件循环，使用线程池发送告警通知")
            threading.Thread(
                target=asyncio.run,
                args=(MonitoringService._send_alert_notification(rule, message),),
                daemon=True
            ).start()

    @staticmethod
    async def _send_alert_notification(rule: AlertRule, message: str):
        """发送告警通知"""
        logger.info(f"发送告警通知: {rule.name} - {message}")

        # 发送邮件通知
        if hasattr(settings, "ALERT_EMAIL_RECIPIENTS") and settings.ALERT_EMAIL_RECIPIENTS:
            try:
                await AlertService.send_email_alert(
                    recipients=settings.ALERT_EMAIL_RECIPIENTS,
                    subject=f"【系统告警】{rule.name}",
                    message=f"告警规则: {rule.name}\n告警消息: {message}\n触发时间: {datetime.now(timezone.utc).isoformat()}",
                )
            except Exception as e:
                logger.error(f"发送邮件告警失败: {e}", exc_info=True)

        # 发送Webhook通知
        if hasattr(settings, "ALERT_WEBHOOK_URL") and settings.ALERT_WEBHOOK_URL:
            try:
                webhook_type = getattr(settings, "ALERT_WEBHOOK_TYPE", "generic")
                await AlertService.send_webhook_alert(
                    webhook_url=settings.ALERT_WEBHOOK_URL,
                    message=f"告警规则: {rule.name}\n告警消息: {message}",
                    webhook_type=webhook_type,
                )
            except Exception as e:
                logger.error(f"发送Webhook告警失败: {e}", exc_info=True)
