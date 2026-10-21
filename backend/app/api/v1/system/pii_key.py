"""PII 字段加密密钥管理（R34-2 / P1-2）。

## 为什么需要这个模块

多机离线同步时 PII 列以**密文**出包（`data_package_service._export_data_type` 的
W18-D8 决策），要求各机使用同一把 `ENCRYPTION_KEY`。但默认安装下每台机器会各自
随机生成密钥 —— 同步到对端后密文永久不可解，界面只显示 `enc.v1:...` 乱码，
用户却以为"同步成功"。数据包侧已加指纹校验拒绝这种导入（`key_fingerprint`），
但用户还需要一个**能真正修好**的入口：把源机密钥搬到目标机。

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET  | `/system/pii-key`         | 查看指纹与配置来源（env / runtime） |
| GET  | `/system/pii-key/export`  | 导出密钥（管理员；搬机用） |
| POST | `/system/pii-key/import`  | 导入密钥（管理员；写运行时密钥存储） |

## 安全约束

1. 三个端点均要求管理员；
2. 导出/导入写审计日志，但**只记指纹，不记密钥本体**；
3. 本机已通过环境变量 `ENCRYPTION_KEY` 显式配置时拒绝导入 —— 环境变量优先级高于
   运行时密钥存储，此时写 runtime 不会生效，静默接受会让运维误以为已修复。
"""

from __future__ import annotations

import base64
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.response import success_response
from app.core.security import get_current_user
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pii-key", tags=["PII 密钥"])

#: 运行时密钥存储中 PII 密钥的键名（与 core/pii_crypto._load_key 保持一致）
_RUNTIME_KEY_NAME = "PII_AESSIV_KEY"

#: 导入密钥的最小长度（与 runtime_secrets._MIN_KEY_LENGTH 同口径）
_MIN_SECRET_LEN = 32

SOURCE_ENV = "env"
SOURCE_RUNTIME = "runtime"


class PiiKeyImportRequest(BaseModel):
    """导入密钥请求体。"""

    key: str = Field(..., description="源机导出的密钥串（base64 或任意 >=32 字符的强密钥）")


def _source() -> str:
    """密钥配置来源：env（环境变量显式配置）或 runtime（运行时密钥存储）。"""
    return SOURCE_ENV if (getattr(settings, "ENCRYPTION_KEY", None) or "").strip() else SOURCE_RUNTIME


def _current_secret() -> str:
    """读取当前生效的原始密钥串（不含 SHA-512 派生）。"""
    if _source() == SOURCE_ENV:
        return settings.ENCRYPTION_KEY.strip()

    from app.utils.runtime_secrets import get_or_create_secret

    return get_or_create_secret(
        _RUNTIME_KEY_NAME,
        generate=lambda: base64.b64encode(os.urandom(64)).decode(),
        require_persisted=True,
    )


def _fingerprint() -> str:
    """当前密钥指纹（SHA-256 前 16 位）。密钥不可用时返回空串。"""
    try:
        from app.core.pii_crypto import key_fingerprint

        return key_fingerprint()
    except Exception:  # pragma: no cover - 密钥初始化失败时端点降级为"不可用"
        logger.warning("读取 PII 密钥指纹失败", exc_info=True)
        return ""


def _audit(db, current_user, action: str, detail: str) -> None:
    """写审计日志（失败不阻断主流程；绝不记录密钥本体）。"""
    try:
        write_work_log(
            db, "system_config", action, 0, detail,
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", ""),
        )
    except Exception:  # pragma: no cover - 审计失败不阻断主流程
        logger.warning("记录 PII 密钥操作审计失败", exc_info=True)


@router.get("", summary="查看 PII 密钥状态")
def get_pii_key_status(current_user=Depends(get_current_user)):
    """返回本机 PII 密钥指纹与配置来源（不含密钥本体）。"""
    require_admin(current_user, error_message="仅管理员可查看 PII 密钥状态")
    fingerprint = _fingerprint()
    return success_response(
        data={
            "fingerprint": fingerprint,
            "source": _source(),
            "available": bool(fingerprint),
        }
    )


@router.get("/export", summary="导出 PII 密钥（搬机）")
def export_pii_key(
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """导出本机 PII 密钥，供其它机器导入以统一密文解钥。"""
    require_admin(current_user, error_message="仅管理员可导出 PII 密钥")
    try:
        secret = _current_secret()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="读取 PII 密钥失败，请检查运行时密钥文件权限") from exc

    fingerprint = _fingerprint()
    _audit(db, current_user, "pii_key_export", "导出 PII 密钥（指纹 %s）" % fingerprint)
    return success_response(
        data={"fingerprint": fingerprint, "key": secret, "source": _source()},
        message="密钥已导出，请通过安全渠道传递",
    )


@router.post("/import", summary="导入 PII 密钥（统一多机密文）")
def import_pii_key(
    body: PiiKeyImportRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """导入源机 PII 密钥；成功后立即生效（无需重启）。"""
    require_admin(current_user, error_message="仅管理员可导入 PII 密钥")

    new_secret = (body.key or "").strip()
    if len(new_secret) < _MIN_SECRET_LEN:
        raise HTTPException(
            status_code=400,
            detail="密钥长度不足（至少 %d 个字符），请使用源机导出的完整密钥" % _MIN_SECRET_LEN,
        )

    if _source() == SOURCE_ENV:
        raise HTTPException(
            status_code=400,
            detail=(
                "本机已通过环境变量 ENCRYPTION_KEY 显式配置密钥，环境变量优先级高于"
                "运行时密钥存储，导入不会生效。请改为在 .env 中统一配置相同 ENCRYPTION_KEY。"
            ),
        )

    from app.utils.runtime_secrets import set_secret

    try:
        set_secret(_RUNTIME_KEY_NAME, new_secret)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="写入运行时密钥失败，请检查磁盘空间与文件权限") from exc

    # 清派生密钥缓存 → 新密钥立即生效（_load_key 下次调用会重新派生）
    from app.core.pii_crypto import reset_decrypt_failure_stats, reset_key_cache

    reset_key_cache()
    reset_decrypt_failure_stats()
    fingerprint = _fingerprint()

    _audit(db, current_user, "pii_key_import", "导入 PII 密钥（新指纹 %s）" % fingerprint)
    return success_response(
        data={"fingerprint": fingerprint, "source": _source()},
        message="密钥已导入并立即生效",
    )
