"""
集中式审计事件处理 — 通过 SQLAlchemy 事件自动记录所有写操作。

替代逐个端点手动调用 write_work_log() 的方案——一个事件监听器覆盖全部模型。
使用方法：应用启动时调用 setup_audit_events() 一次即可。

用户归因：通过 contextvars.ContextVar（app.middleware.audit_context）传递当前
操作人 user_id。认证中间件层（app.core.security.get_current_user）在解析出用户
后写入 ContextVar，本模块在事件触发时读取并填入 work_logs.user_id。
对于无 HTTP 上下文的异步/后台任务（ContextVar 为空），记为 "system" 归因到
应用日志（work_logs.user_id 为 NOT NULL 外键，无法存字符串，故系统级操作落日志
而非 work_logs 表，避免 IntegrityError）。
"""

import logging

from sqlalchemy import event

logger = logging.getLogger(__name__)


def _resolve_actor_id():
    """从审计上下文（ContextVar）解析当前操作人 user_id。

    Returns:
        (user_id, is_system): user_id 为 int 或 None；is_system 标识是否为系统操作。
    """
    try:
        from app.middleware.audit_context import get_current_user as _get_ctx_user_id

        ctx_user_id = _get_ctx_user_id()
    except Exception:
        ctx_user_id = None

    if ctx_user_id is not None:
        return ctx_user_id, False
    # ContextVar 为空 → 系统/后台任务操作
    return None, True


def _get_entity_name(instance) -> str:
    """从 ORM 实例提取可读名称。"""
    for attr in ("name", "title", "village_name", "project_name", "username", "full_name"):
        val = getattr(instance, attr, None)
        if val and isinstance(val, str):
            return str(val)
    return f"{type(instance).__name__}#{getattr(instance, 'id', '?')}"


def _get_entity_type(instance) -> str:
    """从 ORM 实例提取实体类型标识。"""
    cls_name = type(instance).__name__
    mapping = {
        "SupportedVillage": "village",
        "FundBudget": "fund_budget",
        "FundTransferVoucher": "voucher",
        "FundAllocationOrder": "allocation",
        "FundContract": "contract",
        "FundAnomaly": "anomaly",
        "ScholarshipStudent": "scholarship",
        "SchoolProject": "school_project",
        "ApprovalTask": "approval",
        "ApprovalWorkflow": "approval_workflow",
        "RbacRole": "role",
        "UserPermission": "permission",
        "UserRole": "user_role",
        "Organization": "org",
        "RuralTask": "rural_task",
        "Message": "message",
        "Feedback": "feedback",
        "MachineCode": "machine_code",
        "EffectivenessEvaluation": "effectiveness",
        "FundTransaction": "fund_transaction",
        "Todo": "todo",
        "PolicyCategory": "policy_category",
        "Policy": "policy",
        "Project": "project",
        "School": "school",
        "User": "user",
    }
    return mapping.get(cls_name, cls_name.lower())


def _write_audit_from_event(mapper, connection, target, action: str):
    """从 SQLAlchemy 事件写入审计日志。"""
    try:
        from datetime import date

        entity_type = _get_entity_type(target)
        entity_name = _get_entity_name(target)
        content = f"{action}: {entity_name}"

        user_id, is_system = _resolve_actor_id()

        # 系统/后台任务操作：work_logs.user_id 为 NOT NULL 外键，无法存 "system"
        # 字符串。改为落应用日志保留审计轨迹，跳过 work_logs 写入，避免 IntegrityError。
        if is_system:
            logger.info(
                "审计(系统): action=%s entity=%s#%s name=%s",
                action,
                entity_type,
                getattr(target, "id", "?"),
                entity_name,
            )
            return

        connection.execute(
            mapper.local_table.metadata.tables["work_logs"].insert().values(
                category=entity_type,
                content=content,
                log_date=date.today(),
                user_id=user_id,  # 来自 ContextVar 的操作人 ID（审计归因）
            )
        )
    except Exception:
        # 审计轨迹丢失属军事合规风险，必须可观测（升级为 warning）
        logger.warning("审计日志写入失败 (non-critical): %s %s", action, type(target).__name__, exc_info=True)


def _after_insert(mapper, connection, target):
    _write_audit_from_event(mapper, connection, target, "create")


def _after_update(mapper, connection, target):
    _write_audit_from_event(mapper, connection, target, "update")


def _after_delete(mapper, connection, target):
    _write_audit_from_event(mapper, connection, target, "delete")


def setup_audit_events(models: list = None):
    """注册 SQLAlchemy 审计事件监听器——应用启动时调用一次。"""
    if models is None:
        from app.models.fund import Fund
        from app.models.fund_allocation_order import FundAllocationOrder
        from app.models.fund_budget import FundBudget, FundTransaction
        from app.models.fund_lifecycle import FundTransferVoucher, FundContract, FundAnomaly
        from app.models.issue_tracking import Feedback
        from app.models.machine_code import MachineCode
        from app.models.message import Message
        from app.models.organization import Organization
        from app.models.policy import Policy, PolicyCategory
        from app.models.project import Project
        from app.models.rbac import RbacRole, UserPermission, UserRole
        from app.models.rural_task import RuralTask
        from app.models.school import ScholarshipStudent, School, SchoolProject
        from app.models.supported_village import SupportedVillage
        from app.models.todo import Todo
        from app.models.user import User
        from app.models.approval import ApprovalTask, ApprovalWorkflow

        models = [
            Fund, FundAllocationOrder, FundBudget, FundTransaction,
            FundTransferVoucher, FundContract, FundAnomaly,
            Feedback,
            MachineCode,
            Message,
            Organization, Policy, PolicyCategory, Project,
            RbacRole, UserPermission, UserRole,
            RuralTask,
            ScholarshipStudent, School, SchoolProject,
            SupportedVillage, Todo, User,
            ApprovalTask, ApprovalWorkflow,
        ]

    registered = 0
    for model in models:
        event.listen(model, "after_insert", _after_insert)
        event.listen(model, "after_update", _after_update)
        event.listen(model, "after_delete", _after_delete)
        registered += 1

    logger.info("审计事件监听已启用——%d 个模型", registered)
    return registered


def teardown_audit_events(models: list = None):
    """移除审计事件监听（测试环境使用）。"""
    if models is None:
        from app.models.fund import Fund
        from app.models.fund_budget import FundBudget, FundTransaction
        from app.models.fund_lifecycle import FundTransferVoucher, FundContract, FundAnomaly
        from app.models.fund_allocation_order import FundAllocationOrder
        from app.models.issue_tracking import Feedback
        from app.models.machine_code import MachineCode
        from app.models.message import Message
        from app.models.organization import Organization
        from app.models.policy import Policy, PolicyCategory
        from app.models.project import Project
        from app.models.rbac import RbacRole, UserPermission, UserRole
        from app.models.rural_task import RuralTask
        from app.models.school import ScholarshipStudent, School, SchoolProject
        from app.models.supported_village import SupportedVillage
        from app.models.todo import Todo
        from app.models.user import User
        from app.models.approval import ApprovalTask, ApprovalWorkflow

        models = [Fund, FundAllocationOrder, FundBudget, FundTransaction,
                  FundTransferVoucher, FundContract, FundAnomaly,
                  Feedback, MachineCode, Message,
                  Organization, Policy, PolicyCategory, Project,
                  RbacRole, RuralTask, ScholarshipStudent,
                  School, SchoolProject, SupportedVillage, Todo, User,
                  UserPermission, UserRole, ApprovalTask, ApprovalWorkflow]

    for model in models:
        event.remove(model, "after_insert", _after_insert)
        event.remove(model, "after_update", _after_update)
        event.remove(model, "after_delete", _after_delete)
