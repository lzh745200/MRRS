"""备份恢复演练服务（架构评估 C1 · 2026-09-12）。

背景（架构评估 C1【P0】）：备份文件的"创建时校验"（``_verify_backup_recovery``：
zip CRC + SQLite integrity_check）只证明**文件完好**，从未验证过**真能还原**。
数据库文件损坏时才发现备份不可用，是单机系统最高等级的数据风险。

本模块提供**月度自动恢复演练**：

1. 选取最新备份包（``backup_*.zip``）；
2. 把包内 ``data/rural_revitalization.db`` 还原到临时目录（真实 unzip 落盘）；
3. 对还原库执行 ``PRAGMA integrity_check`` + 核心表存在性/行数抽查；
4. 结果写入 :data:`RESTORE_DRILL_STATUS`（供 ``/health`` 暴露）并持久化到
   SystemConfig（``last_restore_drill_time`` / ``last_restore_drill_result``），
   重启后 /health 仍有上次演练结论。

设计约束：
- **只读演练**：还原到系统临时目录，绝不触碰生产数据库文件；
- 失败不抛出到调度器（演练失败本身是重要信号，记录状态 + 通知管理员，
  但不能因演练失败打断其他定时任务）；
- 加密备份无法离线验核（口令在 runtime_secrets，可解密但为最小化攻击面
  演练不解密）——显式记 ``skipped_encrypted`` 状态，不留"未知"盲区。
"""

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# /health 暴露的演练状态（无认证端点：只出文件名与状态，不出绝对路径/异常原文）
RESTORE_DRILL_STATUS: Dict[str, Any] = {
    "status": "never",      # never | ok | fail | skipped_encrypted | no_backup
    "checked_at": None,     # ISO 时间
    "backup_file": None,    # 备份文件名（不含路径）
    "error_type": None,     # 失败时的异常类名（原文进日志）
    "tables_checked": 0,    # 抽查的核心表数量
}

# 核心表抽查清单：存在即计数（行数只进日志/持久化明细，不进 /health）
_DRILL_SAMPLE_TABLES = ("users", "supported_villages", "projects", "funds", "schools")

# 备份包内的数据库成员名（与 backup_service._write_backup_zip 一致）
_DB_MEMBER = "data/rural_revitalization.db"

# SystemConfig 键
_CFG_LAST_TIME = "last_restore_drill_time"
_CFG_LAST_RESULT = "last_restore_drill_result"


def _latest_backup_file(backup_dir: str) -> Optional[str]:
    """返回目录中最新的 backup_*.zip 文件路径（无则 None）。"""
    if not backup_dir or not os.path.isdir(backup_dir):
        return None
    candidates = [
        os.path.join(backup_dir, f)
        for f in os.listdir(backup_dir)
        if f.startswith("backup_") and f.endswith(".zip")
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def _update_status(status: str, backup_file: Optional[str], error_type: Optional[str],
                   tables_checked: int) -> None:
    RESTORE_DRILL_STATUS["status"] = status
    RESTORE_DRILL_STATUS["checked_at"] = datetime.now().isoformat()
    RESTORE_DRILL_STATUS["backup_file"] = os.path.basename(backup_file) if backup_file else None
    RESTORE_DRILL_STATUS["error_type"] = error_type
    RESTORE_DRILL_STATUS["tables_checked"] = tables_checked


def _persist_result() -> None:
    """演练结果持久化到 SystemConfig（失败仅告警，不影响演练结论）。"""
    try:
        from app.services.system_config_service import set_config

        set_config(_CFG_LAST_TIME, RESTORE_DRILL_STATUS["checked_at"] or "", "最近恢复演练时间")
        set_config(
            _CFG_LAST_RESULT,
            json.dumps(RESTORE_DRILL_STATUS, ensure_ascii=False),
            "最近恢复演练结果（/health 同口径）",
        )
    except Exception as e:  # pragma: no cover — 持久化失败不掩盖演练结论
        logger.warning("恢复演练结果持久化失败: %s", e)


def _load_persisted_status() -> None:
    """启动时从 SystemConfig 回填上次演练结论（/health 重启后仍有数据）。"""
    try:
        from app.core.database import SessionLocal
        from app.services.system_config_service import get_config

        db = SessionLocal()
        try:
            raw = get_config(_CFG_LAST_RESULT, "")
        finally:
            db.close()
        if not raw:
            return
        data = json.loads(raw)
        for key in ("status", "checked_at", "backup_file", "error_type", "tables_checked"):
            if key in data:
                RESTORE_DRILL_STATUS[key] = data[key]
    except Exception as e:
        logger.warning("恢复演练历史状态回填失败: %s", e)


def _verify_restored_db(db_path: str) -> Dict[str, Any]:
    """对还原库执行 integrity_check + 核心表抽查。校验失败抛异常。"""
    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(f"integrity_check: {result}")
        tables_checked = 0
        for table in _DRILL_SAMPLE_TABLES:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                continue
            # 表名来自本模块硬编码白名单 _DRILL_SAMPLE_TABLES，无外部输入。
            # 抑制标记必须是 bandit 认的 `# nosec`：CI 与 pre-push 钩子跑的是
            # `python -m bandit -r app/ -ll`，本仓未装 flake8-bandit 插件，
            # 原先的 `# noqa: S608` 是**惰性标记**（不起任何作用，门禁照样红）。
            count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]  # nosec B608
            tables_checked += 1
            logger.info("恢复演练抽查: %s → %d 行", table, count)
        return {"tables_checked": tables_checked}
    finally:
        conn.close()


def run_restore_drill(db=None, backup_dir: Optional[str] = None) -> Dict[str, Any]:
    """执行一次恢复演练，返回状态字典（同时更新 /health 暴露的模块状态）。

    Args:
        db: 可选 Session（未用时忽略，保留参数以便与调度上下文一致）。
        backup_dir: 备份目录；缺省用 BackupService 的默认目录（含配置的目标目录）。

    Returns:
        :data:`RESTORE_DRILL_STATUS` 的快照（含本次演练结论）。
    """
    if backup_dir is None:
        # 与 auto_backup_job 同口径：优先使用配置的外部备份目标目录
        try:
            from app.services.system_config_service import get_config

            configured = (get_config("backup_target_dir", "") or "").strip()
        except Exception:
            configured = ""
        if configured and os.path.isdir(configured):
            backup_dir = configured
        else:
            from app.utils.paths import get_backup_path

            backup_dir = str(get_backup_path())

    backup_file = _latest_backup_file(backup_dir)
    if not backup_file:
        logger.warning("恢复演练跳过：备份目录中无 backup_*.zip（%s）", backup_dir)
        _update_status("no_backup", None, None, 0)
        _persist_result()
        return dict(RESTORE_DRILL_STATUS)

    drill_dir = tempfile.mkdtemp(prefix="restore_drill_")
    try:
        with zipfile.ZipFile(backup_file, "r") as zf:
            names = zf.namelist()
            if _DB_MEMBER not in names:
                raise FileNotFoundError(f"备份包缺少 {_DB_MEMBER}")
            try:
                zf.extract(_DB_MEMBER, drill_dir)
            except RuntimeError as exc:
                # Python zipfile 对加密成员抛 RuntimeError("File ... is encrypted...")
                if "encrypted" in str(exc).lower():
                    logger.info("恢复演练跳过：备份包已加密（%s）", os.path.basename(backup_file))
                    _update_status("skipped_encrypted", backup_file, None, 0)
                    _persist_result()
                    return dict(RESTORE_DRILL_STATUS)
                raise

            restored_db = os.path.join(drill_dir, _DB_MEMBER.replace("/", os.sep))
            detail = _verify_restored_db(restored_db)
            _update_status("ok", backup_file, None, detail["tables_checked"])
            logger.info(
                "恢复演练通过: %s（抽查 %d 张核心表）",
                os.path.basename(backup_file), detail["tables_checked"],
            )
    except Exception as e:
        _update_status("fail", backup_file, type(e).__name__, 0)
        logger.error("恢复演练失败（备份可能不可用，请立即排查）: %s", e, exc_info=True)
    finally:
        shutil.rmtree(drill_dir, ignore_errors=True)

    _persist_result()
    return dict(RESTORE_DRILL_STATUS)


def is_drill_due(interval_days: int = 30) -> bool:
    """距上次演练是否已到期（每日调度任务用，到期才真正执行演练）。"""
    if RESTORE_DRILL_STATUS["status"] == "never" and not RESTORE_DRILL_STATUS["checked_at"]:
        # 首次：若从未持久化过结论则视为到期
        try:
            from app.core.database import SessionLocal
            from app.services.system_config_service import get_config

            db = SessionLocal()
            try:
                return not get_config(_CFG_LAST_TIME, "")
            finally:
                db.close()
        except Exception:
            return True
    try:
        last = datetime.fromisoformat(RESTORE_DRILL_STATUS["checked_at"])
        return (datetime.now() - last).days >= interval_days
    except (ValueError, TypeError):
        return True
