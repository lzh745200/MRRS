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
        raise HTTPException(status_code=500, detail=f"获取配置包列表失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"导出配置包失败: {str(e)}")


@router.post("/import", summary="导入配置包")
async def import_config_package(
    body: ConfigPackageImportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
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
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"配置包数据格式无效: {str(e)}")

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

            svc.set(key, str(value) if not isinstance(value, str) else value)
            imported_count += 1

        logger.info(
            "配置包已导入: %s，导入 %d 项，跳过 %d 项，操作人: %s",
            package.get("name", "unknown"),
            imported_count, skipped_count,
            getattr(current_user, "username", "unknown"),
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
        raise HTTPException(status_code=500, detail=f"导入配置包失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"删除配置包失败: {str(e)}")
