"""
配置包管理 API
提供系统配置的打包导出、导入和版本管理功能
用于配置的备份、迁移和多环境同步
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.permission_utils import require_admin
from app.services.system_config_service import SystemConfigService
from app.services.package_import_guard import (
    assert_content_not_duplicate,
    record_import,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system/config-packages", tags=["配置包管理"])


# ==================== Pydantic 模型 ====================

class ConfigPackageExportRequest(BaseModel):
    """配置包导出请求"""
    name: Optional[str] = Field(None, description="配置包名称")
    description: Optional[str] = Field(None, description="配置包描述")
    include_defaults: bool = Field(False, description="是否包含默认配置项")


class ConfigPackageImportRequest(BaseModel):
    """配置包导入请求"""
    data: str = Field(..., description="JSON 格式的配置包数据")
    overwrite: bool = Field(True, description="是否覆盖已有配置")


class ConfigPackageResponse(BaseModel):
    """配置包列表项"""
    id: str
    name: str
    description: str
    config_count: int
    created_at: str


# ==================== API 端点 ====================


@router.get("", summary="获取可用配置包列表")
async def list_config_packages(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取系统中已创建的配置包列表

    配置包是系统配置的快照，可用于备份、恢复和环境迁移。
    """
    try:
        svc = SystemConfigService(db)
        packages = svc.get_config_packages() if hasattr(svc, 'get_config_packages') else []

        return {
            "success": True,
            "data": {
                "packages": packages,
                "total": len(packages),
            },
        }
    except Exception as e:
        logger.error("获取配置包列表失败: %s", e)
        raise HTTPException(status_code=500, detail="获取配置包列表失败，请稍后重试或联系管理员")


def _verify_config_package_integrity(package) -> None:
    """系统配置包完整性校验（W27，W26-P0-7）。

    抽成独立函数以降低导入端点的圈复杂度。checksum 强制；配置了
    ``PACKAGE_PUBKEY`` 时强制要求 Ed25519 签名（fail-closed）。
    """
    from app.core.config import settings as _settings
    from app.core.package_integrity import PackageIntegrityError, verify_manifest

    try:
        verify_manifest(
            package,
            public_key_hex=_settings.PACKAGE_PUBKEY,
            allow_unsigned=True,
            package_label="系统配置包",
        )
    except PackageIntegrityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/export", summary="导出当前系统配置为配置包")
async def export_config_package(
    body: ConfigPackageExportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """将当前系统配置导出为 JSON 配置包

    生成包含所有配置项、元数据和版本信息的 JSON 包。
    可用于备份配置或迁移到其他环境。
    需要管理员权限（配置含敏感信息）。
    """
    require_admin(current_user, error_message="仅管理员可导出配置包")
    try:
        svc = SystemConfigService(db)
        config_json = svc.export_config()
        config_data = json.loads(config_json)

        package_name = body.name or f"config_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        package = {
            "name": package_name,
            "description": body.description or f"系统配置快照 - {datetime.now().isoformat()}",
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "created_by": getattr(current_user, "username", "unknown"),
            "config_count": len(config_data),
            "configs": config_data,
            "include_defaults": body.include_defaults,
        }
        # W27（W26-P0-7）：补 checksum（强制）与签名（生成方配了私钥时）
        from app.core.config import settings as _settings
        from app.core.package_integrity import sign_manifest

        package = sign_manifest(package, _settings.PACKAGE_SIGNING_KEY)

        # 保存配置包记录
        svc.set(
            f"config_package_{package_name}",
            json.dumps(package, ensure_ascii=False),
            description=f"配置包: {package_name}",
        )

        logger.info(
            "配置包已导出: %s，操作人: %s",
            package_name, getattr(current_user, "username", "unknown"),
        )

        return {
            "success": True,
            "message": f"配置包 '{package_name}' 导出成功",
            "data": package,
        }
    except Exception as e:
        logger.error("导出配置包失败: %s", e)
        raise HTTPException(status_code=500, detail="导出配置包失败，请稍后重试或联系管理员")


@router.post("/import", summary="导入配置包")
async def import_config_package(
    body: ConfigPackageImportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    # 同一校验和的配置包再次导入必须显式确认
    force: bool = False,
):
    """从 JSON 配置包导入系统配置

    将之前导出的配置包数据恢复或应用到当前系统。
    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可导入配置包")

    try:
        # 解析配置包数据
        try:
            package = json.loads(body.data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="配置包数据格式无效，请稍后重试或联系管理员")

        # W27（W26-P0-7）：完整性校验 —— checksum 强制；配了 PACKAGE_PUBKEY 则强制验签
        _verify_config_package_integrity(package)

        # P2：配置包查重（内容哈希；重复且未 force → 409）
        checksum = assert_content_not_duplicate(
            db, str(body.data or "").encode("utf-8"), force=force
        )

        configs = package.get("configs", {})
        if not configs:
            raise HTTPException(status_code=400, detail="配置包中没有配置数据")

        svc = SystemConfigService(db)
        imported_count = 0
        skipped_count = 0

        for key, value in configs.items():
            # 检查 key 是否存在
            existing = svc.get(key)

            if existing is not None and not body.overwrite:
                skipped_count += 1
                continue

            # 深审 #81：SystemConfigService.set 已对 bool/dict/list 做归一
            # （json.dumps），外层再 str() 会把 dict 变成 Python repr（单引号），
            # 之后 get_json 解析必然失败 —— 配置包往返后配置项静默损坏。
            svc.set(key, value)
            imported_count += 1

        logger.info(
            "配置包已导入: %s，导入 %d 项，跳过 %d 项，操作人: %s",
            package.get("name", "unknown"),
            imported_count, skipped_count,
            getattr(current_user, "username", "unknown"),
        )

        # P2：写导入台账（失败不阻断）
        record_import(
            db,
            checksum=checksum,
            package_type="config_package",
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", ""),
            file_name="config_package.json",
            record_count=imported_count,
        )

        return {
            "success": True,
            "message": f"配置包导入完成（导入 {imported_count} 项，跳过 {skipped_count} 项）",
            "data": {
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "package_name": package.get("name", "unknown"),
                "package_version": package.get("version", "unknown"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("导入配置包失败: %s", e)
        raise HTTPException(status_code=500, detail="导入配置包失败，请稍后重试或联系管理员")


@router.delete("/{package_name}", summary="删除配置包")
async def delete_config_package(
    package_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除指定的配置包记录

    需要管理员权限。
    """
    require_admin(current_user, error_message="仅超级管理员可删除配置包")

    try:
        svc = SystemConfigService(db)
        key = f"config_package_{package_name}"
        value = svc.get(key)

        if value is None:
            raise HTTPException(status_code=404, detail=f"配置包 '{package_name}' 不存在")

        svc.delete(key)

        logger.info(
            "配置包已删除: %s，操作人: %s",
            package_name, getattr(current_user, "username", "unknown"),
        )

        return {"success": True, "message": f"配置包 '{package_name}' 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除配置包失败: %s", e)
        raise HTTPException(status_code=500, detail="删除配置包失败，请稍后重试或联系管理员")
