"""
权限配置包 Pydantic Schema

用于离线多机协作场景：管理员导出权限配置为 ZIP 包，
在另一台电脑导入后完全还原权限分配。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════
# 导出
# ══════════════════════════════════════════════════════════════

class PermissionPackageExportRequest(BaseModel):
    """导出权限配置包请求"""
    password: Optional[str] = Field(None, description="导出包加密密码（可选，为空则不加密）")
    description: Optional[str] = Field(None, description="导出说明")
    role_names: Optional[List[str]] = Field(
        None, description="选择性导出：仅包含这些角色（含其用户绑定）。为空/None 导出全部"
    )


class PermissionPackageManifest(BaseModel):
    """权限配置包清单"""
    version: str = Field("1.0", description="配置包版本号")
    export_time: str = Field(..., description="导出时间 ISO 8601")
    user_count: int = Field(0, description="包含的用户数")
    role_count: int = Field(0, description="包含的 RBAC 角色数")
    description: Optional[str] = Field(None, description="导出说明")
    checksum: Optional[str] = Field(None, description="SHA-256 校验和")
    encryption: Optional[Dict[str, Any]] = Field(None, description="加密信息")


class PermissionPackageExportResult(BaseModel):
    """导出结果"""
    success: bool = True
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    user_count: int = 0
    role_count: int = 0
    message: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# 导入
# ══════════════════════════════════════════════════════════════

class PermissionPackagePreview(BaseModel):
    """导入预览数据"""
    version: str = ""
    export_time: Optional[str] = None
    roles: List[Dict[str, Any]] = Field(default_factory=list, description="角色预览列表")
    role_count: int = 0
    user_role_count: int = 0
    user_permission_count: int = 0
    user_menu_count: int = 0
    user_legacy_count: int = 0
    warnings: List[str] = Field(default_factory=list, description="导入前警告")


class PermissionPackageImportResult(BaseModel):
    """导入验证结果"""
    success: bool = True
    package_id: Optional[int] = None
    preview: Optional[PermissionPackagePreview] = None
    errors: List[str] = Field(default_factory=list)
    message: Optional[str] = None
    # 服务端保存的文件名，供前端两步导入（import → confirm/{file_name}）使用
    saved_file_name: Optional[str] = None
    file_name: Optional[str] = None


class PermissionPackageConfirmRequest(BaseModel):
    """确认导入请求"""
    overwrite_existing: bool = Field(True, description="是否覆盖已有配置（mirror 模式）")
    mode: Optional[str] = Field(
        None, description="导入模式：overwrite=完全替换（默认），merge=合并（保留目标机既有配置）"
    )


class PermissionPackageConfirmResult(BaseModel):
    """确认导入结果"""
    success: bool = True
    roles_created: int = 0
    roles_updated: int = 0
    user_roles_assigned: int = 0
    user_permissions_assigned: int = 0
    user_roles_skipped: int = 0
    user_permissions_skipped: int = 0
    user_menus_updated: int = 0
    user_legacy_updated: int = 0
    errors: List[str] = Field(default_factory=list)
    message: Optional[str] = None
