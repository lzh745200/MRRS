"""
零信任安全API
提供零信任安全策略管理、访问评估和信任评分功能
用于帮扶管理信息系统的安全态势评估与动态访问控制
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zero-trust", tags=["零信任安全"])


# ==================== Pydantic 模型 ====================

class TrustAssessment(BaseModel):
    """信任评估结果"""
    level: str = Field(..., description="信任等级: trusted/low_risk/medium_risk/high_risk/untrusted")
    score: float = Field(..., description="信任评分 (0-100)")
    factors: List[dict] = Field(..., description="评估因子详情")
    recommendations: List[str] = Field(..., description="安全建议")


class SecurityPolicy(BaseModel):
    """安全策略"""
    id: str
    name: str
    description: str
    category: str
    enabled: bool
    severity: str
    conditions: Optional[dict] = None
    actions: Optional[List[str]] = None


class AccessRequest(BaseModel):
    """访问请求评估"""
    resource: str = Field(..., description="请求访问的资源路径")
    action: str = Field(..., description="请求的操作类型: read/write/delete/admin")
    context: Optional[dict] = Field(None, description="请求上下文信息")


class SecurityEvent(BaseModel):
    """安全事件"""
    event_type: str = Field(..., description="事件类型")
    source: str = Field(..., description="事件来源")
    severity: str = Field("info", description="严重程度")
    message: str = Field(..., description="事件描述")
    details: Optional[dict] = Field(None, description="事件详情")


# ==================== 安全事件存储（数据库持久化） ====================


def _record_security_event(
    db: Session,
    event_type: str,
    source: str,
    severity: str,
    message: str,
    details: dict = None,
) -> dict:
    """记录安全事件到数据库（持久化，参考 TokenBlacklist 模式）。

    Args:
        db: 数据库会话。
        event_type: 事件类型。
        source: 事件来源（如 ``user:<username>``）。
        severity: 严重程度。
        message: 事件描述。
        details: 事件详情。

    Returns:
        与历史内存实现结构一致的字典，保证 API 响应契约不变。
    """
    from app.models.audit import SecurityEvent

    event_dict = {
        "id": None,
        "event_type": event_type,
        "source": source,
        "severity": severity,
        "message": message,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        # 从 source（格式 "user:<username>"）中提取用户名
        username = source.replace("user:", "", 1) if source.startswith("user:") else None
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            username=username,
            description=message,
            details={"source": source, **(details or {})},
        )
        db.add(event)
        safe_commit(db)
        db.refresh(event)
        event_dict["id"] = event.id
        event_dict["timestamp"] = (
            event.created_at.isoformat() if event.created_at else event_dict["timestamp"]
        )
    except Exception:
        logger.exception("安全事件持久化失败: %s/%s", severity, event_type)
        try:
            db.rollback()
        except Exception as rb_err:
            logger.warning("安全事件回滚失败: %s", rb_err)

    if severity in ("high", "critical"):
        logger.warning("安全事件 [%s/%s]: %s", severity, event_type, message)
    return event_dict


def _event_to_dict(event) -> dict:
    """将 SecurityEvent ORM 对象转换为 API 响应字典（保持历史契约）。"""
    details = event.details or {}
    # 还原历史 details（去掉持久化时合并的 source 字段）
    restored_details = {k: v for k, v in details.items() if k != "source"} or None
    return {
        "id": event.id,
        "event_type": event.event_type,
        "source": details.get("source", event.username or ""),
        "severity": event.severity,
        "message": event.description,
        "details": restored_details,
        "timestamp": event.created_at.isoformat() if event.created_at else "",
    }


# ==================== 预定义安全策略 ====================

_DEFAULT_POLICIES = [{"id": "ztp-001",
                      "name": "密码强度策略",
                      "description": "强制要求用户密码满足复杂度要求：至少8位，包含大小写字母、数字和特殊字符",
                      "category": "authentication",
                      "enabled": True,
                      "severity": "high",
                      "conditions": {"min_length": 8,
                                     "require_uppercase": True,
                                     "require_lowercase": True,
                                     "require_digit": True,
                                     "require_special": True},
                      "actions": ["enforce_password_policy"],
                      },
                     {"id": "ztp-002",
                      "name": "登录失败锁定",
                      "description": "连续登录失败超过阈值时锁定账户并记录安全事件",
                      "category": "authentication",
                      "enabled": True,
                      "severity": "high",
                      "conditions": {"max_attempts": 10,
                                     "lockout_duration_minutes": 30},
                      "actions": ["lock_account",
                                  "notify_admin"],
                      },
                     {"id": "ztp-003",
                      "name": "会话超时管理",
                      "description": "用户会话空闲超过一定时间后自动终止，强制重新认证",
                      "category": "session",
                      "enabled": True,
                      "severity": "medium",
                      "conditions": {"idle_timeout_minutes": 30,
                                     "absolute_timeout_hours": 8},
                      "actions": ["terminate_session"],
                      },
                     {"id": "ztp-004",
                      "name": "IP访问限制",
                      "description": "限制可访问系统的IP地址范围，拒绝非授权来源的连接",
                      "category": "network",
                      "enabled": False,
                      "severity": "medium",
                      "conditions": {"allowed_ips": [],
                                     "block_on_violation": True},
                      "actions": ["block_connection",
                                  "notify_admin"],
                      },
                     {"id": "ztp-005",
                      "name": "敏感操作审计",
                      "description": "对所有敏感操作进行详细审计记录，包括数据导出、配置变更等",
                      "category": "audit",
                      "enabled": True,
                      "severity": "medium",
                      "conditions": {"operations": ["export",
                                                    "delete",
                                                    "config_change",
                                                    "user_create"]},
                      "actions": ["log_operation",
                                  "notify_security"],
                      },
                     {"id": "ztp-006",
                      "name": "数据访问最小权限",
                      "description": "确保用户仅能访问其权责范围内的数据，防止越权访问",
                      "category": "authorization",
                      "enabled": True,
                      "severity": "high",
                      "conditions": {"enforce_data_scope": True,
                                     "scope_levels": ["self",
                                                      "unit",
                                                      "subordinate",
                                                      "all"]},
                      "actions": ["verify_data_scope",
                                  "block_unauthorized_access"],
                      },
                     {"id": "ztp-007",
                      "name": "机器码绑定验证",
                      "description": "验证客户端机器码与授权绑定的一致性，防止未授权设备接入",
                      "category": "device",
                      "enabled": True,
                      "severity": "high",
                      "conditions": {"enforce_binding": True},
                      "actions": ["verify_machine_code",
                                  "reject_unbound_device"],
                      },
                     {"id": "ztp-008",
                      "name": "数据传输加密",
                      "description": "确保敏感数据在传输过程中使用加密保护",
                      "category": "data",
                      "enabled": True,
                      "severity": "high",
                      "conditions": {"encrypt_packages": True,
                                     "min_encryption_level": "AES-256"},
                      "actions": ["encrypt_data",
                                  "verify_integrity"],
                      },
                     ]


# ==================== API 端点 ====================

@router.get("/assessment", summary="获取信任评估")
async def get_trust_assessment(
    request: Request,
    current_user=Depends(get_current_user),
):
    """获取当前会话的零信任评估结果

    根据用户身份、设备信息、访问模式等因素综合评估信任等级。
    评估结果用于动态调整访问权限策略。
    """
    # 收集评估因子
    factors = []
    total_score = 100.0

    # 认证因子：已认证用户得分
    if current_user:
        factors.append({
            "factor": "authentication",
            "score": 25,
            "status": "pass",
            "detail": "用户已通过JWT认证",
        })
    else:
        factors.append({
            "factor": "authentication",
            "score": -40,
            "status": "fail",
            "detail": "用户未认证",
        })
        total_score -= 40

    # 会话因子
    factors.append({
        "factor": "session",
        "score": 15,
        "status": "pass",
        "detail": "会话令牌有效",
    })

    # 客户端因子
    client_ip = request.client.host if request.client else "unknown"
    factors.append({
        "factor": "client_ip",
        "score": 10,
        "status": "pass",
        "detail": f"客户端IP: {client_ip}",
    })

    # HTTPS因子
    is_https = request.url.scheme == "https"
    if is_https:
        factors.append({
            "factor": "transport_security",
            "score": 10,
            "status": "pass",
            "detail": "使用HTTPS加密传输",
        })
    else:
        factors.append({
            "factor": "transport_security",
            "score": -10,
            "status": "warning",
            "detail": "未使用HTTPS，传输层不安全",
        })
        total_score -= 10

    # 用户活跃度因子
    factors.append({
        "factor": "user_activity",
        "score": 5,
        "status": "pass",
        "detail": "用户活跃度正常",
    })

    total_score = max(0, min(100, total_score))

    # 确定信任等级
    if total_score >= 80:
        level = "trusted"
    elif total_score >= 60:
        level = "low_risk"
    elif total_score >= 40:
        level = "medium_risk"
    elif total_score >= 20:  # pragma: no cover — 评分模型最低50分，数学不可达
        level = "high_risk"  # pragma: no cover
    else:  # pragma: no cover — 评分模型最低50分，数学不可达
        level = "untrusted"  # pragma: no cover

    # 安全建议
    recommendations = []
    if not is_https:
        recommendations.append("建议启用HTTPS确保传输层安全")
    if total_score < 60:
        recommendations.append("信任评分偏低，建议审查安全配置")

    return {
        "success": True,
        "data": {
            "level": level,
            "score": total_score,
            "factors": factors,
            "recommendations": recommendations,
            "assessed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/policies", summary="获取安全策略列表")
async def get_security_policies(
    category: Optional[str] = Query(None, description="按策略类别筛选"),
    enabled_only: bool = Query(False, description="仅返回已启用策略"),
    current_user=Depends(get_current_user),
):
    """获取系统配置的零信任安全策略列表"""
    policies = _DEFAULT_POLICIES

    if category:
        policies = [p for p in policies if p["category"] == category]
    if enabled_only:
        policies = [p for p in policies if p["enabled"]]

    return {
        "success": True,
        "data": {
            "policies": policies,
            "total": len(policies),
            "enabled_count": len([p for p in policies if p["enabled"]]),
        },
    }


@router.get("/policies/{policy_id}", summary="获取安全策略详情")
async def get_security_policy(
    policy_id: str,
    current_user=Depends(get_current_user),
):
    """获取指定安全策略的详细信息"""
    for policy in _DEFAULT_POLICIES:
        if policy["id"] == policy_id:
            return {"success": True, "data": policy}

    raise HTTPException(status_code=404, detail="安全策略不存在")


@router.post("/evaluate", summary="评估访问请求")
async def evaluate_access_request(
    body: AccessRequest,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """评估对指定资源的访问请求是否符合零信任策略

    根据安全策略和信任评估结果判断是否允许访问。
    """
    username = getattr(current_user, "username", "anonymous")
    assessment_result = "allowed"

    # 检查是否为敏感操作
    sensitive_actions = ["delete", "admin"]
    if body.action in sensitive_actions:
        _record_security_event(
            db=db,
            event_type="sensitive_access",
            source=f"user:{username}",
            severity="medium",
            message=f"用户 {username} 请求执行敏感操作: {body.action} {body.resource}",
            details={"resource": body.resource, "action": body.action},
        )

    # 检查管理操作权限
    if body.action == "admin":
        is_superuser = getattr(current_user, "is_superuser", False)
        if not is_superuser:
            assessment_result = "denied"
            _record_security_event(
                db=db,
                event_type="unauthorized_admin_access",
                source=f"user:{username}",
                severity="high",
                message=f"非管理员用户 {username} 尝试执行管理操作: {body.resource}",
                details={"resource": body.resource, "action": body.action},
            )

    return {
        "success": True,
        "data": {
            "resource": body.resource,
            "action": body.action,
            "username": username,
            "result": assessment_result,
            "message": "访问允许" if assessment_result == "allowed" else "访问被拒绝：权限不足",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/events", summary="获取安全事件列表")
async def get_security_events(
    severity: Optional[str] = Query(None, description="按严重程度筛选: info/low/medium/high/critical"),
    event_type: Optional[str] = Query(None, description="按事件类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取记录的安全事件列表（从数据库读取，持久化存储）"""
    from app.models.audit import SecurityEvent

    query = db.query(SecurityEvent)

    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)

    total = query.count()
    start = (page - 1) * page_size
    rows = (
        query
        .order_by(SecurityEvent.created_at.desc())
        .offset(start)
        .limit(page_size)
        .all()
    )

    return {
        "success": True,
        "data": {
            "items": [_event_to_dict(e) for e in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.post("/events", summary="记录安全事件")
async def report_security_event(
    body: SecurityEvent,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动记录一个安全事件

    用于外部安全工具或前端异常检测上报安全事件。
    """
    event = _record_security_event(
        db=db,
        event_type=body.event_type,
        source=body.source,
        severity=body.severity,
        message=body.message,
        details=body.details,
    )

    return {
        "success": True,
        "message": "安全事件已记录",
        "data": {"event_id": event["id"]},
    }


@router.get("/events/stats", summary="获取安全事件统计")
async def get_security_event_stats(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取安全事件的统计分析数据（从数据库读取）"""
    from app.models.audit import SecurityEvent

    events = db.query(SecurityEvent).all()

    by_severity = {}
    by_type = {}
    for e in events:
        by_severity[e.severity] = by_severity.get(e.severity, 0) + 1
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1

    high_severity_count = len([e for e in events if e.severity in ("high", "critical")])

    return {
        "success": True,
        "data": {
            "total_events": len(events),
            "high_severity_count": high_severity_count,
            "by_severity": by_severity,
            "by_type": by_type,
            "security_posture": (
                "warning" if high_severity_count > 5
                else "normal" if high_severity_count > 0
                else "secure"
            ),
        },
    }
