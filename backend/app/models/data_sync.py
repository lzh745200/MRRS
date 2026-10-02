"""数据同步模型"""

from datetime import datetime, timezone
from sqlalchemy import Column, ForeignKey, Integer, String, Text, Boolean, JSON
from app.models.base import BaseModel, UtcDateTime


class DataSyncLog(BaseModel):
    """数据同步日志"""

    __tablename__ = "data_sync_logs"

    sync_type = Column(String(20), nullable=False)  # export/import
    status = Column(String(20), nullable=False)  # pending/processing/completed/failed
    package_name = Column(String(255), nullable=False)
    package_path = Column(String(500))

    # 导出信息
    since_time = Column(UtcDateTime())
    modules = Column(JSON)  # 导出的模块列表
    include_files = Column(Boolean, default=False)

    # 导入信息
    conflict_strategy = Column(String(50))  # skip/overwrite/merge/manual
    conflicts_count = Column(Integer, default=0)

    # 统计信息
    total_records = Column(Integer, default=0)
    success_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)

    # 详细信息
    details = Column(JSON)  # 详细的同步信息
    error_message = Column(Text)

    # 操作人
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    user_name = Column(String(100))

    started_at = Column(UtcDateTime(), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(UtcDateTime(), nullable=True)


class DataConflict(BaseModel):
    """数据冲突记录"""

    __tablename__ = "data_conflicts"

    sync_log_id = Column(
        Integer, ForeignKey("data_sync_logs.id", ondelete="CASCADE"), nullable=False
    )  # 关联的同步日志ID

    # 冲突信息
    table_name = Column(String(100), nullable=False)
    record_id = Column(String(100))  # 记录ID（可能是字符串）
    conflict_type = Column(String(50), nullable=False)  # duplicate/modified/deleted

    # 数据
    local_data = Column(JSON)  # 本地数据
    import_data = Column(JSON)  # 导入数据

    # 解决方案
    resolution = Column(String(50))  # keep_local/use_import/merge/skip
    resolved = Column(Boolean, default=False)
    resolved_at = Column(UtcDateTime(), nullable=True)
    resolved_by = Column(Integer)  # 解决人ID

    # 合并后的数据
    merged_data = Column(JSON)

    notes = Column(Text)  # 备注
