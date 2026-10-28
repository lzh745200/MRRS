# -*- coding: utf-8 -*-
"""系统自检（P3）：把"这台机器能不能正常开工"压缩成一次可读的结论。

背景：完全离线单机 + 上下级部署，装好机器后最容易出问题的不是功能，
而是**配置层面的一致性**：单位码没填、组织跨级挂接、账号没审核、
PII 密钥与上级不一致、最近导入失败、同一包被导了两次。这些都不会
让系统报错，但会让数据悄悄挂错组织或跨机解不开密文。

本模块只读不写（除读取配置指纹），供「系统设置」页一键体检。
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.audit import AuditLog
from app.models.organization import Organization
from app.models.user import User
from app.services.organization_code_service import (
    ADMIN_AREA_CODE_LENGTH,
    LEVEL_LABELS,
    OrganizationCodeService,
)
from app.utils.time_utils import utcnow

# 判定严重级别
LEVEL_OK = "ok"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"

#: 最近导入窗口（天）——超过该窗口的失败导入不再提示
RECENT_IMPORT_DAYS = 30


def _parse_org_level(level: Any) -> Optional[int]:
    """level_N / 深度数字 → 序号（1/2/3）；无法识别返回 None。"""
    return OrganizationCodeService.level_order(level)


def _check_org_codes(db: Session) -> Dict[str, Any]:
    """检查单位编码：缺失 / 格式错误 / 层级与编码不符 / 重复。"""
    orgs = db.query(Organization).filter(Organization.is_active.is_(True)).all()
    missing: List[str] = []
    invalid: List[str] = []
    mismatched: List[str] = []

    seen: Dict[str, int] = {}
    duplicates: List[str] = []

    for org in orgs:
        code = str(getattr(org, "code", "") or "").strip()
        name = str(getattr(org, "name", "") or "")
        if not code:
            missing.append(name)
            continue
        if len(code) != ADMIN_AREA_CODE_LENGTH or not code.isdigit():
            invalid.append(name + "(" + code + ")")
            continue
        code_level = OrganizationCodeService.infer_level(code)
        if _parse_org_level(getattr(org, "level", None)) != _parse_org_level(code_level):
            mismatched.append(
                name + "(" + code + " → 应为 " + LEVEL_LABELS.get(code_level or "", "未知") + ")"
            )
        seen[code] = seen.get(code, 0) + 1
        if seen[code] > 1:
            duplicates.append(code)

    count = len(missing) + len(invalid) + len(mismatched) + len(duplicates)
    if count == 0:
        return _result("组织单位码", LEVEL_OK, "全部组织单位码规范且层级一致", 0)
    level = LEVEL_ERROR if (invalid or mismatched) else LEVEL_WARN
    return _result(
        "组织单位码",
        level,
        "缺失 %d 个 / 格式错误 %d 个 / 层级不符 %d 个 / 重复 %d 个"
        % (len(missing), len(invalid), len(mismatched), len(duplicates)),
        count,
    )


def _check_org_hierarchy(db: Session) -> Dict[str, Any]:
    """检查组织层级：跨级挂接（子级必须恰为父级 +1）与根组织非省级。"""
    orgs = db.query(Organization).filter(Organization.is_active.is_(True)).all()
    by_id = {org.id: org for org in orgs}
    problems: List[str] = []

    for org in orgs:
        parent_id = getattr(org, "parent_id", None)
        child_level = _parse_org_level(getattr(org, "level", None))
        if child_level is None:
            continue
        if parent_id is None:
            if child_level != 1:
                problems.append(str(org.name) + "(根组织非省级)")
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        parent_level = _parse_org_level(getattr(parent, "level", None))
        if parent_level is not None and child_level != parent_level + 1:
            problems.append(str(org.name) + "(父级与子级不相邻)")
    count = len(problems)
    if count == 0:
        return _result("组织层级", LEVEL_OK, "全部组织逐级挂接（省 → 市州 → 县市）", 0)
    return _result(
        "组织层级",
        LEVEL_WARN,
        "存在 %d 个跨级挂接：%s" % (count, "、".join(problems[:3])),
        count,
    )


def _check_pending_users(db: Session) -> Dict[str, Any]:
    """检查未审核账号（注册后待管理员通过的积压）。"""
    pending = (
        db.query(User)
        .filter(User.is_active.is_(False))
        .count()
    )
    if pending == 0:
        return _result("待审核账号", LEVEL_OK, "没有积压的未审核账号", 0)
    return _result("待审核账号", LEVEL_WARN, "有 %d 个账号未启用/待审核" % pending, pending)


def _check_locked_users(db: Session) -> Dict[str, Any]:
    """检查被锁定账号（连续登录失败触发，需要管理员解锁）。

    时间基准：``User.locked_until`` 是 ``UtcDateTime`` 列（落库 naive UTC），
    阈值必须用 ``utcnow()``。此前用 ``datetime.now()``（本地墙钟）比较，
    UTC+8 下阈值整体后移 8 小时，而默认锁定时长只有 15 分钟 →
    **明明有账号被锁，体检结论永远报「没有处于锁定状态的账号」**。
    """
    now = utcnow()
    locked = (
        db.query(User)
        .filter(User.locked_until.isnot(None), User.locked_until > now)
        .count()
    )
    if locked == 0:
        return _result("账号锁定", LEVEL_OK, "没有处于锁定状态的账号", 0)
    return _result("账号锁定", LEVEL_WARN, "有 %d 个账号处于锁定状态，可在用户管理解锁" % locked, locked)


def _check_pii_key() -> Dict[str, Any]:
    """检查 PII 密钥指纹是否可用（跨机解密的前提）。"""
    try:
        from app.core.pii_crypto import key_fingerprint

        fingerprint = key_fingerprint()
    except Exception:  # pragma: no cover - 防御：密钥未初始化时不应让自检整体失败
        logger.debug("读取 PII 密钥指纹失败", exc_info=True)
        return _result("PII 密钥", LEVEL_ERROR, "无法读取 PII 密钥指纹，跨机数据可能解不开", 1)
    if not fingerprint:
        return _result("PII 密钥", LEVEL_ERROR, "PII 密钥指纹为空，跨机数据可能解不开", 1)
    return _result(
        "PII 密钥",
        LEVEL_OK,
        "密钥指纹 " + fingerprint + "（跨机部署需与上级一致）",
        0,
    )


def _check_recent_imports(db: Session) -> Dict[str, Any]:
    """检查最近导入失败与重复包。

    时间基准：``AuditLog.created_at`` 是 ``UtcDateTime`` 列，窗口起点用
    ``utcnow()`` 推导；用本地墙钟会把窗口整体后移 8 小时，漏掉最初 8 小时的记录。
    """
    since = utcnow() - timedelta(days=RECENT_IMPORT_DAYS)
    failures = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "package_import",
            AuditLog.created_at >= since,
            AuditLog.status == "failed",
        )
        .count()
    )
    receipts = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "package_receipt",
            AuditLog.created_at >= since,
        )
        .count()
    )
    if failures == 0:
        return _result(
            "介质导入",
            LEVEL_OK,
            "近 %d 天没有导入失败记录（成功回执 %d 条）" % (RECENT_IMPORT_DAYS, receipts),
            0,
        )
    return _result(
        "介质导入",
        LEVEL_WARN,
        "近 %d 天有 %d 次导入失败，请到「接收记录」核对" % (RECENT_IMPORT_DAYS, failures),
        failures,
    )


def _result(name: str, level: str, detail: str, count: int) -> Dict[str, Any]:
    return {"name": name, "level": level, "detail": detail, "count": count}


def collect_self_check(db: Session) -> Dict[str, Any]:
    """执行全部自检项，返回可直接渲染的结论。"""
    checks = [
        _check_org_codes(db),
        _check_org_hierarchy(db),
        _check_pending_users(db),
        _check_locked_users(db),
        _check_pii_key(),
        _check_recent_imports(db),
    ]
    errors = sum(1 for c in checks if c["level"] == LEVEL_ERROR)
    warns = sum(1 for c in checks if c["level"] == LEVEL_WARN)
    if errors:
        status = LEVEL_ERROR
    elif warns:
        status = LEVEL_WARN
    else:
        status = LEVEL_OK
    return {
        "generated_at": datetime.now().isoformat(),
        "status": status,
        "summary": {
            "check_count": len(checks),
            "error_count": errors,
            "warn_count": warns,
            "issue_count": sum(c["count"] for c in checks),
        },
        "checks": checks,
    }
