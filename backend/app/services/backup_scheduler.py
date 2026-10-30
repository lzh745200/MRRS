"""
定时任务调度服务

提供后台定时任务（基于 threading.Timer 实现）：
- 自动数据库备份（每日 02:00）
- KPI 预计算缓存（每日 00:30）
- 资金异常检测（每日 01:00）
- 待办事项到期提醒（每日 08:00）
- 工作周报生成（每周一 06:30）
- 数据库维护（每日 03:00）
- 审计/日志大表保留期清理（每日 04:20）

注意：APScheduler 已移除，使用 threading.Timer 替代。
"""

import logging
import os
import sys
import threading
from datetime import datetime, time, timedelta
from typing import Optional

from app.core.transaction import get_db_context
from app.services.backup_service import BackupService
from app.services.system_config_service import get_config, get_int_config
from app.utils.time_utils import parse_local_wallclock, utcnow, utcnow_naive

logger = logging.getLogger(__name__)

_scheduler_started = False
_timers: list[threading.Timer] = []
_backup_timer: threading.Timer | None = None
_backup_timer_lock = threading.Lock()
# 停止标志：_job 在重排下一次之前必须检查，否则 stop 之后 interval/daily 链
# 仍会继续自我重排（cancel 只能取消「尚未触发」的 Timer，拦不住正在运行中的 _job）
_stopping = threading.Event()

# R36：启动补跑延迟（秒）。等 lifespan 其余启动步骤（建表/迁移/静态资源）落地后
# 再跑，避免与首启初始化抢锁；一次性任务，不自我重排。
BACKUP_CATCHUP_DELAY_SECONDS = 15


def _register_timer(timer: threading.Timer) -> None:
    """登记调度 Timer，并回收已终止的旧句柄（防止 _timers 无限增长）。"""
    _timers[:] = [t for t in _timers if t.is_alive()]
    _timers.append(timer)


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


def _cleanup_expired_backups(db) -> int:
    """按 ``backup_retention_days`` 清理过期备份，返回实际使用的保留天数。

    **单一事实源 + 与备份节奏解耦**：保留策略只由后端配置决定，且不受
    「距上次备份是否满 N 天」影响。

    历史缺陷：本清理原先排在 ``auto_backup_job`` 的**间隔 early return 之后** ——
    而 Electron 每次自动备份都会刷新 ``last_backup_time``，使间隔判定长期命中
    "距上次不足 N 天，跳过"，于是后端清理永久不可达；磁盘上实际只剩 Electron 侧
    硬编码 7 天的那套清理，形成两套事实源。
    """
    retention_days = get_int_config("backup_retention_days", 7, getter=get_config)
    try:
        deleted_count = BackupService(db).cleanup_by_retention_days(retention_days)
        if deleted_count > 0:
            logger.info("按保留 %d 天清理了 %d 个旧备份", retention_days, deleted_count)
    except Exception:
        # 清理失败不应影响备份主流程（下个周期会再试）
        logger.warning("备份保留策略清理失败", exc_info=True)
    return retention_days


def _backup_interval_days() -> int:
    """自动备份间隔（天）—— ``auto_backup_job`` 与启动补跑的**单一事实源**。"""
    return get_int_config("backup_interval_days", 1, getter=get_config)


def _last_backup_time(db):
    """读取 ``last_backup_time``（未配置/空串/脏值 → ``None``，视为从未备份）。

    用 ``time_utils.parse_local_wallclock`` 归一：带时区偏移的脏值不再因
    naive - aware 抛 TypeError 逃逸成"整个自动备份失败"。

    R36：抽成函数是为了让 ``auto_backup_job`` 与启动补跑
    （``_backup_catchup_due``）读**完全同一份**判定输入 —— 否则两处口径漂移会
    在补跑后重复备份，或该补的时候不补。
    """
    from app.models.system_config import SystemConfig

    last_row = (
        db.query(SystemConfig).filter(SystemConfig.key == "last_backup_time").first()
    )
    if last_row and isinstance(getattr(last_row, "value", None), str) and last_row.value:
        return parse_local_wallclock(last_row.value)
    return None


def _backup_catchup_due(now: "datetime | None" = None, db=None) -> "tuple[bool, int]":
    """启动补跑判定：返回 ``(是否需要补跑, 间隔天数)``。

    R36（离线长期运行可靠性）：单机现场常见"机器每天只开机几小时 / 刚好错过
    02:00"，纯每日定时会让自动备份长期不执行。启动时补跑一次即可兜住。

    **幂等**：判定口径与 ``auto_backup_job`` 的间隔 early-return 完全一致
    （同 ``backup_interval_days`` 配置键、同 ``last_backup_time``、同
    ``parse_local_wallclock`` 归一）。补跑成功后 ``BackupService`` 会刷新
    ``last_backup_time``，当日 02:00 的 daily 任务据此正常跳过 —— 不会重复备份。
    从未备份（无记录/脏值）视为到期：这种情况本就该立刻有一份备份。
    """
    interval_days = _backup_interval_days()
    if db is None:
        with get_db_context() as session:
            last_ts = _last_backup_time(session)
    else:
        last_ts = _last_backup_time(db)
    if last_ts is None:
        return True, interval_days
    current = now or datetime.now()
    return (current - last_ts) >= timedelta(days=interval_days), interval_days


def _is_pytest_process() -> bool:
    """当前进程是否 pytest 测试进程（启动补跑的保护开关）。

    为什么需要：启动补跑是**定时器**触发的真实备份，而测试进程里调度器常被
    ``start_backup_scheduler()`` 直接拉起 —— 定时器会在**用例之间**触发，
    落真实备份文件、写 ``last_backup_time`` 与管理员消息，造成跨用例污染与
    偶发失败（而每日任务因为延迟数小时，永远等不到）。生产进程不加载 pytest
    （PyInstaller 产物也不含），因此对真实运行零影响；测试通过 patch 本函数
    来验证补跑语义。
    """
    return "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _run_backup_catchup_job() -> None:
    """启动补跑（一次性）：距上次备份超过间隔或从未备份 → 立即补跑一次自动备份。

    退出语义沿用 ``_stopping``：已停止时连判定都不做（不做幽灵 DB 写），
    判定通过后若期间收到停止信号也不再开跑。判定异常只记 ERROR 不向上抛 ——
    调度线程不允许因单次失败而中断。
    """
    if _stopping.is_set():
        return
    if _is_pytest_process():
        # 测试进程：定时器会在用例间触发，绝不能在这里落真实备份
        logger.debug("pytest 进程，跳过启动补跑")
        return
    try:
        due, interval_days = _backup_catchup_due()
    except Exception:
        logger.error("启动备份补跑判定失败（本次跳过，下次启动再试）", exc_info=True)
        return
    if not due:
        logger.info("距上次备份未超过 %d 天，跳过启动补跑", interval_days)
        return
    logger.warning(
        "距上次备份已超过 %d 天或从未备份，启动时立即补跑一次自动备份", interval_days
    )
    if _stopping.is_set():
        return
    _run_scheduler_job(auto_backup_job)


async def auto_backup_job():
    """自动备份任务（后端调度唯一真相源）。

    每日 02:00 由 scheduler 触发；按 backup_retention_days（默认 7 天）清理过期备份。
    Electron 仅负责触发，不维护任何备份策略。
    """
    with get_db_context() as db:
        try:
            auto_backup_enabled = get_config("auto_backup", "true")
            if auto_backup_enabled != "true":
                logger.info("自动备份已禁用，跳过")
                return

            # 保留策略先于「是否该备份」执行（自动备份开着就每天清一次），
            # 否则间隔判定会把清理一起饿死 —— 详见 _cleanup_expired_backups 注释。
            retention_days = _cleanup_expired_backups(db)

            # 间隔检查: 距上次备份不足 interval_days 则跳过
            interval_days = _backup_interval_days()
            last_ts = _last_backup_time(db)
            if last_ts is not None and datetime.now() - last_ts < timedelta(days=interval_days):
                logger.info("距上次备份不足 %d 天，跳过自动备份", interval_days)
                return

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

            # 备份提醒消息：通知管理员备份结果（消息中心「备份提醒」分类）
            try:
                _send_backup_reminder(
                    db,
                    "自动备份完成",
                    (
                        f"定时备份已生成：{backup.file_name}"
                        f"（{(backup.file_size or 0) / 1024 / 1024:.1f} MB），"
                        f"保留最近 {retention_days} 天。"
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
            from app.core.cache import get_cache_service
            from app.core.constants import ANALYTICS_CACHE_PREFIX

            # Phase G：与 /analytics/kpi-summary 端点共用唯一实现，杜绝口径漂移
            from app.api.v1.data.data.analytics import compute_kpi_summary_data

            data = compute_kpi_summary_data(db)
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


async def data_package_cleanup_job():
    """数据包导出文件保留期清理（W18 P1-6，每日 04:10）。

    单机离线环境下用户频繁导出数据包（每个数十~数百 MB），原实现没有任何累计
    清理：一年后磁盘被撑满 → 备份/导入失败，且首页不会提前预警。保留策略与
    备份同口径（按天，默认 7 天，可由配置覆盖），避免"只增不减"。
    """
    with get_db_context() as db:
        try:
            retention_days = get_int_config(
                "data_package_retention_days", 7, getter=get_config
            )
            from app.services.data_package_service import DataPackageService

            DataPackageService(db).cleanup_exported_files(retention_days)
        except Exception:
            # 清理失败不影响其它任务（下个周期会再试）
            logger.warning("数据包保留期清理失败", exc_info=True)


async def session_cleanup_job():
    """回收过期/已吊销的登录会话行（每日 05:15，保留 30 天供审计）。

    user_sessions（2026-10-14 新增）只增不减：过期/已吊销行保留 30 天供审计追溯，
    超期后回收，防止长期运行的库无限膨胀。
    """
    from datetime import timedelta

    with get_db_context() as db:
        try:
            from app.models.user_session import UserSession
            from app.core.transaction import safe_commit
            from app.utils.time_utils import utcnow

            cutoff = utcnow() - timedelta(days=30)
            expired = (
                db.query(UserSession)
                .filter(UserSession.expires_at.isnot(None), UserSession.expires_at < cutoff)
                .delete(synchronize_session=False)
            )
            revoked = (
                db.query(UserSession)
                .filter(UserSession.revoked_at.isnot(None), UserSession.revoked_at < cutoff)
                .delete(synchronize_session=False)
            )
            safe_commit(db)
            if expired or revoked:
                logger.info("会话清理：回收过期 %s 条、已吊销 %s 条（保留期 30 天）", expired, revoked)
        except Exception:
            logger.error("会话清理作业失败", exc_info=True)


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


async def audit_log_cleanup_job():
    """审计/日志大表保留期清理（W5-T8，每日 04:20）。

    六张审计/日志表（audit_logs / api_access_logs / login_attempts /
    security_events / data_export_logs / token_blacklist）此前只增不减：
    audit_middleware 在 H9 批量缓冲前对每个请求独立落库，长期运行下库体积、
    WAL 与索引维护成本持续上升（备份/体检变慢）。本作业按各表保留期删除超期行
    （默认值单一事实源在 audit_retention_service.DEFAULT_RETENTION_DAYS，可由
    同名 SystemConfig 键覆盖；token_blacklist 只删已过期条目，永久吊销保留）。

    失败不外抛（记 ERROR，下个周期重试），与其余清理作业同约定。
    """
    from app.services.audit_retention_service import (
        DEFAULT_RETENTION_DAYS,
        purge_expired_audit_rows,
    )

    with get_db_context() as db:
        try:
            retention_days = {
                key: get_int_config(key, default, getter=get_config)
                for key, default in DEFAULT_RETENTION_DAYS.items()
            }
            counts = purge_expired_audit_rows(db, retention_days)
        except Exception:
            # 清理失败不阻断其它任务（下个周期会再试），但必须可见
            logger.error("审计日志保留期清理失败", exc_info=True)
            return {}

        total = sum(counts.values())
        if total:
            logger.info(
                "审计日志保留期清理完成：删除 %d 行（%s；保留期 %s 天）",
                total,
                counts,
                retention_days,
            )
        else:
            logger.info("审计日志保留期清理完成：无超期数据")
        return counts


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
            # updated_at 是 UtcDateTime（落库 naive UTC）：周报的「上周」按**本地日历**
            # 解释，必须把本地日界减去时区偏移再与 UTC 列比较；直接把 date 当阈值
            # 会让 UTC+8 下上周最早 8 小时完成的待办漏计（日期字符串比较取前缀）。
            local_offset = timedelta(
                seconds=round((datetime.now() - utcnow_naive()).total_seconds())
            )
            week_start_utc = datetime.combine(week_start, time.min) - local_offset

            log_count = db.query(sa_func.count(WorkLog.id)).filter(WorkLog.log_date >= week_start).scalar() or 0
            completed_todos = (
                db.query(sa_func.count(Todo.id))
                .filter(
                    Todo.completed == True,  # noqa: E712
                    Todo.updated_at >= week_start_utc,
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

    interval_months = get_int_config("auto_package_interval_months", 1, getter=get_config)
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


def recycle_retention_job():
    """回收站保留期策略：清除超过 N 天的软删记录（每日 4:30）"""
    from app.core.database import SessionLocal
    from app.services.retention_service import purge_expired_soft_deleted

    db = SessionLocal()
    try:
        purge_expired_soft_deleted(db)
    except Exception as e:
        logger.error("回收站保留期任务失败: %s", e, exc_info=True)
    finally:
        db.close()


def export_purge_job():
    """过期导出文件回收（R5：每日 04:00）。

    异步导出的文件写入即带 24h 过期时间，下载端据此拒绝过期下载，但此前
    无任何清理逻辑——`exports/` 随使用频率单调增长，A2 原子落盘引入的
    `*.part` 在强杀场景下也可能永久残留。
    """
    from app.core.database import SessionLocal
    from app.services.async_export_service import purge_expired_exports

    db = SessionLocal()
    try:
        purge_expired_exports(db)
    except Exception as e:
        logger.error("过期导出回收任务失败: %s", e, exc_info=True)
    finally:
        db.close()

    # R18：LocalTaskQueue._tasks 只增不减——cleanup() 此前全仓无任何调用点，
    # 每个异步导出任务对象（含 func 闭包 / args / result 引用）永久驻留，
    # 长期运行下缓慢泄漏内存且 list_tasks 越来越慢。挂靠本每日任务一并回收。
    try:
        from app.services.task_queue import task_queue

        removed = task_queue.cleanup(max_age=3600)
        if removed:
            logger.info("任务队列历史记录回收: %d 条", removed)
    except Exception as e:
        logger.error("任务队列清理失败: %s", e, exc_info=True)


async def restore_drill_job():
    """月度备份恢复演练（架构评估 C1）：每日 05:45 检查到期，到期才执行演练。

    演练 = 将最新备份还原到临时目录跑 integrity_check + 核心表抽查
    （只读演练，绝不触碰生产库）。失败向管理员发消息——备份不可用
    必须可见，不能只留在日志里。
    """
    try:
        from app.services.restore_drill_service import is_drill_due, run_restore_drill

        interval_days = get_int_config("restore_drill_interval_days", 30, getter=get_config)
        if not is_drill_due(interval_days):
            logger.info("距上次恢复演练不足 %d 天，跳过", interval_days)
            return

        with get_db_context() as db:
            result = run_restore_drill(db)
            status = result.get("status")
            # 提醒必须在 with 块**内**发送：get_db_context 退出时会 close 会话，
            # 块外继续用该会话会隐式重开一条不受 finally 管理的连接（历史缺陷）。
            if status == "fail":
                try:
                    _send_backup_reminder(
                        db,
                        "恢复演练失败：备份可能不可用",
                        (
                            f"月度备份恢复演练失败（{result.get('backup_file')}，"
                            f"{result.get('error_type')}）。数据库损坏时该备份可能无法还原，"
                            "请立即检查备份目录并手动创建新备份。"
                        ),
                    )
                except Exception as msg_err:
                    logger.warning("恢复演练失败提醒发送失败: %s", msg_err)
            elif status == "ok":
                logger.info(
                    "恢复演练通过: %s（抽查 %d 张核心表）",
                    result.get("backup_file"), result.get("tables_checked", 0),
                )
            else:
                logger.info("恢复演练状态: %s", status)
    except Exception as e:
        logger.error("恢复演练任务失败: %s", e, exc_info=True)


async def subscription_dispatch_job():  # pragma: no cover — 并行会话在途(工单003)，待功能收口后补测
    """报表订阅到期分发（每 15 分钟扫描）：对到期订阅生成报表 + 站内通知。

    工单 003 方案 A：补齐订阅消费方。到期判定与生成逻辑统一在
    SubscriptionDispatchService，generate-now 端点共用同一函数。

    时间基准：必须传 **aware UTC**（``time_utils.utcnow()``）。库中订阅基准是
    naive UTC，而调度规则按本地时区解释；此前这里传本地 naive ``datetime.now()``
    直接与之比较，本机时区偏移量级的提前派发（UTC+8 即 8 小时，2026-10-02 修复）。
    """
    from app.core.database import SessionLocal
    from app.services.subscription_dispatch_service import SubscriptionDispatchService

    db = SessionLocal()
    try:
        stats = await SubscriptionDispatchService().dispatch_due_subscriptions(
            db, utcnow()
        )
        if stats["dispatched"] or stats["failed"]:
            logger.info(
                "订阅分发完成: 生成 %d / 跳过 %d / 失败 %d",
                stats["dispatched"], stats["skipped"], stats["failed"],
            )
    except Exception as e:
        logger.error("订阅分发任务失败: %s", e, exc_info=True)
    finally:
        db.close()


def _run_scheduler_job(job_fn):
    """执行单个调度任务，兼容同步与 async 函数（模块级以便测试）。

    同步函数（如 recycle_retention_job）直接调用即完成；async 函数返回协程后
    在独立事件循环中执行。2026-09-06 修复前本逻辑对同步函数调
    run_until_complete(非协程) 抛 TypeError 被 except 吞掉——同步任务实际从未执行。
    """
    import asyncio

    loop = None
    try:
        result = job_fn()
        if not asyncio.iscoroutine(result):
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(result)
    except Exception as e:
        logger.error("定时任务执行失败: %s", e)
    finally:
        # 修复：run_until_complete 抛异常时原实现不会执行 loop.close()，
        # 导致每次失败泄漏一个事件循环（IOCP/selector fd + 未回收任务）
        if loop is not None:
            loop.close()


def chunk_cleanup_job():
    """清理过期分片上传会话（R4：磁盘 chunks/ 与内存 _sessions 双回收）。"""
    from app.services.chunked_upload_service import get_chunked_upload_service

    cleaned = get_chunked_upload_service().cleanup_expired_sessions()
    if cleaned:
        logger.info("分片上传过期会话清理完成: %s 个", cleaned)


def _schedule_daily(coro_func, hour, minute, task_name):
    """每日 HH:MM 调度（R8：重排 Timer 统一登记，_stopping 后不再自我延续）。"""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    delay = (target - now).total_seconds()

    def _job():
        if _stopping.is_set():
            return
        _run_scheduler_job(coro_func)
        if _stopping.is_set():
            return
        _schedule_daily(coro_func, hour, minute, task_name)

    t = threading.Timer(delay, _job)
    t.daemon = True
    t.name = f"scheduler-{task_name}"
    _register_timer(t)
    t.start()


def _schedule_weekly(coro_func, weekday, hour, minute, task_name):
    """每周 weekday HH:MM 调度（R8：同 _schedule_daily）。"""
    now = datetime.now()
    days_ahead = weekday - now.weekday()
    if days_ahead < 0:
        days_ahead += 7
    target = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(weeks=1)
    delay = (target - now).total_seconds()

    def _job():
        if _stopping.is_set():
            return
        _run_scheduler_job(coro_func)
        if _stopping.is_set():
            return
        _schedule_weekly(coro_func, weekday, hour, minute, task_name)

    t = threading.Timer(delay, _job)
    t.daemon = True
    t.name = f"scheduler-{task_name}"
    _register_timer(t)
    t.start()


def _schedule_interval(coro_func, interval_seconds, task_name):
    """按固定间隔调度（首次延迟 interval 秒）。

    R8（2026-09-12）：递归重排的 Timer 此前从不入 _timers，stop_backup_scheduler
    的 cancel 拦不到它们 → 关闭后 interval 链仍会触发（幽灵 DB 写）。
    现统一经 _register_timer 登记并回收已终止句柄。
    """

    def _job():
        if _stopping.is_set():
            return
        _run_scheduler_job(coro_func)
        if _stopping.is_set():
            return
        t = threading.Timer(interval_seconds, _job)
        t.daemon = True
        t.name = f"scheduler-{task_name}"
        _register_timer(t)
        t.start()

    t = threading.Timer(interval_seconds, _job)
    t.daemon = True
    t.name = f"scheduler-{task_name}"
    _register_timer(t)
    t.start()


def _schedule_oneshot(coro_func, delay_seconds, task_name):
    """一次性延迟任务（**不**自我重排）。

    R36：启动补跑这类"只做一次"的动作不能走 ``_schedule_daily/interval``
    （后者会周期重排）。但仍沿用 R8 的登记约定：Timer 经 ``_register_timer``
    入表（stop 时可 cancel），触发时先看 ``_stopping``（停止后不执行）。
    """
    def _job():
        if _stopping.is_set():
            return
        _run_scheduler_job(coro_func)

    t = threading.Timer(delay_seconds, _job)
    t.daemon = True
    t.name = f"scheduler-{task_name}"
    _register_timer(t)
    t.start()


def parse_backup_schedule(schedule: str) -> tuple[int, int, Optional[int], Optional[int]]:
    """解析 UI 生成的 5 段 cron：分 时 日 月 周。

    仅支持本项目 UI 可表达的形式：日/周至少一个为 ``*``。返回
    ``(minute, hour, month_day, weekday)``，其中 weekday 为 cron 语义
    （0=周日）。非法输入抛 ``ValueError``，由调用方给 400。
    """
    parts = (schedule or "").split()
    if len(parts) != 5:
        raise ValueError("cron 必须为 5 段（分 时 日 月 周）")
    minute_s, hour_s, dom_s, month_s, dow_s = parts
    try:
        minute = int(minute_s)
        hour = int(hour_s)
    except ValueError as exc:
        raise ValueError("cron 分/时必须是数字") from exc
    if not (0 <= minute <= 59 and 0 <= hour <= 23):
        raise ValueError("cron 分/时越界")
    if month_s != "*":
        raise ValueError("备份计划暂只支持每月每天（月份字段必须为 *）")
    if dom_s != "*" and dow_s != "*":
        raise ValueError("cron 日与周只能指定一个（另一个必须为 *）")
    try:
        dom = int(dom_s) if dom_s != "*" else None
        dow = int(dow_s) if dow_s != "*" else None
    except ValueError as exc:
        raise ValueError("cron 日/周必须是数字或 *") from exc
    if dom is not None and not (1 <= dom <= 31):
        raise ValueError("cron 日越界")
    if dow is not None and not (0 <= dow <= 6):
        raise ValueError("cron 周越界（0=周日）")
    return minute, hour, dom, dow


def next_backup_run(schedule: str, now: datetime | None = None) -> datetime:
    """计算下一次备份时间（本地时区；最多向前扫描 370 天）。"""
    minute, hour, dom, dow = parse_backup_schedule(schedule)
    base = now or datetime.now()
    for offset in range(0, 371):
        day = (base + timedelta(days=offset)).date()
        if dom is not None and day.day != dom:
            continue
        if dow is not None and ((day.weekday() + 1) % 7) != dow:
            continue
        candidate = datetime.combine(day, time(hour=hour, minute=minute))
        if candidate > base:
            return candidate
    raise ValueError("cron 在一年内没有可执行时间")


def _schedule_auto_backup_cron() -> None:
    """按 SystemConfig 的 cron 重排自动备份；配置变更后立即热生效。"""
    global _backup_timer
    schedule = get_config("backup_schedule_cron", "0 2 * * *") or "0 2 * * *"
    try:
        target = next_backup_run(schedule)
    except ValueError:
        logger.warning("备份 cron 非法，回退每日 02:00: %s", schedule)
        target = next_backup_run("0 2 * * *")
    delay = max(1.0, (target - datetime.now()).total_seconds())

    def _job():
        if _stopping.is_set():
            return
        _run_scheduler_job(auto_backup_job)
        if _stopping.is_set():
            return
        _schedule_auto_backup_cron()

    with _backup_timer_lock:
        if _backup_timer is not None:
            _backup_timer.cancel()
        t = threading.Timer(delay, _job)
        t.daemon = True
        t.name = "scheduler-auto_backup"
        _register_timer(t)
        _backup_timer = t
        t.start()


def reschedule_auto_backup_job() -> None:
    """配置更新后热重排；调度器未启动时只做校验，不创建 Timer。"""
    if not _scheduler_started:
        return
    _schedule_auto_backup_cron()


def _schedule_backup_catchup(delay_seconds: int = BACKUP_CATCHUP_DELAY_SECONDS) -> None:
    """登记启动备份补跑（一次性；判定与执行见 ``_run_backup_catchup_job``）。"""
    _schedule_oneshot(_run_backup_catchup_job, delay_seconds, "backup_catchup")


def start_backup_scheduler():
    """启动后台调度器（仅轻量任务，不含自动备份和 VACUUM）

    使用 threading.Timer 实现简易定时调度，替代已移除的 APScheduler。
    """
    global _scheduler_started  # pragma: no cover - global 声明行，无执行语义
    if _scheduler_started:
        logger.info("调度器已在运行，跳过重复启动")
        return
    # 复位停止标志：允许 stop() 之后再次 start（与 _wal_thread 复位同理）
    _stopping.clear()

    _schedule_daily(kpi_precalculate_job, 0, 30, "kpi_precalculate")
    _schedule_daily(recycle_retention_job, 4, 30, "recycle_retention")
    _schedule_daily(anomaly_detection_job, 1, 0, "anomaly_detection")
    _schedule_auto_backup_cron()
    # R36（离线长期运行可靠性）：启动补跑 —— 机器每天只开机数小时/刚好错过 02:00 时，
    # 纯每日定时会让自动备份长期不执行。启动后延迟 BACKUP_CATCHUP_DELAY_SECONDS 秒
    # 判定一次：距上次备份超过 backup_interval_days（或从未备份）→ 立即补跑一次。
    # 一次性、不重排；判定口径与 auto_backup_job 完全一致，补跑后当日 02:00 正常跳过。
    _schedule_backup_catchup()
    _schedule_daily(auto_package_job, 3, 0, "auto_package")
    _schedule_daily(message_cleanup_job, 3, 30, "message_cleanup")
    # R27：过期/已吊销登录会话回收（user_sessions 只增不减）
    _schedule_daily(session_cleanup_job, 5, 15, "session_cleanup")
    # W5-T8：审计/日志大表保留期清理（audit_logs/api_access_logs/login_attempts/
    # security_events/data_export_logs/token_blacklist 六表只增不减，每请求双写）
    _schedule_daily(audit_log_cleanup_job, 4, 20, "audit_log_cleanup")
    # R5：过期导出文件 + 残留 .part 回收（此前 expires_at 只用于拒绝下载，无回收）
    _schedule_daily(export_purge_job, 4, 0, "export_purge")
    _schedule_daily(restore_drill_job, 5, 45, "restore_drill")
    _schedule_interval(reminder_scan_job, 6 * 3600, "reminder_scan")
    _schedule_daily(todo_reminder_job, 8, 0, "todo_reminder")
    _schedule_weekly(weekly_report_job, 0, 6, 30, "weekly_report")
    _schedule_interval(subscription_dispatch_job, 900, "subscription_dispatch")
    # R4：分片上传过期会话清理（此前 cleanup_expired_sessions 无任何生产调用点，
    # 放弃的会话在 uploads/chunks/ 与内存 _sessions 中永久泄漏）
    _schedule_interval(chunk_cleanup_job, 1800, "chunk_cleanup")
    # W18 P1-6：数据包导出文件保留期清理（此前 data-packages 目录只增不减，
    # 长期运行撑满磁盘 → 备份/导入失败）
    _schedule_daily(data_package_cleanup_job, 4, 10, "data_package_cleanup")

    _scheduler_started = True
    logger.info(
        "调度器已启动（KPI预计算 + 异常检测 + 自动备份 + 启动补跑 + 自动打包 + 消息清理"
        " + 过期导出回收 + 恢复演练 + 提醒扫描 + 待办提醒 + 周报 + 订阅分发"
        " + 分片清理 + 数据包清理 + 审计日志清理）"
    )


def stop_backup_scheduler():
    """停止备份调度器"""
    global _scheduler_started, _backup_timer
    # 先置停止标志再 cancel：拦住「正在执行、即将重排下一次」的 _job
    _stopping.set()
    for t in _timers:
        t.cancel()
    _timers.clear()
    with _backup_timer_lock:
        _backup_timer = None
    _scheduler_started = False
    logger.info("调度器已停止")
