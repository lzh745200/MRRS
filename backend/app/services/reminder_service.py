"""
审批超时提醒服务

使用后台线程定期检查超时审批，生成提醒消息。
单机版替代Celery的方案——使用diskcache或内置threading。

在 main.py lifespan 中调用:
    reminder = start_approval_reminder(check_interval_minutes=30)
    # shutdown时:
    stop_approval_reminder(reminder)
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CHECK_INTERVAL_MINUTES = 30
DEFAULT_DEADLINE_HOURS = 48
DEFAULT_WARNING_HOURS = 36  # 提前12小时警告


class ApprovalReminderService:
    """审批超时提醒服务 —— 后台线程定期扫描超时审批"""

    def __init__(self, check_interval_minutes: int = DEFAULT_CHECK_INTERVAL_MINUTES):
        self._check_interval = check_interval_minutes * 60  # 转换为秒
        self._deadline_hours = DEFAULT_DEADLINE_HOURS
        self._warning_hours = DEFAULT_WARNING_HOURS
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    def start(self):
        """启动后台提醒线程"""
        if self._running:
            logger.warning("审批提醒服务已在运行中")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._scan_loop,
            daemon=True,
            name="approval-reminder",
        )
        self._thread.start()
        self._running = True
        logger.info(f"审批提醒服务已启动，检查间隔: {self._check_interval // 60}分钟")

    def stop(self):
        """停止后台提醒线程"""
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)
        self._running = False
        logger.info("审批提醒服务已停止")

    def _scan_loop(self):  # pragma: no cover
        """后台扫描循环"""
        # 首次启动等待30秒，确保数据库已初始化（stop 时立即唤醒）
        if self._stop_event.wait(30):
            return

        while not self._stop_event.is_set():
            try:
                self._check_overdue_approvals()
            except Exception as e:
                logger.error(f"审批超时检查失败: {e}", exc_info=True)

            try:
                self._check_deadline_reminders()
            except Exception as e:
                logger.error(f"截止日提醒检查失败: {e}", exc_info=True)

            # 等待下一次检查（响应停止信号）
            self._stop_event.wait(self._check_interval)

    def _check_overdue_approvals(self):  # pragma: no cover
        """检查超时和即将超时的审批"""
        from app.core.database import SessionLocal
        from app.models.approval import ApprovalTask, ApprovalStatus

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            deadline = now - timedelta(hours=self._deadline_hours)
            warning_time = now - timedelta(hours=self._warning_hours)

            # 查询超过48小时未处理的审批（status 在 ApprovalTask 上）
            overdue = (
                db.query(ApprovalTask)
                .filter(
                    ApprovalTask.status == ApprovalStatus.PENDING.value,
                    ApprovalTask.created_at <= deadline,
                )
                .all()
            )

            # 查询超过36小时未处理的审批（预警）
            approaching = (
                db.query(ApprovalTask)
                .filter(
                    ApprovalTask.status == ApprovalStatus.PENDING.value,
                    ApprovalTask.created_at <= warning_time,
                    ApprovalTask.created_at > deadline,
                )
                .all()
            )

            # 为超时审批创建提醒消息
            for task in overdue:
                self._create_reminder_message(db, task, "overdue")

            # 为即将超时审批创建预警消息
            for task in approaching:
                self._create_reminder_message(db, task, "approaching")

            if overdue or approaching:
                logger.info(
                    f"审批提醒扫描完成: {len(overdue)}条超时, {len(approaching)}条预警"
                )
                safe_commit(db)

        finally:
            db.close()

    def _create_reminder_message(self, db, approval_task, level: str):  # pragma: no cover
        """创建提醒消息（幂等——同一审批任务+同一提醒级别不重复创建）"""
        from app.models.message import Message

        # 检查是否已发送过同类提醒（通过 link 字段标识关联实体）
        ref_link = f"/approval/tasks/{approval_task.id}"
        existing = (
            db.query(Message)
            .filter(
                Message.link == ref_link,
                Message.message_type == f"approval_{level}",
            )
            .first()
        )
        if existing:
            return

        if level == "overdue":
            title = f"审批超时提醒 - #{approval_task.id}"
            content = f"审批任务 #{approval_task.id}（{approval_task.title or '无标题'}）已超过48小时未处理，请尽快审批。"
        else:
            title = f"审批预警提醒 - #{approval_task.id}"
            content = f"审批任务 #{approval_task.id}（{approval_task.title or '无标题'}）已超过36小时未处理，请及时审批以免超时。"

        message = Message(
            user_id=approval_task.current_approver_id,
            title=title,
            content=content,
            message_type=f"approval_{level}",
            link=ref_link,
            is_read=False,
        )
        db.add(message)
        logger.info(f"审批提醒已创建: {title}")

    def _check_deadline_reminders(self):  # pragma: no cover
        """检查项目/里程碑/待办截止日，生成到期提醒"""
        from app.core.database import SessionLocal
        from app.models.message import Message
        from app.models.project import Project
        from app.models.todo import Todo

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            three_days_later = now + timedelta(days=3)
            created_count = 0

            # 项目截止日提醒（3天内到期或已逾期）
            if hasattr(Project, "end_date"):
                overdue_projects = (
                    db.query(Project)
                    .filter(
                        Project.is_active == True,  # noqa: E712
                        Project.status.notin_(["completed", "cancelled"]),
                        Project.end_date != None,  # noqa: E711
                        Project.end_date <= three_days_later,
                    )
                    .limit(20)
                    .all()
                )
                for proj in overdue_projects:
                    ref_link = f"/projects/{proj.id}"
                    existing = db.query(Message).filter(
                        Message.link == ref_link,
                        Message.message_type == "project_deadline",
                    ).first()
                    if not existing:
                        is_overdue = proj.end_date < now.date() if hasattr(proj.end_date, 'year') else False
                        title = f"项目{'已逾期' if is_overdue else '即将到期'} - {proj.name or proj.id}"
                        status_text = '已逾期请尽快处理' if is_overdue else '即将到期请注意'
                        content = f"项目「{proj.name or ''}」截止日期为 {proj.end_date}，{status_text}。"
                        db.add(Message(
                            user_id=proj.created_by,
                            title=title,
                            content=content,
                            message_type="project_deadline",
                            link=ref_link,
                            is_read=False,
                        ))
                        created_count += 1

            # 待办截止日提醒（已逾期）
            if hasattr(Todo, "deadline"):
                overdue_todos = (
                    db.query(Todo)
                    .filter(
                        Todo.completed == False,  # noqa: E712
                        Todo.deadline != None,  # noqa: E711
                        Todo.deadline < now.date(),
                    )
                    .limit(20)
                    .all()
                )
                for todo in overdue_todos:
                    ref_link = f"/todos/{todo.id}"
                    existing = db.query(Message).filter(
                        Message.link == ref_link,
                        Message.message_type == "todo_overdue",
                    ).first()
                    if not existing:
                        db.add(Message(
                            user_id=todo.user_id,
                            title=f"待办已逾期 - {todo.title or todo.id}",
                            content=f"待办「{todo.title or ''}」截止日期为 {todo.deadline}，已逾期请尽快完成。",
                            message_type="todo_overdue",
                            link=ref_link,
                            is_read=False,
                        ))
                        created_count += 1

            if created_count > 0:
                safe_commit(db)
                logger.info(f"截止日提醒扫描完成: 创建{created_count}条提醒")

        finally:
            db.close()


# ══════════════════════════════════════════════════════════════
#  全局实例管理
# ══════════════════════════════════════════════════════════════

_reminder_service: Optional[ApprovalReminderService] = None


def start_approval_reminder(  # pragma: no cover
    check_interval_minutes: int = DEFAULT_CHECK_INTERVAL_MINUTES,
) -> ApprovalReminderService:
    """启动审批提醒服务（在main.py lifespan中调用）"""
    global _reminder_service
    if _reminder_service is not None:
        logger.warning("审批提醒服务全局实例已存在，返回现有实例")
        return _reminder_service
    _reminder_service = ApprovalReminderService(check_interval_minutes)
    _reminder_service.start()
    return _reminder_service


def stop_approval_reminder(service: Optional[ApprovalReminderService] = None):  # pragma: no cover
    """停止审批提醒服务（在main.py lifespan shutdown中调用）"""
    global _reminder_service
    target = service or _reminder_service
    if target:
        target.stop()
        if target is _reminder_service:
            _reminder_service = None
