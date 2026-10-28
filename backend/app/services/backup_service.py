"""
系统备份服务（增强版）
新增功能：增量备份、备份验证、备份加密（AES-256）、备份压缩级别配置
"""

import ast
import base64
import hashlib
import json
import logging
import time
import uuid
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig
from app.core.maintenance import maintenance_window
from app.utils.upload_helper import read_zip_member
from app.core.transaction import retry_on_deadlock, safe_commit
from app.utils.time_utils import as_utc, utcnow
from app.utils.env_utils import parse_env_int

logger = logging.getLogger(__name__)

# W12-T045: 手动备份 / upload-restore 最低剩余空间阈值（500MB）
BACKUP_MIN_FREE_MB = 500


class BackupRestoreError(Exception):
    """备份恢复失败异常"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class BackupIncompleteError(Exception):
    """备份包不完整异常（如未包含数据库文件），视为备份失败"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# ── PII 密钥指纹（备份可迁移性，批次 2）─────────────────────────────────
# 背景（历史 P1）：换机/重装后 ENCRYPTION_KEY 不同，备份包里的 9 列 AES-SIV
# 密文将永久不可解，而备份包不含任何密钥线索、恢复时也无从判断。
# 取舍：**不把密钥写进备份**（写进去等于把密钥随包扩散，离线介质更易泄漏），
# 只写 SHA-256 前 16 位指纹（``app.core.pii_crypto.key_fingerprint``，与
# 自检「PII 密钥指纹」同一口径），恢复时比对；不一致默认拒绝，可显式强制。
KEY_FINGERPRINT_FIELD = "key_fingerprint"

KEY_MISMATCH_MESSAGE = (
    "备份来自不同密钥的机器，恢复后敏感字段（身份证号/联系电话等）将不可读；"
    "如确认使用旧密钥，请先导入密钥或使用强制恢复（allow_key_mismatch=true）。"
)


class BackupKeyMismatchError(BackupRestoreError):
    """备份包的 PII 密钥指纹与本机不一致（跨机/重装后恢复）。

    Attributes:
        backup_fingerprint: 备份包记录的指纹（16 位十六进制）
        current_fingerprint: 本机当前密钥指纹
    """

    def __init__(
        self,
        message: str = KEY_MISMATCH_MESSAGE,
        backup_fingerprint: Optional[str] = None,
        current_fingerprint: Optional[str] = None,
    ):
        super().__init__(message)
        self.backup_fingerprint = backup_fingerprint
        self.current_fingerprint = current_fingerprint


def _current_key_fingerprint() -> Optional[str]:
    """本机 PII 密钥指纹；密钥不可用/读取失败时返回 None（不阻断备份/恢复）。"""
    try:
        from app.core.pii_crypto import key_fingerprint

        return key_fingerprint()
    except Exception:
        logger.warning("读取 PII 密钥指纹失败，本次跳过密钥一致性标记/校验", exc_info=True)
        return None


def _parse_backup_info(raw: Any) -> Optional[Dict[str, Any]]:
    """解析 ``backup_info.json``（兼容历史 ``str(dict)`` 写法）。

    历史全量备份用 ``zipf.writestr(..., str(backup_info))`` 写入，是 Python
    dict 的 repr（单引号），``json.loads`` 必然失败；早期读取方（preview /
    verify）因此一直拿不到元信息。这里先按 JSON 解析，失败再退回
    ``ast.literal_eval``，两种格式都能读；非对象/不可解析一律返回 None
    （调用方按"旧备份、无指纹"兼容处理）。
    """
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return None
    return parsed if isinstance(parsed, dict) else None


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


def backups_share_volume_with_database(db_path: str, backup_dir: str) -> Optional[bool]:
    """备份目录是否与数据库**同一物理卷**（C1 数据安全可见化，2026-09-12）。

    为什么需要：备份与数据库同盘时，断电/盘损会把"数据 + 备份"一起带走，
    恢复无从谈起。配套约定要求 `backup_target_dir` 指向独立物理盘/U 盘，
    但此前没有任何机制让"没配"这件事可见。

    判定方式（跨平台、无外部依赖）：
    - 两条路径都存在 → 比较 ``os.stat().st_dev``（同一设备号即同卷，最可靠）；
    - 否则退回**路径前缀**判定：有盘符时比盘符（Windows），
      无盘符时比首层挂载点（POSIX，如 /data vs /mnt/usb）；
    - 既无盘符也不是绝对路径（相对路径）→ 返回 None（"未知"，
      **绝不猜成"安全"**）。

    注意：这里刻意用**原始路径**做前缀判定（不做 abspath）—— 否则 Windows 上
    `abspath("/data/x")` 会被补上盘符，POSIX 分支永远不可达，本地 100% 覆盖率
    门禁与 CI 行为会分叉。

    Returns:
        True 同卷（风险）／False 异卷（安全）／None 无法判定
    """
    if not db_path or not backup_dir:
        return None

    try:
        # 直接比较设备号：任一路径不存在/无权限即抛 OSError，落到下方前缀兜底。
        # （刻意不先用 os.path.exists 把关 —— 它会吞掉 OSError，
        #   使兜底分支永久不可达，本地覆盖率门禁与 CI 会分叉。）
        db_dev = os.stat(db_path).st_dev
        bk_dev = os.stat(backup_dir).st_dev
        return db_dev == bk_dev
    except OSError:
        pass

    db_drive = os.path.splitdrive(db_path)[0]
    bk_drive = os.path.splitdrive(backup_dir)[0]
    if db_drive or bk_drive:
        # Windows：盘符不同即不同物理卷（网络盘符各自独立）
        return db_drive.lower() == bk_drive.lower()

    db_norm = db_path.replace("\\", "/")
    bk_norm = backup_dir.replace("\\", "/")
    if not (db_norm.startswith("/") and bk_norm.startswith("/")):
        return None

    # POSIX：以首层挂载点近似（/data vs /mnt/usb）
    db_mount = "/" + db_norm.lstrip("/").split("/")[0]
    bk_mount = "/" + bk_norm.lstrip("/").split("/")[0]
    return db_mount == bk_mount


def _copy_database_with_retry(
    backup_db_path: str, database_path: str, db_coordinator
) -> None:
    """覆盖复制目标数据库，带 3 次退避重试。

    R10-F1（真实 HTTP 探测 2026-09-13，Windows 实测 Errno 22）：目标文件可能被
    杀软/资源管理器/在途请求短暂占用，瞬态占用不该让恢复整体失败；
    3 次均失败则 fail-loud 抛 BackupRestoreError（不静默半恢复）。
    """
    last_copy_err: Exception | None = None
    for attempt in range(3):
        try:
            if db_coordinator is not None:
                with db_coordinator.exclusive_write(timeout=120.0):
                    shutil.copy(backup_db_path, database_path)
            else:
                shutil.copy(backup_db_path, database_path)
            return
        except OSError as copy_err:
            last_copy_err = copy_err
            logger.warning(
                "恢复复制数据库失败（第 %d/3 次）: %s", attempt + 1, copy_err
            )
            time.sleep(0.5 * (attempt + 1))
    raise BackupRestoreError(
        f"恢复复制数据库失败（重试后仍被占用）: {last_copy_err}"
    )


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
        # 数据库路径：优先取当前会话实际绑定的引擎 URL（唯一可信来源），
        # 兜底 get_database_path()（其自身已按 DATABASE_URL 环境变量解析）。
        # 历史缺陷：仅按静态规则推断，打包 + Electron 注入环境下与真实
        # 在用库分叉，导致备份的是陈旧文件、恢复写回错误位置。
        self.database_path = str(self._resolve_database_path())
        # 上传目录同样使用运行时解析（与 files.py 写入目录一致）
        from app.utils.paths import get_runtime_uploads_path

        self.uploads_dir = str(get_runtime_uploads_path())

        # 确保备份目录存在
        os.makedirs(self.backup_dir, exist_ok=True)

        # 增量备份配置
        # ⚠️ 现状说明（W25 复核，2026-10-20）：``INCREMENTAL_BACKUP_ENABLED`` 目前
        # **只被** :meth:`create_incremental_backup` 读取，而该方法在生产代码中
        # **没有任何调度方/端点调用**（仅测试调用；``backup_scheduler``、``immediate_backup``、
        # ``system/backup`` 与 ``version_service`` 走的全是全量 ``create_backup``）。
        # 也就是说：把本开关设为 true **并不会**让系统自动做增量备份，默认值 true
        # 只是历史遗留。真正接线（调度分流 + 恢复链验证）属独立功能项；
        # 在那之前请勿把本开关当作"已启用增量备份"的依据。
        self.incremental_enabled = os.getenv("INCREMENTAL_BACKUP_ENABLED", "true").lower() == "true"
        # 压缩级别 0-9：非数字回退默认、越界收敛到合法区间。
        # 历史缺陷：裸 int() 在环境变量非数字时抛 ValueError → 每次构造
        # BackupService 即失败 → 备份创建/列表/清理整条链路不可用。
        self.compression_level = min(9, max(0, parse_env_int("BACKUP_COMPRESSION_LEVEL", 6)))
        self.last_backup_manifest = self._load_last_manifest()

    def _resolve_database_path(self) -> Path:
        """解析当前会话实际绑定的 SQLite 文件路径；无法解析时走路径工具兜底。"""
        try:
            bind = self.db.get_bind()
            url = str(bind.url)
        except Exception as exc:  # noqa: BLE001 - 兜底但必须留痕
            logger.warning('_resolve_database_path 兜底失败（已降级）: %s', exc, exc_info=True)
            url = ""
        from app.utils.paths import db_file_from_url

        candidate = db_file_from_url(url)
        if candidate is None:
            from app.utils.paths import get_database_path

            candidate = get_database_path()
        return candidate.absolute()

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

    def _ensure_disk_space(self, min_mb: int = BACKUP_MIN_FREE_MB) -> None:
        """磁盘空间预检（W12-T045：默认 ≥500MB；磁盘满载时提前失败，避免写出损坏的 .zip/.bak 文件）"""
        try:
            from app.core.database import check_disk_space

            disk = check_disk_space(min_mb=min_mb)
            if not disk.get("sufficient", False):
                raise BackupRestoreError(
                    f"磁盘剩余空间不足（{disk.get('free_mb', -1)}MB < {min_mb}MB），备份已取消"
                )
        except BackupRestoreError:
            raise
        except Exception as _disk_err:  # pragma: no cover - 预检本身失败不阻塞备份
            logger.warning("磁盘空间预检失败: %s", _disk_err)

    def _create_consistency_snapshot(self) -> Optional[str]:
        """使用 SQLite Backup API 生成一致性快照（自动合并 -wal 内容）。

        快照失败直接抛 BackupIncompleteError（R6，fail-loud）。原实现回退
        「WAL checkpoint + 裸拷贝主库」：此时仍留在 -wal 中、未合并的已提交
        事务会全部丢失，而备份包又能通过 CRC + integrity_check 校验——
        产出「陈旧但合法」的备份并被调度器标记成功，破坏灾备语义。
        宁可当天无可用备份（次日自动重试），也不可静默产出会丢数据的备份。
        """
        if not os.path.exists(self.database_path):
            # 主库不存在：交由上层按「备份未包含数据库文件」语义失败
            return None
        snapshot_path = None
        try:
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
            return snapshot_path
        except Exception as exc:
            if snapshot_path and os.path.exists(snapshot_path):
                try:
                    os.remove(snapshot_path)
                except OSError:
                    logger.debug("快照临时文件清理失败（残留于 %s）", snapshot_path)
            raise BackupIncompleteError(
                f"一致性快照失败，已中止备份（-wal 数据保持原样，不会丢失）: {exc}"
            ) from exc

    def _write_backup_zip(
        self, backup_file_path: str, snapshot_path: Optional[str],
        timestamp: str, description: str, include_uploads: bool,
    ) -> None:
        """写入备份 zip（原子落盘，架构评估 A2）。

        先写 ``.part`` 临时文件、成功后 ``os.replace`` 到最终路径——进程在
        写入中途被杀（断电/强杀，捕获不到异常）时不会在备份目录留下半截
        zip 被备份列表/cleanup 当作有效备份。异常路径删除 .part 半成品并
        清理快照，行为与原实现一致。
        """
        part_path = backup_file_path + ".part"
        try:
            with zipfile.ZipFile(part_path, "w", zipfile.ZIP_DEFLATED) as zipf:
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
                # PII 密钥指纹：跨机/重装后判断"备份里的密文还能不能解"。
                # 只写指纹（16 位十六进制），绝不写密钥材料本身；读不到指纹时
                # 省略该字段（保持旧包格式，恢复端按"无指纹"兼容处理）。
                _fp = _current_key_fingerprint()
                if _fp:
                    backup_info[KEY_FINGERPRINT_FIELD] = _fp
                # 写合法 JSON（历史用 str(dict)，preview/verify 的 json.loads 必然失败）
                zipf.writestr(
                    "backup_info.json",
                    json.dumps(backup_info, ensure_ascii=False, indent=2),
                )
            # 原子替换：最终路径要么不存在、要么是完整包
            os.replace(part_path, backup_file_path)
        except Exception:
            # 备份写入失败：删除 .part 半成品，避免残留进入备份列表干扰 cleanup_old_backups
            try:
                os.remove(part_path)
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

    def _verify_backup_recovery(self, backup_file_path: str) -> None:
        """恢复性校验（架构评估 C1）：备份必须"可被还原使用"，而非仅存在。

        此前仅校验 zip 内含数据库条目，无法发现 db 页损坏 / 成员 CRC 错误；
        "备份成功"但还原时才发现损坏是最坏故障模式（帮扶数据不可再采集）。
        校验内容：zip 结构 CRC（testzip）+ 库文件 SQLite integrity_check。
        失败即删包抛 BackupIncompleteError（fail-loud），避免坏备份挤占
        备份轮换名额造成"最新备份不可用"。

        调用时机：加密之前（明文 zip），故密码备份同样被校验。
        """
        fd, verify_db_path = tempfile.mkstemp(suffix=".db", prefix="backup_verify_")
        os.close(fd)
        try:
            try:
                with zipfile.ZipFile(backup_file_path, "r") as zf:
                    bad_member = zf.testzip()
                    if bad_member is not None:
                        raise BackupIncompleteError(f"备份包 CRC 校验失败: {bad_member}")
                    # R2 同族加固：原实现 zf.read 把整个库文件物化进内存后才落盘 ——
                    # 库文件可达 GB 级（本仓单机桌面长期运行的真实形态），备份校验
                    # 自己成了内存峰值点。改为 1MB 分块流式解压落盘，峰值与库大小无关。
                    with zf.open("data/rural_revitalization.db") as src, open(verify_db_path, "wb") as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
            except zipfile.BadZipFile as exc:
                raise BackupIncompleteError(f"备份包损坏（非有效 zip）: {exc}") from exc
            except KeyError as exc:
                raise BackupIncompleteError("备份包缺少数据库文件") from exc

            conn = sqlite3.connect(verify_db_path)
            try:
                try:
                    check_result = conn.execute("PRAGMA integrity_check").fetchone()[0]
                except sqlite3.DatabaseError as exc:
                    # 载荷非 SQLite / 页损坏：转成明确的备份失败，避免裸
                    # DatabaseError 以 500 形态逃逸（调用方对 BackupIncompleteError
                    # 有专门的失败语义处理）
                    raise BackupIncompleteError(
                        f"备份数据库完整性校验失败: {exc}"
                    ) from exc
            finally:
                conn.close()
            if check_result != "ok":
                raise BackupIncompleteError(f"备份数据库完整性校验失败: {check_result}")
        finally:
            try:
                os.remove(verify_db_path)
            except OSError:
                pass
        logger.info("备份恢复性校验通过: %s", os.path.basename(backup_file_path))

    # D1（架构评估）：备份是"长事务 + 多表写入"，与用户写操作争抢 SQLite 写锁时
    # 会以 database is locked 失败（busy_timeout 10s 用尽）。备份失败意味着当天
    # 没有可用备份，代价高，故此处做锁竞争退避重试（safe_commit 失败已 rollback，
    # 整个工作单元可安全重跑）。
    @retry_on_deadlock(max_retries=3, delay=1.0)
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
        # 生成备份文件名（毫秒级时间戳 + 短随机后缀：并发同毫秒创建时仅靠
        # 毫秒仍会互相覆盖并撞 system_configs 唯一键 — 2026-09-06 R8 并发
        # 探针实测三并发一个 500，故追加 uuid4 短码保证唯一）
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        unique_suffix = f"{now.microsecond // 1000:03d}_{uuid.uuid4().hex[:6]}"
        backup_file_name = f"backup_{timestamp}_{unique_suffix}.zip"
        backup_file_path = os.path.join(self.backup_dir, backup_file_name)

        self._ensure_disk_space()

        # 一致性快照：SQLite Backup API（自动合并 -wal 内容），失败回退 checkpoint + 裸拷贝
        snapshot_path = self._create_consistency_snapshot()

        self._write_backup_zip(
            backup_file_path, snapshot_path, timestamp, description, include_uploads
        )

        # 完整性校验：备份包必须包含数据库文件，否则视为备份失败（fail-loud，
        # 杜绝"备份成功"假象——历史上曾静默产出不含数据库的空包）
        try:
            with zipfile.ZipFile(backup_file_path, "r") as _zf:
                _has_db = "data/rural_revitalization.db" in _zf.namelist()
        except Exception as exc:  # noqa: BLE001 - 兜底但必须留痕
            logger.warning('create_backup 兜底失败（已降级）: %s', exc, exc_info=True)
            _has_db = False
        if not _has_db:
            try:
                os.remove(backup_file_path)
            except OSError:
                pass
            raise BackupIncompleteError(
                f"备份未能包含数据库文件（database_path={self.database_path}），已中止并删除半成品"
            )

        # 恢复性校验（架构评估 C1）：zip CRC + SQLite integrity_check——
        # 备份必须"可被还原使用"；失败删包抛错，避免坏备份进入轮换名单
        self._verify_backup_recovery(backup_file_path)

        # ── 加密（可选） ──
        if password:
            self._encrypt_file(backup_file_path, password)
            logger.info("备份已加密: %s", backup_file_name)

        # 获取文件大小
        file_size = os.path.getsize(backup_file_path)

        # 保存备份记录到数据库（key 携带毫秒后缀，与文件名同源，
        # 修复同秒两次备份触发 system_configs 唯一键冲突的 500）
        config_key = f"backup_{timestamp}_{unique_suffix}"
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
            # W18-B：created_at 是 UtcDateTime 列（UTC 语义），此前写本地 naive
            # datetime.now()，在 UTC+8 主机会落成"未来 8 小时"，备份列表时间虚高。
            created_at=utcnow(),
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
        """创建当前状态的快照（W2-T8：DB 快照走 Backup API 合并 WAL）"""
        snapshot_db_path = None
        snapshot_uploads_dir = None
        if os.path.exists(self.database_path):
            # 复用一致性快照（SQLite Backup API 自动合并 -wal；失败内部回退
            # checkpoint+拷贝）。返回 None 时回退裸拷贝主库文件。
            # R6 语义：一致性快照失败必须 fail-loud。裸拷贝主库文件不含 -wal 内容，
            # 会产出"看起来合法却丢数据"的陈旧快照，比直接失败危险得多。
            snapshot_db_path = self._create_consistency_snapshot()
            if not snapshot_db_path:
                raise BackupIncompleteError(
                    "一致性快照不可用，已中止备份（拒绝产出不含 WAL 内容的陈旧快照）"
                )
        if os.path.exists(self.uploads_dir):
            snapshot_uploads_dir = f"{self.uploads_dir}_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copytree(self.uploads_dir, snapshot_uploads_dir)
        return snapshot_db_path, snapshot_uploads_dir

    def _validate_backup_schema_version(self, backup_db_path: str) -> None:
        """恢复前置校验：备份库的 alembic 版本不得高于当前代码 head（W18-D7）。

        缺陷：原实现只校验 integrity_check。「新版本机器 → 旧版本机器」搬运备份包
        （上传恢复正是为此设计）后，备份库的 alembic_version 高于当前代码全部迁移，
        生产环境启动 alembic upgrade 直接 raise → **应用永久无法启动**，而恢复界面
        本身也在应用内 → 用户无法自助回退。
        """
        import sqlite3

        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        if not os.path.exists(backup_db_path):
            return  # 由调用方按"缺库"处理
        chk = sqlite3.connect(backup_db_path)
        try:
            row = chk.execute("SELECT version_num FROM alembic_version").fetchone()
            backup_rev = row[0] if row else None
        except sqlite3.OperationalError:
            backup_rev = None   # 无 alembic_version 表（极老备份）→ 按可升级处理
        finally:
            chk.close()
        if not backup_rev:
            return
        from app.utils.paths import get_project_backend_dir

        backend_dir = Path(get_project_backend_dir())
        cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
        # backend/alembic.ini 不含 script_location（由启动代码动态注入），
        # 这里必须显式给 —— 否则 from_config 抛 CommandError 被吞 → 校验静默失效
        cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        try:
            script_dir = ScriptDirectory.from_config(cfg)
            head = script_dir.get_current_head()
        except Exception:  # pragma: no cover - alembic 配置损坏属启动期问题
            logger.warning("恢复前置校验: 迁移链不可读，跳过版本比对", exc_info=True)
            return
        if not head:
            return
        # backup_rev 必须是当前脚本链上可定位的 revision（在链上 → 可升级）
        known = {rev.revision for rev in script_dir.walk_revisions()}
        if backup_rev not in known:
            msg = (
                "该备份来自更高版本（schema revision %s 不在当前程序的迁移链上，"
                "当前 head=%s）。请先升级本机程序后再恢复，或联系管理员。"
            ) % (backup_rev, head)
            raise BackupRestoreError(msg)

    def _restore_database_from_backup(self, temp_dir: str) -> bool:
        """从备份中恢复数据库（WAL 安全：先释放连接池再覆盖，清理残留 -wal/-shm）"""
        backup_db_path = os.path.join(temp_dir, "data", "rural_revitalization.db")
        if not os.path.exists(backup_db_path):
            return False
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        # 写协调器独占窗口: 与批量导入等 opt-in 写路径互斥, 避免恢复覆盖期间
        # 长写事务交错。注: 普通请求的小写事务不经此锁（SQLite 单写者 +
        # busy_timeout 兜底）, 恢复完成后仍建议重启后端以彻底隔离旧文件句柄。

        # R10-F1（真实 HTTP 探测 2026-09-13，Windows 实测 Errno 22）：先释放
        # 本服务持有的会话连接——请求级 get_db 会话在恢复期间仍 checkout 着
        # 目标数据库文件的连接（WAL 映射），Windows 上覆盖该文件必失败。
        # 释放后由下方 engine.dispose() 一并关闭池内连接。
        try:
            self.db.close()
        except Exception:  # pragma: no cover - 会话已关闭/为 Mock 时忽略
            logger.debug("恢复前关闭服务会话失败", exc_info=True)
        try:
            from app.core.database import engine, db_coordinator
            engine.dispose()
        except Exception as _dispose_err:
            logger.warning("释放连接池失败（不影响恢复）: %s", _dispose_err)
            db_coordinator = None
        try:
            # 删除残留的 WAL/SHM 文件，避免旧日志污染恢复后的数据库
            for suffix in ("-wal", "-shm"):
                stale_path = f"{self.database_path}{suffix}"
                if os.path.exists(stale_path):
                    try:
                        os.unlink(stale_path)
                    except OSError:
                        logger.warning("残留 %s 文件清理失败: %s", suffix, stale_path)
            # R10-F1：覆盖复制带 3 次退避重试——Windows 上目标文件可能被
            # 杀软/资源管理器/在途请求短暂占用，瞬态占用不该让恢复整体失败
            _copy_database_with_retry(backup_db_path, self.database_path, db_coordinator)
        finally:
            # copy 后再次 dispose: 清理恢复窗口期间新建的池连接,
            # 使后续请求重新打开已替换的数据库文件
            try:
                from app.core.database import engine as _engine
                _engine.dispose()
            except Exception as exc:  # noqa: BLE001 - 兜底但必须留痕
                logger.warning('_restore_database_from_backup 兜底失败（已降级）: %s', exc, exc_info=True)
                pass

        # T046：恢复后立即做一致性自检（fail-fast，防止损坏库被静默启用）
        try:
            chk = sqlite3.connect(self.database_path)
            try:
                row = chk.execute("PRAGMA integrity_check").fetchone()
                result = (row[0] if row else "unknown")
            finally:
                chk.close()
            if result != "ok":
                logger.error("恢复后完整性校验未通过: %s", result)
                return False
        except Exception as _chk_err:
            # fail-closed：无法证明健康即视为失败，禁止损坏库被静默启用
            logger.error("恢复后完整性校验执行异常，按失败处理: %s", _chk_err)
            return False

        return True

    def _restore_uploads_from_backup(self, temp_dir: str) -> bool:
        """从备份中恢复上传文件"""
        backup_uploads_dir = os.path.join(temp_dir, "uploads")
        if not os.path.exists(backup_uploads_dir):
            return False
        if os.path.exists(self.uploads_dir):
            shutil.rmtree(self.uploads_dir, ignore_errors=True)
        # dirs_exist_ok：rmtree 在 Windows 上可能因文件被占用而「部分删除」并留下目录，
        # 原实现此时 copytree 会抛 FileExistsError，使恢复失败并连锁破坏回滚
        shutil.copytree(backup_uploads_dir, self.uploads_dir, dirs_exist_ok=True)
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

    def _preserve_snapshot(self, snapshot_db_path):
        """把快照移入 backup_dir/pre_restore/（W18-D11）。

        原实现把快照留在 %TEMP%：进程被杀/清理 TEMP 即永久丢失 —— 那是恢复失败时
        用户唯一的"恢复前状态"。移入备份目录（有保留期治理）并返回新路径。
        """
        try:
            from app.utils.paths import get_backup_path

            pre_dir = get_backup_path("pre_restore")
            pre_dir.mkdir(parents=True, exist_ok=True)
            target = pre_dir / os.path.basename(snapshot_db_path)
            if os.path.abspath(snapshot_db_path) != os.path.abspath(str(target)):
                if os.path.exists(str(target)):
                    try:
                        os.unlink(str(target))
                    except OSError:
                        stem = os.path.splitext(os.path.basename(snapshot_db_path))[0]
                        target = pre_dir / (stem + "_%d.db" % int(time.time()))
                os.replace(snapshot_db_path, str(target))
            return str(target)
        except Exception:  # noqa: BLE001 - 保底：快照原地保留，不因移入失败而丢失
            logger.warning("快照移入 pre_restore 目录失败，原地保留: %s",
                           snapshot_db_path, exc_info=True)
            return snapshot_db_path

    def _rollback_to_snapshots(self, snapshot_db_path, snapshot_uploads_dir):
        """恢复失败时回滚到快照（W18-D11：原子替换 + 失败可自救）。

        原实现 unlink+copy 两步：Windows 上库文件被后台线程占用时 unlink 失败 →
        **半恢复状态**（备份内容已生效，回滚却失败）且快照困在 %TEMP%。
        修复：os.replace 原子换名（同卷原子，无 unlink 窗口）；仍失败时把快照
        移入 backup_dir/pre_restore/ 并把路径写进异常 —— 用户重启后能自助还原。
        """
        if snapshot_db_path and os.path.exists(snapshot_db_path):
            replaced = False
            if os.path.exists(self.database_path):
                try:
                    # 原子换名：Windows 上目标被独占打开时仍可能失败，但不会出现
                    # "旧文件已删、新文件没就位"的中间态
                    os.replace(snapshot_db_path, self.database_path)
                    replaced = True
                except OSError as replace_err:
                    # 兜底：copy2 覆盖（目标被独占时仍可能失败，与旧行为等价）
                    try:
                        shutil.copy2(snapshot_db_path, self.database_path)
                        replaced = True
                        try:
                            os.unlink(snapshot_db_path)
                        except OSError:
                            pass
                    except OSError as copy_err:
                        preserved = self._preserve_snapshot(snapshot_db_path)
                        logger.error(
                            "回滚: 数据库文件 %s 被占用（replace: %s / copy: %s），快照已保留在 %s",
                            self.database_path, replace_err, copy_err, preserved,
                        )
                        raise RuntimeError(
                            "回滚失败：数据库文件被占用。恢复前快照已保留在 %s，"
                            "请重启本程序（释放文件句柄）后按该路径手工恢复数据" % preserved
                        ) from copy_err
            else:
                shutil.copy2(snapshot_db_path, self.database_path)
                replaced = True
            if replaced:  # pragma: no branch - 到此 replaced 必为 True（replace/copy 成功才置真，双失败已 raise）
                try:
                    if os.path.exists(snapshot_db_path):
                        os.unlink(snapshot_db_path)
                except OSError:
                    logger.warning("回滚: 快照清理失败（残留于 %s）", snapshot_db_path)
        if snapshot_uploads_dir and os.path.exists(snapshot_uploads_dir):
            if os.path.exists(self.uploads_dir):
                shutil.rmtree(self.uploads_dir, ignore_errors=True)
            shutil.copytree(snapshot_uploads_dir, self.uploads_dir, dirs_exist_ok=True)
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

    # ── PII 密钥指纹校验（批次 2：备份可迁移性）──────────────────────

    @staticmethod
    def _read_backup_key_fingerprint(zip_path: str) -> Optional[str]:
        """读取备份包记录的本机 PII 密钥指纹；无法读到则返回 None。

        None 的语义是「旧备份/无指纹/元信息不可读」——调用方按兼容放行处理
        （不能因为老包没有线索就锁死恢复通道，那才是真正的数据不可用）。
        加密备份必须先解密：调用方传入的是已解密后的 ``restore_source``。
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zipf:
                raw = read_zip_member(zipf, "backup_info.json")
        except Exception:
            # 缺成员（KeyError）/坏 ZIP/体积超限（HTTPException）：交给后续
            # 恢复流程按既有语义报错，此处只表示"读不到指纹"
            logger.debug("备份包未提供可读的 backup_info.json: %s", zip_path, exc_info=True)
            return None
        info = _parse_backup_info(raw)
        if not info:
            return None
        fp = info.get(KEY_FINGERPRINT_FIELD)
        if isinstance(fp, str) and fp.strip():
            return fp.strip()
        return None

    @staticmethod
    def _audit_key_mismatch(
        filename: str,
        backup_fingerprint: str,
        current_fingerprint: str,
        forced: bool,
        operator: Optional[str] = None,
    ) -> None:
        """审计密钥指纹不一致（拒绝与强制都留痕）。

        只写指纹（16 位十六进制），不写任何密钥材料；审计失败不得影响恢复语义。
        """
        try:
            from app.utils.audit_logger import AuditLevel, AuditLogger

            AuditLogger.log(
                action="system_restore_key_mismatch",
                username=operator,
                resource_type="backup",
                resource_id=filename,
                details={
                    "filename": filename,
                    "backup_fingerprint": backup_fingerprint,
                    "current_fingerprint": current_fingerprint,
                    "forced": bool(forced),
                },
                level=AuditLevel.WARNING if forced else AuditLevel.CRITICAL,
            )
        except Exception:
            logger.error("密钥指纹不一致审计写入失败（不影响恢复判定）", exc_info=True)

    def _enforce_key_fingerprint(
        self,
        restore_source: str,
        backup_file_path: str,
        allow_key_mismatch: bool,
        operator: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """恢复前的密钥一致性闸门（**必须在覆盖生产库之前**调用）。

        Returns:
            指纹不一致且被显式放行时返回 ``{"forced": True, ...}``，用于在恢复
            结果里标记"这次恢复是有意跨密钥的"；其余情况返回 None。

        Raises:
            BackupKeyMismatchError: 指纹不一致且未显式放行。
        """
        backup_fp = self._read_backup_key_fingerprint(restore_source)
        if not backup_fp:
            # 旧备份/无指纹/元信息不可读 → 兼容放行（无法判断 ≠ 不一致）
            logger.info("备份包未记录 PII 密钥指纹（旧备份），跳过密钥一致性校验")
            return None

        current_fp = _current_key_fingerprint()
        if not current_fp:
            # 本机指纹算不出来（密钥未初始化）→ 无法判定，放行但留 warning
            logger.warning(
                "本机 PII 密钥指纹不可用，无法校验备份密钥一致性（备份指纹=%s）",
                backup_fp,
            )
            return None

        if backup_fp == current_fp:
            return None

        filename = os.path.basename(backup_file_path)
        self._audit_key_mismatch(
            filename=filename,
            backup_fingerprint=backup_fp,
            current_fingerprint=current_fp,
            forced=allow_key_mismatch,
            operator=operator,
        )
        if allow_key_mismatch:
            logger.warning(
                "备份密钥指纹与本机不一致（备份=%s，本机=%s），已按强制恢复继续: %s",
                backup_fp, current_fp, filename,
            )
            return {
                "forced": True,
                "backup_fingerprint": backup_fp,
                "current_fingerprint": current_fp,
            }
        logger.error(
            "拒绝恢复：备份密钥指纹与本机不一致（备份=%s，本机=%s）: %s",
            backup_fp, current_fp, filename,
        )
        raise BackupKeyMismatchError(
            KEY_MISMATCH_MESSAGE,
            backup_fingerprint=backup_fp,
            current_fingerprint=current_fp,
        )

    def restore_backup(
        self,
        backup_file_path: str,
        password: str | None = None,
        allow_key_mismatch: bool = False,
        operator: Optional[str] = None,
    ) -> Dict:
        """从备份恢复系统（R7：外层维护窗口 + 事务保护 + 加密检测）

        维护窗口语义见 app.core.maintenance：
        置位维护模式 → 等在途请求归零 → 执行恢复 → finally 解除。

        Args:
            backup_file_path: 备份文件路径
            password: 加密密码（加密备份必需）
            allow_key_mismatch: 备份的 PII 密钥指纹与本机不一致时是否强制继续
                （默认 False：拒绝并给出明确中文提示；见 BackupKeyMismatchError）
            operator: 操作人标识（仅用于审计留痕，可为 None）

        Returns:
            恢复结果（含 maintenance_window_ms，供前端/日志留痕）
        """
        with maintenance_window("restore_backup") as window:
            result = self._restore_backup_impl(
                backup_file_path,
                password,
                allow_key_mismatch=allow_key_mismatch,
                operator=operator,
            )
            result["maintenance_window_ms"] = window.elapsed_ms()
            return result

    def _restore_backup_impl(
        self,
        backup_file_path: str,
        password: str | None = None,
        allow_key_mismatch: bool = False,
        operator: Optional[str] = None,
    ) -> Dict:
        """
        恢复实现（调用方须已进入维护窗口）

        Args:
            backup_file_path: 备份文件路径
            password: 加密密码（加密备份必需）
            allow_key_mismatch: 密钥指纹不一致时是否强制继续
            operator: 操作人标识（审计用）

        Returns:
            恢复结果

        Raises:
            ValueError: 备份文件已加密但未提供密码，或密码错误
            BackupKeyMismatchError: 备份密钥指纹与本机不一致且未强制放行
        """
        if not os.path.exists(backup_file_path):
            raise FileNotFoundError(f"备份文件不存在: {backup_file_path}")

        restore_source, decrypted_temp_path = self._resolve_restore_source(backup_file_path, password)
        temp_dir = tempfile.mkdtemp(prefix="restore_")
        snapshot_db_path = None
        snapshot_uploads_dir = None

        try:
            # 密钥一致性闸门（批次 2）：**必须在建快照与覆盖生产库之前**。
            # 不一致且未强制 → 抛 BackupKeyMismatchError，现场库一个字节都不动。
            key_mismatch = self._enforce_key_fingerprint(
                restore_source, backup_file_path, allow_key_mismatch, operator
            )

            # 快照必须建在 try 内：否则它在磁盘写满/文件被占用时抛错，
            # 后面的 finally 不会执行 —— restore_XXXX 临时目录与（加密备份解密出的）
            # 明文临时包会永久残留在 %TEMP%，后者还是敏感数据落盘
            snapshot_db_path, snapshot_uploads_dir = self._create_snapshots()

            with zipfile.ZipFile(restore_source, "r") as zipf:
                self._safe_extractall(zipf, temp_dir)

            # W18-D7：版本前置校验（在覆盖生产库**之前**，失败即拒绝且不碰现场）
            self._validate_backup_schema_version(
                os.path.join(temp_dir, "data", "rural_revitalization.db")
            )

            database_restored = self._restore_database_from_backup(temp_dir)
            if not database_restored:
                # fail-loud：备份包缺库、或恢复后完整性校验未通过时，生产库可能已被
                # 替换为不可用文件。原实现丢弃该返回值照样返回 success=True，
                # 还会删掉唯一回滚快照，导致「恢复失败却报成功且再无退路」。
                raise BackupRestoreError("数据库恢复失败（备份包缺少数据库文件或完整性校验未通过）")

            uploads_restored = self._restore_uploads_from_backup(temp_dir)

            self._cleanup_snapshots(snapshot_db_path, snapshot_uploads_dir)

            result = {
                "success": True,
                "message": "系统恢复成功",
                "database_restored": database_restored,
                "uploads_restored": uploads_restored,
            }
            if key_mismatch:
                # 让调用方/前端能明确区分「强制的跨密钥恢复」与普通恢复
                result["key_mismatch"] = key_mismatch
                result["message"] = (
                    "系统恢复成功（已按强制方式跨密钥恢复，敏感字段可能不可读）"
                )
            return result

        except BackupKeyMismatchError:
            # 拒绝发生在任何写操作之前：无需回滚，保留原始异常类型与中文提示
            # （被下方通用分支包装成 BackupRestoreError 会丢掉 409 语义）
            raise

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
        # 两类键都要匹配：全量 backup_YYYYMMDD_HHMMSS 与增量 backup_incremental_*。
        # 历史只匹配 backup_20%，增量备份永远不出现在列表里（不可见 → 不会被轮转清理）。
        return (
            self.db.query(SystemConfig)
            .filter(
                or_(
                    SystemConfig.key.like("backup_20%"),
                    SystemConfig.key.like("backup_incremental_%"),
                ),
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
                        backup_type=("incremental" if file_name.startswith("backup_incremental_") else "full"),
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
                except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
                    # 删除失败必须保留记录：原实现吞掉异常仍删记录，
                    # 产生「列表不可见、UI 无法再删、清理永不重试」的幽灵备份
                    logger.warning(
                        "备份文件删除失败（已保留记录以便重试）: %s (%s)",
                        config.value, exc,
                    )
                    continue
            self.db.delete(config)
            deleted_count += 1

        if deleted_count > 0:
            safe_commit(self.db)

        return deleted_count

    # D1：保留期清理是批量删除，同样会与在线写入争抢 SQLite 写锁 → 退避重试
    @retry_on_deadlock(max_retries=3, delay=1.0)
    def cleanup_by_retention_days(self, days: int) -> int:
        """按保留天数清理旧备份：删除 created_at 早于 (now - days) 的备份记录与文件。

        Args:
            days: 保留天数（<=0 表示不清理）

        Returns:
            删除的备份数量
        """
        if days <= 0:
            return 0
        # 时间基准统一 UTC：库中 created_at 是 aware UTC（models.base.UtcDateTime），
        # 此前用本地 naive 的 datetime.now() 作 cutoff 与之比较 —— 在同一类缺陷里
        # 属静默偏一个时区差；改类型后该比较会响亮抛 TypeError，正好暴露出来。
        cutoff = utcnow() - timedelta(days=days)
        records = self._query_backup_records()
        deleted_count = 0
        for rec in records:
            rec_time = rec.created_at
            if isinstance(rec_time, str):
                try:
                    rec_time = datetime.fromisoformat(rec_time)
                except ValueError:
                    continue
            if rec_time is not None and as_utc(rec_time) < cutoff:
                if rec.value and os.path.exists(rec.value):
                    try:
                        os.unlink(rec.value)
                    except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
                        # 同 cleanup_old_backups：删除失败保留记录，等待下次清理重试
                        logger.warning(
                            "保留期清理删除备份失败（已保留记录）: %s (%s)",
                            rec.value, exc,
                        )
                        continue
                self.db.delete(rec)
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
            _fp = _current_key_fingerprint()
            if _fp:
                backup_info[KEY_FINGERPRINT_FIELD] = _fp
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
                existing.updated_at = utcnow()

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
            backup_file_name = f"backup_incremental_{timestamp}_{uuid.uuid4().hex[:6]}.zip"
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

            config, file_size = self._save_incremental_backup_record(
                backup_file_path, description, changed_files, timestamp,
            )

            # 清单必须在备份记录落库**之后**推进：先写清单而记录写失败，
            # 下次增量会认为这些文件已备份 → 静默漏备（深审 LIVE）。
            self._save_manifest(current_manifest)
            self.last_backup_manifest = current_manifest

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

                # 读取备份信息（兼容历史 str(dict) 写法，见 _parse_backup_info）
                try:
                    backup_info_data = read_zip_member(zipf, "backup_info.json")
                    backup_info = _parse_backup_info(backup_info_data)
                except Exception as exc:  # noqa: BLE001 - 兜底但必须留痕
                    logger.warning('verify_backup 兜底失败（已降级）: %s', exc, exc_info=True)
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

                if not db_verified:
                    # fail-loud：原实现只要 ZIP 结构完好就返回 status="ok"，
                    # 把「备份存在但库已损坏」这一最坏故障模式判为「验证通过」，
                    # 掩盖了备份不可还原的事实
                    return {
                        "status": "error",
                        "message": "备份文件验证失败：数据库完整性校验未通过",
                        "file_hash": file_hash,
                        "file_count": len(file_list),
                        "backup_info": backup_info,
                        "database_verified": False,
                    }

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
                "disk_space": self.get_disk_space_info(),
            }

        except Exception as e:
            logger.error(f"获取备份统计失败: {e}")
            return {"status": "error", "message": str(e)}

    def get_disk_space_info(self) -> Dict:
        """W12-T045: 返回备份目录 / 数据库目录剩余空间（MB）与阈值充足标记"""
        from app.core.database import check_disk_space

        def _one(path: str) -> Dict:
            try:
                d = check_disk_space(min_mb=BACKUP_MIN_FREE_MB, path=path)
                return {
                    "path": path,
                    "free_mb": d.get("free_mb", -1),
                    "total_mb": d.get("total_mb", -1),
                    "sufficient": d.get("sufficient", False),
                }
            except Exception as _e:  # noqa: BLE001
                logger.warning("磁盘空间探测失败 path=%s: %s", path, _e)
                return {"path": path, "free_mb": -1, "total_mb": -1, "sufficient": True}

        return {
            "backup_dir": _one(self.backup_dir),
            "db_dir": _one(os.path.dirname(self.database_path or self.backup_dir)),
            "threshold_mb": BACKUP_MIN_FREE_MB,
        }


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
