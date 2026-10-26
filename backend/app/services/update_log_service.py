"""系统更新日志服务

管理系统更新日志的CRUD操作和版本历史初始化。

功能：
- 记录系统更新日志
- 查询更新历史
- 初始化版本历史数据（从第一个版本到当前）
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.transaction import safe_commit
from app.models.system_config import SystemUpdateLog
from app.services.version_history_data import VERSION_HISTORY_DATA

logger = logging.getLogger(__name__)


# 版本历史数据由仓库唯一账本 CHANGELOG.md 派生（scripts/sync_update_log.py 生成，
# scripts/check_update_log.py 在 CI 中校验一致性）。改版本说明请改 CHANGELOG.md。

class UpdateLogService:
    """系统更新日志服务"""

    def __init__(self, db: Session):
        self.db = db

    def record_update(
        self,
        version: str,
        description: str = "",
        updated_by: str = None,
    ) -> SystemUpdateLog:
        """
        记录一次系统更新

        Args:
            version: 版本号
            description: 更新描述
            updated_by: 更新人（可选）

        Returns:
            创建的更新日志记录
        """
        log_entry = SystemUpdateLog(
            id=str(uuid.uuid4()),
            version=version,
            description=description,
            updated_by=updated_by,
        )
        self.db.add(log_entry)
        safe_commit(self.db)
        self.db.refresh(log_entry)

        logger.info("系统更新已记录: %s", version)
        return log_entry

    def get_update_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by_desc: bool = True,
    ) -> List[SystemUpdateLog]:
        """
        查询更新日志列表

        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
            order_by_desc: 是否按时间倒序排列

        Returns:
            更新日志记录列表
        """
        query = self.db.query(SystemUpdateLog)

        # 次级排序用 version：历史库里同一天发布的多个版本 created_at 完全相同，
        # 只按时间排序时同批版本的先后是随机的（实测 1.18.2 会排在 1.18.3 前面）。
        if order_by_desc:
            query = query.order_by(SystemUpdateLog.created_at.desc(), SystemUpdateLog.version.desc())
        else:
            query = query.order_by(SystemUpdateLog.created_at.asc(), SystemUpdateLog.version.asc())

        return query.offset(skip).limit(limit).all()

    def get_latest_update(self) -> Optional[SystemUpdateLog]:
        """
        获取最新的更新记录

        Returns:
            最新的更新日志记录，如果没有则返回None
        """
        return self.db.query(SystemUpdateLog).order_by(SystemUpdateLog.created_at.desc()).first()

    def get_update_by_version(self, version: str) -> Optional[SystemUpdateLog]:
        """
        根据版本号获取更新记录

        Args:
            version: 版本号

        Returns:
            更新日志记录，如果没有则返回None
        """
        return self.db.query(SystemUpdateLog).filter(SystemUpdateLog.version == version).first()

    def is_version_recorded(self, version: str) -> bool:
        """
        检查版本是否已记录

        Args:
            version: 版本号

        Returns:
            是否已记录
        """
        count = self.db.query(SystemUpdateLog).filter(SystemUpdateLog.version == version).count()
        return count > 0

    def get_update_count(self) -> int:
        """
        获取更新日志总数

        Returns:
            记录总数
        """
        return self.db.query(SystemUpdateLog).count()

    def _build_version_description(self, version_data: dict) -> str:
        """从版本数据构建完整描述文本"""
        description = version_data["description"]
        if version_data.get("features"):
            features_text = "\n".join(f"- {feature}" for feature in version_data["features"])
            description = f"{description}\n\n更新内容:\n{features_text}"
        return description

    def _create_version_entry(self, version_data: dict, updated_by: str, seq: int = 0) -> SystemUpdateLog:
        """创建单条版本日志记录。

        `seq` 是版本在历史列表中的序号（升序）。同一天常有多个版本发布（如 1.18.2–1.18.7
        全部是 2026-10-25），若只用日期做 created_at，多条记录时间戳相同，
        `ORDER BY created_at DESC` 的顺序就不稳定，列表会出现 1.18.2 排在 1.18.3 前面。
        这里按序号加秒偏移，使 created_at 严格递增，倒序即等于语义化版本倒序。
        前端只显示日期，秒级偏移不可见。
        """
        description = self._build_version_description(version_data)
        log_entry = SystemUpdateLog(
            id=str(uuid.uuid4()),
            version=version_data["version"],
            description=description,
            updated_by=updated_by,
        )
        base = datetime.fromisoformat(version_data["date"] + "T00:00:00")
        log_entry.created_at = base + timedelta(seconds=max(0, seq))
        return log_entry

    def initialize_version_history(self, updated_by: str = "system", force: bool = False) -> Dict:
        """
        初始化版本历史数据
        如果数据库中没有更新日志记录，则从历史数据初始化

        Args:
            updated_by: 更新人标识
            force: 是否强制重新初始化（清空后重填）

        Returns:
            初始化结果统计
        """
        if force:
            # 强制重新初始化：清空所有记录（系统级操作，不受组织隔离限制）
            deleted = self.db.query(SystemUpdateLog).delete()
            safe_commit(self.db)
            logger.info("强制重新初始化：已删除 %s 条旧记录", deleted)

        # 检查是否已有记录
        existing_count = self.get_update_count()
        if existing_count > 0:
            logger.info("更新日志已存在 %s 条记录，跳过初始化", existing_count)
            return {
                "status": "skipped",
                "message": "更新日志已存在，跳过初始化",
                "existing_count": existing_count,
                "initialized_count": 0,
            }

        # 从历史数据创建记录
        initialized_count = 0
        for seq, version_data in enumerate(VERSION_HISTORY_DATA):
            log_entry = self._create_version_entry(version_data, updated_by, seq)
            self.db.add(log_entry)
            initialized_count += 1

        if initialized_count > 0:
            safe_commit(self.db)
            logger.info("版本历史初始化完成，共创建 %s 条记录", initialized_count)
        else:
            logger.info("所有版本历史记录已存在，无需初始化")

        return {
            "status": "success",
            "message": f"成功初始化 {initialized_count} 条版本历史记录",
            "initialized_count": initialized_count,
        }

    def sync_version_history(self, updated_by: str = "system") -> Dict:
        """
        同步版本历史数据：检查 VERSION_HISTORY_DATA 中是否有未记录的版本并补充。
        保留已有记录，仅补充缺失版本。

        Args:
            updated_by: 更新人标识

        Returns:
            同步结果统计
        """
        # 一次性取出已记录版本，避免对 97 个版本各查一次库（启动路径上这很贵）
        recorded = {row[0] for row in self.db.query(SystemUpdateLog.version).all()}

        synced_count = 0
        for seq, version_data in enumerate(VERSION_HISTORY_DATA):
            if version_data["version"] not in recorded:
                log_entry = self._create_version_entry(version_data, updated_by, seq)
                self.db.add(log_entry)
                synced_count += 1

        if synced_count > 0:
            safe_commit(self.db)
            logger.info("版本历史同步完成，共补充 %s 条记录", synced_count)
        else:
            logger.info("版本历史已是最新，无需同步")

        return {
            "status": "success",
            "message": f"同步完成，共补充 {synced_count} 条版本历史记录",
            "synced_count": synced_count,
        }

    def check_and_record_version_change(
        self,
        current_version: str,
        updated_by: str = "system",
    ) -> Optional[Dict]:
        """
        检查版本变更并自动记录

        Args:
            current_version: 当前版本号（从version.json读取）
            updated_by: 更新人标识

        Returns:
            如果版本变更被记录，返回变更信息；否则返回None
        """
        latest = self.get_latest_update()

        if latest is None:
            # 没有任何记录，初始化历史
            result = self.initialize_version_history(updated_by)
            return {
                "action": "initialize",
                "result": result,
            }

        # 老库补齐：历史数据源会随版本新增条目（应用内日志曾长期停在 1.1.1），
        # 只靠"检测版本变化"只会补记当前这一条，中间版本仍缺失。这里每次启动做一次
        # 幂等同步，缺失的版本会被补上；已存在的不动。
        sync_result = self.sync_version_history(updated_by)
        synced_count = sync_result.get("synced_count", 0)

        if latest.version != current_version:
            # 版本发生变化，查找版本描述
            description = "系统更新"
            for v_data in VERSION_HISTORY_DATA:
                if v_data["version"] == current_version:
                    description = self._build_version_description(v_data)
                    break

            # 记录更新
            self.record_update(
                version=current_version,
                description=description,
                updated_by=updated_by,
            )

            logger.info("检测到版本变更: %s -> %s", latest.version, current_version)
            return {
                "action": "record_change",
                "old_version": latest.version,
                "new_version": current_version,
                "synced_count": synced_count,
            }

        if synced_count:
            logger.info("版本未变更，已补齐 %s 条缺失的历史版本记录", synced_count)
        return None  # 版本未变更
