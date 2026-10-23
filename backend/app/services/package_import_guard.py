# -*- coding: utf-8 -*-
"""介质数据包导入守卫（P2）：校验和查重 + 导入台账。

设计意图（完全离线 + 上下级 + 介质传输场景）：

* **查重**：同一个 U 盘来回拷、同一包装两遍是高频误操作。以「整包 SHA256」为
  指纹，在导入前查审计台账，命中则拒绝并要求显式 force=true 才放行。
* **台账**：复用既有 audit_logs 表（动作 package_import，resource_id 存校验和），
  不新增表、不新增迁移，避免与并行改造冲突。
* **健壮性**：写台账失败绝不影响导入主流程（仅记 debug 日志）。

本模块只做「读包 + 查台账 + 写台账」，不解析包内容，也不修改
data_package_service 的业务逻辑，便于后续与 W27 业务键改造无缝合并。
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.audit import AuditLog
from app.utils.audit_logger import AuditAction, AuditLevel, AuditLogger

# 分块读取大小（1MB）：避免大包一次性读入内存，也满足「读取必须限长」门禁
_CHUNK_SIZE = 1024 * 1024

# 台账动作名（与 audit_logs.action 一致）
PACKAGE_IMPORT_ACTION = "package_import"


def package_checksum(file_path: str) -> str:
    """计算整包 SHA256（分块读取，1MB 一块）。"""
    digest = hashlib.sha256()
    with open(file_path, "rb") as fp:
        while True:
            chunk = fp.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    """把值转成可 JSON 序列化的形态（datetime 转 ISO 字符串）。"""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def find_previous_import(db: Session, checksum: str) -> Optional[Dict[str, Any]]:
    """按整包校验和查最近一次成功导入记录。"""
    if not checksum:
        return None
    try:
        row = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == PACKAGE_IMPORT_ACTION,
                AuditLog.resource_id == checksum,
            )
            .order_by(AuditLog.id.desc())
            .first()
        )
    except Exception:  # pragma: no cover - 防御：查询故障不阻断导入
        logger.debug("数据包台账查询失败", exc_info=True)
        return None
    # 只认真实 ORM 行：测试里的 MagicMock 桩 / 其它类型一律视为未命中
    if not isinstance(row, AuditLog):
        return None
    payload = row.new_value if isinstance(row.new_value, dict) else {}
    return {
        "username": row.username or "",
        "created_at": _json_safe(payload.get("imported_at") or row.created_at),
        "package_type": row.resource_type or "",
        "file_name": payload.get("file_name") or "",
    }


def build_duplicate_message(previous: Dict[str, Any]) -> str:
    """拼装「该包已导入过」的提示文案（含时间与操作人）。"""
    when = previous.get("created_at") or "未知时间"
    who = previous.get("username") or "未知操作人"
    return (
        "该数据包已于 " + str(when) + " 由 " + str(who) + " 导入过；"
        "如确需再次导入，请传入 force=true"
    )


def record_import(
    db: Session,
    *,
    checksum: str,
    package_type: str,
    user_id: Optional[int] = None,
    username: str = "",
    file_name: str = "",
    source_org_code: Optional[str] = None,
    record_count: int = 0,
    result: str = "success",
) -> None:
    """写一条导入台账（失败只记 debug，不影响导入主流程）。"""
    try:
        AuditLogger.log(
            action=AuditAction.PACKAGE_IMPORT,
            user_id=user_id,
            username=username,
            resource_type=package_type,
            resource_id=checksum,
            details={
                "checksum": checksum,
                "package_type": package_type,
                "file_name": _json_safe(file_name),
                "source_org_code": _json_safe(source_org_code),
                "record_count": record_count,
                "result": result,
                "imported_at": datetime.now().isoformat(),
            },
            level=AuditLevel.INFO,
        )
    except Exception:  # pragma: no cover - 防御：台账写失败不阻断导入
        logger.debug("数据包台账写入失败", exc_info=True)
