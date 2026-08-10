"""
系统配置API
提供系统运行参数的查询和修改功能
用于帮扶管理信息系统的参数调优和个性化配置
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.system_config_service import SystemConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["系统配置"])


# ==================== Pydantic 模型 ====================

class ConfigItem(BaseModel):
    """单个配置项"""
    key: str = Field(..., description="配置键")
    value: str = Field(..., description="配置值")
    description: Optional[str] = Field(None, description="配置说明")


class ConfigBatchUpdate(BaseModel):
    """批量更新配置"""
    configs: List[ConfigItem] = Field(..., description="配置项列表")


class ConfigExportImport(BaseModel):
    """配置导入导出"""
    data: str = Field(..., description="JSON格式的配置数据")


# ==================== API 端点 ====================


@router.get("", summary="获取所有系统配置")
async def get_all_configs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取所有系统配置项的键值对列表

    返回系统中所有持久化的配置参数及其说明。
    """
    svc = SystemConfigService(db)
    configs = svc.get_all()

    # 为每个配置项附加说明信息
    items = []
    for key, value in configs.items():
        desc = svc.DEFAULT_CONFIGS.get(key, {}).get("description", "")
        items.append({"key": key, "value": value, "description": desc})

    from app.core.response import ok_list

    return ok_list(items=items, total=len(items))


@router.put("", summary="批量更新配置项")
async def batch_update_configs(
    batch: ConfigBatchUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """批量更新多个系统配置项

    一次请求更新多个配置参数，减少多次API调用的开销。
    需要管理员权限。
    """
    from app.core.permission_utils import require_admin
    require_admin(current_user, error_message="仅超级管理员可修改系统配置")

    svc = SystemConfigService(db)
    updated = []

    for item in batch.configs:
        svc.set(item.key, item.value, item.description)
        updated.append(item.key)

    logger.info(
        "批量更新 %d 项系统配置，操作人: %s",
        len(updated),
        getattr(current_user, "username", "unknown"),
    )

    return {
        "success": True,
        "message": f"成功更新 {len(updated)} 项配置",
        "data": {"updated_keys": updated},
    }


@router.get("/export/json", summary="导出配置为JSON")
async def export_configs(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """导出所有系统配置为JSON字符串

    可用于配置的备份和迁移。
    """
    svc = SystemConfigService(db)
    config_json = svc.export_config()

    return {
        "success": True,
        "data": {
            "format": "json",
            "content": config_json,
        },
    }


@router.post("/import/json", summary="从JSON导入配置")
async def import_configs(
    body: ConfigExportImport,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """从JSON字符串导入系统配置

    可用于配置的恢复和迁移。需要管理员权限。
    """
    from app.core.permission_utils import require_admin
    require_admin(current_user, error_message="仅超级管理员可导入系统配置")

    svc = SystemConfigService(db)
    success = svc.import_config(body.data)

    if not success:
        raise HTTPException(status_code=400, detail="配置数据格式无效，请使用有效的JSON")

    logger.info(
        "系统配置已从JSON导入，操作人: %s",
        getattr(current_user, "username", "unknown"),
    )

    return {"success": True, "message": "配置导入成功"}


@router.get("/defaults", summary="获取默认配置值")
async def get_default_configs():
    """获取系统内建的所有默认配置项

    用于了解系统的可配置参数及其默认值。
    """
    defaults = [
        {"key": k, "value": v["value"], "description": v["description"]}
        for k, v in SystemConfigService.DEFAULT_CONFIGS.items()
    ]

    return {
        "success": True,
        "data": {
            "defaults": defaults,
            "total": len(defaults),
        },
    }


@router.get("/{key}", summary="获取指定配置项")
async def get_config(
    key: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取指定配置项的值及其说明"""
    svc = SystemConfigService(db)
    value = svc.get(key)

    if value is None:
        raise HTTPException(status_code=404, detail=f"配置项 '{key}' 不存在")

    desc = svc.DEFAULT_CONFIGS.get(key, {}).get("description", "")

    return {
        "success": True,
        "data": {
            "key": key,
            "value": value,
            "description": desc,
        },
    }


@router.put("/{key}", summary="更新指定配置项")
async def update_config(
    key: str,
    value: str = Query(..., description="配置值"),
    description: Optional[str] = Query(None, description="配置说明"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """更新指定配置项的值

    修改系统运行参数，如备份间隔、数据保留天数、会话超时时间等。
    需要管理员权限。
    """
    from app.core.permission_utils import require_admin
    require_admin(current_user, error_message="仅超级管理员可修改系统配置")

    svc = SystemConfigService(db)
    svc.set(key, value, description)

    logger.info(
        "系统配置 '%s' 已更新为 '%s'，操作人: %s",
        key,
        value,
        getattr(current_user, "username", "unknown"),
    )

    return {
        "success": True,
        "message": f"配置项 '{key}' 已更新",
        "data": {"key": key, "value": value},
    }


@router.delete("/{key}", summary="删除指定配置项")
async def delete_config(
    key: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除指定配置项

    删除非默认的配置项，系统将回退使用默认值。
    需要管理员权限。
    """
    from app.core.permission_utils import require_admin
    require_admin(current_user, error_message="仅超级管理员可删除系统配置")

    svc = SystemConfigService(db)

    # 不允许删除核心默认配置
    if key in svc.DEFAULT_CONFIGS:
        raise HTTPException(status_code=400, detail=f"不能删除核心默认配置项 '{key}'")

    success = svc.delete(key)
    if not success:
        raise HTTPException(status_code=404, detail=f"配置项 '{key}' 不存在")

    logger.info(
        "系统配置 '%s' 已删除，操作人: %s",
        key,
        getattr(current_user, "username", "unknown"),
    )

    return {"success": True, "message": f"配置项 '{key}' 已删除"}
