"""
系统备份服务（增强版）
新增功能：增量备份、备份验证、备份加密（AES-256）、备份压缩级别配置
"""

import base64
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class BackupRestoreError(Exception):
    """备份恢复失败异常"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class BackupRecord:
    """备份记录"""

    def __init__(
        self,
        backup_id: int,
        file_name: str,
        file_path: str,
        file_size: int,
        description: str,
        created_at: datetime,
        backup_type: str = "full",  # full, incremental
        checksum: Optional[str] = None,
    ):
        self.backup_id = backup_id
        self.file_name = file_name
        self.file_path = file_path
        self.file_size = file_size
        self.description = description
        self.created_at = created_at
        self.backup_type = backup_type
        self.checksum = checksum


class BackupService:
    """系统备份服务"""

    def __init__(self, db: Session, backup_dir: str = None):
        self.db = db
        # 使用配置中的备份目录或动态计算用户可写路径
        if backup_dir is None:
            from app.utils.paths import get_backup_path

            self.backup_dir = str(get_backup_path())
        else:
            self.backup_dir = backup_dir
        # 数据库路径使用统一的路径工具模块
        from app.utils.paths import get_database_path

        self.database_path = str(get_database_path().absolute())
        # 上传目录也使用动态路径
        from app.utils.paths import get_uploads_path

        self.uploads_dir = str(get_uploads_path())

        # 确保备份目录存在
        os.makedirs(self.backup_dir, exist_ok=True)

        # 增量备份配置
        self.incremental_enabled = os.getenv("INCREMENTAL_BACKUP_ENABLED", "true").lower() == "true"
        self.compression_level = int(os.getenv("BACKUP_COMPRESSION_LEVEL", "6"))  # 0-9
        self.last_backup_manifest = self._load_last_manifest()

    def _validate_path(self, file_path: str) -> bool:
        """
        验证路径安全性，防止路径遍历攻击

        Args:
            file_path: 要验证的文件路径

        Returns:
            路径是否安全
        """
        try:
            # 规范化路径，解析符号链接
            real_path = Path(file_path).resolve()
            allowed_dir = Path(self.uploads_dir).resolve()

            # 确保路径在允许的目录内
            return real_path.is_relative_to(allowed_dir)
        except Exception as e:
            logger.warning(f"路径验证失败: {file_path}, 错误: {e}")
            return False

    # ── 加密工具 ────────────────────────────────────────────────

    _ENCRYPTED_MARKER = b"MRRMS_BACKUP_ENCRYPTED_V1"

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """使用 PBKDF2 从密码派生 AES-256 密钥（Fernet 兼容）。"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    @staticmethod
    def _encrypt_file(file_path: str, password: str) -> None:
        """使用 AES-256（Fernet）加密文件，原地替换。"""
        salt = os.urandom(16)
        key = BackupService._derive_key(password, salt)
        fernet = Fernet(key)

        with open(file_path, "rb") as f:
            plaintext = f.read()

        encrypted = fernet.encrypt(plaintext)

        with open(file_path, "wb") as f:
            f.write(BackupService._ENCRYPTED_MARKER)
            f.write(salt)
            f.write(encrypted)

    @staticmethod
    def _is_encrypted(file_path: str) -> bool:
        """检测备份文件是否为加密格式。"""
        with open(file_path, "rb") as f:
            return f.read(len(BackupService._ENCRYPTED_MARKER)) == BackupService._ENCRYPTED_MARKER

    @staticmethod
    def _decrypt_to_temp(file_path: str, password: str) -> str:
        """解密备份文件到临时文件，返回临时文件路径。密码错误时抛出 ValueError。

        不解密到原文件位置（保留原始加密备份以防后续恢复步骤失败）。
        """
        with open(file_path, "rb") as f:
            marker = f.read(len(BackupService._ENCRYPTED_MARKER))
            if marker != BackupService._ENCRYPTED_MARKER:
                raise ValueError("文件不是加密格式")
            salt = f.read(16)
            encrypted = f.read()

        key = BackupService._derive_key(password, salt)
        fernet = Fernet(key)
        try:
            plaintext = fernet.decrypt(encrypted)
        except Exception:
            raise ValueError("密码错误或备份文件已损坏") from None

        # 写入临时文件（保留原始加密备份不受影响）
        temp_fd, temp_path = tempfile.mkstemp(suffix=".zip", prefix="decrypted_backup_")
        with os.fdopen(temp_fd, "wb") as f:
            f.write(plaintext)
        return temp_path

    @staticmethod
    def _decrypt_file(file_path: str, password: str) -> None:
        """解密备份文件，原地替换为明文（已弃用，保留向后兼容）。

        新代码应使用 _decrypt_to_temp 以避免破坏原始加密备份。
        """
        temp_path = BackupService._decrypt_to_temp(file_path, password)
        shutil.move(temp_path, file_path)

    # ── 备份操作 ────────────────────────────────────────────────

    def create_backup(
        self, description: str = "手动备份", include_uploads: bool = True,
        password: str | None = None,
    ) -> BackupRecord:
        """
        创建系统备份

        Args:
            description: 备份描述
            include_uploads: 是否包含上传文件

        Returns:
            备份记录
        """
        # 生成备份文件名（毫秒级时间戳，避免同秒两次备份互相覆盖）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file_name = f"backup_{timestamp}_{int(datetime.now().timestamp() * 1000) % 1000:03d}.zip"
        backup_file_path = os.path.join(self.backup_dir, backup_file_name)

        # 磁盘空间预检（≥150MB，覆盖 db + uploads + zip 压缩余量；磁盘满载时提前失败，
        # 避免写出损坏的 .zip/.bak 文件）
        try:
            from app.core.database import check_disk_space

            disk = check_disk_space(min_mb=150)
            if not disk.get("sufficient", False):
                raise BackupRestoreError(
                    f"磁盘剩余空间不足（{disk.get('free_mb', -1)}MB < 150MB），备份已取消"
                )
        except BackupRestoreError:
            raise
        except Exception as _disk_err:  # pragma: no cover - 预检本身失败不阻塞备份
            logger.warning("磁盘空间预检失败: %s", _disk_err)

        # 一致性快照：使用 SQLite Backup API 复制在线数据库（自动合并 -wal 内容），
        # 替代裸文件拷贝 —— 并发写入/强制断电场景下保证备份包内数据库一致
        snapshot_path = None
        try:
            if os.path.exists(self.database_path):
                fd, snapshot_path = tempfile.mkstemp(suffix=".db", prefix="backup_snapshot_")
                os.close(fd)
                src = sqlite3.connect(self.database_path)
                dst = sqlite3.connect(snapshot_path)
                try:
                    with dst:
                        src.backup(dst)
                finally:
                    dst.close()
                    src.close()
        except Exception as _snap_err:
            logger.error("SQLite 一致性快照失败，回退 WAL checkpoint + 裸拷贝: %s", _snap_err)
            if snapshot_path:
                try:
                    os.remove(snapshot_path)
                except OSError:
                    pass
                snapshot_path = None
            # 回退：原 WAL checkpoint 逻辑
            try:
                _conn = sqlite3.connect(self.database_path)
                try:
                    _conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                finally:
                    _conn.close()
            except Exception as _wal_err:
                logger.warning("备份前 WAL checkpoint 失败（备份可能不完整）: %s", _wal_err)

        # 创建备份（zip 写入异常时 finally 统一清理快照，避免泄漏 backup_snapshot_*.db）
        try:
            with zipfile.ZipFile(backup_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # 备份数据库（优先一致性快照，回退主库文件）
                if snapshot_path and os.path.exists(snapshot_path):
                    zipf.write(snapshot_path, "data/rural_revitalization.db")
                elif os.path.exists(self.database_path):
                    zipf.write(self.database_path, "data/rural_revitalization.db")

                # 备份上传文件
                if include_uploads and os.path.exists(self.uploads_dir):
                    for root, dirs, files in os.walk(self.uploads_dir):
                        for file in files:
                            file_path = os.path.join(root, file)

                            # 验证路径安全性，防止路径遍历攻击
                            if not self._validate_path(file_path):
                                logger.warning(f"跳过不安全的路径: {file_path}")
                                continue

                            arcname = os.path.join("uploads", os.path.relpath(file_path, self.uploads_dir))
                            zipf.write(file_path, arcname)

                # 添加备份信息
                backup_info = {
                    "timestamp": timestamp,
                    "description": description,
                    "include_uploads": include_uploads,
                    "database_included": os.path.exists(self.database_path),
                    "created_at": datetime.now().isoformat(),
                }
                zipf.writestr("backup_info.json", str(backup_info))
        except Exception:
            # 备份写入失败：删除损坏的半成品 zip，避免残留进入备份列表干扰 cleanup_old_backups
            try:
                os.remove(backup_file_path)
            except OSError:
                pass
            raise
        finally:
            # 清理一致性快照临时文件（无论成功/异常，避免磁盘残留）
            if snapshot_path:
                try:
                    os.remove(snapshot_path)
                except OSError:
                    pass

        # ── 加密（可选） ──
        if password:
            self._encrypt_file(backup_file_path, password)
            logger.info("备份已加密: %s", backup_file_name)

        # 获取文件大小
        file_size = os.path.getsize(backup_file_path)

        # 保存备份记录到数据库
        config_key = f"backup_{timestamp}"
        config = SystemConfig(key=config_key, value=backup_file_path, description=f"备份: {description}")
        self.db.add(config)

        # 更新最后备份时间
        from app.services.system_config_service import SystemConfigService

        config_service = SystemConfigService(self.db)
        config_service.set("last_backup_time", datetime.now().isoformat())

        safe_commit(self.db)

        return BackupRecord(
            backup_id=config.id,
            file_name=backup_file_name,
            file_path=backup_file_path,
            file_size=file_size,
            description=description,
            created_at=datetime.now(),
        )

    def _safe_extractall(self, zipf: zipfile.ZipFile, dest_dir: str) -> None:
        """
        安全解压 ZIP 文件，防止 zip slip 路径穿越攻击。

        对包内每个成员的目标路径进行规范化校验，确保最终路径仍在
        dest_dir 内部，否则跳过该成员并记录警告。
        """
        dest_path = Path(dest_dir).resolve()
        for member in zipf.infolist():
            # 规范化成员名称中的反斜杠（Windows zip 兼容）
            member_name = member.filename.replace("\\", "/")
            # 拒绝绝对路径或包含 ".." 的成员
            if os.path.isabs(member_name) or ".." in member_name.split("/"):
                logger.warning(f"跳过不安全的 zip 成员: {member.filename}")
                continue
            target = (dest_path / member_name).resolve()
            try:
                target.relative_to(dest_path)
            except ValueError:
                logger.warning(f"跳过逃逸路径的 zip 成员: {member.filename}")
                continue
            zipf.extract(member, dest_dir)

    def _resolve_restore_source(self, backup_file_path: str, password: str | None = None):
        """处理加密检测和解密，返回(restore_source, decrypted_temp_path)"""
        if self._is_encrypted(backup_file_path):
            if not password:
                raise ValueError("备份文件已加密，请提供密码")
            logger.info("检测到加密备份，正在解密到临时文件...")
            decrypted_temp_path = self._decrypt_to_temp(backup_file_path, password)
            return decrypted_temp_path, decrypted_temp_path
        else:
            if password:
                logger.warning("提供了密码但备份文件未加密，密码将被忽略")
            return backup_file_path, None

    def _create_snapshots(self):
        """创建当前状态的快照"""
        snapshot_db_path = None
        snapshot_uploads_dir = None
        if os.path.exists(self.database_path):
            snapshot_db_path = f"{self.database_path}.snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy(self.database_path, snapshot_db_path)
        if os.path.exists(self.uploads_dir):
            snapshot_uploads_dir = f"{self.uploads_dir}_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copytree(self.uploads_dir, snapshot_uploads_dir)
        return snapshot_db_path, snapshot_uploads_dir

    def _restore_database_from_backup(self, temp_dir: str) -> bool:
        """从备份中恢复数据库（WAL 安全：先释放连接池再覆盖，清理残留 -wal/-shm）"""
        backup_db_path = os.path.join(temp_dir, "data", "rural_revitalization.db")
        if not os.path.exists(backup_db_path):
            return False
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        # 先释放数据库连接池：Windows 下 SQLite 持有文件句柄，
        # 不释放直接覆盖可能失败；且释放后残留的 -wal/-shm 可安全删除。
        try:
            from app.core.database import engine
            engine.dispose()
        except Exception as _dispose_err:
            logger.warning("释放连接池失败（不影响恢复）: %s", _dispose_err)
        # 删除残留的 WAL/SHM 文件，避免旧日志污染恢复后的数据库
        for suffix in ("-wal", "-shm"):
            stale_path = f"{self.database_path}{suffix}"
            if os.path.exists(stale_path):
                try:
                    os.unlink(stale_path)
                except OSError:
                    logger.warning("残留 %s 文件清理失败: %s", suffix, stale_path)
        shutil.copy(backup_db_path, self.database_path)
        return True

    def _restore_uploads_from_backup(self, temp_dir: str) -> bool:
        """从备份中恢复上传文件"""
        backup_uploads_dir = os.path.join(temp_dir, "uploads")
        if not os.path.exists(backup_uploads_dir):
            return False
        if os.path.exists(self.uploads_dir):
            shutil.rmtree(self.uploads_dir, ignore_errors=True)
        shutil.copytree(backup_uploads_dir, self.uploads_dir)
        return True

    def _cleanup_snapshots(self, snapshot_db_path, snapshot_uploads_dir):
        """恢复成功后删除快照"""
        if snapshot_db_path and os.path.exists(snapshot_db_path):
            try:
                os.unlink(snapshot_db_path)
            except FileNotFoundError:
                pass
        if snapshot_uploads_dir and os.path.exists(snapshot_uploads_dir):
            shutil.rmtree(snapshot_uploads_dir, ignore_errors=True)

    def _rollback_to_snapshots(self, snapshot_db_path, snapshot_uploads_dir):
        """恢复失败时回滚到快照"""
        if snapshot_db_path and os.path.exists(snapshot_db_path):
            if os.path.exists(self.database_path):
                try:
                    os.unlink(self.database_path)
                except FileNotFoundError:
                    pass
            shutil.copy(snapshot_db_path, self.database_path)
            try:
                os.unlink(snapshot_db_path)
            except FileNotFoundError:
                pass
        if snapshot_uploads_dir and os.path.exists(snapshot_uploads_dir):
            if os.path.exists(self.uploads_dir):
                shutil.rmtree(self.uploads_dir, ignore_errors=True)
            shutil.copytree(snapshot_uploads_dir, self.uploads_dir)
            shutil.rmtree(snapshot_uploads_dir, ignore_errors=True)

    def _cleanup_temp(self, temp_dir, decrypted_temp_path):
        """清理临时文件"""
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        if decrypted_temp_path and os.path.exists(decrypted_temp_path):
            try:
                os.unlink(decrypted_temp_path)
            except OSError:
                pass

    def restore_backup(self, backup_file_path: str, password: str | None = None) -> Dict:
        """
        从备份恢复系统（带事务保护 + 加密检测）

        Args:
            backup_file_path: 备份文件路径
            password: 加密密码（加密备份必需）

        Returns:
            恢复结果

        Raises:
            ValueError: 备份文件已加密但未提供密码，或密码错误
        """
        if not os.path.exists(backup_file_path):
            raise FileNotFoundError(f"备份文件不存在: {backup_file_path}")

        restore_source, decrypted_temp_path = self._resolve_restore_source(backup_file_path, password)
        temp_dir = tempfile.mkdtemp(prefix="restore_")
        snapshot_db_path, snapshot_uploads_dir = self._create_snapshots()

        try:
            with zipfile.ZipFile(restore_source, "r") as zipf:
                self._safe_extractall(zipf, temp_dir)

            database_restored = self._restore_database_from_backup(temp_dir)
            uploads_restored = self._restore_uploads_from_backup(temp_dir)

            self._cleanup_snapshots(snapshot_db_path, snapshot_uploads_dir)

            return {
                "success": True,
                "message": "系统恢复成功",
                "database_restored": database_restored,
                "uploads_restored": uploads_restored,
            }

        except Exception as e:
            self._rollback_to_snapshots(snapshot_db_path, snapshot_uploads_dir)
            raise BackupRestoreError(f"恢复失败，已回滚到原始状态: {e}")

        finally:
            self._cleanup_temp(temp_dir, decrypted_temp_path)

    def _query_backup_records(self):
        """查询备份记录（仅匹配备份文件条目，排除 backup_* 配置键）。

        备份记录 key 形如 backup_YYYYMMDD_HHMMSS 且值指向 .zip 文件；
        配置键（backup_interval_days / backup_target_dir 等）不参与备份管理。
        """
        return (
            self.db.query(SystemConfig)
            .filter(
                SystemConfig.key.like("backup_20%"),
                SystemConfig.value.like("%.zip"),
            )
            .order_by(SystemConfig.created_at.desc())
            .all()
        )

    def list_backups(self) -> List[BackupRecord]:
        """
        列出所有备份

        Returns:
            备份记录列表
        """
        backups = []

        # 查询数据库中的备份记录（仅 .zip 文件条目，排除 backup_* 配置键）
        configs = self._query_backup_records()

        for config in configs:
            if os.path.exists(config.value) and os.path.isfile(config.value):
                file_size = os.path.getsize(config.value)
                file_name = os.path.basename(config.value)

                backups.append(
                    BackupRecord(
                        backup_id=config.id,
                        file_name=file_name,
                        file_path=config.value,
                        file_size=file_size,
                        description=config.description,
                        created_at=config.created_at,
                    )
                )

        return backups

    def delete_backup(self, backup_id: int) -> bool:
        """
        删除备份

        Args:
            backup_id: 备份ID

        Returns:
            是否删除成功
        """
        config = self.db.query(SystemConfig).filter(SystemConfig.id == backup_id).first()

        if not config:
            return False

        # 删除备份文件
        if os.path.exists(config.value):
            try:
                os.unlink(config.value)
            except FileNotFoundError:
                pass

        # 删除数据库记录
        self.db.delete(config)
        safe_commit(self.db)

        return True

    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        清理旧备份

        Args:
            keep_count: 保留的备份数量

        Returns:
            删除的备份数量
        """
        # 获取所有备份（仅 .zip 文件条目，排除 backup_* 配置键）
        configs = self._query_backup_records()

        # 删除超出数量的旧备份
        deleted_count = 0
        for config in configs[keep_count:]:
            if os.path.exists(config.value):
                try:
                    os.unlink(config.value)
                except (FileNotFoundError, IsADirectoryError, PermissionError):
                    pass
            self.db.delete(config)
            deleted_count += 1

        if deleted_count > 0:
            safe_commit(self.db)

        return deleted_count

    def get_backup_size(self) -> int:
        """
        获取备份目录总大小

        Returns:
            总大小（字节）
        """
        try:
            total_size = 0
            if not os.path.exists(self.backup_dir):
                logger.warning(f"备份目录不存在: {self.backup_dir}")
                return 0

            for file in os.listdir(self.backup_dir):
                file_path = os.path.join(self.backup_dir, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
            return total_size
        except Exception as e:
            logger.error(f"计算备份大小失败: {e}")
            return 0

    # ==================== 增量备份功能 ====================

    def _load_last_manifest(self) -> Optional[Dict]:
        """加载最后一次备份的清单"""
        try:
            manifest_file = os.path.join(self.backup_dir, "last_manifest.json")
            if os.path.exists(manifest_file):
                with open(manifest_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"加载备份清单失败: {e}")
            return None

    def _save_manifest(self, manifest: Dict):
        """保存备份清单"""
        try:
            manifest_file = os.path.join(self.backup_dir, "last_manifest.json")
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存备份清单失败: {e}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件SHA256哈希"""
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败 {file_path}: {e}")
            return ""

    def _get_file_manifest(self, directory: str) -> Dict[str, Dict]:
        """获取目录下所有文件的清单（路径 -> {size, mtime, hash}）"""
        manifest = {}
        try:
            if not os.path.exists(directory):
                return manifest

            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not self._validate_path(file_path):
                        continue

                    try:
                        stat = os.stat(file_path)
                        rel_path = os.path.relpath(file_path, ".")
                        manifest[rel_path] = {
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                            "hash": self._calculate_file_hash(file_path),
                        }
                    except Exception as e:
                        logger.warning(f"获取文件信息失败 {file_path}: {e}")

            return manifest
        except Exception as e:
            logger.error(f"获取文件清单失败: {e}")
            return manifest

    def _build_current_manifest(self, include_uploads: bool) -> Dict:
        """构建当前文件清单（数据库 + 上传文件）"""
        current_manifest = {}
        if os.path.exists(self.database_path):
            current_manifest[self.database_path] = {
                "size": os.path.getsize(self.database_path),
                "mtime": os.path.getmtime(self.database_path),
                "hash": self._calculate_file_hash(self.database_path),
            }
        if include_uploads:
            uploads_manifest = self._get_file_manifest(self.uploads_dir)
            current_manifest.update(uploads_manifest)
        return current_manifest

    def _find_changed_files(self, current_manifest: Dict) -> List[str]:
        """比较当前清单与上次备份，找出变更的文件列表"""
        if not self.last_backup_manifest:
            return list(current_manifest.keys())
        changed_files = []
        for file_path, file_info in current_manifest.items():
            last_info = self.last_backup_manifest.get(file_path)
            if not last_info or last_info["hash"] != file_info["hash"]:
                changed_files.append(file_path)
        return changed_files

    def _write_incremental_backup_zip(
        self, backup_file_path: str, changed_files: List[str],
        current_manifest: Dict, timestamp: str, description: str,
        include_uploads: bool,
    ):
        """写入增量备份 ZIP 文件"""
        with zipfile.ZipFile(
            backup_file_path,
            "w",
            zipfile.ZIP_DEFLATED,
            compresslevel=self.compression_level,
        ) as zipf:
            for file_path in changed_files:
                if os.path.exists(file_path):
                    try:
                        arcname = os.path.relpath(file_path)
                    except ValueError:
                        arcname = os.path.basename(file_path)
                    zipf.write(file_path, arcname)

            backup_info = {
                "timestamp": timestamp,
                "description": description,
                "backup_type": "incremental",
                "include_uploads": include_uploads,
                "changed_files": len(changed_files),
                "created_at": datetime.now().isoformat(),
                "manifest": current_manifest,
            }
            zipf.writestr(
                "backup_info.json",
                json.dumps(backup_info, indent=2, ensure_ascii=False),
            )

    def _save_incremental_backup_record(
        self, backup_file_path: str, description: str,
        changed_files: List[str], timestamp: str,
    ):
        """保存增量备份记录到数据库"""
        file_size = os.path.getsize(backup_file_path)
        config_key = f"backup_incremental_{timestamp}"
        config = SystemConfig(
            key=config_key,
            value=backup_file_path,
            description=f"增量备份: {description} ({len(changed_files)}个文件)",
        )
        self.db.add(config)

        from app.services.system_config_service import SystemConfigService
        config_service = SystemConfigService(self.db)
        try:
            config_service.set("last_backup_time", datetime.now().isoformat())
        except Exception as e:
            logger.warning(f"更新last_backup_time失败，尝试更新: {e}")
            existing = self.db.query(SystemConfig).filter(SystemConfig.key == "last_backup_time").first()
            if existing:
                existing.value = datetime.now().isoformat()
                existing.updated_at = datetime.now()

        safe_commit(self.db)
        return config, file_size

    def create_incremental_backup(self, description: str = "增量备份", include_uploads: bool = True) -> Dict:
        """
        创建增量备份（仅备份变更的文件）

        Args:
            description: 备份描述
            include_uploads: 是否包含上传文件

        Returns:
            备份结果
        """
        if not self.incremental_enabled:
            logger.warning("增量备份未启用，执行完整备份")
            result = self.create_backup(description, include_uploads)
            if result:
                return {
                    "status": "success",
                    "backup_id": result.backup_id,
                    "file_name": result.file_name,
                    "file_path": result.file_path,
                    "file_size": result.file_size,
                    "backup_type": "full",
                    "description": description,
                    "created_at": result.created_at.isoformat(),
                }
            else:
                return {"status": "error", "message": "创建完整备份失败"}

        logger.info("开始创建增量备份...")

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file_name = f"backup_incremental_{timestamp}.zip"
            backup_file_path = os.path.join(self.backup_dir, backup_file_name)

            current_manifest = self._build_current_manifest(include_uploads)
            changed_files = self._find_changed_files(current_manifest)

            if not changed_files:
                logger.info("没有文件变更，跳过增量备份")
                return {
                    "status": "skipped",
                    "message": "没有文件变更",
                    "changed_files": 0,
                }

            logger.info(f"发现 {len(changed_files)} 个变更文件")

            self._write_incremental_backup_zip(
                backup_file_path, changed_files, current_manifest,
                timestamp, description, include_uploads,
            )

            self._save_manifest(current_manifest)
            self.last_backup_manifest = current_manifest

            config, file_size = self._save_incremental_backup_record(
                backup_file_path, description, changed_files, timestamp,
            )

            logger.info(f"增量备份完成: {backup_file_name} ({file_size / 1024 / 1024:.2f}MB)")

            return {
                "status": "success",
                "backup_id": config.id,
                "file_name": backup_file_name,
                "file_path": backup_file_path,
                "file_size": file_size,
                "backup_type": "incremental",
                "changed_files": len(changed_files),
                "description": description,
                "created_at": datetime.now().isoformat(),
            }

        except Exception as e:
            error_msg = f"创建增量备份失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

    def verify_backup(self, backup_file_path: str) -> Dict:
        """
        验证备份文件完整性

        Args:
            backup_file_path: 备份文件路径

        Returns:
            验证结果
        """
        logger.info(f"验证备份文件: {backup_file_path}")

        try:
            if not os.path.exists(backup_file_path):
                return {"status": "error", "message": "备份文件不存在"}

            # 计算文件哈希
            file_hash = self._calculate_file_hash(backup_file_path)

            # 加密备份无法直接验证内容，需先通过恢复流程解密
            if self._is_encrypted(backup_file_path):
                return {
                    "status": "error",
                    "message": "备份文件已加密，无法直接验证内容（请通过恢复流程输入密码后验证）",
                    "file_hash": file_hash,
                    "encrypted": True,
                }

            # 尝试打开ZIP文件
            with zipfile.ZipFile(backup_file_path, "r") as zipf:
                # 测试ZIP文件完整性
                bad_file = zipf.testzip()
                if bad_file:
                    return {
                        "status": "error",
                        "message": f"ZIP文件损坏: {bad_file}",
                    }

                # 读取备份信息
                try:
                    backup_info_data = zipf.read("backup_info.json")
                    backup_info = json.loads(backup_info_data)
                except Exception:
                    backup_info = None

                # 获取文件列表
                file_list = zipf.namelist()

            # 验证数据库文件（如果存在）
            db_verified = False
            if "data/rural_revitalization.db" in file_list:
                # 提取数据库文件到临时位置
                temp_dir = tempfile.mkdtemp(prefix="verify_")

                try:
                    with zipfile.ZipFile(backup_file_path, "r") as zipf:
                        zipf.extract("data/rural_revitalization.db", temp_dir)

                    temp_db_path = os.path.join(temp_dir, "data/rural_revitalization.db")

                    # 验证数据库完整性
                    conn = sqlite3.connect(temp_db_path)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    result = cursor.fetchone()
                    conn.close()

                    db_verified = result and result[0] == "ok"

                finally:
                    # 清理临时文件
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)

            return {
                "status": "ok",
                "message": "备份文件验证通过",
                "file_hash": file_hash,
                "file_count": len(file_list),
                "backup_info": backup_info,
                "database_verified": db_verified,
            }

        except Exception as e:
            error_msg = f"验证备份失败: {e}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

    def get_backup_statistics(self) -> Dict:
        """获取备份统计信息"""
        try:
            backups = self.list_backups()

            total_size = sum(b.file_size for b in backups)
            full_backups = [b for b in backups if b.backup_type == "full"]
            incremental_backups = [b for b in backups if b.backup_type == "incremental"]

            return {
                "total_backups": len(backups),
                "full_backups": len(full_backups),
                "incremental_backups": len(incremental_backups),
                "total_size": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "oldest_backup": (backups[-1].created_at.isoformat() if backups else None),
                "newest_backup": backups[0].created_at.isoformat() if backups else None,
            }

        except Exception as e:
            logger.error(f"获取备份统计失败: {e}")
            return {"status": "error", "message": str(e)}


def get_backup_service(db: Session = None) -> "BackupService":
    """
    获取备份服务实例。

    如果传入了 db session，则每次返回绑定该 session 的新实例（避免复用过期
    session）。仅当 db=None 且需要一个无 session 的轻量实例时，才使用全局
    缓存（仅用于读取备份目录等不涉及数据库写入的场景）。
    """
    if db is not None:
        return BackupService(db)

    # db=None 时才使用全局缓存（仅限只读场景，如 download/preview）
    global _backup_service_no_db
    if _backup_service_no_db is None:
        _backup_service_no_db = BackupService(None)
    return _backup_service_no_db


# 全局无 db 缓存实例（仅供只读路由使用，延迟初始化）
_backup_service_no_db = None

# 使用 get_backup_service() 获取服务实例（延迟初始化）
# 不要在这里直接实例化，以避免模块导入时的副作用
