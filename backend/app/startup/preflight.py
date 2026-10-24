# coding: utf-8
"""启动预检（W18 P2-3）：把"运行时才莫名报错"的问题提前到启动时说清楚。

原有启动自检只有数据库完整性（quick_check）。现场还有四类问题会在运行中
以"某功能莫名报错"的形式出现，且日志里很难归因：

1. 磁盘剩余空间不足 —— 备份/导入开始失败，但首页无任何提示；
2. 数据库文件不可写 —— 只读挂载/权限被改，写操作全部失败；
3. 系统时钟落后于数据最新记录 —— 单机离线机器常被手动改时间，
   会让"最近 N 天"统计漏数据、调度任务错时；
4. PII 加密密钥不可用 —— 既有密文解不开（换机/换 ENCRYPTION_KEY），
   表现为列表里身份证号显示异常而不是启动报错。

本模块只**报警**、不阻断启动（单机现场：能跑比完美更重要），符合
"诊断包/日志能说清楚"的既有脱敏口径：只出指标值与类名，不出路径原文。
"""
import logging
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 阈值（单机离线现场经验值）
DISK_FREE_WARN_MB = 1024
CLOCK_DRIFT_WARN_DAYS = 1

# R36：/health 用的时钟检查缓存时长（秒）。
# /health 会被 Electron/监控高频轮询，若每次都查一次"最近审计时间"，等于给热路径
# 加一条 DB 查询；而时钟漂移是分钟级现象，缓存 2 分钟完全够用（长跑机器仍能发现）。
CLOCK_HEALTH_CACHE_TTL_SECONDS = 120

_clock_cache: Dict = {}
_clock_cache_at: Optional[float] = None
_clock_lock = threading.Lock()


def _check_disk_free() -> Dict:
    """数据目录所在卷的剩余空间。"""
    try:
        from app.utils.paths import get_app_data_dir

        usage = shutil.disk_usage(str(get_app_data_dir()))
        free_mb = round(usage.free / (1024 * 1024), 1)
        return {
            "status": "ok" if free_mb >= DISK_FREE_WARN_MB else "warning",
            "free_mb": free_mb,
            "threshold_mb": DISK_FREE_WARN_MB,
        }
    except Exception as exc:  # noqa: BLE001 - 预检不允许因单项失败而崩溃
        return {"status": "unknown", "error_type": type(exc).__name__}


def _check_db_writable() -> Dict:
    """数据库文件可写性（只读文件系统/权限被改时提前暴露）。"""
    try:
        from app.utils.paths import get_database_path

        path = get_database_path()
        if not path.exists():
            return {"status": "unknown", "exists": False}
        return {
            "status": "ok" if os.access(path, os.W_OK) else "warning",
            "exists": True,
            "writable": os.access(path, os.W_OK),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "unknown", "error_type": type(exc).__name__}


def _latest_audit_time() -> Optional[datetime]:
    """最近一条审计日志时间（用于判断系统时钟是否落后）。"""
    from app.core.database import SessionLocal
    from app.models.audit import AuditLog

    session = SessionLocal()
    try:
        return session.query(AuditLog.created_at).order_by(AuditLog.created_at.desc()).limit(1).scalar()
    finally:
        session.close()


def _check_clock_drift() -> Dict:
    """系统时钟与数据最新记录的时间差（时钟落后会让统计/调度错乱）。"""
    try:
        latest = _latest_audit_time()
        if latest is None:
            return {"status": "ok", "reason": "no_data"}
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        behind_days = (latest - now).total_seconds() / 86400
        if behind_days > CLOCK_DRIFT_WARN_DAYS:
            return {
                "status": "warning",
                "reason": "system_clock_behind_data",
                "behind_days": round(behind_days, 1),
            }
        return {"status": "ok", "behind_days": round(max(behind_days, 0.0), 1)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "unknown", "error_type": type(exc).__name__}


def _clock_health_payload(result: Dict) -> Dict:
    """把预检结果收敛为 ``/health`` 的 ``clock`` 载荷 ``{status, behind_days}``。

    只出二元组：``/health`` 无需认证，``reason``/``error_type`` 等内部细节留在
    启动日志与诊断包里（口径同 migration 只出异常类名）。
    """
    return {
        "status": result.get("status", "unknown"),
        "behind_days": result.get("behind_days"),
    }


def clock_health(max_age_seconds: Optional[int] = None) -> Dict:
    """时钟漂移的可查询状态（供 ``/health`` 使用；R36）。

    带 TTL 缓存（默认 ``CLOCK_HEALTH_CACHE_TTL_SECONDS``）：TTL 内重复调用不查库，
    过期后重新检查 —— 长跑机器（离线现场常年不重启）上的时钟漂移因此仍能被发现。

    返回 ``{status, behind_days}``：``ok`` / ``warning``（落后于数据记录）/
    ``unknown``（检查本身失败，例如库不可读）。
    """
    global _clock_cache_at
    ttl = CLOCK_HEALTH_CACHE_TTL_SECONDS if max_age_seconds is None else max_age_seconds
    with _clock_lock:
        now = time.monotonic()
        if _clock_cache and _clock_cache_at is not None and (now - _clock_cache_at) < ttl:
            return _clock_health_payload(_clock_cache)
        # 持锁执行检查：并发 /health 轮询时只跑一次，避免打爆数据库
        result = _check_clock_drift()
        _clock_cache.clear()
        _clock_cache.update(result)
        _clock_cache_at = now
        return _clock_health_payload(result)


def _sample_existing_ciphertext() -> Optional[str]:
    """从库中取一条**既有** PII 密文（只取一条，不扫全表）。

    W18-B：原先的加密探针只做「用当前密钥加密一个探针值再解回来」的自证，
    密钥被换掉时它**照样通过** —— 因为新密钥对新数据本来就是自洽的。
    真正要回答的是「库里已有的密文还解得开吗」，所以必须取真实存量密文。

    走裸 SQL 而不是 ORM：``EncryptedText`` 的 ``LIKE`` 会把模式串也加密掉，
    匹配不到任何行。
    """
    try:
        from sqlalchemy import text as _sql_text

        from app.core.database import SessionLocal

        session = SessionLocal()
        try:
            row = session.execute(
                _sql_text("SELECT phone FROM users WHERE phone LIKE 'enc.v1:%' LIMIT 1")
            ).fetchone()
            return row[0] if row else None
        finally:
            session.close()
    except Exception:  # noqa: BLE001 - 预检不允许因取样失败而崩溃（新库/表未建）
        return None


def _check_encryption_key() -> Dict:
    """PII 加密密钥可用性：当前密钥自洽 **且** 既有密文可解。"""
    try:
        from app.core.pii_crypto import decrypt_pii, encrypt_pii

        probe = "preflight-probe"
        token = encrypt_pii(probe)
        if token is None:
            return {"status": "unknown"}
        if decrypt_pii(token) != probe:
            return {"status": "warning", "reason": "self_check_failed"}

        sample = _sample_existing_ciphertext()
        if not sample:
            return {"status": "ok", "existing_ciphertext": False}
        # 解密失败时 decrypt_pii 会把密文原样返回（不抛异常），据此判定密钥不匹配
        if str(decrypt_pii(sample)).startswith("enc.v1:"):
            return {
                "status": "warning",
                "reason": "existing_ciphertext_undecryptable",
                "existing_ciphertext": True,
            }
        return {"status": "ok", "existing_ciphertext": True}
    except Exception as exc:  # noqa: BLE001
        return {"status": "warning", "error_type": type(exc).__name__}


def run_preflight_checks() -> Dict:
    """执行全部预检并记录告警（返回结构化结果，供诊断/测试使用）。"""
    results = {
        "disk": _check_disk_free(),
        "database_writable": _check_db_writable(),
        "clock": _check_clock_drift(),
        "encryption_key": _check_encryption_key(),
    }
    for name, result in results.items():
        if result.get("status") == "warning":
            logger.warning("启动预检告警 [%s]: %s", name, result)
    return results
