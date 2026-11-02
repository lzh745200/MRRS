"""
版本管理服务
功能：管理系统版本、升级、回滚
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class VersionService:
    """版本管理服务"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.version_file = self.base_dir / "version.json"
        self.history_file = self.base_dir / "data" / "version_history.json"
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"创建版本历史目录失败: {e}")

        # 当前版本信息
        self.current_version = self._load_current_version()

    def _record_update_log_sync(self, version: str, description: str) -> None:
        """同步方法：记录更新日志到数据库"""
        try:
            from app.core.database import SessionLocal
            from app.services.update_log_service import UpdateLogService

            db = SessionLocal()
            try:
                update_service = UpdateLogService(db)
                update_service.record_update(
                    version=version,
                    description=description,
                    updated_by="system",
                )
            finally:
                db.close()
        except Exception:
            logger.warning("记录更新日志到数据库失败", exc_info=True)

    def _load_current_version(self) -> Dict:
        """加载当前版本信息"""
        try:
            if self.version_file.exists():
                with open(self.version_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                default_version = {
                    "version": settings.PROJECT_VERSION,
                    "build": datetime.now().strftime("%Y%m%d"),
                    "release_date": datetime.now().strftime("%Y-%m-%d"),
                    "description": "全面优化版本 - 性能提升、安全加固、UI体验改善",
                }
                self._save_version(default_version)
                return default_version
        except Exception as e:
            logger.error("加载版本信息失败: %s", e)
            return {
                "version": "unknown",
                "build": "unknown",
                "release_date": "unknown",
                "description": "版本信息加载失败",
            }

    def _save_version(self, version_info: Dict):
        """保存版本信息"""
        try:
            with open(self.version_file, "w", encoding="utf-8") as f:
                json.dump(version_info, f, indent=2, ensure_ascii=False)
            logger.info("版本信息已保存: %s", version_info["version"])
        except Exception as e:
            logger.error("保存版本信息失败: %s", e)

    def _load_history(self) -> List[Dict]:
        """加载版本历史"""
        try:
            if self.history_file.exists():
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                return []
        except Exception as e:
            logger.error("加载版本历史失败: %s", e)
            return []

    def _save_history(self, history: List[Dict]):
        """保存版本历史"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("保存版本历史失败: %s", e)

    def get_current_version(self) -> Dict:
        """获取当前版本"""
        return self.current_version.copy()

    def get_version_history(self, limit: int = 10) -> List[Dict]:
        """获取版本历史"""
        history = self._load_history()
        return history[-limit:][::-1]  # 返回最近的N个版本，倒序

    def check_version_change(self) -> Optional[Dict]:
        """检测版本变更"""
        try:
            config_version = settings.PROJECT_VERSION

            # 比较版本
            if config_version != self.current_version.get("version"):
                return {
                    "changed": True,
                    "old_version": self.current_version.get("version"),
                    "new_version": config_version,
                }
            else:
                return {"changed": False, "version": config_version}

        except Exception as e:
            logger.error("检测版本变更失败: %s", e)
            return None

    def upgrade(
        self,
        new_version: str,
        description: str = "",
        backup_before_upgrade: bool = True,
    ) -> Dict:
        """
        执行版本升级

        Args:
            new_version: 新版本号
            description: 升级说明
            backup_before_upgrade: 升级前是否备份

        Returns:
            升级结果
        """
        logger.info("开始升级到版本 %s...", new_version)

        try:
            old_version = self.current_version.get("version")

            # 1. 备份数据库
            backup_path = None
            if backup_before_upgrade:
                logger.info("正在备份数据库...")
                from app.services.backup_service import get_backup_service

                backup_record = get_backup_service().create_backup(
                    description=f"升级前备份 ({old_version} -> {new_version})"
                )
                if backup_record:
                    backup_path = backup_record.file_path if hasattr(backup_record, "file_path") else None
                    logger.info("数据库备份成功: %s", backup_path)
                else:
                    logger.warning("数据库备份失败，继续升级")

            # 2. 执行数据库迁移（如果需要）
            logger.info("检查数据库迁移...")
            migration_result = self._run_migrations(old_version, new_version)

            # 3. 更新配置文件（如果需要）
            logger.info("更新配置文件...")
            config_result = self._update_config(old_version, new_version)

            # 4. 更新版本信息
            new_version_info = {
                "version": new_version,
                "build": datetime.now().strftime("%Y%m%d"),
                "release_date": datetime.now().strftime("%Y-%m-%d"),
                "description": description or f"从 {old_version} 升级",
                "upgraded_at": datetime.now().isoformat(),
                "upgraded_from": old_version,
                "backup_path": backup_path,
            }
            self._save_version(new_version_info)
            self.current_version = new_version_info

            # 5. 记录升级历史
            history = self._load_history()
            history.append(
                {
                    "action": "upgrade",
                    "old_version": old_version,
                    "new_version": new_version,
                    "timestamp": datetime.now().isoformat(),
                    "description": description,
                    "backup_path": backup_path,
                    "migration_result": migration_result,
                    "config_result": config_result,
                }
            )
            self._save_history(history)

            # 6. 记录到系统更新日志（数据库）- 使用线程池避免阻塞事件循环
            # 注意：此方法必须由 async 函数调用，使用 asyncio.to_thread
            # 当前为 sync 方法，延迟到外部调用时记录

            logger.info("升级完成: %s -> %s", old_version, new_version)

            return {
                "status": "success",
                "old_version": old_version,
                "new_version": new_version,
                "backup_path": backup_path,
                "migration_result": migration_result,
                "config_result": config_result,
            }

        except Exception as e:
            error_msg = f"升级失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

    def rollback(self, target_version: Optional[str] = None) -> Dict:
        """
        回滚到指定版本

        Args:
            target_version: 目标版本号，如果为None则回滚到上一个版本

        Returns:
            回滚结果
        """
        logger.info("开始回滚到版本 %s...", target_version or "上一个版本")

        try:
            current_version = self.current_version.get("version")
            history = self._load_history()

            if not history:
                return {"status": "error", "message": "没有可回滚的版本"}

            # 查找目标版本
            if target_version:
                # 查找指定版本的备份
                target_record = None
                for record in reversed(history):
                    if record.get("new_version") == target_version:
                        target_record = record
                        break

                if not target_record:
                    return {
                        "status": "error",
                        "message": f"未找到版本 {target_version} 的升级记录",
                    }
            else:
                # 回滚到上一个版本
                target_record = history[-1]
                target_version = target_record.get("old_version")

            # 检查备份文件
            backup_path = target_record.get("backup_path")
            if not backup_path or not Path(backup_path).exists():
                return {
                    "status": "error",
                    "message": f"未找到版本 {target_version} 的备份文件",
                }

            # 恢复备份
            logger.info("正在恢复备份: %s", backup_path)
            from app.services.backup_service import BackupRestoreError, get_backup_service

            try:
                restore_result = get_backup_service().restore_backup(Path(backup_path).name)
            except BackupRestoreError as e:
                return {
                    "status": "error",
                    "message": e.message,
                }

            if not restore_result.get("success"):
                return {
                    "status": "error",
                    "message": f"恢复备份失败: {restore_result.get('message')}",
                }

            # 更新版本信息
            rollback_version_info = {
                "version": target_version,
                "build": datetime.now().strftime("%Y%m%d"),
                "release_date": datetime.now().strftime("%Y-%m-%d"),
                "description": f"从 {current_version} 回滚",
                "rolled_back_at": datetime.now().isoformat(),
                "rolled_back_from": current_version,
            }
            self._save_version(rollback_version_info)
            self.current_version = rollback_version_info

            # 记录回滚历史
            history.append(
                {
                    "action": "rollback",
                    "old_version": current_version,
                    "new_version": target_version,
                    "timestamp": datetime.now().isoformat(),
                    "backup_path": backup_path,
                }
            )
            self._save_history(history)

            # 记录到系统更新日志（数据库）- 由外部 async 函数调用时处理

            logger.info("回滚完成: %s -> %s", current_version, target_version)

            return {
                "status": "success",
                "old_version": current_version,
                "new_version": target_version,
                "backup_path": backup_path,
            }

        except Exception as e:
            error_msg = f"回滚失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

    def _run_migrations(self, old_version: str, new_version: str) -> Dict:
        """执行数据库迁移"""
        try:
            # 这里可以根据版本号执行特定的迁移脚本
            # 目前使用自动迁移（main.py中的_migrate_missing_columns）
            logger.info("数据库迁移: %s -> %s", old_version, new_version)

            # 触发自动迁移
            from app.core.database import engine
            from app.models.base import Base as ModelBase

            # 导入所有模型
            import app.models  # noqa: F401

            # 执行自动迁移
            from app.core.migration_helper import migrate_missing_columns

            migrate_missing_columns(engine, ModelBase)

            return {"status": "success", "message": "数据库迁移完成"}

        except Exception as e:
            error_msg = f"数据库迁移失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

    def _update_config(self, old_version: str, new_version: str) -> Dict:
        """更新配置文件"""
        try:
            # 这里可以根据版本号更新配置文件
            # 目前不需要特殊处理
            logger.info("配置更新: %s -> %s", old_version, new_version)

            return {"status": "success", "message": "配置更新完成"}

        except Exception as e:
            error_msg = f"配置更新失败: {e}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

    def compare_versions(self, version1: str, version2: str) -> int:
        """
        比较两个版本号

        Returns:
            1: version1 > version2
            0: version1 == version2
            -1: version1 < version2
        """
        try:
            v1_parts = [int(x) for x in version1.split(".")]
            v2_parts = [int(x) for x in version2.split(".")]

            # 补齐长度
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts += [0] * (max_len - len(v1_parts))
            v2_parts += [0] * (max_len - len(v2_parts))

            # 逐位比较
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1

            return 0

        except Exception as e:
            logger.error("版本比较失败: %s", e)
            return 0


# 全局实例
version_service = VersionService()
