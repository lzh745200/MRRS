"""数据包管理 Schema"""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


from app.models.data_package import PackageType


class PackageStatusEnum(str, enum.Enum):
    """数据包状态"""

    CREATED = "created"
    EXPORTING = "exporting"
    VALIDATED = "validated"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataPackageValidationError(BaseModel):
    """数据包验证错误条目"""

    field: str = ""
    message: str = ""
    data_type: Optional[str] = None
    row: Optional[int] = None


class DataPackageResponse(BaseModel):
    """数据包响应"""

    id: int
    org_id: Optional[int] = None
    package_code: str = ""
    type: PackageType = PackageType.report
    status: str = "draft"
    description: Optional[str] = None
    file_name: Optional[str] = None
    file_size: int = 0
    record_count: int = 0
    is_encrypted: bool = False
    created_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DataPackageListResponse(BaseModel):
    """数据包列表响应"""

    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[DataPackageResponse] = []


class DataPackageExportRequest(BaseModel):
    """数据包导出请求"""

    org_id: Optional[int] = None
    data_types: List[str] = []
    description: Optional[str] = None
    type: PackageType = PackageType.report  # task: 任务包, report: 上报包
    incremental: bool = False  # 增量包: 仅导出 sync_version 大于 since_sync_version 的记录
    since_sync_version: Optional[int] = None  # 增量基准版本（配合 incremental=True）

    @field_validator("data_types")
    @classmethod
    def validate_data_types(cls, v: List[str]) -> List[str]:
        """验证 data_types 不能为空"""
        if not v or len(v) == 0:
            raise ValueError("至少需要选择一种数据类型")
        return v


class DataPackageManifest(BaseModel):
    """数据包清单"""

    version: str = "1.0"
    package_type: PackageType = PackageType.report  # report: 上报, task: 任务, update: 更新
    org_code: Optional[str] = ""
    org_name: Optional[str] = ""
    data_types: List[str] = []
    record_counts: Dict[str, int] = {}
    export_time: Optional[datetime] = None
    exported_by: Optional[str] = None
    description: Optional[str] = None
    checksum: Optional[str] = None
    encryption: str = "none"  # none, aes256
    compression: str = "zip"
    dependencies: List[str] = []  # 依赖的其他数据包
    incremental: bool = False  # 是否增量更新
    base_package_id: Optional[int] = None  # 基础包ID（增量更新时）
    changes: Optional[Dict[str, Any]] = None  # 变更记录（增量更新时）
    created_at: Optional[datetime] = None


class DataPackageExportResult(BaseModel):
    """数据包导出结果"""

    package_id: int
    package_code: str = ""
    file_path: Optional[str] = None
    file_name: str = ""
    file_size: int = 0
    manifest: Optional[DataPackageManifest] = None
    download_url: Optional[str] = None


class DataPackageImportResult(BaseModel):
    """数据包导入结果"""

    package_id: int
    package_code: str = ""
    status: Optional[str] = None
    manifest: Optional[DataPackageManifest] = None
    preview: List[Any] = []
    validation: Optional[Any] = None
    records_imported: int = 0
    errors: List[str] = []


class DataPackagePreviewData(BaseModel):
    """数据包预览"""

    data_type: str = ""
    total: int = 0
    sample: List[Dict[str, Any]] = []
    columns: List[str] = []
    tables: List[str] = []
    record_counts: Dict[str, int] = {}
    sample_data: Optional[Dict[str, Any]] = None


class DataPackageValidationResult(BaseModel):
    """数据包验证结果"""

    is_valid: bool = True
    errors: List[Any] = []
    warnings: List[str] = []
    manifest: Optional[DataPackageManifest] = None


class DataPackageConfirmRequest(BaseModel):
    """数据包确认导入请求"""

    package_id: Optional[int] = None
    confirm: bool = True
    overwrite_existing: bool = False
    selected_types: Optional[List[str]] = None


class DataPackageConfirmResult(BaseModel):
    """数据包确认导入结果"""

    success: bool = True
    package_id: Optional[int] = None
    imported_counts: Dict[str, int] = {}
    skipped_counts: Dict[str, int] = {}
    error_counts: Dict[str, int] = {}
    errors: List[Any] = []
    records_imported: int = 0
    message: str = ""
