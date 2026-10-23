"""系统自检 API（P3）。

GET /api/v1/system/self-check —— 仅管理员。

与 /system/diagnostics（基础设施/运行时排障，含日志/资源）不同，
本端点只做**配置一致性体检**：单位码、组织层级、账号状态、PII 密钥、
介质导入近况。不返回任何 PII、不含日志正文，供「系统设置」页一键体检。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.response import success_response
from app.core.security import get_current_user
from app.services.self_check_service import collect_self_check

router = APIRouter(prefix="/self-check", tags=["系统自检"])


@router.get("", summary="系统自检（仅管理员）")
def self_check(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """配置一致性体检：单位码 / 组织层级 / 账号 / PII 密钥 / 介质导入。"""
    require_admin(current_user)
    return success_response(data=collect_self_check(db))
