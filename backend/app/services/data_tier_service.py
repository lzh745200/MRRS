"""
数据分级存储服务

实现数据生命周期管理，将数据按访问频率分为三级：
- 热数据 (Hot): 最近1年，高频访问，存储在主数据库
- 温数据 (Warm): 1-3年，中频访问，可归档到辅助存储
- 冷数据 (Cold): 3年以上，低频访问，可归档到压缩文件

"""

import json
import gzip
from datetime import timezone, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.database import SessionLocal
from app.core.transaction import safe_commit


class DataTier(str, Enum):
    """数据分级"""

    HOT = "hot"  # 热数据: < 1年
    WARM = "warm"  # 温数据: 1-3年
    COLD = "cold"  # 冷数据: > 3年


class DataTierConfig:
    """数据分级配置"""

    # 分级时间阈值（天）
    HOT_THRESHOLD_DAYS = 365
    WARM_THRESHOLD_DAYS = 365 * 3

    # 存储路径配置
    HOT_DATA_PATH = settings.DATABASE_URL.replace("sqlite:///", "")
    WARM_DATA_PATH = str(Path(settings.DATABASE_URL.replace("sqlite:///", "")).parent / "warm_data.db")
    COLD_ARCHIVE_PATH = str(Path(settings.DATABASE_URL.replace("sqlite:///", "")).parent / "archives")

    # 归档配置
    COMPRESSION_ENABLED = True
    ARCHIVE_BATCH_SIZE = 1000


class DataTierService:
    """
    数据分级存储服务

    管理数据在不同存储层级之间的迁移：
    - 热数据 -> 温数据: 1年后自动迁移
    - 温数据 -> 冷数据: 3年后归档到压缩文件
    - 冷数据恢复: 按需恢复到温/热存储
    """

    _instance: Optional["DataTierService"] = None

    def __new__(cls) -> "DataTierService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.config = DataTierConfig()

        # 确保归档目录存在
        try:
            Path(self.config.COLD_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"创建归档目录失败: {e}")

    def determine_tier(self, record_date: datetime) -> DataTier:
        """
        根据记录日期确定数据分级

        Args:
            record_date: 记录日期

        Returns:
            数据分级
        """
        now = datetime.now(timezone.utc)
        # 兼容 timezone-naive 的输入日期
        if record_date.tzinfo is None:
            record_date = record_date.replace(tzinfo=timezone.utc)
        age_days = (now - record_date).days

        if age_days <= self.config.HOT_THRESHOLD_DAYS:
            return DataTier.HOT
        elif age_days <= self.config.WARM_THRESHOLD_DAYS:
            return DataTier.WARM
        else:
            return DataTier.COLD

    def get_archive_stats(self, db: Session) -> Dict[str, Any]:
        """
        获取归档统计信息

        Returns:
            统计数据
        """
        stats = {
            "total_records": 0,
            "by_tier": {
                DataTier.HOT: {"count": 0, "oldest": None, "newest": None},
                DataTier.WARM: {"count": 0, "oldest": None, "newest": None},
                DataTier.COLD: {"count": 0, "files": []},
            },
            "storage": {
                "hot_db_size": 0,
                "warm_db_size": 0,
                "cold_archive_size": 0,
            },
        }

        # 检查主数据库大小
        hot_db_path = Path(self.config.HOT_DATA_PATH)
        if hot_db_path.exists():
            stats["storage"]["hot_db_size"] = hot_db_path.stat().st_size

        # 检查温数据数据库大小
        warm_db_path = Path(self.config.WARM_DATA_PATH)
        if warm_db_path.exists():
            stats["storage"]["warm_db_size"] = warm_db_path.stat().st_size

        # 检查冷数据归档大小
        cold_path = Path(self.config.COLD_ARCHIVE_PATH)
        if cold_path.exists():
            total_size = sum(f.stat().st_size for f in cold_path.glob("*.gz") if f.is_file())
            stats["storage"]["cold_archive_size"] = total_size
            stats["by_tier"][DataTier.COLD]["files"] = [f.name for f in cold_path.glob("*.gz")]

        return stats

    def archive_records(
        self,
        db: Session,
        model_class: Any,
        date_field: str = "created_at",
        before_date: Optional[datetime] = None,
        batch_size: int = 1000,
    ) -> Tuple[int, str]:
        """
        归档旧记录到温/冷存储

        Args:
            db: 数据库会话
            model_class: 模型类
            date_field: 日期字段名
            before_date: 归档此日期之前的记录
            batch_size: 批次大小

        Returns:
            (归档数量, 状态信息)
        """
        if before_date is None:
            before_date = datetime.now(timezone.utc) - timedelta(days=self.config.HOT_THRESHOLD_DAYS)

        # 确保比较时 timezone 兼容（SQLite 列可能是 naive datetime）
        compare_date = before_date.replace(tzinfo=None) if before_date.tzinfo else before_date

        # 查询待归档记录
        query = db.query(model_class).filter(getattr(model_class, date_field) < compare_date)

        total_count = query.count()
        if total_count == 0:
            return 0, "没有需要归档的记录"

        archived = 0
        tier = self.determine_tier(before_date)

        try:
            if tier == DataTier.WARM:
                archived = self._archive_to_warm_storage(db, query, model_class, batch_size)
            else:
                archived = self._archive_to_cold_storage(db, query, model_class, batch_size)

            return archived, f"成功归档 {archived}/{total_count} 条记录到 {tier.value} 存储"

        except Exception as e:
            logger.error(f"归档失败: {e}")
            return archived, f"归档失败: {e}"

    def _archive_to_warm_storage(self, db: Session, query: Any, model_class: Any, batch_size: int) -> int:
        """
        归档到温存储（辅助数据库）

        实现：将记录移动到温数据数据库
        """
        archived = 0

        # 这里简化实现：实际应该创建温数据数据库连接并迁移
        # 目前只是记录日志，实际迁移需要更复杂的实现
        for record in query.limit(batch_size).all():
            # 标记记录为已归档（软删除或添加归档标记）
            if hasattr(record, "is_archived"):
                record.is_archived = True
            archived += 1

        safe_commit(db)
        logger.info(f"归档 {archived} 条记录到温存储")
        return archived

    def _archive_to_cold_storage(self, db: Session, query: Any, model_class: Any, batch_size: int) -> int:
        """
        归档到冷存储（压缩文件）

        实现：将记录导出为 JSON 并压缩存储
        """
        records = []
        record_ids = []

        for record in query.limit(batch_size).all():
            # 转换为字典
            record_dict = self._model_to_dict(record)
            records.append(record_dict)
            record_ids.append(record.id)

        if not records:
            return 0

        # 生成归档文件名
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        model_name = model_class.__name__.lower()
        archive_file = f"{model_name}_{timestamp}.json.gz"
        archive_path = Path(self.config.COLD_ARCHIVE_PATH) / archive_file

        # 压缩并保存
        json_data = json.dumps(records, ensure_ascii=False, default=str)

        if self.config.COMPRESSION_ENABLED:
            with gzip.open(archive_path, "wt", encoding="utf-8") as f:
                f.write(json_data)
        else:
            archive_path = archive_path.with_suffix(".json")
            with open(archive_path, "w", encoding="utf-8") as f:
                f.write(json_data)

        # 删除已归档的记录
        query.filter(model_class.id.in_(record_ids)).delete(synchronize_session=False)
        safe_commit(db)

        logger.info(f"归档 {len(records)} 条记录到冷存储: {archive_file}")
        return len(records)

    def _model_to_dict(self, model_instance: Any) -> Dict[str, Any]:
        """将模型实例转换为字典"""
        result = {}
        for column in model_instance.__table__.columns:
            value = getattr(model_instance, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    def restore_from_archive(
        self, db: Session, model_class: Any, archive_file: str, record_ids: Optional[List[int]] = None
    ) -> Tuple[int, str]:
        """
        从归档恢复数据

        Args:
            db: 数据库会话
            model_class: 模型类
            archive_file: 归档文件名
            record_ids: 指定恢复的记录ID（None则恢复全部）

        Returns:
            (恢复数量, 状态信息)
        """
        # 防路径穿越：archive_file 直接来自 API 查询参数。
        # Path(base) / "../../etc/passwd" 会逃逸出归档目录；绝对路径更会**完全覆盖**
        # base（pathlib 语义），造成任意文件读取。要求它必须是纯文件名。
        if not archive_file or Path(archive_file).name != archive_file:
            return 0, f"非法的归档文件名: {archive_file}"

        archive_path = Path(self.config.COLD_ARCHIVE_PATH) / archive_file

        if not archive_path.exists():
            return 0, f"归档文件不存在: {archive_file}"

        try:
            # 读取归档数据
            if archive_file.endswith(".gz"):
                with gzip.open(archive_path, "rt", encoding="utf-8") as f:
                    records = json.load(f)
            else:
                with open(archive_path, "r", encoding="utf-8") as f:
                    records = json.load(f)

            # 过滤指定记录
            if record_ids:
                records = [r for r in records if r.get("id") in record_ids]

            # 恢复记录
            restored = 0
            for record_dict in records:
                try:
                    # 移除 id 避免冲突
                    record_dict.pop("id", None)
                    # 创建新记录
                    new_record = model_class(**record_dict)
                    db.add(new_record)
                    restored += 1
                except Exception as e:
                    logger.warning(f"恢复记录失败: {e}")

            safe_commit(db)
            return restored, f"成功恢复 {restored} 条记录"

        except Exception as e:
            db.rollback()
            logger.error(f"恢复归档失败: {e}")
            return 0, f"恢复失败: {e}"

    def cleanup_old_archives(self, max_age_days: int = 365) -> Tuple[int, str]:
        """
        清理过期的归档文件

        Args:
            max_age_days: 最大保留天数

        Returns:
            (删除数量, 状态信息)
        """
        archive_path = Path(self.config.COLD_ARCHIVE_PATH)
        if not archive_path.exists():
            return 0, "归档目录不存在"

        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max_age_days)
        deleted = 0

        for archive_file in archive_path.glob("*.gz"):
            try:
                mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if mtime < cutoff_date:
                    archive_file.unlink()
                    deleted += 1
                    logger.info(f"删除过期归档: {archive_file.name}")
            except Exception as e:
                logger.error(f"删除归档文件失败 {archive_file.name}: {e}")

        return deleted, f"清理了 {deleted} 个过期归档文件"

    def get_storage_summary(self) -> Dict[str, Any]:
        """
        获取存储摘要报告

        Returns:
            存储摘要
        """
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tiers": {
                DataTier.HOT: {
                    "description": "热数据 (< 1年)",
                    "storage_path": self.config.HOT_DATA_PATH,
                    "retention_days": self.config.HOT_THRESHOLD_DAYS,
                },
                DataTier.WARM: {
                    "description": "温数据 (1-3年)",
                    "storage_path": self.config.WARM_DATA_PATH,
                    "retention_days": self.config.WARM_THRESHOLD_DAYS,
                },
                DataTier.COLD: {
                    "description": "冷数据 (> 3年)",
                    "storage_path": self.config.COLD_ARCHIVE_PATH,
                    "compression_enabled": self.config.COMPRESSION_ENABLED,
                },
            },
            "recommendations": [],
        }

        # 获取实际存储大小
        _session = SessionLocal()
        try:
            stats = self.get_archive_stats(_session)
        finally:
            _session.close()
        summary["storage_sizes"] = stats["storage"]

        # 生成建议
        total_size = sum(stats["storage"].values())
        hot_ratio = stats["storage"]["hot_db_size"] / total_size if total_size > 0 else 0

        if hot_ratio > 0.8:
            summary["recommendations"].append(
                {
                    "level": "warning",
                    "message": "热数据占比过高，建议执行归档任务",
                    "action": "运行 archive_records 任务",
                }
            )

        if stats["storage"]["cold_archive_size"] > 1024 * 1024 * 1024:  # > 1GB
            summary["recommendations"].append(
                {"level": "info", "message": "冷数据归档较大，可考虑迁移到对象存储", "action": "配置 S3/GCS 冷存储"}
            )

        return summary


# 全局实例
data_tier_service = DataTierService()
