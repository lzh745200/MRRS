"""
定时任务调度服务

提供后台定时任务（基于 threading.Timer 实现）：
- 自动数据库备份（每日 02:00）
- KPI 预计算缓存（每日 00:30）
- 资金异常检测（每日 01:00）
- 待办事项到期提醒（每日 08:00）
- 工作周报生成（每周一 06:30）
- 数据库维护（每日 03:00）

注意：APScheduler 已移除，使用 threading.Timer 替代。
"""

import logging
import os
import threading
from datetime import datetime, timedelta

from app.core.transaction import get_db_context
from app.services.backup_service import BackupService
from app.services.system_config_service import get_config

logger = logging.getLogger(__name__)

_scheduler_started = False
_timers: list[threading.Timer] = []


def _admin_user_ids(db):
    """查询管理员用户 ID 列表（用于备份结果/失败提醒）"""
    from app.models.user import User

    return [
        row[0]
        for row in db.query(User.id)
        .filter(
            User.is_active == True,  # noqa: E712
            (User.is_superuser == True) | (User.role.in_(["admin", "super_admin"])),  # noqa: E712
        )
        .all()
    ]


def _send_backup_reminder(db, title: str, content: str) -> None:
    """向管理员发送备份提醒消息（消息中心「备份提醒」分类）"""
    from app.services.message_service import MessageService

    admin_ids = _admin_user_ids(db)
    if admin_ids:
        MessageService(db).send_batch_messages(
            user_ids=admin_ids,
            message_type="backup",
            title=title,
            content=content,
            link="/system/backup",
        )


async def auto_backup_job():
    """自动备份任务（支持自定义目标目录与默认加密，按 backup_interval_days 间隔执行）"""
    with get_db_context() as db:
        try:
            auto_backup_enabled = get_config("auto_backup", "false")
            if auto_backup_enabled != "true":
                logger.info("自动备份已禁用，跳过")
                return

            # 间隔检查: 距上次备份不足 interval_days 则跳过
            from datetime import datetime as _dt, timedelta as _td
            from app.models.system_config import SystemConfig

            interval_days = int(get_config("backup_interval_days", "30") or 30)
            last_row = (
                db.query(SystemConfig)
                .filter(SystemConfig.key == "last_backup_time")
                .first()
            )
            if last_row and isinstance(getattr(last_row, "value", None), str) and last_row.value:
                try:
                    last_ts = _dt.fromisoformat(last_row.value)
                    if _dt.now() - last_ts < _td(days=interval_days):
                        logger.info("距上次备份不足 %d 天，跳过自动备份", interval_days)
                        return
                except ValueError:
                    pass

            from app.utils.drive_detect import ensure_target_dir

            target_dir = get_config("backup_target_dir", "") or None
            encrypt = get_config("backup_encrypt", "false") == "true"
            if target_dir and not ensure_target_dir(target_dir):
                logger.warning("备份目标目录不可写: %s，回退默认目录", target_dir)
                target_dir = None

            backup_service = BackupService(db, backup_dir=target_dir) if target_dir else BackupService(db)
            if encrypt:
                # 加密口令：从 runtime_secrets 读取/生成持久密钥（随机 32 字符），
                # 替代硬编码 "auto-backup-key"（公开已知口令 = 加密形同虚设）
                from app.utils.runtime_secrets import get_or_create_secret

                backup_password = get_or_create_secret(
                    "BACKUP_ENCRYPTION_KEY",
                    generate=lambda: __import__("secrets").token_urlsafe(32),
                )
                backup = backup_service.create_backup(
                    description="自动备份", include_uploads=False,
                    password=backup_password,
                )
            else:
                backup = backup_service.create_backup(
                    description="自动备份", include_uploads=False,
                )
            logger.info("自动备份完成: %s, 大小: %d 字节", backup.file_name, backup.file_size or 0)

            max_count = int(get_config("max_backup_count", "3"))
            deleted_count = backup_service.cleanup_old_backups(keep_count=max_count)
            if deleted_count > 0:
                logger.info("清理了 %d 个旧备份", deleted_count)

            # 备份提醒消息：通知管理员备份结果（消息中心「备份提醒」分类）
            try:
                _send_backup_reminder(
                    db,
                    "自动备份完成",
                    (
                        f"定时备份已生成：{backup.file_name}"
                        f"（{(backup.file_size or 0) / 1024 / 1024:.1f} MB），"
                        f"仅保留最近 {max_count} 份。"
                    ),
                )
            except Exception as msg_err:
                logger.warning("备份完成提醒消息发送失败: %s", msg_err)
        except Exception as e:
            logger.error("自动备份失败: %s", str(e), exc_info=True)
            try:
                _send_backup_reminder(
                    db,
                    "自动备份失败",
                    f"定时自动备份执行失败：{e}，请检查备份目录与磁盘空间后手动备份。",
                )
            except Exception as msg_err:
                logger.warning("备份失败提醒消息发送失败: %s", msg_err)


async def kpi_precalculate_job():
    """定时预计算 KPI 统计，写入缓存（每日 00:30）"""
    with get_db_context() as db:
        try:
            from sqlalchemy import func as sa_func
            from app.models.project import Project
            from app.models.supported_village import SupportedVillage
            from app.core.cache import get_cache_service
            from app.core.constants import ANALYTICS_CACHE_PREFIX

            total_villages = (
                db.query(sa_func.count(SupportedVillage.id))
                .filter(SupportedVillage.is_active.is_(True))
                .scalar()
                or 0
            )
            # 软删项目不参与 KPI 统计（与 /analytics/kpi-summary 口径一致）
            rows = (
                db.query(Project.status, sa_func.count(Project.id))
                .filter(Project.is_active == True)  # noqa: E712
                .group_by(Project.status)
                .all()
            )
            counts = {status: cnt for status, cnt in rows}
            total_projects = sum(counts.values())
            completed_projects = counts.get("completed", 0)
            approved_projects = counts.get("approved", 0)

            data = {
                "total_villages": total_villages,
                "total_projects": total_projects,
                "completed_projects": completed_projects,
                "approved_projects": approved_projects,
                "completion_rate": round(completed_projects / total_projects * 100, 1) if total_projects else 0,
                "period": "month",
            }
            cache = await get_cache_service()
            await cache.set(f"{ANALYTICS_CACHE_PREFIX}kpi_summary_month", data, 86400)
            logger.info("KPI 统计预计算完成，已写入缓存")
        except Exception as e:
            logger.error("KPI 预计算失败: %s", e, exc_info=True)


async def anomaly_detection_job():
    """定时资金异常检测（每日 01:00），将新异常写入系统消息"""
    with get_db_context() as db:
        try:
            from app.models.project import Project
            from app.models.user import User
            from app.services.fund_anomaly_detector import detect_anomalies
            from app.services.message_service import MessageService

            active_projects = (
                db.query(Project)
                .filter(
                    Project.is_active == True,  # noqa: E712
                    Project.status.in_(["active", "approved"]),
                )
                .all()
            )
            total_new = 0
            for project in active_projects:
                try:
                    anomalies = detect_anomalies(db, project.id)
                    total_new += len(anomalies)
                except Exception as e:
                    # 单项目检测失败不阻断其他项目，但必须可见（资金异常漏报风险）
                    logger.warning("项目 %s 异常检测失败: %s", project.id, e, exc_info=True)
                    continue

            if total_new > 0:
                svc = MessageService(db)
                admin_ids = [
                    row[0]
                    for row in db.query(User.id)
                    .filter(User.is_superuser == True, User.is_active == True)  # noqa: E712
                    .all()
                ]
                svc.send_batch_messages(
                    user_ids=admin_ids,
                    message_type="system",
                    title=f"资金异常检测提醒：发现 {total_new} 条新异常",
                    content=f"定时异常检测（{datetime.now().strftime('%Y-%m-%d')}）发现 {total_new} 条新资金异常，请及时处理。",
                    link="/funds/anomaly",
                )
                logger.info("资金异常检测完成，发现 %d 条新异常", total_new)
            else:
                logger.info("资金异常检测完成，未发现新异常")
        except Exception as e:
            logger.error("资金异常检测失败: %s", e, exc_info=True)


async def todo_reminder_job():
    """检查今日及明日到期的待办事项并推送提醒（每日 08:00）"""
    with get_db_context() as db:
        try:
            from app.models.todo import Todo
            from app.services.message_service import MessageService

            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            today_str = today.strftime("%Y-%m-%d")
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")

            todos = (
                db.query(Todo)
                .filter(
                    Todo.completed == False,  # noqa: E712
                    Todo.deadline.isnot(None),
                    Todo.deadline >= today_str,
                    Todo.deadline <= tomorrow_str,
                )
                .all()
            )
            svc = MessageService(db)
            for todo in todos:
                if todo.user_id is None:
                    continue
                days_left = (datetime.strptime(todo.deadline, "%Y-%m-%d").date() - today).days
                label = "今日到期" if days_left == 0 else "明日到期"
                svc.send_task_message(
                    user_id=todo.user_id,
                    title=f"待办提醒：{todo.title}（{label}）",
                    content=f"您有一项待办事项「{todo.title}」{label}，请及时处理。",
                    link="/work-calendar",
                )
            logger.info("待办提醒推送完成，共 %d 条", len(todos))
        except Exception as e:
            logger.error("待办提醒失败: %s", e, exc_info=True)


async def message_cleanup_job():
    """清理过期站内消息（每日 03:30，保留最近 30 天）"""
    with get_db_context() as db:
        try:
            from app.services.message_service import MessageService

            svc = MessageService(db)
            deleted = svc.cleanup_old_messages(days=30)
            logger.info("消息清理完成，删除 %d 条过期消息（保留 30 天）", deleted)
        except Exception as e:
            logger.error("消息清理失败: %s", e, exc_info=True)


async def weekly_report_job():
    """每周一生成工作周报消息（每周一 06:30）"""
    with get_db_context() as db:
        try:
            from app.models.work_log import WorkLog
            from app.models.todo import Todo
            from app.models.user import User
            from app.services.message_service import MessageService
            from sqlalchemy import func as sa_func

            today = datetime.now().date()
            week_start = today - timedelta(days=7)

            log_count = db.query(sa_func.count(WorkLog.id)).filter(WorkLog.log_date >= week_start).scalar() or 0
            completed_todos = (
                db.query(sa_func.count(Todo.id))
                .filter(
                    Todo.completed == True,  # noqa: E712
                    Todo.updated_at >= week_start,
                )
                .scalar()
                or 0
            )
            content = (
                f"上周（{week_start} ~ {today}）工作汇总：\n"
                f"• 工作日志记录 {log_count} 条\n"
                f"• 完成待办事项 {completed_todos} 项\n"
                "新的一周祝工作顺利！"
            )

            user_ids = [row[0] for row in db.query(User.id).filter(User.is_active == True).all()]  # noqa: E712
            svc = MessageService(db)
            svc.send_batch_messages(
                user_ids=user_ids,
                message_type="system",
                title=f"工作周报 ({week_start} ~ {today})",
                content=content,
                link="/analytics/work-analysis",
            )
            logger.info("工作周报已推送给 %d 名用户", len(user_ids))
        except Exception as e:
            logger.error("工作周报生成失败: %s", e, exc_info=True)


async def database_maintenance_job():
    """定时数据库维护（每日 03:00）：VACUUM + WAL checkpoint + PRAGMA optimize"""
    try:
        import sqlite3
        from app.utils.paths import get_database_path

        db_path = str(get_database_path().absolute())
        if not os.path.exists(db_path):
            logger.warning("数据库文件不存在，跳过维护")
            return

        before_size = os.path.getsize(db_path)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA optimize")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA integrity_check")
        finally:
            conn.close()

        after_size = os.path.getsize(db_path)
        saved_kb = round((before_size - after_size) / 1024, 1)
        logger.info(
            "数据库维护完成 (优化前: %.1fMB, 优化后: %.1fMB, 节省: %.1fKB)",
            before_size / 1024 / 1024, after_size / 1024 / 1024, saved_kb,
        )
    except Exception as e:
        logger.error("数据库维护失败: %s", e, exc_info=True)


async def auto_package_job():
    """定期自动打包数据（单机防丢失）：按 auto_package_interval_months 生成数据包到指定目录。

    单机场景：即使本机损坏，U盘/共享盘里仍保留最近的数据包可恢复。
    """
    try:
        with get_db_context() as db:
            await _auto_package_with_db(db)
    except Exception as e:
        logger.error("自动打包失败: %s", e, exc_info=True)


async def reminder_scan_job():
    """统一提醒扫描（每 6 小时）：审批超时/项目截止/预算预警 → Message 表"""
    try:
        from app.services.reminder_orchestrator import run_reminder_scans

        created = run_reminder_scans()
        if created:
            logger.info("提醒扫描完成，新增 %d 条提醒", len(created))
    except Exception as e:
        logger.error("提醒扫描失败: %s", e, exc_info=True)


async def _auto_package_with_db(db):
    """自动打包核心逻辑（独立函数便于测试）"""
    enabled = get_config("auto_package_enabled", "false")
    if enabled != "true":
        return

    from datetime import datetime as _dt

    interval_months = int(get_config("auto_package_interval_months", "1") or 1)
    target_dir = (get_config("auto_package_dir", "") or "").strip()
    if not target_dir:
        logger.info("自动打包未配置目标目录，跳过")
        return
    from app.utils.drive_detect import ensure_target_dir

    if not ensure_target_dir(target_dir):
        logger.warning("自动打包目标目录不可写: %s，跳过", target_dir)
        return

    # 间隔检查
    from app.models.system_config import SystemConfig

    last_row = (
        db.query(SystemConfig)
        .filter(SystemConfig.key == "last_package_time")
        .first()
    )
    if last_row and isinstance(getattr(last_row, "value", None), str) and last_row.value:
        try:
            last_ts = _dt.fromisoformat(last_row.value)
            months = (datetime.now().year - last_ts.year) * 12 + (datetime.now().month - last_ts.month)
            if months < interval_months:
                logger.info("距上次自动打包不足 %d 个月，跳过", interval_months)
                return
        except ValueError:
            pass

    # 打包全部数据类型
    from app.models.organization import Organization
    from app.services.data_package_service import DataPackageService

    org = db.query(Organization).order_by(Organization.id).first()
    if not org:
        logger.warning("无组织数据，跳过自动打包")
        return

    from app.services.data_package_service import DATA_TYPE_MODELS

    svc = DataPackageService(db)
    result = await svc.export_package(
        org_id=org.id,
        data_types=list(DATA_TYPE_MODELS.keys()),
        export_by=0,
        description="定期自动打包",
    )

    # 复制到目标目录（U盘/共享盘）
    import shutil

    src = result.file_path
    if os.path.exists(src):
        os.makedirs(target_dir, exist_ok=True)
        dst = os.path.join(target_dir, os.path.basename(src))
        shutil.copy2(src, dst)
        logger.info("自动打包完成: %s (记录 %d 条)", dst, result.total_records or 0)
    else:
        logger.warning("自动打包文件未生成: %s", src)

    # 记录上次打包时间
    from app.services.system_config_service import set_config

    set_config("last_package_time", datetime.now().isoformat(), "最近自动打包时间")


def start_backup_scheduler():
    """启动后台调度器（仅轻量任务，不含自动备份和 VACUUM）

    使用 threading.Timer 实现简易定时调度，替代已移除的 APScheduler。
    """
    global _scheduler_started  # pragma: no cover - global 声明行，无执行语义
    if _scheduler_started:
        logger.info("调度器已在运行，跳过重复启动")
        return

    import asyncio

    def _run_async_job(coro_func):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro_func())
            loop.close()
        except Exception as e:
            logger.error("定时任务执行失败: %s", e)

    def _schedule_daily(coro_func, hour, minute, task_name):
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()

        def _job():
            _run_async_job(coro_func)
            _schedule_daily(coro_func, hour, minute, task_name)

        t = threading.Timer(delay, _job)
        t.daemon = True
        t.name = f"scheduler-{task_name}"
        t.start()
        _timers.append(t)

    def _schedule_weekly(coro_func, weekday, hour, minute, task_name):
        now = datetime.now()
        days_ahead = weekday - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        target = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(weeks=1)
        delay = (target - now).total_seconds()

        def _job():
            _run_async_job(coro_func)
            _schedule_weekly(coro_func, weekday, hour, minute, task_name)

        t = threading.Timer(delay, _job)
        t.daemon = True
        t.name = f"scheduler-{task_name}"
        t.start()
        _timers.append(t)

    def _schedule_interval(coro_func, interval_seconds, task_name):
        """按固定间隔调度（首次延迟 interval 秒）。
        递归 Timer 不加入 _timers（daemon 线程随进程退出），避免列表无限增长。
        """

        def _job():
            _run_async_job(coro_func)
            t = threading.Timer(interval_seconds, _job)
            t.daemon = True
            t.name = f"scheduler-{task_name}"
            t.start()

        t = threading.Timer(interval_seconds, _job)
        t.daemon = True
        t.name = f"scheduler-{task_name}"
        t.start()
        _timers.append(t)

    _schedule_daily(kpi_precalculate_job, 0, 30, "kpi_precalculate")
    _schedule_daily(anomaly_detection_job, 1, 0, "anomaly_detection")
    _schedule_daily(auto_backup_job, 2, 0, "auto_backup")
    _schedule_daily(auto_package_job, 3, 0, "auto_package")
    _schedule_daily(message_cleanup_job, 3, 30, "message_cleanup")
    _schedule_interval(reminder_scan_job, 6 * 3600, "reminder_scan")
    _schedule_daily(todo_reminder_job, 8, 0, "todo_reminder")
    _schedule_weekly(weekly_report_job, 0, 6, 30, "weekly_report")

    _scheduler_started = True
    logger.info("调度器已启动（KPI预计算 + 异常检测 + 自动备份 + 自动打包 + 消息清理 + 提醒扫描 + 待办提醒 + 周报）")


def stop_backup_scheduler():
    """停止备份调度器"""
    global _scheduler_started
    for t in _timers:
        t.cancel()
    _timers.clear()
    _scheduler_started = False
    logger.info("调度器已停止")


def get_scheduler_status():
    """获取调度器状态"""
    return {
        "running": _scheduler_started,
        "jobs": [
            {"id": t.name, "name": t.name, "next_run_time": None}
            for t in _timers
            if t.is_alive()
        ],
    }
