"""报表订阅到期分发服务（工单 003 方案 A+B 落地）

订阅创建后由调度器每 15 分钟扫描一次到期项（方案 A），并提供
generate-now 端点供手动立即生成（方案 B）。单机版「送达」语义：
报表文件落盘（订阅方 output_dir 或运行时 uploads/subscription_reports）
+ 站内消息通知。email 字段单机版不发（模型注释已声明保留兼容）。

next_run_at 为纯函数（无 IO、无墙钟读取）：CI#84 墙钟黑洞教训——
时间语义必须可确定性测试。
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_SEND_TIME = "08:00"
_VALID_FREQUENCIES = {"daily", "weekly", "monthly", "quarterly"}
_WEEKDAY_ALIASES = {
    "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7,
}


def _parse_send_time(send_time: Optional[str]) -> tuple:
    """解析 "HH:MM"/"HH:MM:SS"；空值/非法值回落 08:00（不抛错，容错优先）。"""
    raw = (send_time or "").strip()
    if not raw:
        raw = _DEFAULT_SEND_TIME
    parts = raw.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return 8, 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return 8, 0
    return hour, minute


def _normalize_send_day(frequency: str, send_day: Optional[int]) -> Optional[int]:
    """按频次归一 send_day；越界/非法返回 None（由调用方按频次取默认值）。"""
    if send_day is None:
        return None
    try:
        day = int(send_day)
    except (TypeError, ValueError):
        return None
    if frequency == "weekly":
        return day if 1 <= day <= 7 else None
    # monthly / quarterly：1..31，越界由钳制语义处理
    return day if 1 <= day <= 31 else None


def _clamp_day(year: int, month: int, day: int) -> int:
    """把日钳制到该月最后一天（send_day=31 在 2 月 → 28/29）。"""
    if month == 12:
        next_month_first = datetime(year + 1, 1, 1)
    else:
        next_month_first = datetime(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    return min(day, last_day)


def next_run_at(
    frequency: str, send_day: Optional[int], send_time: Optional[str], base: datetime
) -> datetime:
    """计算 base 之后（严格晚于）的下一次运行时间。

    Args:
        frequency: daily/weekly/monthly/quarterly，未知值抛 ValueError。
        send_day: weekly=1..7（周一..周日）；monthly/quarterly=1..31（按月钳制）；
            daily 忽略。None 取各频次默认（weekly=周一，monthly/quarterly=1 号）。
        send_time: "HH:MM"/"HH:MM:SS"，空/非法回落 08:00。
        base: 计算基准（订阅的 last_sent_at 或 created_at），结果严格晚于 base。

    Returns:
        datetime: 下一次运行时刻。
    """
    freq = (frequency or "").strip().lower()
    if freq not in _VALID_FREQUENCIES:
        raise ValueError(f"未知发送频率: {frequency!r}")

    hour, minute = _parse_send_time(send_time)
    day = _normalize_send_day(freq, send_day)

    def _at(year: int, month: int, day_of_month: int) -> datetime:
        return datetime(year, month, day_of_month, hour, minute)

    if freq == "daily":
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate

    if freq == "weekly":
        weekday = day if day is not None else 1  # 默认周一
        target_wd = weekday - 1  # datetime.weekday(): Monday=0
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (target_wd - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= base:
            candidate += timedelta(weeks=1)
        return candidate

    # monthly / quarterly
    if freq == "monthly":
        anchor_day = day if day is not None else 1
        candidate = base.replace(
            day=_clamp_day(base.year, base.month, anchor_day),
            hour=hour, minute=minute, second=0, microsecond=0,
        )
        if candidate <= base:
            # 滚到下一个月（跨年安全；先钳制日再构造，31 在 2 月不越界）
            year, month = (base.year + 1, 1) if base.month == 12 else (base.year, base.month + 1)
            candidate = _at(year, month, _clamp_day(year, month, anchor_day))
        return candidate

    # quarterly：季度首月（1/4/7/10）的 anchor_day
    anchor_day = day if day is not None else 1
    quarter_months = (1, 4, 7, 10)
    year, month = base.year, base.month
    while month not in quarter_months:
        month += 1
        if month > 12:
            month = 1
            year += 1
    candidate = base.replace(
        year=year, month=month, day=_clamp_day(year, month, anchor_day),
        hour=hour, minute=minute, second=0, microsecond=0,
    )
    if candidate <= base:
        next_q_month = month + 3
        if next_q_month > 12:
            next_q_month -= 12
            year += 1
        candidate = base.replace(
            year=year, month=next_q_month,
            day=_clamp_day(year, next_q_month, anchor_day),
            hour=hour, minute=minute, second=0, microsecond=0,
        )
    return candidate


def _period_starts_after(base: datetime, sent: datetime, frequency: str) -> bool:
    """sent 是否已不在 base 所在的发送周期内（防同周期重复生成的辅助判定）。

    dispatch 以 last_sent_at 为 next_run_at 的基准（见 dispatch_due_subscriptions），
    生成成功后 last_sent_at 即为新的 base，下一次运行必然严格晚于它——
    因此本函数在主链路中不再需要，仅保留给未来需要独立周期语义时使用。
    """
    try:
        return next_run_at(frequency, None, None, base) <= sent
    except ValueError:
        return False


class SubscriptionDispatchService:
    """订阅到期扫描与单条生成。"""

    async def generate_for_subscription(
        self,
        db,
        sub,
        user: Any,
        now: datetime,
    ) -> Dict[str, Any]:
        """为单条订阅生成报表文件并落盘 + 站内消息通知。

        Args:
            db: 数据库会话。
            sub: ReportSubscription 记录。
            user: 订阅属主（生成走其数据权限过滤）。
            now: 本次生成时间戳（写入 last_sent_at 与文件名）。

        Returns:
            {"file_name", "file_path", "size"}
        """
        from app.services.report_service import ReportService
        from app.utils.paths import get_runtime_uploads_path

        out_dir = (
            Path(sub.output_dir)
            if getattr(sub, "output_dir", None)
            else get_runtime_uploads_path("subscription_reports")
        )
        out_dir.mkdir(parents=True, exist_ok=True)

        fmt = (sub.format or "xlsx").strip().lower()
        query_params: Dict[str, Any] = {
            "year": sub.year,
            "report_type": sub.report_type or "",
        }
        report_service = ReportService(db)
        if fmt == "pdf":
            payload = await report_service.export_to_pdf(query_params, user=user)
            ext = "pdf"
        else:
            # xlsx 为默认（word/其它未知值安全回落 excel；公文 word 报表走
            # 「官方报表导出」区已有专门入口，订阅不做猜测性扩展）
            payload = await report_service.export_to_excel(query_params, user=user)
            ext = "xlsx"

        file_name = f"subscription-{sub.id}-{now.strftime('%Y%m%d%H%M%S')}.{ext}"
        file_path = out_dir / file_name
        file_path.write_bytes(payload)

        sub.last_sent_at = now
        from app.core.transaction import safe_commit

        safe_commit(db)

        from app.services.message_service import MessageService

        MessageService(db).send_system_message(
            user_id=sub.user_id,
            title=f"订阅报表已生成：{sub.name}",
            content=(
                f"您订阅的报表「{sub.name}」已生成（{file_name}，"
                f"{len(payload)} 字节），已保存到报表输出目录。"
            ),
            link="/export",
        )
        logger.info(
            "订阅 %s 报表生成完成: %s (%d 字节)", sub.id, file_path, len(payload)
        )
        return {"file_name": file_name, "file_path": str(file_path), "size": len(payload)}

    async def dispatch_due_subscriptions(self, db, now: datetime) -> Dict[str, int]:
        """扫描全部启用订阅，对到期项生成并送达。

        到期判定：next_run_at(frequency, send_day, send_time, base) <= now，
        其中 base = last_sent_at（上次生成时间）或 created_at（从未生成）。
        生成成功后 last_sent_at=now 成为新基准——下一次运行必然严格晚于它，
        同一周期天然不会重复生成。

        Returns:
            {"dispatched": N, "skipped": N, "failed": N}
        """
        from app.models.supported_village import ReportSubscription
        from app.models.user import User

        stats = {"dispatched": 0, "skipped": 0, "failed": 0}
        subs = (
            db.query(ReportSubscription)
            .filter(ReportSubscription.is_active.is_(True))
            .all()
        )
        for sub in subs:
            try:
                base = sub.last_sent_at or sub.created_at
                if base is None:
                    stats["skipped"] += 1
                    continue
                due_at = next_run_at(
                    sub.frequency, sub.send_day, sub.send_time, base
                )
                if due_at > now:
                    stats["skipped"] += 1
                    continue
                owner = db.query(User).filter(User.id == sub.user_id).first()
                await self.generate_for_subscription(db, sub, owner, now)
                stats["dispatched"] += 1
            except Exception as e:
                stats["failed"] += 1
                logger.error(
                    "订阅 %s 生成失败（不影响其余订阅）: %s", sub.id, e, exc_info=True
                )
                db.rollback()
        return stats
